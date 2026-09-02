from datetime import datetime
from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, String, Text,
)
from sqlalchemy.orm import relationship
from database import Base


class Assessment(Base):
    __tablename__ = "assessments"

    id              = Column(String, primary_key=True)
    dataset_id      = Column(String, nullable=False)
    catalog_url     = Column(String, nullable=False)
    llm_model       = Column(String, nullable=False, default="gpt-4o-mini")
    assessed_by     = Column(String, nullable=True)
    notes           = Column(Text, nullable=True)

    # lifecycle
    status          = Column(String, default="pending")   # pending/running/complete/error
    error_message   = Column(Text, nullable=True)

    # SME review
    sme_review_status = Column(String, default="not_started")  # not_started/in_progress/approved
    sme_approved_by   = Column(String, nullable=True)

    # Computed scores (stored after agent run, recomputed after SME overrides)
    overall_score   = Column(Float, nullable=True)
    f_score         = Column(Float, nullable=True)
    a_score         = Column(Float, nullable=True)
    i_score         = Column(Float, nullable=True)
    r_score         = Column(Float, nullable=True)

    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    scores = relationship(
        "IndicatorScore",
        back_populates="assessment",
        cascade="all, delete-orphan",
        order_by="IndicatorScore.indicator_id",
    )


class IndicatorScore(Base):
    __tablename__ = "indicator_scores"

    id                   = Column(String, primary_key=True)
    assessment_id        = Column(String, ForeignKey("assessments.id"), nullable=False)

    indicator_id         = Column(String, nullable=False)
    principle            = Column(String, nullable=False)   # F/A/I/R
    indicator_name       = Column(String, nullable=False)
    priority             = Column(String, nullable=False)   # essential/important/useful
    weight               = Column(Integer, default=1)

    # Agent output
    auto_score           = Column(Integer, nullable=False)
    auto_reasoning       = Column(Text, nullable=True)
    auto_evidence_summary = Column(Text, nullable=True)

    # SME overrides
    sme_score            = Column(Integer, nullable=True)   # None = use auto_score
    sme_notes            = Column(Text, nullable=True)
    sme_approved         = Column(Boolean, default=False)

    updated_at           = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    assessment = relationship("Assessment", back_populates="scores")
