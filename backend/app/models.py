"""
TalentRank SQLAlchemy ORM Models.
Tables: jobs, candidates, scores, explanations.
Uses JSONB on PostgreSQL and plain JSON on SQLite.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Text,
    Float,
    Integer,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.db import Base

# Automatic dialect mapping: JSONB on Postgres, plain JSON on SQLite
JSONType = JSON().with_variant(JSONB(), "postgresql")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(255), nullable=False)
    raw_text = Column(Text, nullable=False)
    requirements = Column(JSONType, nullable=False, default=dict)
    required_years = Column(Float, nullable=True)
    degree_level = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    candidates = relationship("Candidate", back_populates="job", cascade="all, delete-orphan")
    scores = relationship("Score", back_populates="job", cascade="all, delete-orphan")


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    parse_status = Column(String(50), nullable=False, default="ok")
    parse_warnings = Column(JSONType, nullable=False, default=list)
    name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(100), nullable=True)
    total_years = Column(Float, nullable=False, default=0.0)
    skills = Column(JSONType, nullable=False, default=list)
    entries = Column(JSONType, nullable=False, default=list)
    education = Column(JSONType, nullable=False, default=dict)
    sections = Column(JSONType, nullable=False, default=dict)
    raw_text = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    job = relationship("Job", back_populates="candidates")
    score = relationship("Score", back_populates="candidate", uselist=False, cascade="all, delete-orphan")
    explanation = relationship("Explanation", back_populates="candidate", uselist=False, cascade="all, delete-orphan")


class Score(Base):
    __tablename__ = "scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(String(36), ForeignKey("candidates.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    total = Column(Integer, nullable=False)
    skills_score = Column(Float, nullable=False)
    semantic_score = Column(Float, nullable=False)
    experience_score = Column(Float, nullable=False)
    education_score = Column(Float, nullable=False)
    must_have_coverage = Column(Float, nullable=False)
    capped = Column(Boolean, nullable=False, default=False)

    candidate = relationship("Candidate", back_populates="score")
    job = relationship("Job", back_populates="scores")


class Explanation(Base):
    __tablename__ = "explanations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    candidate_id = Column(String(36), ForeignKey("candidates.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    payload = Column(JSONType, nullable=False, default=dict)

    candidate = relationship("Candidate", back_populates="explanation")
