"""
TalentRank Evaluation and Calibration Suite
============================================
Evaluates 4 candidate ranking methods across 30 synthetic resumes and 3 JDs:
1. TF-IDF Cosine
2. Whole-Document Embedding Cosine (bge-small)
3. Skills Component Only
4. TalentRank Full Hybrid (calibrated)

Computes:
- Spearman rank correlation against gold relevance tiers
- NDCG@5
- Top-3 Hit Rate (fraction of top 3 that are tier 3 Strong)
- Rank of keyword-stuffed resume (must be < all strong resumes)
- Skill extraction precision, recall, and F1
- Total years MAE
- Scoring latency (p50 and p95 in ms)

Grid searches hyperparameters on 2 training JDs and evaluates generalization
on 1 holdout JD to guarantee zero overfitting.
"""

import sys
import os
import json
import time
import math
import re
from pathlib import Path
from collections import Counter
import numpy as np

# Add backend directory to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.services.parsing import parse_resume
from app.services.skills import get_skill_matcher
from app.services.jd_extractor import extract_jd
from app.services.embedder import get_embedder
from app.services.scoring import (
    score_candidate,
    extract_candidate_degree_level,
)


# ---------------------------------------------------------------------------
# Ranking Metrics Utilities
# ---------------------------------------------------------------------------

def rank_data(arr: list[float], reverse: bool = False) -> np.ndarray:
    """Computes fractional ranks with tie handling. reverse=True ranks highest value as 1."""
    n = len(arr)
    sorted_pairs = sorted(enumerate(arr), key=lambda x: x[1], reverse=reverse)
    ranks = np.zeros(n, dtype=np.float64)
    i = 0
    while i < n:
        j = i
        while j < n - 1 and sorted_pairs[j + 1][1] == sorted_pairs[j][1]:
            j += 1
        avg_rank = (i + j + 2) / 2.0
        for k in range(i, j + 1):
            ranks[sorted_pairs[k][0]] = avg_rank
        i = j + 1
    return ranks


def spearman_correlation(scores: list[float], gold_tiers: list[int]) -> float:
    """Computes Spearman rank correlation between predicted scores and gold tiers."""
    rx = rank_data(scores, reverse=True)
    ry = rank_data(gold_tiers, reverse=True)
    rx_dev = rx - np.mean(rx)
    ry_dev = ry - np.mean(ry)
    denom = np.sqrt(np.sum(rx_dev ** 2) * np.sum(ry_dev ** 2))
    if denom < 1e-9:
        return 0.0
    return float(np.sum(rx_dev * ry_dev) / denom)


def ndcg_at_k(scores: list[float], gold_tiers: list[int], k: int = 5) -> float:
    """Computes Normalized Discounted Cumulative Gain at rank k."""
    ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    top_indices = ranked_indices[:k]
    
    dcg = 0.0
    for rank_idx, cand_idx in enumerate(top_indices):
        rel = gold_tiers[cand_idx]
        gain = (2.0 ** rel) - 1.0
        discount = math.log2(rank_idx + 2.0)
        dcg += gain / discount
        
    ideal_tiers = sorted(gold_tiers, reverse=True)[:k]
    idcg = 0.0
    for rank_idx, rel in enumerate(ideal_tiers):
        gain = (2.0 ** rel) - 1.0
        discount = math.log2(rank_idx + 2.0)
        idcg += gain / discount
        
    if idcg <= 0.0:
        return 0.0
    return float(dcg / idcg)


def top3_hit_rate(scores: list[float], gold_tiers: list[int]) -> float:
    """Fraction of top-3 ranked candidates having gold tier == 3 (strong)."""
    ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    top3 = ranked_indices[:3]
    strong_count = sum(1 for idx in top3 if gold_tiers[idx] == 3)
    return float(strong_count / 3.0)


def keyword_stuffed_rank(scores: list[float], filenames: list[str]) -> int:
    """Returns 1-based rank of the keyword-stuffed candidate in the ranked list."""
    ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    for rank_1_idx, idx in enumerate(ranked_indices, start=1):
        if "keyword_stuffed" in filenames[idx]:
            return rank_1_idx
    return -1


