"""
Unit tests for SkillMatcher, JD Extractor, and Skill Extraction Evaluation against gold.json.
Tests:
- Traps:
  - k8s equals Kubernetes
  - Java is never JavaScript
  - C++, C#, .NET, Node.js match correctly
  - Ambiguous short names (R, C, Go) gated by context
- Evidence labeling (experience vs skills_list vs other)
- JD extraction: sections, must_have vs nice_to_have, required_years (ranges), degree_level, free_text, responsibilities
- Skill extraction precision and recall against eval/gold.json
"""

import json
from pathlib import Path
import pytest

from app.services.skills import get_skill_matcher
from app.services.jd_extractor import extract_jd
from app.services.parsing import parse_resume


def test_trap_k8s_equals_kubernetes():
    matcher = get_skill_matcher()
    text = "Deployed containerized workloads to k8s clusters."
    matches = matcher.extract_skills_from_text(text)
    canonical_skills = [m["canonical"] for m in matches]
    assert "Kubernetes" in canonical_skills


def test_trap_java_is_not_javascript():
    matcher = get_skill_matcher()
    
    # 1. Text with only JavaScript
    js_text = "Experienced frontend engineer developing web applications in JavaScript and React."
    js_matches = matcher.extract_skills_from_text(js_text)
    js_canonicals = [m["canonical"] for m in js_matches]
    assert "JavaScript" in js_canonicals
    assert "Java" not in js_canonicals, "Java must NOT match JavaScript"

    # 2. Text with only Java
    java_text = "Architected high-throughput backend services using Java and Spring Boot."
    java_matches = matcher.extract_skills_from_text(java_text)
    java_canonicals = [m["canonical"] for m in java_matches]
    assert "Java" in java_canonicals
    assert "JavaScript" not in java_canonicals


def test_trap_special_symbols_cplusplus_csharp_dotnet_nodejs():
    matcher = get_skill_matcher()
    text = "Systems built using C++, C#, .NET Core, and Node.js backend services."
    matches = matcher.extract_skills_from_text(text)
    canonicals = [m["canonical"] for m in matches]
    assert "C++" in canonicals
    assert "C#" in canonicals
    assert ".NET" in canonicals
    assert "Node.js" in canonicals


def test_ambiguous_short_names_go_r_c():
    matcher = get_skill_matcher()

    # Negative cases (prose without programming context)
    neg_text = "I will go to the office tomorrow to take vitamin C and read section R."
    neg_matches = matcher.extract_skills_from_text(neg_text, is_skills_section=False)
    neg_canonicals = [m["canonical"] for m in neg_matches]
    assert "Go" not in neg_canonicals
    assert "C" not in neg_canonicals
    assert "R" not in neg_canonicals

    # Positive cases: inside skills section
    skills_sec_text = "Python, R, Go, C, Docker"
    pos_skills_matches = matcher.extract_skills_from_text(skills_sec_text, is_skills_section=True)
    pos_skills_canonicals = [m["canonical"] for m in pos_skills_matches]
    assert "Go" in pos_skills_canonicals
    assert "R" in pos_skills_canonicals
    assert "C" in pos_skills_canonicals

    # Positive cases: in prose with programming context
    pos_prose_text = "Developed microservices in Go programming language and built drivers in C language."
    pos_prose_matches = matcher.extract_skills_from_text(pos_prose_text, is_skills_section=False)
    pos_prose_canonicals = [m["canonical"] for m in pos_prose_matches]
    assert "Go" in pos_prose_canonicals
    assert "C" in pos_prose_canonicals


def test_evidence_labeling():
    matcher = get_skill_matcher()
    sections = {
        "summary": "Professional software engineer.",
        "skills": "Kafka, Redis, Docker",
        "experience": "Engineered microservices in Java using Spring Boot with PostgreSQL.",
    }
    resume_skills = matcher.match_resume_skills(sections)
    evidence_map = {s["skill"]: s["evidence"] for s in resume_skills}

    # Found in experience
    assert evidence_map.get("Java") == "experience"
    assert evidence_map.get("Spring Boot") == "experience"
    assert evidence_map.get("PostgreSQL") == "experience"

    # Found ONLY in skills section
    assert evidence_map.get("Kafka") == "skills_list"
    assert evidence_map.get("Redis") == "skills_list"


def test_jd_extractor_full():
    base_dir = Path(__file__).resolve().parent.parent.parent
    jd_path = base_dir / "eval" / "jds" / "java_backend.txt"
    with open(jd_path, "r", encoding="utf-8") as f:
        jd_text = f.read()

    extracted = extract_jd(jd_text)
    assert "Java" in extracted["title"] or "Engineer" in extracted["title"]
    assert extracted["required_years"] == 4.0  # 4-6 years -> lower bound 4.0
    assert extracted["degree_level"] == 2      # Bachelor's -> 2

    # Check must-have vs nice-to-have
    must_have = extracted["must_have_skills"]
    nice_to_have = extracted["nice_to_have_skills"]

    assert "Java" in must_have
    assert "Spring Boot" in must_have
    assert "SQL" in must_have
    assert "PostgreSQL" in must_have
    assert "Docker" in must_have

    assert "Kubernetes" in nice_to_have
    assert "Kafka" in nice_to_have
    assert "Redis" in nice_to_have

    # Check responsibilities and free text
    assert len(extracted["responsibilities_lines"]) >= 3
    assert any("microservices" in r.lower() for r in extracted["responsibilities_lines"])


