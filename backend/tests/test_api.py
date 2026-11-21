"""
API Integration Tests for TalentRank.
Tests:
- /api/health and /api/scoring-config endpoints
- Job creation, upload, and requirements update
- Resume upload validation:
  - Wrong type rejected (.txt or .png to resume endpoint)
  - Oversize rejected (> 4 MB)
  - Invalid magic bytes rejected (e.g. fake.pdf with bad header)
  - Scanned PDF returns no_text_layer
  - One bad file does not stop batch/subsequent uploads
- End-to-end matching, ranking, anonymization, and CSV export
- Cascade deletion of jobs
"""

import io
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db import init_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    init_db()


def test_health_and_config_endpoints():
    res_health = client.get("/api/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "ok"
    assert res_health.json()["model_loaded"] is True

    res_config = client.get("/api/scoring-config")
    assert res_config.status_code == 200
    cfg = res_config.json()
    assert "weights" in cfg
    assert "thresholds" in cfg
    assert "skills" in cfg["weights"]
    assert abs(sum(cfg["weights"].values()) - 1.0) < 1e-4


def test_job_creation_and_requirements_update():
    # 1. Create job
    jd_payload = {
        "title": "Backend Java Engineer",
        "text": """Job Title: Backend Java Engineer
Requirements:
- Strong proficiency in Java and Spring Boot.
- Experience with PostgreSQL and Docker.
Preferred:
- Kubernetes and Kafka.
Experience: 4-6 years of experience required.
Education: Bachelor's degree in Computer Science."""
    }
    res_create = client.post("/api/jobs", json=jd_payload)
    assert res_create.status_code == 201
    job_data = res_create.json()
    job_id = job_data["id"]
    assert job_data["title"] == "Backend Java Engineer"
    assert job_data["required_years"] == 4.0
    assert job_data["degree_level"] == 2

    # 2. Update requirements (recruiter chip edit)
    update_payload = {
        "title": "Lead Backend Java Architect",
        "required_years": 5.0,
        "skills": [
            {"name": "Java", "importance": "must_have"},
            {"name": "Spring Boot", "importance": "must_have"},
            {"name": "Kubernetes", "importance": "must_have"}  # Promoted from nice-to-have
        ]
    }
    res_update = client.put(f"/api/jobs/{job_id}/requirements", json=update_payload)
    assert res_update.status_code == 200
    updated_data = res_update.json()
    assert updated_data["title"] == "Lead Backend Java Architect"
    assert updated_data["required_years"] == 5.0
    assert "Kubernetes" in updated_data["requirements"]["must_have_skills"]


def test_resume_upload_validations():
    # Setup a job
    res_job = client.post("/api/jobs", json={
        "text": "Software Engineer needed. Must know Java, Spring Boot and SQL. 3 years experience."
    })
    job_id = res_job.json()["id"]

    # 1. Wrong type rejected
    wrong_type_file = {"file": ("malicious.exe", b"MZexecutabledata", "application/octet-stream")}
    res_wrong = client.post(f"/api/jobs/{job_id}/resumes", files=wrong_type_file)
    assert res_wrong.status_code == 400
    assert "Unsupported file extension" in res_wrong.json()["detail"]

    # 2. Oversize rejected (> 4 MB)
    oversized_data = b"%PDF-" + b"0" * (4 * 1024 * 1024 + 100)
    oversized_file = {"file": ("huge.pdf", oversized_data, "application/pdf")}
    res_oversize = client.post(f"/api/jobs/{job_id}/resumes", files=oversized_file)
    assert res_oversize.status_code == 413
    assert "exceeds maximum allowed size" in res_oversize.json()["detail"]

    # 3. Invalid magic bytes rejected (fake PDF)
    fake_pdf = {"file": ("fake.pdf", b"This is plain text, not a real PDF binary.", "application/pdf")}
    res_fake = client.post(f"/api/jobs/{job_id}/resumes", files=fake_pdf)
    assert res_fake.status_code == 400
    assert "Missing %PDF- magic signature" in res_fake.json()["detail"]

    # 4. Scanned PDF returns no_text_layer
    # A valid PDF structure with an empty page (fewer than 200 chars)
    import pymupdf
    empty_doc = pymupdf.open()
    empty_doc.new_page()
    empty_pdf_bytes = empty_doc.tobytes()
    empty_doc.close()

    scanned_file = {"file": ("scanned_resume.pdf", empty_pdf_bytes, "application/pdf")}
    res_scanned = client.post(f"/api/jobs/{job_id}/resumes", files=scanned_file)
    assert res_scanned.status_code == 201
    cand_scanned = res_scanned.json()
    assert cand_scanned["parse_status"] == "no_text_layer"
    assert len(cand_scanned["parse_warnings"]) > 0

    # 5. One bad file does NOT break subsequent uploads
    valid_resumes_dir = Path(__file__).resolve().parent.parent.parent / "eval" / "resumes"
    valid_sample = valid_resumes_dir / "java_01_strong.pdf"
    assert valid_sample.exists()

    with open(valid_sample, "rb") as f:
        valid_bytes = f.read()

    res_good = client.post(
        f"/api/jobs/{job_id}/resumes",
        files={"file": ("java_01_strong.pdf", valid_bytes, "application/pdf")}
    )
    assert res_good.status_code == 201
    assert res_good.json()["parse_status"] == "ok"


def test_full_flow_matching_and_ranking_10_resumes():
    """Full workflow test uploading 10 synthetic Java resumes, matching, ranking, and exporting."""
    base_dir = Path(__file__).resolve().parent.parent.parent
    jd_path = base_dir / "eval" / "jds" / "java_backend.txt"
    resumes_dir = base_dir / "eval" / "resumes"

    with open(jd_path, "r", encoding="utf-8") as f:
        jd_text = f.read()

    # 1. Create job
    res_job = client.post("/api/jobs", json={"text": jd_text})
    assert res_job.status_code == 201
    job_id = res_job.json()["id"]

    # 2. Upload 10 Java synthetic resumes (single-column PDF, two-column PDF, table DOCX, plain DOCX)
    java_resumes = [
        "java_01_strong.pdf",
        "java_02_strong.pdf",
        "java_03_strong.docx",
        "java_04_medium.docx",
        "java_05_medium.pdf",
        "java_06_medium.pdf",
        "java_07_weak.docx",
        "java_08_weak.docx",
        "java_09_irrelevant.pdf",
        "java_10_keyword_stuffed.pdf"
    ]

    uploaded_ids = []
    for fname in java_resumes:
        fpath = resumes_dir / fname
        assert fpath.exists(), f"Resume {fname} must exist"
        with open(fpath, "rb") as f:
            fbytes = f.read()

        mime = "application/pdf" if fname.endswith(".pdf") else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        res_upload = client.post(
            f"/api/jobs/{job_id}/resumes",
            files={"file": (fname, fbytes, mime)}
        )
        assert res_upload.status_code == 201, f"Failed upload for {fname}: {res_upload.text}"
        uploaded_ids.append(res_upload.json()["id"])

    assert len(uploaded_ids) == 10

    # 3. Run Matching (re-runnable)
    res_match = client.post(f"/api/jobs/{job_id}/match")
    assert res_match.status_code == 200
    assert res_match.json()["scored_count"] == 10

    # 4. Get Rankings without anonymization
    res_ranking = client.get(f"/api/jobs/{job_id}/ranking")
    assert res_ranking.status_code == 200
    ranking_data = res_ranking.json()
    summary = ranking_data["summary"]
    candidates = ranking_data["candidates"]

    assert summary["scored_candidates"] == 10
    assert summary["top_score"] >= 75
    assert len(candidates) == 10

    # Verification: Strong resumes rank above keyword-stuffed and irrelevant
    strong_ranks = [c["rank"] for c in candidates if "strong" in c["filename"]]
    kw_rank = [c["rank"] for c in candidates if "keyword_stuffed" in c["filename"]][0]
    irrelevant_rank = [c["rank"] for c in candidates if "irrelevant" in c["filename"]][0]

    for sr in strong_ranks:
        assert sr < kw_rank, f"Strong resume (rank {sr}) should outrank keyword-stuffed (rank {kw_rank})"
        assert sr < irrelevant_rank, f"Strong resume (rank {sr}) should outrank irrelevant (rank {irrelevant_rank})"

    # 5. Get Rankings with anonymization
    res_anon = client.get(f"/api/jobs/{job_id}/ranking?anonymize=true")
    assert res_anon.status_code == 200
    anon_candidates = res_anon.json()["candidates"]
    assert anon_candidates[0]["name"] == "Candidate 1"
    assert "anonymized" in anon_candidates[0]["email"]

    # 6. Candidate Detail Endpoint
    top_cand_id = candidates[0]["id"]
    res_detail = client.get(f"/api/candidates/{top_cand_id}")
    assert res_detail.status_code == 200
    detail = res_detail.json()
    assert "score" in detail and detail["score"] is not None
    assert "explanation" in detail and detail["explanation"] is not None
    assert len(detail["explanation"]["reasons"]) > 0

    # 7. CSV Export
    res_csv = client.get(f"/api/jobs/{job_id}/export.csv")
    assert res_csv.status_code == 200
    assert "text/csv" in res_csv.headers["content-type"]
    assert "Candidate Name" in res_csv.text

    # 8. Cascade delete job
    res_del = client.delete(f"/api/jobs/{job_id}")
    assert res_del.status_code == 204

    # Verify job is deleted
    res_check = client.get(f"/api/jobs/{job_id}")
    assert res_check.status_code == 404