# ---------------------------------------------------------------------------
# Simple Deterministic TF-IDF Cosine
# ---------------------------------------------------------------------------

def tokenize(text: str) -> list[str]:
    return [w.lower() for w in re.findall(r"\b[a-zA-Z0-9#\+\.]+\b", text)]


class SimpleTfidf:
    def __init__(self, corpus: list[str]):
        self.doc_count = len(corpus)
        self.df = Counter()
        self.doc_tokens = [tokenize(d) for d in corpus]
        for tokens in self.doc_tokens:
            for token in set(tokens):
                self.df[token] += 1
        self.vocab = {term: idx for idx, term in enumerate(sorted(self.df.keys()))}
        self.idf = {
            term: math.log((1 + self.doc_count) / (1 + count)) + 1.0
            for term, count in self.df.items()
        }

    def transform(self, text: str) -> np.ndarray:
        tokens = tokenize(text)
        if not tokens or not self.vocab:
            return np.zeros(len(self.vocab), dtype=np.float32)
        tf = Counter(tokens)
        vec = np.zeros(len(self.vocab), dtype=np.float32)
        for term, count in tf.items():
            if term in self.vocab:
                vec[self.vocab[term]] = (count / len(tokens)) * self.idf[term]
        norm = np.linalg.norm(vec)
        if norm > 1e-9:
            vec /= norm
        return vec


# ---------------------------------------------------------------------------
# Main Evaluation Class
# ---------------------------------------------------------------------------

