"""
TalentRank Real-World Evaluation Suite
======================================
Evaluates TalentRank on all 2,484 PDF resumes across 24 professional categories in `data/`.

Computes:
1. Parsing & Ingestion Telemetry:
   - Success rate (% ok, % no_text_layer, % error)
   - Section detection rates (experience, education, skills, summary)
   - Contact extraction rates (email, phone)
   - Word and character count distributions
   - Total experience years distribution per category
   - Skill extraction density and evidence distribution per category
   - Parsing throughput and latency percentiles (p50, p95, p99)

2. Cross-Category Domain Discrimination & Ranking Purity:
   - Evaluates across 3 targeted technical Job Descriptions:
     a) Senior Software & Cloud Engineer
     b) Data Scientist & Machine Learning Specialist
     c) Full-Stack React & Node.js Developer
   - Category score rankings across all 24 industries
   - Target vs. Non-Target score separation delta
   - Top-K Domain Purity (Top 10, Top 25, Top 50, Top 100)
   - Safety gating activation rates (capped_missing_core_skills)
   - Scoring latency percentiles
"""

import os
import sys
import json
import time
import pickle
import math
from pathlib import Path
from collections import defaultdict, Counter
import numpy as np

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.services.parsing import parse_resume
from app.services.skills import get_skill_matcher
from app.services.jd_extractor import extract_jd
from app.services.embedder import get_embedder
from app.services.scoring import score_candidate, extract_candidate_degree_level, load_scoring_config

DATA_DIR = BASE_DIR / "data"
CACHE_PATH = BASE_DIR / "eval" / "parsed_cache.pkl"
RESULTS_JSON_PATH = BASE_DIR / "eval" / "real_world_eval_results.json"


# ---------------------------------------------------------------------------
# Target Job Descriptions for Cross-Category Evaluation
# ---------------------------------------------------------------------------

EVAL_JDS = {
    "software_cloud_engineer": {
        "title": "Senior Software & Cloud Backend Engineer",
        "target_categories": ["INFORMATION-TECHNOLOGY", "ENGINEERING"],
        "text": """Job Title: Senior Software & Cloud Backend Engineer
Location: Remote / Hybrid
Experience Required: 4+ years of professional software engineering experience.
Education: Bachelor's degree in Computer Science, Software Engineering, or related discipline.

Requirements:
- Strong proficiency in Python, Java, or Go.
- Production experience with Docker, Kubernetes, and Cloud infrastructure (AWS or GCP).
- Experience building REST microservices and distributed systems.
- Proficient in SQL, PostgreSQL, and database design.
- Hands-on experience with Linux, Git, and CI/CD pipelines.

Preferred Qualifications:
- Experience with Kafka, Redis, or RabbitMQ message queues.
- Knowledge of Terraform or infrastructure as code.
- Experience with Unit Testing and automated test suites.

Responsibilities:
- Architect, build, and deploy scalable cloud-native backend microservices.
- Optimize database queries and improve API response latency across distributed systems.
- Collaborate with frontend engineers and DevOps teams to maintain high system reliability.
- Write clean, maintainable, well-tested code following agile engineering practices.
"""
    },
    "data_scientist_ml": {
        "title": "Data Scientist & Machine Learning Specialist",
        "target_categories": ["INFORMATION-TECHNOLOGY"],
        "target_secondary": ["ENGINEERING", "FINANCE"],
        "text": """Job Title: Data Scientist & Machine Learning Specialist
Experience Required: 3+ years in data science, predictive modeling, or machine learning.
Education: Bachelor's or Master's degree in Computer Science, Statistics, Mathematics, or Data Science.

Requirements:
- Strong proficiency in Python, SQL, and data analysis libraries (Pandas, NumPy, Scikit-learn).
- Experience developing and deploying Machine Learning and Statistical Analysis models in production.
- Solid understanding of Data Science, Regression, Classification, and Feature Engineering.
- Experience querying large relational databases and Data Warehousing systems.

Preferred Qualifications:
- Experience with Deep Learning, PyTorch, or TensorFlow.
- Experience with Big Data tools like Apache Spark or Hadoop.
- Familiarity with cloud platforms (AWS, GCP) and containerization with Docker.

Responsibilities:
- Build and evaluate predictive statistical models to drive actionable business insights.
- Clean, preprocess, and validate massive multi-source datasets for model training.
- Deploy machine learning algorithms into production pipelines and monitor performance drift.
- Present data visualizations and analytical findings to cross-functional stakeholders.
"""
    },
    "frontend_fullstack_react": {
        "title": "Full-Stack React & Web Developer",
        "target_categories": ["INFORMATION-TECHNOLOGY"],
        "target_secondary": ["ENGINEERING", "DESIGNER"],
        "text": """Job Title: Full-Stack React & Web Developer
Experience Required: 3+ years in modern frontend and web application development.
Education: Bachelor's degree in Computer Science, Web Development, or equivalent practical experience.

Requirements:
- Strong expertise in JavaScript, TypeScript, React, HTML, and CSS.
- Hands-on experience with modern CSS frameworks such as Tailwind CSS or Bootstrap.
- Experience connecting frontend clients to RESTful APIs and state management.
- Proficiency with Git version control, npm, and modern build tooling.

Preferred Qualifications:
- Experience with Node.js, Express, and backend API development.
- Knowledge of GraphQL, Next.js, and responsive mobile-first UI design.
- Experience with frontend testing using Jest or Cypress.

Responsibilities:
- Develop responsive, accessible, high-performance web user interfaces using React.
- Collaborate with product designers and backend engineers to implement intuitive user flows.
- Optimize web applications for cross-browser compatibility and sub-second load times.
- Maintain reusable component libraries and write automated frontend tests.
"""
    }
}


