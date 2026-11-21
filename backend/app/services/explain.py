"""
Score Explanation Service.
Generates human-readable, transparent reasoning and component breakdowns
explaining exactly how a candidate's score was computed.
"""

from typing import Dict, List, Any, Optional

def generate_reasons(
    components: Dict[str, float],
    weights: Dict[str, float],
    must_have_total: int,
    must_have_matched: int,
    must_have_names: List[str],
    missing_must_haves: List[str],
    skills_list_only: List[str],
    partial_matches: List[Dict[str, Any]],
    required_years: Optional[float],
    total_years: float,
    relevant_years: float,
    required_degree_level: int,
    candidate_degree_level: int,
    is_capped: bool,
    cap_score: int,
    coverage: float,
) -> List[str]:
    reasons: List[str] = []

    # 1. Gating Flag Reason
    if is_capped:
        reasons.append(
            f"Score capped at {cap_score} because must-have skill coverage ({coverage * 100:.0f}%) is below the 50% threshold."
        )

    # 2. Must-Have Skills Summary
    if must_have_total > 0:
        matched_sample = ", ".join(must_have_names[:5])
        if len(must_have_names) > 5:
            matched_sample += f", +{len(must_have_names) - 5} more"
        reasons.append(
            f"Covers {must_have_matched} of {must_have_total} must-have skills ({matched_sample or 'none'})."
        )

    # 3. Missing Must-Haves
    if missing_must_haves:
        missing_sample = ", ".join(missing_must_haves[:5])
        if len(missing_must_haves) > 5:
            missing_sample += f", +{len(missing_must_haves) - 5} more"
        reasons.append(f"Missing must-have skills: {missing_sample}.")

    # 4. Reduced Credit for Skills-List-Only Matches
    if skills_list_only:
        sample_skills = ", ".join(skills_list_only[:3])
        reasons.append(
            f"'{sample_skills}' appears only in the skills list with no supporting experience, so credit was reduced to 0.6."
        )

    # 5. Semantic Partial Skill Matches
    if partial_matches:
        for p in partial_matches[:2]:
            reasons.append(
                f"Partial semantic match: '{p['required']}' matched closely with '{p['closest']}' (similarity {p['similarity']:.2f}, credit {p['credit']:.2f})."
            )

    # 6. Experience Timeline & Relevance
    exp_score = components.get("experience", 0.0)
    if required_years is not None and required_years > 0:
        reasons.append(
            f"{relevant_years:.1f} relevant years of {required_years:.1f} required gives an experience score of {exp_score:.2f} (total career duration: {total_years:.1f} yrs)."
        )
    else:
        reasons.append(
            f"Candidate has {total_years:.1f} total years of experience (no strict year requirement specified)."
        )

    # 7. Education Level
    deg_names = {0: "None specified", 1: "Associate / Diploma", 2: "Bachelor's", 3: "Master's", 4: "PhD / Doctorate"}
    if required_degree_level > 0:
        if candidate_degree_level >= required_degree_level:
            reasons.append(
                f"Meets education requirement: holds a {deg_names.get(candidate_degree_level, 'degree')} (required: {deg_names.get(required_degree_level)})."
            )
        elif candidate_degree_level == required_degree_level - 1:
            reasons.append(
                f"Holds a {deg_names.get(candidate_degree_level, 'degree')}, one level below the required {deg_names.get(required_degree_level)} (partial credit 0.5)."
            )
        else:
            reasons.append(
                f"Education level ({deg_names.get(candidate_degree_level, 'None')}) is below the required {deg_names.get(required_degree_level)}."
            )

    # 8. Semantic Alignment
    semantic_score = components.get("semantic", 0.0)
    if semantic_score >= 0.70:
        reasons.append(
            f"Strong semantic alignment ({semantic_score * 100:.0f}%) between resume experience bullets and job responsibilities."
        )
    elif semantic_score <= 0.40:
        reasons.append(
            f"Low semantic overlap ({semantic_score * 100:.0f}%) with job duties and core responsibilities."
        )

    return reasons


def format_components_list(
    raw_components: Dict[str, float],
    weights: Dict[str, float]
) -> List[Dict[str, Any]]:
    """Format components as [{name, raw, weight, points}]."""
    display_names = {
        "skills": "Skills Match",
        "semantic": "Semantic Alignment",
        "experience": "Experience Relevance",
        "education": "Education Level"
    }
    result = []
    for key in ["skills", "semantic", "experience", "education"]:
        raw = raw_components.get(key, 0.0)
        weight = weights.get(key, 0.0)
        points = round(100.0 * weight * raw, 1)
        result.append({
            "name": display_names.get(key, key.title()),
            "raw": round(raw, 3),
            "weight": weight,
            "points": points
        })
    return result