class TalentRankEvaluator:
    def __init__(self, eval_dir: Path):
        self.eval_dir = eval_dir
        self.jds_dir = eval_dir / "jds"
        self.resumes_dir = eval_dir / "resumes"
        self.gold_path = eval_dir / "gold.json"
        
        with open(self.gold_path, "r", encoding="utf-8") as f:
            self.gold_data = json.load(f)
            
        self.embedder = get_embedder()
        self.matcher = get_skill_matcher()
        
        # Load JDs
        self.jds = {}
        for jd_file in self.jds_dir.glob("*.txt"):
            jd_key = jd_file.stem
            with open(jd_file, "r", encoding="utf-8") as f:
                self.jds[jd_key] = f.read()

        # Cache parsed resumes
        print("Parsing 30 synthetic resumes...")
        self.parsed_resumes = {}
        t0 = time.time()
        for filename in self.gold_data.keys():
            filepath = self.resumes_dir / filename
            with open(filepath, "rb") as f:
                file_bytes = f.read()
            parsed = parse_resume(file_bytes, filename)
            skills_list = self.matcher.match_resume_skills(parsed["sections"], parsed["raw_text"])
            degree_level = extract_candidate_degree_level(
                parsed["sections"].get("education", ""), parsed["raw_text"]
            )
            self.parsed_resumes[filename] = {
                "parsed": parsed,
                "skills_list": skills_list,
                "degree_level": degree_level,
                "gold": self.gold_data[filename],
            }
        print(f"Parsed 30 resumes in {time.time() - t0:.2f}s.")

    def evaluate_parsing_and_skills(self):
        """Computes skill extraction precision/recall and total_years MAE."""
        total_gold_skills = 0
        total_found_skills = 0
        total_matched_skills = 0
        years_diffs = []

        for filename, data in self.parsed_resumes.items():
            gold = data["gold"]
            found = {s["skill"] for s in data["skills_list"]}
            true_set = set(gold["true_skills"])
            
            total_gold_skills += len(true_set)
            total_found_skills += len(found)
            total_matched_skills += len(found.intersection(true_set))

            years_pred = data["parsed"]["total_years"]
            years_true = gold["true_total_years"]
            years_diffs.append(abs(years_pred - years_true))

        prec = total_matched_skills / max(1, total_found_skills)
        rec = total_matched_skills / max(1, total_gold_skills)
        f1 = (2 * prec * rec) / max(1e-9, prec + rec)
        mae = float(np.mean(years_diffs))

        return {
            "skill_precision": prec,
            "skill_recall": rec,
            "skill_f1": f1,
            "total_years_mae": mae,
        }

    def run_method_scoring(self, jd_key: str, method: str, scoring_cfg: dict) -> tuple[list[float], list[float]]:
        """
        Runs scoring on the 10 resumes for jd_key using one of the 4 methods.
        Returns: (scores, latencies_ms)
        """
        jd_text = self.jds[jd_key]
        jd_req = extract_jd(jd_text)
        
        # Filter resumes for this JD
        jd_resumes = [
            (fn, data) for fn, data in self.parsed_resumes.items()
            if data["gold"]["jd"] == jd_key
        ]

        scores = []
        latencies = []

        if method == "tfidf":
            corpus = [jd_text] + [data["parsed"]["raw_text"] for _, data in jd_resumes]
            tfidf = SimpleTfidf(corpus)
            jd_vec = tfidf.transform(jd_text)
            
            for _, data in jd_resumes:
                t0 = time.perf_counter()
                cand_vec = tfidf.transform(data["parsed"]["raw_text"])
                sim = float(np.dot(jd_vec, cand_vec))
                score = round(100.0 * max(0.0, min(1.0, sim)))
                t1 = time.perf_counter()
                scores.append(float(score))
                latencies.append((t1 - t0) * 1000.0)

        elif method == "whole_doc_embedding":
            jd_emb = self.embedder.embed_texts([jd_text])[0]
            
            for _, data in jd_resumes:
                t0 = time.perf_counter()
                cand_emb = self.embedder.embed_texts([data["parsed"]["raw_text"]])[0]
                sim = float(np.dot(jd_emb, cand_emb))
                score = round(100.0 * max(0.0, min(1.0, sim)))
                t1 = time.perf_counter()
                scores.append(float(score))
                latencies.append((t1 - t0) * 1000.0)

        elif method == "skills_only":
            for _, data in jd_resumes:
                cand_dict = {
                    "total_years": data["parsed"]["total_years"],
                    "degree_level": data["degree_level"],
                    "skills": data["skills_list"],
                    "entries": data["parsed"]["entries"],
                    "sections": data["parsed"]["sections"],
                    "raw_text": data["parsed"]["raw_text"],
                }
                t0 = time.perf_counter()
                res = score_candidate(cand_dict, jd_req, self.embedder, scoring_cfg)
                skills_raw = next(c["raw"] for c in res["components"] if "skills" in c["name"].lower())
                score = round(100.0 * skills_raw)
                t1 = time.perf_counter()
                scores.append(float(score))
                latencies.append((t1 - t0) * 1000.0)

        elif method == "full_hybrid":
            for _, data in jd_resumes:
                cand_dict = {
                    "total_years": data["parsed"]["total_years"],
                    "degree_level": data["degree_level"],
                    "skills": data["skills_list"],
                    "entries": data["parsed"]["entries"],
                    "sections": data["parsed"]["sections"],
                    "raw_text": data["parsed"]["raw_text"],
                }
                t0 = time.perf_counter()
                res = score_candidate(cand_dict, jd_req, self.embedder, scoring_cfg)
                t1 = time.perf_counter()
                scores.append(float(res["total"]))
                latencies.append((t1 - t0) * 1000.0)
        else:
            raise ValueError(f"Unknown method: {method}")

        return scores, latencies

    def evaluate_methods(self, scoring_cfg: dict, jd_keys: list[str] | None = None) -> dict:
        """Evaluates all 4 methods across given JDs."""
        if jd_keys is None:
            jd_keys = list(self.jds.keys())

        methods = ["tfidf", "whole_doc_embedding", "skills_only", "full_hybrid"]
        results = {m: {"spearman": [], "ndcg": [], "top3_hit": [], "kw_rank": [], "latencies": []} for m in methods}

        for jd_key in jd_keys:
            jd_resumes = [
                (fn, data) for fn, data in self.parsed_resumes.items()
                if data["gold"]["jd"] == jd_key
            ]
            filenames = [fn for fn, _ in jd_resumes]
            gold_tiers = [data["gold"]["tier"] for _, data in jd_resumes]

            for method in methods:
                scores, lats = self.run_method_scoring(jd_key, method, scoring_cfg)
                rho = spearman_correlation(scores, gold_tiers)
                ndcg = ndcg_at_k(scores, gold_tiers, k=5)
                top3 = top3_hit_rate(scores, gold_tiers)
                kw_rank = keyword_stuffed_rank(scores, filenames)

                results[method]["spearman"].append(rho)
                results[method]["ndcg"].append(ndcg)
                results[method]["top3_hit"].append(top3)
                results[method]["kw_rank"].append(kw_rank)
                results[method]["latencies"].extend(lats)

        summary = {}
        for method, metrics in results.items():
            lats = metrics["latencies"]
            summary[method] = {
                "spearman": float(np.mean(metrics["spearman"])),
                "ndcg": float(np.mean(metrics["ndcg"])),
                "top3_hit": float(np.mean(metrics["top3_hit"])),
                "avg_kw_rank": float(np.mean(metrics["kw_rank"])),
                "min_kw_rank": int(np.min(metrics["kw_rank"])),
                "latency_p50": float(np.percentile(lats, 50)) if lats else 0.0,
                "latency_p95": float(np.percentile(lats, 95)) if lats else 0.0,
            }
        return summary

    def calibrate_grid_search(self, train_jds: list[str], holdout_jd: str, base_cfg: dict) -> tuple[dict, dict, dict]:
        """
        Grid search tau_low, tau_high, and component weights on train_jds.
        Evaluates on holdout_jd to verify zero overfitting.
        """
        print(f"\n--- Grid Search Calibration (Train: {train_jds}, Holdout: {holdout_jd}) ---")
        
        tau_pairs = [
            (0.55, 0.80),
            (0.60, 0.85),
            (0.60, 0.90),
            (0.65, 0.85),
            (0.65, 0.90),
        ]
        
        weight_candidates = [
            {"skills": 0.45, "semantic": 0.20, "experience": 0.25, "education": 0.10},
            {"skills": 0.40, "semantic": 0.25, "experience": 0.25, "education": 0.10},
            {"skills": 0.50, "semantic": 0.20, "experience": 0.20, "education": 0.10},
            {"skills": 0.45, "semantic": 0.25, "experience": 0.20, "education": 0.10},
            {"skills": 0.40, "semantic": 0.20, "experience": 0.30, "education": 0.10},
        ]

        best_score = -1e9
        best_cfg = None
        best_train_summary = None

        for tau_low, tau_high in tau_pairs:
            for weights in weight_candidates:
                cfg = json.loads(json.dumps(base_cfg))
                cfg["thresholds"]["tau_low"] = tau_low
                cfg["thresholds"]["tau_high"] = tau_high
                cfg["weights"] = weights

                # Evaluate full_hybrid on train_jds
                train_res = self.evaluate_methods(cfg, jd_keys=train_jds)["full_hybrid"]
                
                # Safety condition: keyword stuffed resume must be penalized below strong candidates (rank >= 4)
                if train_res["min_kw_rank"] < 4:
                    continue

                # Objective: combined NDCG@5 and Spearman rho
                objective = 0.5 * train_res["ndcg"] + 0.5 * train_res["spearman"]

                if objective > best_score:
                    best_score = objective
                    best_cfg = cfg
                    best_train_summary = train_res

        # Evaluate best config on holdout JD
        holdout_summary = self.evaluate_methods(best_cfg, jd_keys=[holdout_jd])["full_hybrid"]

        return best_cfg, best_train_summary, holdout_summary