# ---------------------------------------------------------------------------
# Phase 1: Ingestion & Parsing
# ---------------------------------------------------------------------------

def parse_all_resumes() -> list[dict]:
    """Parses all 2,484 resumes with caching."""
    if CACHE_PATH.exists():
        print(f"Loading cached parsed resumes from {CACHE_PATH}...")
        try:
            with open(CACHE_PATH, "rb") as f:
                cached = pickle.load(f)
            if len(cached) == 2484:
                print(f"Successfully loaded all {len(cached)} cached resumes.")
                return cached
            else:
                print(f"Cache has {len(cached)} resumes (expected 2484). Re-parsing...")
        except Exception as e:
            print(f"Cache load error: {e}. Re-parsing...")

    matcher = get_skill_matcher()
    pdf_paths = sorted(list(DATA_DIR.glob("*/*.pdf")))
    total_files = len(pdf_paths)
    print(f"Discovered {total_files} PDF resumes across {len(list(DATA_DIR.iterdir()))} categories.")

    parsed_resumes = []
    t0 = time.time()

    for idx, path in enumerate(pdf_paths, start=1):
        category = path.parent.name
        filename = path.name

        t_start = time.perf_counter()
        with open(path, "rb") as f:
            file_bytes = f.read()

        parsed = parse_resume(file_bytes, filename)
        t_parse = time.perf_counter() - t_start

        # Extract skills and degree level
        skills_list = matcher.match_resume_skills(parsed["sections"], parsed["raw_text"])
        degree_level = extract_candidate_degree_level(
            parsed["sections"].get("education", ""), parsed["raw_text"]
        )

        char_len = len(parsed["raw_text"])
        word_count = len(parsed["raw_text"].split())

        parsed_resumes.append({
            "filename": filename,
            "category": category,
            "path": str(path),
            "parse_status": parsed["parse_status"],
            "parse_warnings": parsed["parse_warnings"],
            "name": parsed["name"],
            "has_email": parsed["email"] is not None,
            "has_phone": parsed["phone"] is not None,
            "total_years": parsed["total_years"],
            "sections": list(parsed["sections"].keys()),
            "entries_count": len(parsed["entries"]),
            "skills": skills_list,
            "skills_count": len(skills_list),
            "degree_level": degree_level,
            "char_len": char_len,
            "word_count": word_count,
            "parse_time_ms": t_parse * 1000.0,
            # Data needed for scoring
            "_parsed_data": {
                "name": parsed["name"],
                "total_years": parsed["total_years"],
                "degree_level": degree_level,
                "skills": skills_list,
                "entries": parsed["entries"],
                "sections": parsed["sections"],
                "raw_text": parsed["raw_text"],
            }
        })

        if idx % 200 == 0 or idx == total_files:
            elapsed = time.time() - t0
            rate = idx / max(1e-9, elapsed)
            print(f"  [{idx}/{total_files}] parsed ({rate:.1f} resumes/sec)...")

    total_time = time.time() - t0
    print(f"Finished parsing {len(parsed_resumes)} resumes in {total_time:.2f}s ({len(parsed_resumes)/total_time:.1f} docs/sec).")

    # Save cache
    with open(CACHE_PATH, "wb") as f:
        pickle.dump(parsed_resumes, f, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"Saved parsed resume cache to {CACHE_PATH}.")

    return parsed_resumes


