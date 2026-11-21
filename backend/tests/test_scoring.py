"""
Unit tests for scoring engine, golden worked example, deterministic repeatability,
explanation component point sum, and core skill safety gating.
"""

from unittest.mock import MagicMock
import numpy as np
import pytest

from app.services.scoring import score_candidate, load_scoring_config


def test_golden_worked_example_exact_80():
    """
    Golden worked example from specification:
    - Required skills:
        Must: Java, Spring Boot, SQL, REST, Docker (weight 1.0 each)
        Nice: Kubernetes, AWS (weight 0.5 each)
    - Credits:
        Java: 1.0, Spring Boot: 1.0, SQL: 1.0, REST: 1.0, Docker: 0.6
        Kubernetes: 0.0, AWS: 0.4
    - Skills calculation:
        (4.6 + 0.4 * 0.5) / 6.0 = 4.8 / 6.0 = 0.80
    - Semantic: 0.70
    - Experience: 4.0 / 5.0 = 0.80
    - Education: 1.0
    - Weights: 0.45 * 0.80 + 0.20 * 0.70 + 0.25 * 0.80 + 0.10 * 1.0
               = 0.36 + 0.14 + 0.20 + 0.10 = 0.80
    - Total: round(100 * 0.80) = exactly 80.
    """
    config = {
        "weights": {"skills": 0.45, "semantic": 0.20, "experience": 0.25, "education": 0.10},
        "skill_weights": {"must_have": 1.0, "nice_to_have": 0.5},
        "skill_credits": {"exact_experience": 1.0, "exact_skills_list": 0.6, "exact_other": 0.6, "partial_semantic_factor": 0.5},
        "thresholds": {"tau_low": 0.60, "tau_high": 0.85, "relevant_experience_cosine": 0.60},
        "experience_defaults": {"no_requirement_min_1_yr": 1.0, "no_requirement_less_1_yr": 0.5},
        "education_credits": {"meets_or_exceeds": 1.0, "one_level_below": 0.5, "below": 0.0, "no_requirement": 1.0},
        "gate": {"must_have_coverage_threshold": 0.50, "cap_score": 65, "flag_name": "capped_missing_core_skills"}
    }

    jd = {
        "title": "Senior Java Developer",
        "required_years": 5.0,
        "degree_level": 2,  # Bachelor's
        "skills": [
            {"name": "Java", "importance": "must_have"},
            {"name": "Spring Boot", "importance": "must_have"},
            {"name": "SQL", "importance": "must_have"},
            {"name": "REST", "importance": "must_have"},
            {"name": "Docker", "importance": "must_have"},
            {"name": "Kubernetes", "importance": "nice_to_have"},
            {"name": "AWS", "importance": "nice_to_have"},
        ],
        "responsibilities_lines": ["Develop Java backend services with Spring Boot and SQL."],
        "free_text_lines": []
    }

    # Candidate setup
    candidate = {
        "skills": [
            {"skill": "Java", "evidence": "experience"},
            {"skill": "Spring Boot", "evidence": "experience"},
            {"skill": "SQL", "evidence": "experience"},
            {"skill": "REST", "evidence": "experience"},
            {"skill": "Docker", "evidence": "skills_list"},  # credit 0.6
            {"skill": "Amazon Cloud Services", "evidence": "experience"}  # produces 0.4 via mock
        ],
        "entries": [
            {
                "title": "Backend Engineer",
                "text": "Jan 2020 - Dec 2023: Constructed scalable distributed microservices in production.",
                "start_date": "2020-01",
                "end_date": "2023-12"
            }
        ],
        "total_years": 4.0,
        "sections": {
            "education": "BS in Computer Science, State University, 2016 - 2020",
            "experience": "Jan 2020 - Dec 2023: Constructed scalable distributed microservices in production."
        }
    }

    # Mock embedder
    mock_embedder = MagicMock()
    
    # In scoring:
    # AWS is nice_to_have. Credit = ramp((sim - 0.60) / 0.25) * 0.5.
    # To get credit = 0.4: ramp * 0.5 = 0.4 => ramp = 0.80 => (sim - 0.60)/0.25 = 0.80 => sim = 0.80.
    # Semantic: ramp((sim - 0.60)/0.25) = 0.70 => sim = 0.775.
    def mock_embed(texts, **kwargs):
        arr = []
        for t in texts:
            if t == "AWS":
                arr.append([0.80] + [0.0] * 383)
            elif t == "Kubernetes":
                arr.append([0.0] * 384)
            elif t == "Amazon Cloud Services":
                arr.append([1.00] + [0.0] * 383)
            elif "develop java backend" in t.lower():
                # JD responsibilities line
                arr.append([0.775] + [0.0] * 383)
            elif "constructed scalable" in t.lower():
                # Candidate bullet point: dot product with JD line = 0.775 * 1.0 = 0.775
                arr.append([1.00] + [0.0] * 383)
            elif "senior java developer" in t.lower() or "backend engineer" in t.lower():
                # Experience query match >= 0.60
                arr.append([1.00] + [0.0] * 383)
            else:
                arr.append([1.00] + [0.0] * 383)
        return np.array(arr, dtype=np.float32)

    mock_embedder.embed_texts.side_effect = mock_embed

    result = score_candidate(candidate, jd, mock_embedder, config)

    assert result["total"] == 80, f"Expected exactly 80, got {result['total']}"
    assert result["capped"] is False
    assert result["education"]["credit"] == 1.0

    # Verify points breakdown adds up to total
    components = result["components"]
    points_sum = round(sum(c["points"] for c in components))
    assert points_sum == 80