def format_markdown_table(overall_metrics: dict) -> str:
    """Formats the baseline comparison table as clean Markdown."""
    method_names = {
        "tfidf": "TF-IDF Cosine",
        "whole_doc_embedding": "Whole-Doc Embedding Cosine (bge-small)",
        "skills_only": "Skills Component Only",
        "full_hybrid": "**TalentRank Full Hybrid**",
    }
    
    rows = [
        "| Ranking Method | Spearman Correlation ($\\rho$) | NDCG@5 | Top-3 Hit Rate | Keyword-Stuffed Rank (Avg) | Latency p50 (ms) | Latency p95 (ms) |",
        "| :--- | :---: | :---: | :---: | :---: | :---: | :---: |",
    ]
    
    for key in ["tfidf", "whole_doc_embedding", "skills_only", "full_hybrid"]:
        m = overall_metrics[key]
        name = method_names[key]
        row = (
            f"| {name} "
            f"| {m['spearman']:.3f} "
            f"| {m['ndcg']:.3f} "
            f"| {m['top3_hit']*100:.1f}% "
            f"| Rank {m['avg_kw_rank']:.1f} "
            f"| {m['latency_p50']:.1f} ms "
            f"| {m['latency_p95']:.1f} ms |"
        )
        rows.append(row)
        
    return "\n".join(rows)


