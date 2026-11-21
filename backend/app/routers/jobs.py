"""
Jobs API Router.
Endpoints:
- POST /api/jobs: Create job from raw text
- POST /api/jobs/upload: Create job from uploaded file (.txt, .pdf, .docx)
- PUT /api/jobs/{id}/requirements: Update recruiter-edited requirements
- POST /api/jobs/{id}/resumes: Upload a single resume (<= 4MB, magic bytes check)
- POST /api/jobs/{id}/match: Run / re-run matching for all candidates
- GET /api/jobs/{id}/ranking: Get ranked candidate list (with min_score & anonymize)
- GET /api/jobs/{id}/export.csv: Export candidate ranking as CSV
- DELETE /api/jobs/{id}: Delete job and associated candidates/scores
"""

import io
import csv
import zipfile
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import numpy as np

from app.db import get_db
from app.models import Job, Candidate, Score, Explanation
from app.schemas import (
    JobCreate,
    JobResponse,
    RequirementsUpdate,
    RankingResponse,
    RankingCandidateItem,
    RankingSummary,
    CandidateSummary,
)
from app.services.jd_extractor import extract_jd
from app.services.parsing import parse_resume, clean_text, extract_pdf_text, extract_docx_text
from app.services.skills import get_skill_matcher
from app.services.embedder import get_embedder
from app.services.scoring import score_candidate, load_scoring_config
from app.services.logger import record_log

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

MAX_FILE_SIZE = 4 * 1024 * 1024  # 4 MB limit (Vercel payload constraint is 4.5 MB)