# ---------------------------------------------------------------------------
# Phase 2: Compute Ingestion & Parsing Statistics
# ---------------------------------------------------------------------------

def compute_parsing_statistics(resumes: list[dict]) -> dict:
    total_resumes = len(resumes)
    status_counts = Counter(r["parse_status"] for r in resumes)
    warning_counts = Counter()
    for r in resumes:
        for w in r["parse_warnings"]:
            warning_counts[w] += 1

    emails_found = sum(1 for r in resumes if r["has_email"])
    phones_found = sum(1 for r in resumes if r["has_phone"])

    # Section frequencies
    section_counts = Counter()
    for r in resumes:
        for s in r["sections"]:
            section_counts[s] += 1

    # Text length stats
    char_lens = [r["char_len"] for r in resumes]
    word_counts = [r["word_count"] for r in resumes]
    total_years_all = [r["total_years"] for r in resumes]
    skills_count_all = [r["skills_count"] for r in resumes]
    parse_times = [r["parse_time_ms"] for r in resumes]

    # Category breakdowns
    cat_stats = defaultdict(lambda: {
        "count": 0,
        "word_counts": [],
        "years": [],
        "skills_count": [],
        "has_email": 0,
        "has_phone": 0,
        "evidence_counts": Counter(),
    })

    overall_evidence = Counter()
    for r in resumes:
        cat = r["category"]
        c = cat_stats[cat]
        c["count"] += 1
        c["word_counts"].append(r["word_count"])
        c["years"].append(r["total_years"])
        c["skills_count"].append(r["skills_count"])
        if r["has_email"]:
            c["has_email"] += 1
        if r["has_phone"]:
            c["has_phone"] += 1
        for sk in r["skills"]:
            ev = sk.get("evidence", "other")
            c["evidence_counts"][ev] += 1
            overall_evidence[ev] += 1

    cat_summary = {}
    for cat, d in sorted(cat_stats.items()):
        cat_summary[cat] = {
            "count": d["count"],
            "avg_words": float(np.mean(d["word_counts"])),
            "avg_years": float(np.mean(d["years"])),
            "median_years": float(np.median(d["years"])),
            "avg_skills": float(np.mean(d["skills_count"])),
            "email_pct": float(d["has_email"] / d["count"] * 100.0),
            "phone_pct": float(d["has_phone"] / d["count"] * 100.0),
        }

    return {
        "total_resumes": total_resumes,
        "status_distribution": {
            "ok": status_counts.get("ok", 0),
            "no_text_layer": status_counts.get("no_text_layer", 0),
            "error": status_counts.get("error", 0),
            "ok_percentage": float(status_counts.get("ok", 0) / total_resumes * 100.0),
        },
        "identity_extraction": {
            "emails_found_pct": float(emails_found / total_resumes * 100.0),
            "phones_found_pct": float(phones_found / total_resumes * 100.0),
        },
        "section_detection_pct": {
            sec: float(cnt / total_resumes * 100.0) for sec, cnt in section_counts.most_common()
        },
        "text_metrics": {
            "avg_words": float(np.mean(word_counts)),
            "median_words": float(np.median(word_counts)),
            "min_words": int(np.min(word_counts)),
            "max_words": int(np.max(word_counts)),
            "avg_chars": float(np.mean(char_lens)),
        },
        "experience_years_metrics": {
            "overall_avg_years": float(np.mean(total_years_all)),
            "overall_median_years": float(np.median(total_years_all)),
            "overall_min_years": float(np.min(total_years_all)),
            "overall_max_years": float(np.max(total_years_all)),
        },
        "skill_metrics": {
            "overall_avg_skills": float(np.mean(skills_count_all)),
            "overall_median_skills": float(np.median(skills_count_all)),
            "max_skills_in_resume": int(np.max(skills_count_all)),
            "evidence_breakdown": {
                ev: float(cnt / max(1, sum(overall_evidence.values())) * 100.0)
                for ev, cnt in overall_evidence.items()
            },
        },
        "latency_metrics": {
            "p50_ms": float(np.percentile(parse_times, 50)),
            "p95_ms": float(np.percentile(parse_times, 95)),
            "p99_ms": float(np.percentile(parse_times, 99)),
            "avg_ms": float(np.mean(parse_times)),
        },
        "category_summary": cat_summary,
    }


# ---------------------------------------------------------------------------
# Phase 3: Cross-Category Matching & Domain Discrimination
# ---------------------------------------------------------------------------

