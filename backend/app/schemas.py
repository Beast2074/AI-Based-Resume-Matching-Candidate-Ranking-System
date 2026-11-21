"""
TalentRank Pydantic Request & Response Schemas.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, model_validator


class JobCreate(BaseModel):
    title: Optional[str] = None
    text: str = Field("", description="Raw job description text")
    raw_text: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_text_fields(cls, data: Any):
        if isinstance(data, dict):
            val = data.get("text") or data.get("raw_text") or ""
            data["text"] = val
            data["raw_text"] = val
        return data


class RequirementsUpdate(BaseModel):
    title: Optional[str] = None
    skills: List[Dict[str, Any]] = Field(default_factory=list)
    required_years: Optional[float] = None
    degree_level: Optional[int] = None


class JobResponse(BaseModel):
    model_config = {"from_attributes": True}
    id: str
    title: str
    raw_text: str
    requirements: Dict[str, Any]
    required_years: Optional[float] = None
    degree_level: int = 0
    created_at: datetime


class CandidateSummary(BaseModel):
    model_config = {"from_attributes": True}
    id: str
    job_id: str
    filename: str
    parse_status: str
    parse_warnings: List[str]
    name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    total_years: float
    skills: List[Dict[str, Any]]
    created_at: datetime


class RankingCandidateItem(BaseModel):
    rank: int
    id: str
    filename: str
    name: str
    email: Optional[str]
    phone: Optional[str]
    total_years: float
    relevant_years: float
    total: int
    skills_score: float
    semantic_score: float
    experience_score: float
    education_score: float
    must_have_coverage: float
    capped: bool
    matched_skills: List[str]
    flags: List[str]


class RankingSummary(BaseModel):
    total_candidates: int
    scored_candidates: int
    top_score: int
    median_score: float
    capped_count: int


class RankingResponse(BaseModel):
    job_id: str
    summary: RankingSummary
    candidates: List[RankingCandidateItem]


class CandidateDetailResponse(BaseModel):
    id: str
    job_id: str
    filename: str
    name: str
    email: Optional[str]
    phone: Optional[str]
    parse_status: str
    parse_warnings: List[str]
    total_years: float
    raw_text: str
    sections: Dict[str, str]
    skills: List[Dict[str, Any]]
    entries: List[Dict[str, Any]]
    education: Dict[str, Any]
    score: Optional[Dict[str, Any]] = None
    explanation: Optional[Dict[str, Any]] = None