def test_deterministic_scoring_repeatability():
    """Verify that scoring the same candidate twice yields identical results."""
    from app.services.embedder import get_embedder
    embedder = get_embedder()

    jd = {
        "title": "Backend Java Engineer",
        "required_years": 4.0,
        "degree_level": 2,
        "skills": [
            {"name": "Java", "importance": "must_have"},
            {"name": "Spring Boot", "importance": "must_have"},
            {"name": "PostgreSQL", "importance": "must_have"},
            {"name": "Docker", "importance": "nice_to_have"},
        ],
        "responsibilities_lines": ["Build RESTful microservices in Java with Spring Boot."],
        "free_text_lines": []
    }

    candidate = {
        "skills": [
            {"skill": "Java", "evidence": "experience"},
            {"skill": "Spring Boot", "evidence": "experience"},
            {"skill": "PostgreSQL", "evidence": "skills_list"},
        ],
        "entries": [
            {
                "title": "Java Developer",
                "text": "Jan 2021 - Dec 2024: Built backend services.",
                "start_date": "2021-01",
                "end_date": "2024-12"
            }
        ],
        "total_years": 4.0,
        "sections": {
            "education": "Bachelor of Science in Software Engineering, 2017 - 2021",
            "experience": "Jan 2021 - Dec 2024: Built backend services in Java."
        }
    }

    res1 = score_candidate(candidate, jd, embedder)
    res2 = score_candidate(candidate, jd, embedder)

    assert res1["total"] == res2["total"]
    assert res1["raw_total"] == res2["raw_total"]
    assert res1["must_have_coverage"] == res2["must_have_coverage"]
    assert res1["reasons"] == res2["reasons"]


def test_safety_gating_caps_at_65():
    """Verify that must-have coverage < 0.50 caps total at 65 and adds capped_missing_core_skills flag."""
    config = {
        "weights": {"skills": 0.45, "semantic": 0.20, "experience": 0.25, "education": 0.10},
        "skill_weights": {"must_have": 1.0, "nice_to_have": 0.5},
        "skill_credits": {"exact_experience": 1.0, "exact_skills_list": 0.6, "exact_other": 0.6, "partial_semantic_factor": 0.5},
        "thresholds": {"tau_low": 0.60, "tau_high": 0.85, "relevant_experience_cosine": 0.60},
        "experience_defaults": {"no_requirement_min_1_yr": 1.0, "no_requirement_less_1_yr": 0.5},
        "education_credits": {"meets_or_exceeds": 1.0, "one_level_below": 0.5, "below": 0.0, "no_requirement": 1.0},
        "gate": {"must_have_coverage_threshold": 0.50, "cap_score": 65, "flag_name": "capped_missing_core_skills"}
    }

    jd = {
        "title": "Data Scientist",
        "required_years": 2.0,
        "degree_level": 2,
        "skills": [
            {"name": "Python", "importance": "must_have"},
            {"name": "Machine Learning", "importance": "must_have"},
            {"name": "scikit-learn", "importance": "must_have"},
            {"name": "Pandas", "importance": "must_have"},
        ],
        "responsibilities_lines": ["Data science analytics."],
        "free_text_lines": []
    }

    # Candidate has high experience (10 years) and degree, but covers only 1 of 4 must-have skills (coverage = 0.25 < 0.5)
    candidate = {
        "skills": [
            {"skill": "Python", "evidence": "experience"}
        ],
        "entries": [
            {
                "title": "Senior Analytics Lead",
                "text": "Jan 2014 - Dec 2024: Lead analyst.",
                "start_date": "2014-01",
                "end_date": "2024-12"
            }
        ],
        "total_years": 10.0,
        "sections": {
            "education": "PhD in Statistics, 2010 - 2014",
            "experience": "Lead analyst."
        }
    }

    mock_embedder = MagicMock()
    def mock_embed(texts, **kwargs):
        arr = []
        for t in texts:
            if t == "Python":
                arr.append([1.0] + [0.0] * 383)
            elif t in ["Machine Learning", "scikit-learn", "Pandas"]:
                arr.append([0.0, 1.0] + [0.0] * 382)  # Orthogonal to Python
            else:
                arr.append([1.0] + [0.0] * 383)
        return np.array(arr, dtype=np.float32)

    mock_embedder.embed_texts.side_effect = mock_embed

    res = score_candidate(candidate, jd, mock_embedder, config)

    assert res["must_have_coverage"] == 0.25
    assert res["capped"] is True
    assert "capped_missing_core_skills" in res["flags"]
    assert res["total"] <= 65
    assert any("Score capped at 65" in r for r in res["reasons"])