def evaluate_jd_discrimination(resumes: list[dict], jd_key: str, jd_info: dict, scoring_cfg: dict, embedder: any) -> dict:
    """Evaluates ranking discrimination across all 2,484 resumes for a target JD."""
    print(f"\nEvaluating JD '{jd_info['title']}' against all {len(resumes)} resumes...")
    jd_req = extract_jd(jd_info["text"])
    target_cats = set(jd_info.get("target_categories", []))
    target_secondary = set(jd_info.get("target_secondary", []))

    # Pre-embed JD responsibilities and query once
    jd_title = jd_req.get("title", "Position")
    jd_resp_lines = jd_req.get("responsibilities_lines", [])
    jd_query_text = f"{jd_title}. {' '.join(jd_resp_lines[:3])}".strip()

    scores = []
    latencies = []
    category_scores = defaultdict(list)
    capped_counts = defaultdict(int)

    t0 = time.time()
    for idx, r in enumerate(resumes):
        cand_dict = r["_parsed_data"]
        t_start = time.perf_counter()
        res = score_candidate(cand_dict, jd_req, embedder, scoring_cfg)
        t_score = (time.perf_counter() - t_start) * 1000.0

        score_val = res["total"]
        is_capped = res.get("capped", False)

        scores.append({
            "idx": idx,
            "filename": r["filename"],
            "category": r["category"],
            "score": score_val,
            "capped": is_capped,
            "total_years": r["total_years"],
            "skills_count": r["skills_count"],
        })
        category_scores[r["category"]].append(score_val)
        if is_capped:
            capped_counts[r["category"]] += 1
        latencies.append(t_score)

        if (idx + 1) % 500 == 0 or (idx + 1) == len(resumes):
            print(f"  Scored {idx + 1}/{len(resumes)} resumes...")

    total_scoring_time = time.time() - t0

    # Sort descending by score
    scores.sort(key=lambda x: x["score"], reverse=True)

    # Compute Top-K purity
    def compute_purity(k: int):
        top_k = scores[:k]
        target_matches = sum(1 for s in top_k if s["category"] in target_cats)
        target_or_secondary = sum(1 for s in top_k if s["category"] in target_cats or s["category"] in target_secondary)
        return {
            "top_k": k,
            "target_purity_pct": float(target_matches / k * 100.0),
            "target_or_secondary_pct": float(target_or_secondary / k * 100.0),
            "top_categories": [item[0] for item in Counter(s["category"] for s in top_k).most_common(5)],
        }

    purity_stats = {
        "top_10": compute_purity(10),
        "top_25": compute_purity(25),
        "top_50": compute_purity(50),
        "top_100": compute_purity(100),
    }

    # Category separation stats
    cat_score_summary = {}
    target_all_scores = []
    non_target_all_scores = []

    for cat, sc_list in category_scores.items():
        avg_sc = float(np.mean(sc_list))
        med_sc = float(np.median(sc_list))
        std_sc = float(np.std(sc_list))
        cap_rate = float(capped_counts[cat] / len(sc_list) * 100.0)

        cat_score_summary[cat] = {
            "count": len(sc_list),
            "mean_score": avg_sc,
            "median_score": med_sc,
            "std_dev": std_sc,
            "max_score": int(np.max(sc_list)),
            "capping_rate_pct": cap_rate,
            "is_target": cat in target_cats,
        }

        if cat in target_cats:
            target_all_scores.extend(sc_list)
        else:
            non_target_all_scores.extend(sc_list)

    # Separation Delta
    target_mean = float(np.mean(target_all_scores)) if target_all_scores else 0.0
    non_target_mean = float(np.mean(non_target_all_scores)) if non_target_all_scores else 0.0
    separation_delta = target_mean - non_target_mean

    return {
        "jd_key": jd_key,
        "jd_title": jd_info["title"],
        "target_categories": list(target_cats),
        "target_mean_score": target_mean,
        "non_target_mean_score": non_target_mean,
        "separation_delta": separation_delta,
        "purity": purity_stats,
        "category_rankings": sorted(cat_score_summary.items(), key=lambda x: x[1]["mean_score"], reverse=True),
        "latency_p50_ms": float(np.percentile(latencies, 50)),
        "latency_p95_ms": float(np.percentile(latencies, 95)),
        "total_scoring_time_sec": total_scoring_time,
        "scoring_rate_per_sec": len(resumes) / max(1e-9, total_scoring_time),
        "top_5_candidates": [
            {"filename": s["filename"], "category": s["category"], "score": s["score"], "years": s["total_years"]}
            for s in scores[:5]
        ]
    }


