"""
Scoring & Ranking Service.
Computes deterministic scores based on:
1. Skills Matching (Exact, Evidence-discounted, and Semantic fallbacks)
2. Semantic Max-Similarity (JD responsibilities & free text vs resume bullets)
3. Experience Relevance (cosine-filtered relevant career months)
4. Education Level matching
5. Core Skills Safety Gating policy
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import numpy as np

from app.services.explain import generate_reasons, format_components_list
from app.services.parsing import calculate_total_years, extract_date_ranges_from_line


def load_scoring_config() -> Dict[str, Any]:
    config_path = Path(__file__).resolve().parent.parent / "config" / "scoring.json"
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def ramp(sim: float, tau_low: float, tau_high: float) -> float:
    """Clamps (sim - tau_low) / (tau_high - tau_low) to 0.0 .. 1.0."""
    if sim <= tau_low:
        return 0.0
    if sim >= tau_high:
        return 1.0
    return (sim - tau_low) / (tau_high - tau_low)


def extract_candidate_degree_level(education_text: str, raw_text: str = "") -> int:
    """Extract candidate highest degree level (0=None, 1=Associate, 2=Bachelor, 3=Master, 4=PhD)."""
    search_text = f"{education_text}\n{raw_text}".lower()
    if re.search(r"\b(?:ph\.?d\.?|doctorate|doctoral)\b", search_text):
        return 4
    if re.search(r"\b(?:master'?s?|m\.?s\.?|mba|postgraduate)\b", search_text):
        return 3
    if re.search(r"\b(?:bachelor'?s?|b\.?s\.?|b\.?a\.?|undergraduate|b\.?tech|b\.?e\.)\b", search_text):
        return 2
    if re.search(r"\b(?:diploma|associate'?s?|vocational)\b", search_text):
        return 1
    return 0


def score_candidate(
    candidate: Dict[str, Any],
    jd: Dict[str, Any],
    embedder: Any,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Computes deterministic match score and complete explanation payload.
    """
    if config is None:
        config = load_scoring_config()

    weights = config["weights"]
    skill_weights = config["skill_weights"]
    skill_credits = config["skill_credits"]
    thresholds = config["thresholds"]
    gate_config = config["gate"]

    tau_low = thresholds["tau_low"]
    tau_high = thresholds["tau_high"]

    # -------------------------------------------------------------
    # 1. Skills Component
    # -------------------------------------------------------------
    jd_skills = jd.get("skills", [])
    candidate_skills = candidate.get("skills", [])
    
    # Map candidate skills by canonical name and lowercased name
    candidate_skill_map = {s["skill"].lower(): s for s in candidate_skills}

    matched_skills = []
    partial_skills = []
    missing_skills = []

    total_weight = 0.0
    weighted_credit_sum = 0.0
    must_have_credits = []
    must_have_matched_names = []
    skills_list_only_names = []

    # Prepare candidate skill names for fallback semantic search
    cand_skill_names = [s["skill"] for s in candidate_skills]
    cand_skill_embeds = None
    if cand_skill_names and embedder:
        cand_skill_embeds = np.asarray(embedder.embed_texts(cand_skill_names), dtype=np.float32)

    for req in jd_skills:
        req_name = req["name"]
        importance = req.get("importance", "must_have")
        weight = skill_weights.get(importance, 1.0)
        total_weight += weight

        # Support "any_of" grouped skills (e.g. ['Java', 'Kotlin'])
        any_of_variants = req.get("any_of") or [req_name]

        best_match = None
        best_exact_variant = None
        best_credit = -1.0
        best_evidence = None

        for variant in any_of_variants:
            cand_m = candidate_skill_map.get(variant.lower())
            if cand_m:
                ev = cand_m.get("evidence", "skills_list")
                if ev == "experience":
                    c_val = skill_credits.get("exact_experience", 1.0)
                elif ev == "skills_list":
                    c_val = skill_credits.get("exact_skills_list", 0.6)
                else:
                    c_val = skill_credits.get("exact_other", 0.6)

                if c_val > best_credit:
                    best_credit = c_val
                    best_match = cand_m
                    best_exact_variant = variant
                    best_evidence = ev

        # A) Exact or Alias match found for at least one any_of alternative
        if best_match is not None:
            if best_evidence == "skills_list":
                skills_list_only_names.append(req_name)

            matched_skills.append({
                "skill": req_name,
                "matched_as": best_exact_variant,
                "credit": best_credit,
                "evidence": best_evidence,
                "snippet": best_match.get("snippet", "")
            })
            if importance == "must_have":
                must_have_matched_names.append(req_name)
                must_have_credits.append(best_credit)

            weighted_credit_sum += weight * best_credit

        # B) Semantic Partial Match Fallback
        else:
            best_sim = 0.0
            closest_skill = None
            if cand_skill_names and cand_skill_embeds is not None and len(cand_skill_names) > 0:
                for variant in any_of_variants:
                    raw_req_vec = embedder.embed_texts([variant])
                    req_vec = np.asarray(raw_req_vec[0], dtype=np.float32)
                    sims = np.dot(cand_skill_embeds, req_vec)
                    best_idx = int(np.argmax(sims))
                    cur_sim = float(sims[best_idx])
                    if cur_sim > best_sim:
                        best_sim = cur_sim
                        closest_skill = cand_skill_names[best_idx]

            partial_factor = skill_credits.get("partial_semantic_factor", 0.5)
            min_partial_sim = thresholds.get("min_partial_skill_sim", 0.75)
            min_partial_credit = thresholds.get("min_partial_skill_credit", 0.20)
            credit = ramp(best_sim, tau_low, tau_high) * partial_factor

            # A partial match is only valid if similarity is high-confidence (>= 0.75).
            # Weak cross-tech overlaps (e.g. SQL vs Python at 0.74 or GitHub vs PyTorch at 0.57)
            # must be recognized as missing skills, not partial coverage.
            if credit >= min_partial_credit and best_sim >= min_partial_sim:
                partial_skills.append({
                    "required": req_name,
                    "closest": closest_skill,
                    "similarity": round(best_sim, 3),
                    "credit": round(credit, 3)
                })
                if importance == "must_have":
                    must_have_credits.append(credit)
                weighted_credit_sum += weight * credit
            else:
                missing_skills.append({
                    "skill": req_name,
                    "importance": importance
                })
                if importance == "must_have":
                    must_have_credits.append(0.0)

    skills_score = weighted_credit_sum / total_weight if total_weight > 0 else 1.0
    must_have_coverage = (
        sum(must_have_credits) / len(must_have_credits)
        if must_have_credits else 1.0
    )

    # -------------------------------------------------------------
    # 2. Semantic Component (Max-Similarity Matching)
    # -------------------------------------------------------------
    jd_eval_lines = jd.get("responsibilities_lines", []) + jd.get("free_text_lines", [])
    
    # Candidate bullet points across experience and projects
    cand_bullets = []
    for entry in candidate.get("entries", []):
        entry_text = entry.get("text", "")
        for line in entry_text.split("\n"):
            line_str = line.strip()
            # remove leading dash or bullet
            line_str = re.sub(r"^[\s*\-_•·]+\s*", "", line_str)
            if len(line_str.split()) >= 4:
                cand_bullets.append(line_str)

    if not cand_bullets:
        # Fallback to whole experience text or raw text lines
        exp_sec = candidate.get("sections", {}).get("experience", "")
        for line in exp_sec.split("\n"):
            if len(line.split()) >= 4:
                cand_bullets.append(line.strip())

    if not jd_eval_lines or not cand_bullets:
        # Compare whole JD text to candidate experience text
        if embedder:
            jd_full = f"{jd.get('title', '')} {' '.join(jd.get('responsibilities_lines', []))}"
            cand_full = candidate.get("sections", {}).get("experience", candidate.get("raw_text", ""))
            v_jd = np.asarray(embedder.embed_texts([jd_full])[0], dtype=np.float32)
            v_cand = np.asarray(embedder.embed_texts([cand_full])[0], dtype=np.float32)
            sim = float(np.dot(v_jd, v_cand))
            semantic_score = ramp(sim, tau_low, tau_high)
        else:
            semantic_score = 0.5
    else:
        # Max-similarity over each JD line
        if embedder:
            jd_embeds = np.asarray(embedder.embed_texts(jd_eval_lines), dtype=np.float32)
            cand_bullet_embeds = np.asarray(embedder.embed_texts(cand_bullets), dtype=np.float32)
            
            # Matrix cosine: shape (len(jd_lines), len(bullets))
            sim_matrix = np.dot(jd_embeds, cand_bullet_embeds.T)
            best_cosines = np.max(sim_matrix, axis=1)
            line_credits = [ramp(float(sim), tau_low, tau_high) for sim in best_cosines]
            semantic_score = float(np.mean(line_credits))
        else:
            semantic_score = 0.5

    # -------------------------------------------------------------
    # 3. Experience Component
    # -------------------------------------------------------------
    required_years = jd.get("required_years")
    total_years = candidate.get("total_years", 0.0)
    
    relevant_date_ranges = []
    jd_desc_query = f"{jd.get('title', '')} {' '.join(jd.get('responsibilities_lines', []))}"
    jd_query_vec = np.asarray(embedder.embed_texts([jd_desc_query])[0], dtype=np.float32) if embedder else None

    for entry in candidate.get("entries", []):
        entry_text = f"{entry.get('title', '')}\n{entry.get('text', '')}"
        is_relevant = True
        
        if embedder and jd_query_vec is not None:
            raw_entry_vec = embedder.embed_texts([entry_text])
            entry_vec = np.asarray(raw_entry_vec[0], dtype=np.float32)
            entry_sim = float(np.dot(entry_vec, jd_query_vec))
            if entry_sim < thresholds.get("relevant_experience_cosine", 0.60):
                is_relevant = False

        if is_relevant:
            # Extract date ranges for this entry
            dr_list = extract_date_ranges_from_line(entry_text)
            for dr in dr_list:
                relevant_date_ranges.append(dr)

    # Compute non-overlapping relevant years
    relevant_years = calculate_total_years(relevant_date_ranges) if relevant_date_ranges else 0.0
    # Safeguard: relevant_years cannot exceed total_years
    relevant_years = min(relevant_years, total_years)

    if required_years is not None and required_years > 0:
        experience_score = float(np.clip(relevant_years / required_years, 0.0, 1.0))
        ratio = round(relevant_years / required_years, 2)
    else:
        if total_years >= 1.0:
            experience_score = config["experience_defaults"]["no_requirement_min_1_yr"]
        else:
            experience_score = config["experience_defaults"]["no_requirement_less_1_yr"]
        ratio = 1.0

    # -------------------------------------------------------------
    # 4. Education Component
    # -------------------------------------------------------------
    required_degree_level = jd.get("degree_level", 0)
    candidate_education_sec = candidate.get("sections", {}).get("education", "")
    candidate_degree_level = extract_candidate_degree_level(candidate_education_sec, candidate.get("raw_text", ""))

    edu_credits = config["education_credits"]
    if required_degree_level == 0:
        education_score = edu_credits["no_requirement"]
    elif candidate_degree_level >= required_degree_level:
        education_score = edu_credits["meets_or_exceeds"]
    elif candidate_degree_level == required_degree_level - 1:
        education_score = edu_credits["one_level_below"]
    else:
        education_score = edu_credits["below"]

    # -------------------------------------------------------------
    # 5. Composite Score & Gating Policy
    # -------------------------------------------------------------
    raw_total = 100.0 * (
        weights["skills"] * skills_score
        + weights["semantic"] * semantic_score
        + weights["experience"] * experience_score
        + weights["education"] * education_score
    )

    flags = []
    is_capped = False
    cap_score = gate_config["cap_score"]

    if must_have_coverage < gate_config["must_have_coverage_threshold"]:
        is_capped = True
        flags.append(gate_config["flag_name"])
        total_score = min(round(raw_total), cap_score)
        try:
            from app.services.logger import record_log
            record_log("SCORING", "WARNING", f"Safety gate capped candidate score from {raw_total:.1f} to {total_score} (missing must-have skills)")
        except Exception:
            pass
    else:
        total_score = round(raw_total)

    # -------------------------------------------------------------
    # 6. Explanations Payload
    # -------------------------------------------------------------
    raw_components = {
        "skills": skills_score,
        "semantic": semantic_score,
        "experience": experience_score,
        "education": education_score
    }
    components_list = format_components_list(raw_components, weights)

    must_have_total = len([s for s in jd_skills if s.get("importance") == "must_have"])
    missing_must_haves = [s["skill"] for s in missing_skills if s.get("importance") == "must_have"]

    reasons = generate_reasons(
        components=raw_components,
        weights=weights,
        must_have_total=must_have_total,
        must_have_matched=len(must_have_matched_names),
        must_have_names=must_have_matched_names,
        missing_must_haves=missing_must_haves,
        skills_list_only=skills_list_only_names,
        partial_matches=partial_skills,
        required_years=required_years,
        total_years=total_years,
        relevant_years=relevant_years,
        required_degree_level=required_degree_level,
        candidate_degree_level=candidate_degree_level,
        is_capped=is_capped,
        cap_score=cap_score,
        coverage=must_have_coverage,
    )

    return {
        "total": total_score,
        "raw_total": round(raw_total, 2),
        "capped": is_capped,
        "must_have_coverage": round(must_have_coverage, 3),
        "components": components_list,
        "matched_skills": matched_skills,
        "partial_skills": partial_skills,
        "missing_skills": missing_skills,
        "experience": {
            "required_years": required_years,
            "total_years": round(total_years, 1),
            "relevant_years": round(relevant_years, 1),
            "ratio": ratio
        },
        "education": {
            "required_level": required_degree_level,
            "candidate_level": candidate_degree_level,
            "credit": education_score
        },
        "reasons": reasons,
        "flags": flags
    }