def validate_file_magic_bytes(filename: str, content: bytes) -> str:
    """
    Validates file extension and binary magic bytes.
    Returns detected extension ('pdf' or 'docx') or raises HTTPException.
    """
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum allowed size of 4 MB ({len(content) / (1024*1024):.2f} MB provided)."
        )

    lower_name = filename.lower()
    
    # PDF verification: starts with %PDF-
    if lower_name.endswith(".pdf"):
        if not content.startswith(b"%PDF-"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid PDF file: Missing %PDF- magic signature."
            )
        return "pdf"

    # DOCX verification: starts with PK and is a valid zip archive
    elif lower_name.endswith(".docx"):
        if not (content.startswith(b"PK\x03\x04") or content.startswith(b"PK\x05\x06") or content.startswith(b"PK\x07\x08")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid DOCX file: Missing PK ZIP magic signature."
            )
        if not zipfile.is_zipfile(io.BytesIO(content)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Corrupted DOCX archive: File is not a valid OpenXML ZIP package."
            )
        return "docx"

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file extension. Only .pdf and .docx resume files are allowed."
        )


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job(payload: JobCreate, db: Session = Depends(get_db)):
    """Create a new job from raw text."""
    text_content = payload.text or getattr(payload, "raw_text", "") or ""
    extracted = extract_jd(text_content)
    title = payload.title or extracted.get("title", "Job Position")
    
    job = Job(
        title=title,
        raw_text=text_content,
        requirements=extracted,
        required_years=extracted.get("required_years"),
        degree_level=extracted.get("degree_level", 0),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    record_log("JD_EXTRACTOR", "INFO", f"Job created: '{job.title}' ({len(extracted.get('skills', []))} requirements extracted, min {job.required_years or 0}y exp)")
    return job


@router.post("/upload", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def upload_job_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Create a job description by uploading a .txt, .pdf, or .docx file."""
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="JD file exceeds 4 MB limit.")

    fname = file.filename or "job_description.txt"
    lower_name = fname.lower()

    if lower_name.endswith(".pdf"):
        text, _, _ = extract_pdf_text(content)
    elif lower_name.endswith(".docx"):
        text, _, _ = extract_docx_text(content)
    else:
        text = clean_text(content.decode("utf-8", errors="ignore"))

    if len(text.strip()) < 20:
        raise HTTPException(status_code=400, detail="Uploaded file contains insufficient text for a job description.")

    extracted = extract_jd(text)
    title = extracted.get("title", "Job Position")
    job = Job(
        title=title,
        raw_text=text,
        requirements=extracted,
        required_years=extracted.get("required_years"),
        degree_level=extracted.get("degree_level", 0),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    record_log("JD_EXTRACTOR", "INFO", f"Job created: '{job.title}' ({len(extracted.get('skills', []))} requirements extracted, min {job.required_years or 0}y exp)")
    return job


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job


@router.put("/{job_id}/requirements", response_model=JobResponse)
def update_requirements(job_id: str, payload: RequirementsUpdate, db: Session = Depends(get_db)):
    """Recruiter updates the extracted requirements (skills chips, years, degree level)."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    reqs = dict(job.requirements or {})
    if payload.title:
        job.title = payload.title
        reqs["title"] = payload.title
    if payload.skills is not None:
        normalized_skills = []
        for s in payload.skills:
            skill_name = s.get("name") or s.get("skill") or ""
            if skill_name:
                normalized_skills.append({
                    "name": skill_name,
                    "skill": skill_name,
                    "importance": s.get("importance", "must_have"),
                    "any_of": s.get("any_of") or [skill_name],
                    "category": s.get("category", "software"),
                })
        reqs["skills"] = normalized_skills
        reqs["must_have_skills"] = [s["name"] for s in normalized_skills if s.get("importance") == "must_have"]
        reqs["nice_to_have_skills"] = [s["name"] for s in normalized_skills if s.get("importance") == "nice_to_have"]
    if payload.required_years is not None:
        job.required_years = payload.required_years
        reqs["required_years"] = payload.required_years
    if payload.degree_level is not None:
        job.degree_level = payload.degree_level
        reqs["degree_level"] = payload.degree_level

    job.requirements = reqs
    db.commit()
    db.refresh(job)
    return job


@router.post("/{job_id}/resumes", response_model=CandidateSummary, status_code=status.HTTP_201_CREATED)
async def upload_resume(job_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Upload ONE resume per request (<= 4 MB, PDF or DOCX with magic byte validation).
    Parses resume, extracts skills, and saves candidate. A bad file returns a clear error
    and never breaks other files.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    content = await file.read()
    filename = file.filename or "resume.pdf"
    
    # 1. Validate magic bytes and size
    validate_file_magic_bytes(filename, content)

    # 2. Parse resume
    parsed = parse_resume(content, filename)

    # 3. Match candidate skills
    matcher = get_skill_matcher()
    skills = matcher.match_resume_skills(parsed.get("sections", {}), parsed.get("raw_text", ""))

    # 4. Check for existing candidate in this job (Upsert to prevent duplicates)
    existing_cand = None
    if parsed.get("email"):
        existing_cand = db.query(Candidate).filter(
            Candidate.job_id == job.id,
            Candidate.email == parsed["email"]
        ).first()

    if not existing_cand:
        existing_cand = db.query(Candidate).filter(
            Candidate.job_id == job.id,
            Candidate.filename == filename
        ).first()

    if existing_cand:
        existing_cand.filename = filename
        existing_cand.parse_status = parsed["parse_status"]
        existing_cand.parse_warnings = parsed["parse_warnings"]
        existing_cand.name = parsed["name"]
        existing_cand.email = parsed["email"]
        existing_cand.phone = parsed["phone"]
        existing_cand.total_years = parsed["total_years"]
        existing_cand.skills = skills
        existing_cand.entries = parsed.get("entries", [])
        existing_cand.education = {"text": parsed.get("sections", {}).get("education", "")}
        existing_cand.sections = parsed.get("sections", {})
        existing_cand.raw_text = parsed.get("raw_text", "")
        db.commit()
        db.refresh(existing_cand)
        record_log("PARSER", "INFO", f"Updated existing candidate '{filename}' ({parsed['name']})")
        return existing_cand

    candidate = Candidate(
        job_id=job.id,
        filename=filename,
        parse_status=parsed["parse_status"],
        parse_warnings=parsed["parse_warnings"],
        name=parsed["name"],
        email=parsed["email"],
        phone=parsed["phone"],
        total_years=parsed["total_years"],
        skills=skills,
        entries=parsed.get("entries", []),
        education={"text": parsed.get("sections", {}).get("education", "")},
        sections=parsed.get("sections", {}),
        raw_text=parsed.get("raw_text", ""),
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    record_log("PARSER", "INFO", f"Ingested resume '{filename}': {len(skills)} skills detected, {parsed['total_years']}y verifiable exp")
    return candidate


@router.post("/{job_id}/match")
def match_candidates(job_id: str, db: Session = Depends(get_db)):
    """
    Re-runnable endpoint that computes scores and explanations for all candidates under this job.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    candidates = db.query(Candidate).filter(Candidate.job_id == job_id).all()
    if not candidates:
        return {"job_id": job_id, "scored_count": 0, "message": "No candidates uploaded for this job."}

    embedder = get_embedder()
    config = load_scoring_config()
    scored_count = 0
    record_log("SCORING", "INFO", f"Triggered matching batch for {len(candidates)} candidates on job '{job.title}'")

    for cand in candidates:
        cand_dict = {
            "skills": cand.skills or [],
            "entries": cand.entries or [],
            "total_years": cand.total_years,
            "sections": cand.sections or {},
            "raw_text": cand.raw_text or "",
        }
        res = score_candidate(cand_dict, job.requirements, embedder, config)
        record_log("SCORING", "INFO", f"Candidate '{cand.filename}' scored: {res['total']}/100 (Capped: {res['capped']})")

        # Upsert Score
        score_obj = db.query(Score).filter(Score.candidate_id == cand.id).first()
        if not score_obj:
            score_obj = Score(
                candidate_id=cand.id,
                job_id=job.id,
                total=res["total"],
                skills_score=res["components"][0]["raw"],
                semantic_score=res["components"][1]["raw"],
                experience_score=res["components"][2]["raw"],
                education_score=res["components"][3]["raw"],
                must_have_coverage=res["must_have_coverage"],
                capped=res["capped"],
            )
            db.add(score_obj)
        else:
            score_obj.total = res["total"]
            score_obj.skills_score = res["components"][0]["raw"]
            score_obj.semantic_score = res["components"][1]["raw"]
            score_obj.experience_score = res["components"][2]["raw"]
            score_obj.education_score = res["components"][3]["raw"]
            score_obj.must_have_coverage = res["must_have_coverage"]
            score_obj.capped = res["capped"]

        # Upsert Explanation
        exp_obj = db.query(Explanation).filter(Explanation.candidate_id == cand.id).first()
        if not exp_obj:
            exp_obj = Explanation(
                candidate_id=cand.id,
                payload=res
            )
            db.add(exp_obj)
        else:
            exp_obj.payload = res

        scored_count += 1

    db.commit()
    record_log("SCORING", "INFO", f"Batch matching complete: {scored_count} candidates scored.")
    return {"job_id": job_id, "scored_count": scored_count, "message": f"Successfully scored {scored_count} candidates."}


@router.get("/{job_id}/ranking", response_model=RankingResponse)
def get_ranking(
    job_id: str,
    min_score: int = Query(0, ge=0, le=100),
    anonymize: bool = Query(False),
    db: Session = Depends(get_db)
):
    """
    Returns ranked candidate list with summary statistics.
    Anonymize mode replaces name, email and phone with 'Candidate N'.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    candidates = db.query(Candidate).filter(Candidate.job_id == job_id).all()
    scores = db.query(Score).filter(Score.job_id == job_id).all()
    score_map = {s.candidate_id: s for s in scores}
    explanations = db.query(Explanation).filter(Explanation.candidate_id.in_([c.id for c in candidates])).all()
    exp_map = {e.candidate_id: e.payload for e in explanations}

    ranked_items = []
    seen_identities = set()

    for cand in candidates:
        identity = (cand.email or cand.name or cand.filename or "").strip().lower()
        if identity in seen_identities:
            continue
        seen_identities.add(identity)

        s = score_map.get(cand.id)
        if not s:
            continue
        if s.total < min_score:
            continue

        exp = exp_map.get(cand.id, {})
        matched_skills_names = [m["skill"] for m in exp.get("matched_skills", [])]
        relevant_years = exp.get("experience", {}).get("relevant_years", cand.total_years)
        flags = exp.get("flags", [])

        ranked_items.append({
            "id": cand.id,
            "filename": cand.filename,
            "name": cand.name or "Candidate",
            "email": cand.email,
            "phone": cand.phone,
            "total_years": cand.total_years,
            "relevant_years": relevant_years,
            "total": s.total,
            "skills_score": s.skills_score,
            "semantic_score": s.semantic_score,
            "experience_score": s.experience_score,
            "education_score": s.education_score,
            "must_have_coverage": s.must_have_coverage,
            "capped": s.capped,
            "matched_skills": matched_skills_names,
            "flags": flags,
        })

    # Sort descending by total score, then relevant years
    ranked_items.sort(key=lambda x: (x["total"], x["relevant_years"]), reverse=True)

    # Assign ranks and apply anonymization if requested
    final_candidates: List[RankingCandidateItem] = []
    scores_list = [c["total"] for c in ranked_items]
    capped_count = sum(1 for c in ranked_items if c["capped"])

    for idx, item in enumerate(ranked_items, start=1):
        if anonymize:
            anon_name = f"Candidate {idx}"
            anon_email = f"candidate{idx}@anonymized.local"
            anon_phone = "REDACTED"
        else:
            anon_name = item["name"]
            anon_email = item["email"]
            anon_phone = item["phone"]

        final_candidates.append(RankingCandidateItem(
            rank=idx,
            id=item["id"],
            filename=item["filename"],
            name=anon_name,
            email=anon_email,
            phone=anon_phone,
            total_years=item["total_years"],
            relevant_years=item["relevant_years"],
            total=item["total"],
            skills_score=item["skills_score"],
            semantic_score=item["semantic_score"],
            experience_score=item["experience_score"],
            education_score=item["education_score"],
            must_have_coverage=item["must_have_coverage"],
            capped=item["capped"],
            matched_skills=item["matched_skills"],
            flags=item["flags"],
        ))

    summary = RankingSummary(
        total_candidates=len(candidates),
        scored_candidates=len(scores),
        top_score=max(scores_list) if scores_list else 0,
        median_score=float(np.median(scores_list)) if scores_list else 0.0,
        capped_count=capped_count,
    )

    return RankingResponse(job_id=job.id, summary=summary, candidates=final_candidates)


@router.get("/{job_id}/export.csv")
def export_ranking_csv(job_id: str, db: Session = Depends(get_db)):
    """Export ranked candidate list as downloadable CSV."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    candidates = db.query(Candidate).filter(Candidate.job_id == job_id).all()
    scores = db.query(Score).filter(Score.job_id == job_id).all()
    score_map = {s.candidate_id: s for s in scores}
    explanations = db.query(Explanation).filter(Explanation.candidate_id.in_([c.id for c in candidates])).all()
    exp_map = {e.candidate_id: e.payload for e in explanations}

    items = []
    for cand in candidates:
        s = score_map.get(cand.id)
        if not s:
            continue
        exp = exp_map.get(cand.id, {})
        items.append({
            "name": cand.name or "Candidate",
            "email": cand.email or "",
            "filename": cand.filename,
            "total": s.total,
            "relevant_years": exp.get("experience", {}).get("relevant_years", cand.total_years),
            "total_years": cand.total_years,
            "skills": s.skills_score,
            "semantic": s.semantic_score,
            "experience": s.experience_score,
            "education": s.education_score,
            "coverage": s.must_have_coverage,
            "capped": "YES" if s.capped else "NO",
            "matched_skills": "; ".join(m["skill"] for m in exp.get("matched_skills", [])),
            "flags": "; ".join(exp.get("flags", [])),
        })

    items.sort(key=lambda x: (x["total"], x["relevant_years"]), reverse=True)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Rank", "Candidate Name", "Email", "Filename", "Total Match %",
        "Must-Have Coverage", "Relevant Years", "Total Years",
        "Skills Score", "Semantic Score", "Experience Score", "Education Score",
        "Capped Policy", "Matched Skills", "Flags"
    ])

    for rank, it in enumerate(items, start=1):
        writer.writerow([
            rank, it["name"], it["email"], it["filename"], it["total"],
            f"{it['coverage'] * 100:.1f}%", it["relevant_years"], it["total_years"],
            f"{it['skills'] * 100:.1f}%", f"{it['semantic'] * 100:.1f}%",
            f"{it['experience'] * 100:.1f}%", f"{it['education'] * 100:.1f}%",
            it["capped"], it["matched_skills"], it["flags"]
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=candidate_ranking_{job.id[:8]}.csv"}
    )


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(job_id: str, db: Session = Depends(get_db)):
    """Delete a job and cascade delete all its candidates, scores and explanations."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    db.delete(job)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
