"""
Candidates API Router.
Endpoints:
- GET /api/candidates/{candidate_id}: Detailed profile, score breakdown, and full explanation payload
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Candidate, Score, Explanation
from app.schemas import CandidateDetailResponse

router = APIRouter(prefix="/api/candidates", tags=["candidates"])


@router.get("/{candidate_id}", response_model=CandidateDetailResponse)
def get_candidate_detail(
    candidate_id: str,
    anonymize: bool = Query(False),
    db: Session = Depends(get_db)
):
    """
    Retrieve candidate profile, parse status, score breakdown and explanation payload.
    When anonymize=True, name, email and phone are redacted.
    """
    cand = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not cand:
        raise HTTPException(status_code=404, detail="Candidate not found.")

    score = db.query(Score).filter(Score.candidate_id == cand.id).first()
    explanation = db.query(Explanation).filter(Explanation.candidate_id == cand.id).first()

    name = cand.name or "Candidate"
    email = cand.email
    phone = cand.phone

    if anonymize:
        name = "Candidate"
        email = "candidate@anonymized.local"
        phone = "REDACTED"

    score_dict = None
    if score:
        score_dict = {
            "total": score.total,
            "skills_score": score.skills_score,
            "semantic_score": score.semantic_score,
            "experience_score": score.experience_score,
            "education_score": score.education_score,
            "must_have_coverage": score.must_have_coverage,
            "capped": score.capped,
        }

    return CandidateDetailResponse(
        id=cand.id,
        job_id=cand.job_id,
        filename=cand.filename,
        name=name,
        email=email,
        phone=phone,
        parse_status=cand.parse_status,
        parse_warnings=cand.parse_warnings or [],
        total_years=cand.total_years,
        raw_text=cand.raw_text or "",
        sections=cand.sections or {},
        skills=cand.skills or [],
        entries=cand.entries or [],
        education=cand.education or {},
        score=score_dict,
        explanation=explanation.payload if explanation else None,
    )