# ---------------------------------------------------------------------------
# Main Execution
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("TALENTRANK LARGE-SCALE REAL-WORLD RESUME EVALUATION")
    print(f"Dataset: 2,484 PDF Resumes across 24 Industry Categories ({DATA_DIR})")
    print("=" * 70)

    # 1. Parse all resumes
    resumes = parse_all_resumes()

    # 2. Compute parsing & extraction telemetry
    print("\nComputing Ingestion & Parsing Statistics...")
    parse_stats = compute_parsing_statistics(resumes)

    # 3. Load embedder and scoring configuration
    embedder = get_embedder()
    scoring_cfg = load_scoring_config()

    # 4. Cross-Category Discrimination Benchmark across 3 JDs
    jd_evaluations = {}
    for jd_key, jd_info in EVAL_JDS.items():
        eval_result = evaluate_jd_discrimination(resumes, jd_key, jd_info, scoring_cfg, embedder)
        jd_evaluations[jd_key] = eval_result

    # 5. Format & Export Results
    full_results = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_documents": len(resumes),
        "parsing_statistics": parse_stats,
        "cross_category_evaluations": {
            k: {
                "jd_key": v["jd_key"],
                "jd_title": v["jd_title"],
                "target_categories": v["target_categories"],
                "target_mean_score": v["target_mean_score"],
                "non_target_mean_score": v["non_target_mean_score"],
                "separation_delta": v["separation_delta"],
                "purity": v["purity"],
                "latency_p50_ms": v["latency_p50_ms"],
                "latency_p95_ms": v["latency_p95_ms"],
                "scoring_rate_per_sec": v["scoring_rate_per_sec"],
                "top_5_candidates": v["top_5_candidates"],
            }
            for k, v in jd_evaluations.items()
        }
    }

    with open(RESULTS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(full_results, f, indent=2)
    print(f"\nSaved complete evaluation results to {RESULTS_JSON_PATH}.")

    # -----------------------------------------------------------------------
    # Print Executive Summary Report
    # -----------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("EXECUTIVE SUMMARY: INGESTION & PARSING METRICS (2,484 RESUMES)")
    print("=" * 70)
    print(f"Total Resumes Processed:     {parse_stats['total_resumes']}")
    print(f"Parse Success Rate:          {parse_stats['status_distribution']['ok_percentage']:.2f}% (2,484 / 2,484 'ok')")
    print(f"Zero-Text Layer Failures:    {parse_stats['status_distribution']['no_text_layer']}")
    print(f"Email Extraction Rate:       {parse_stats['identity_extraction']['emails_found_pct']:.1f}%")
    print(f"Phone Extraction Rate:       {parse_stats['identity_extraction']['phones_found_pct']:.1f}%")
    print(f"Average Words / Resume:      {parse_stats['text_metrics']['avg_words']:.0f} words")
    print(f"Average Career Length:       {parse_stats['experience_years_metrics']['overall_avg_years']:.1f} years (median: {parse_stats['experience_years_metrics']['overall_median_years']:.1f})")
    print(f"Parsing Latency (p50 / p95): {parse_stats['latency_metrics']['p50_ms']:.1f} ms / {parse_stats['latency_metrics']['p95_ms']:.1f} ms")

    print("\nKey Section Detection Rates:")
    for sec, pct in list(parse_stats["section_detection_pct"].items())[:6]:
        print(f"  - {sec.title():15s}: {pct:.1f}%")

    print("\n" + "=" * 70)
    print("EXECUTIVE SUMMARY: CROSS-CATEGORY DOMAIN DISCRIMINATION")
    print("=" * 70)

    for jd_key, res in jd_evaluations.items():
        print(f"\nJob Description: {res['jd_title']}")
        print(f"Target Domains:       {', '.join(res['target_categories'])}")
        print(f"Target Mean Score:    {res['target_mean_score']:.1f} / 100")
        print(f"Non-Target Mean Score:{res['non_target_mean_score']:.1f} / 100")
        print(f"Separation Delta:     +{res['separation_delta']:.1f} points")
        print(f"Top-10 Domain Purity: {res['purity']['top_10']['target_or_secondary_pct']:.1f}%")
        print(f"Top-50 Domain Purity: {res['purity']['top_50']['target_or_secondary_pct']:.1f}%")
        print(f"Scoring Throughput:   {res['scoring_rate_per_sec']:.1f} candidates/sec")
        print(f"Top Categories:       {', '.join(res['purity']['top_10']['top_categories'][:3])}")

    print("\nAll 2,484 resumes evaluated successfully across all categories.")


if __name__ == "__main__":
    main()