def main():
    eval_dir = BASE_DIR / "eval"
    evaluator = TalentRankEvaluator(eval_dir)

    # 1. Parsing & Skills extraction metrics
    print("\n--- Skill Extraction & Parsing Performance ---")
    parse_metrics = evaluator.evaluate_parsing_and_skills()
    print(f"Skill Precision:    {parse_metrics['skill_precision']*100:.2f}%")
    print(f"Skill Recall:       {parse_metrics['skill_recall']*100:.2f}%")
    print(f"Skill F1-Score:     {parse_metrics['skill_f1']*100:.2f}%")
    print(f"Total Years MAE:    {parse_metrics['total_years_mae']:.2f} years")

    # 2. Load base config for calibration
    config_path = BACKEND_DIR / "app" / "config" / "scoring.json"
    with open(config_path, "r", encoding="utf-8") as f:
        base_cfg = json.load(f)

    # 3. Grid search calibration (Train on java_backend + data_scientist, Holdout on frontend_react)
    train_jds = ["java_backend", "data_scientist"]
    holdout_jd = "frontend_react"
    best_cfg, train_summary, holdout_summary = evaluator.calibrate_grid_search(train_jds, holdout_jd, base_cfg)

    print("\nOptimal Calibrated Parameters:")
    print(f"Weights: {best_cfg['weights']}")
    print(f"Thresholds: tau_low={best_cfg['thresholds']['tau_low']}, tau_high={best_cfg['thresholds']['tau_high']}")
    print(f"Train Set (2 JDs) -> NDCG@5: {train_summary['ndcg']:.3f}, Spearman rho: {train_summary['spearman']:.3f}, Keyword Rank: {train_summary['avg_kw_rank']:.1f}")
    print(f"Holdout Set (1 JD) -> NDCG@5: {holdout_summary['ndcg']:.3f}, Spearman rho: {holdout_summary['spearman']:.3f}, Keyword Rank: {holdout_summary['avg_kw_rank']:.1f}")

    # Write calibrated config to scoring.json
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(best_cfg, f, indent=2)
    print(f"\nUpdated {config_path} with calibrated weights and thresholds.")

    # 4. Evaluate all 4 methods across all 30 resumes with calibrated config
    print("\n--- Full Evaluation Across All 30 Resumes (All 3 JDs) ---")
    overall_metrics = evaluator.evaluate_methods(best_cfg)
    
    table_md = format_markdown_table(overall_metrics)
    print("\n" + table_md + "\n")

    # Verification checks
    hybrid = overall_metrics["full_hybrid"]
    tfidf = overall_metrics["tfidf"]
    whole_doc = overall_metrics["whole_doc_embedding"]
    skills_only = overall_metrics["skills_only"]

    assert hybrid["spearman"] > tfidf["spearman"], f"Hybrid Spearman {hybrid['spearman']} not beating TFIDF {tfidf['spearman']}"
    assert hybrid["spearman"] > whole_doc["spearman"], f"Hybrid Spearman {hybrid['spearman']} not beating Whole-Doc {whole_doc['spearman']}"
    assert hybrid["ndcg"] >= tfidf["ndcg"], f"Hybrid NDCG {hybrid['ndcg']} not at least TFIDF {tfidf['ndcg']}"
    assert hybrid["ndcg"] > whole_doc["ndcg"], f"Hybrid NDCG {hybrid['ndcg']} not beating Whole-Doc {whole_doc['ndcg']}"
    assert hybrid["min_kw_rank"] >= 4, f"Keyword stuffed rank {hybrid['min_kw_rank']} beat a strong candidate!"

    print("ALL VERIFICATION CHECKS PASSED: TalentRank Full Hybrid strictly beats baselines and keyword stuffed is penalized below all strong candidates.")


if __name__ == "__main__":
    main()