def test_precision_recall_against_gold():
    base_dir = Path(__file__).resolve().parent.parent.parent
    gold_path = base_dir / "eval" / "gold.json"
    resumes_dir = base_dir / "eval" / "resumes"

    with open(gold_path, "r", encoding="utf-8") as f:
        gold_data = json.load(f)

    matcher = get_skill_matcher()
    tp_total = 0
    fp_total = 0
    fn_total = 0

    for filename, meta in gold_data.items():
        file_path = resumes_dir / filename
        with open(file_path, "rb") as f:
            file_bytes = f.read()

        parsed = parse_resume(file_bytes, filename)
        matched_skills = matcher.match_resume_skills(parsed["sections"], parsed["raw_text"])
        predicted_canonical = set(s["skill"] for s in matched_skills)
        gold_canonical = set(meta["true_skills"])

        # True Positives: predicted and in gold
        tp = len(predicted_canonical.intersection(gold_canonical))
        # False Positives: predicted but not in gold
        fp = len(predicted_canonical - gold_canonical)
        # False Negatives: in gold but not predicted
        fn = len(gold_canonical - predicted_canonical)

        tp_total += tp
        fp_total += fp
        fn_total += fn

    precision = tp_total / (tp_total + fp_total) if (tp_total + fp_total) > 0 else 0.0
    recall = tp_total / (tp_total + fn_total) if (tp_total + fn_total) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    print("\n--- SKILL EXTRACTION EVALUATION REPORT ---")
    print(f"Total True Positives:  {tp_total}")
    print(f"Total False Positives: {fp_total}")
    print(f"Total False Negatives: {fn_total}")
    print(f"Precision:             {precision * 100.0:.2f}%")
    print(f"Recall:                {recall * 100.0:.2f}%")
    print(f"F1-Score:              {f1 * 100.0:.2f}%")

    assert precision >= 0.85, f"Skill extraction precision {precision:.2f} is below 85%"
    assert recall >= 0.85, f"Skill extraction recall {recall:.2f} is below 85%"


def test_negation_detection_prevents_false_positive_skill_credit():
    matcher = get_skill_matcher()

    # 1. Negative mentions should be discarded
    neg_text = "I have no experience with Kubernetes and never worked with AWS in production."
    neg_matches = [m["canonical"] for m in matcher.extract_skills_from_text(neg_text)]
    assert "Kubernetes" not in neg_matches, "Negated Kubernetes was falsely matched!"
    assert "AWS" not in neg_matches, "Negated AWS was falsely matched!"

    # 2. Positive mentions should still be captured cleanly
    pos_text = "Responsible for zero downtime deployment using Kubernetes and Docker."
    pos_matches = [m["canonical"] for m in matcher.extract_skills_from_text(pos_text)]
    assert "Kubernetes" in pos_matches, "Valid Kubernetes match was incorrectly skipped!"
    assert "Docker" in pos_matches, "Valid Docker match was incorrectly skipped!"

    # 3. Resume section matching test
    sections = {
        "experience": "Without any direct experience in GraphQL. Proficient in Python and PostgreSQL.",
        "skills": "Python, PostgreSQL"
    }
    resume_skills = [s["skill"] for s in matcher.match_resume_skills(sections)]
    assert "GraphQL" not in resume_skills, "Negated GraphQL was included in resume skills!"
    assert "Python" in resume_skills
    assert "PostgreSQL" in resume_skills


def test_any_of_skill_grouping_and_scoring():
    from app.services.scoring import score_candidate, load_scoring_config
    config = load_scoring_config()

    jd_text = """Job Title: Backend Engineer
Requirements:
- Strong proficiency in Java or Kotlin.
- Experience with PostgreSQL or MySQL.
Responsibilities:
- Build backend APIs.
"""
    extracted = extract_jd(jd_text)

    # Check that any_of groups were detected
    grouped_reqs = {s["name"]: s for s in extracted["skills"]}
    assert "Java / Kotlin" in grouped_reqs
    assert grouped_reqs["Java / Kotlin"]["any_of"] == ["Java", "Kotlin"]
    assert "PostgreSQL / MySQL" in grouped_reqs
    assert grouped_reqs["PostgreSQL / MySQL"]["any_of"] == ["PostgreSQL", "MySQL"]

    # Candidate A has Java only (no Kotlin)
    cand_java = {
        "skills": [{"skill": "Java", "evidence": "experience"}],
        "entries": [{"title": "Backend Dev", "text": "Built services in Java.", "start_date": "2020-01", "end_date": "2023-01"}],
        "total_years": 3.0,
        "sections": {"experience": "Built services in Java."}
    }
    res_a = score_candidate(cand_java, extracted, None, config)
    matched_a = [s["skill"] for s in res_a["matched_skills"]]
    assert "Java / Kotlin" in matched_a, "Candidate with Java did not satisfy Java / Kotlin requirement!"

    # Candidate B has Kotlin only (no Java)
    cand_kotlin = {
        "skills": [{"skill": "Kotlin", "evidence": "experience"}],
        "entries": [{"title": "Android/Backend", "text": "Wrote backend code in Kotlin.", "start_date": "2020-01", "end_date": "2023-01"}],
        "total_years": 3.0,
        "sections": {"experience": "Wrote backend code in Kotlin."}
    }
    res_b = score_candidate(cand_kotlin, extracted, None, config)
    matched_b = [s["skill"] for s in res_b["matched_skills"]]
    assert "Java / Kotlin" in matched_b, "Candidate with Kotlin did not satisfy Java / Kotlin requirement!"

