from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class AssessmentCreate(BaseModel):
    dataset_id:  str
    catalog_url: str
    llm_model:   str = "gpt-4o-mini"
    assessed_by: Optional[str] = None
    notes:       Optional[str] = None


class RunRequest(BaseModel):
    api_key: str


class SmeOverride(BaseModel):
    indicator_id: str
    sme_score:    Optional[int] = None   # None = keep agent score
    sme_notes:    Optional[str] = None
    sme_approved: bool = False


class SmeReviewIn(BaseModel):
    overrides:     list[SmeOverride]
    approved_by:   Optional[str] = None
    mark_approved: bool = False


class IndicatorScoreOut(BaseModel):
    indicator_id:          str
    principle:             str
    indicator_name:        str
    priority:              str
    weight:                int
    auto_score:            int
    auto_reasoning:        Optional[str]
    auto_evidence_summary: Optional[str]
    sme_score:             Optional[int]
    sme_notes:             Optional[str]
    sme_approved:          bool
    final_score:           int

    model_config = {"from_attributes": True}


class AssessmentOut(BaseModel):
    id:                str
    dataset_id:        str
    catalog_url:       str
    llm_model:         str
    assessed_by:       Optional[str]
    notes:             Optional[str]
    status:            str
    error_message:     Optional[str]
    sme_review_status: str
    sme_approved_by:   Optional[str]
    overall_score:     Optional[float]
    f_score:           Optional[float]
    a_score:           Optional[float]
    i_score:           Optional[float]
    r_score:           Optional[float]
    created_at:        datetime
    updated_at:        datetime
    scores:            list[IndicatorScoreOut] = []

    model_config = {"from_attributes": True}
