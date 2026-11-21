# System Architecture & Design Decisions

This document tracks architectural choices, technical constraints, and trade-offs made during development.

## 1. Hosting Architecture
- **Decision**: The system is architected as two decoupled deployments from a single monorepo: `frontend` (React 18 + Vite SPA) and `backend` (FastAPI serverless/container function on Python 3.12).
- **Vercel Constraints**: Max uncompressed bundle size is 500 MB (safety limit is 350 MB). Max request duration is 60 seconds. Ephemeral filesystem means models must be bundled or cached deterministically.

## 2. Local Deterministic Embeddings
- **Decision**: Bundled `BAAI/bge-small-en-v1.5` ONNX model loaded via FastEmbed / ONNX Runtime without PyTorch.
- **Offline Guarantee**: Enforced `HF_HUB_OFFLINE=1` so no network requests or external API calls are made at runtime. 384-dimensional normalized embeddings are computed deterministically.

## 3. Skill Matching Engine: Regex Matcher over spaCy
- **Decision**: In Step 0 bundle size verification, the total uncompressed backend size with spaCy exceeded the 350 MB limit. In accordance with the prompt specification, spaCy was dropped in favor of a specialized regex matcher behind the `SkillMatcher` interface. This reduced bundle overhead by ~55 MB while providing exact token/word-boundary control for edge cases (C++, C#, .NET, Java vs. JavaScript, Go, R).

## 4. PyMuPDF Dependency Pinning
- **Decision**: Pinned `pymupdf>=1.24.0,<2.0.0`. Newer 2.x releases bundled experimental layout/LLM dependencies (`pymupdf4llm`, `networkx`, `tabulate`, `psutil`) adding over 70 MB of unnecessary bloat. Pinning to 1.x preserves lean, fast MuPDF C-bindings for PDF text and block extraction while respecting Vercel's bundle budget.

## 5. Hyperparameter Calibration & Holdout Generalization
- **Decision**: Calibrated scoring weights and semantic threshold hyperparameters using a 2:1 training/holdout split across job domains. Grid search tuned `tau_low` (0.55), `tau_high` (0.80), and component weights (`skills: 0.40`, `semantic: 0.25`, `experience: 0.25`, `education: 0.10`) on `java_backend` and `data_scientist`, while evaluating on `frontend_react` as an unseen holdout.
- **Result**: The calibrated parameters achieved perfect NDCG@5 (1.000) and high Spearman correlation ($\rho = 0.925$ holdout, $0.967$ train) while keeping keyword-stuffed resumes strictly below all genuine candidates (Rank 8.3 average). All calibrated weights and thresholds are stored in `backend/app/config/scoring.json`.
