"""
assessments.py
──────────────
CRUD, agent run (SSE streaming), and SME review endpoints.
"""
from __future__ import annotations

import json
import queue
import sys
import os
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from database import SessionLocal, get_db
import models
import schemas

router = APIRouter()

# Thread-safe queues for SSE streaming: assessment_id -> queue.Queue
_run_registry: dict[str, queue.Queue] = {}

# fair_agent_core.py lives one level above this api/ directory
_CORE_DIR: str = ""   # populated by main.py after sys.path is set

NODE_MSGS: dict[str, tuple[str, int]] = {
    "discover":       ("Fetching catalog metadata & schema …", 12),
    "assess_F":       ("Assessing Findability (F) …", 28),
    "assess_A":       ("Assessing Accessibility (A) …", 45),
    "assess_I":       ("Assessing Interoperability (I) …", 62),
    "assess_R":       ("Assessing Reusability (R) …", 78),
    "compile_report": ("Compiling final scorecard …", 93),
}


# ─────────────────────────────────────────────────────────────────────────────
# Score computation helpers
# ─────────────────────────────────────────────────────────────────────────────

def _indicators():
    from fair_agent_core import INDICATORS  # noqa: PLC0415
    return INDICATORS


def _compute_from_list(scorecard: list[dict]) -> dict:
    """Compute F/A/I/R and overall percentages from a scorecard list (agent output)."""
    inds = _indicators()
    ind_map = {i.id: i for i in inds}
    result: dict[str, float] = {}
    total_possible = total_achieved = 0
    for p in "FAIR":
        p_inds = [i for i in inds if i.principle == p]
        p_poss = sum(i.weight * 3 for i in p_inds)
        p_ach = sum(
            item.get("score", 0) * ind_map[item["indicator_id"]].weight
            for item in scorecard
            if item.get("principle") == p and item.get("indicator_id") in ind_map
        )
        result[f"{p.lower()}_score"] = round(p_ach / p_poss * 100, 1) if p_poss else 0.0
        total_possible += p_poss
        total_achieved += p_ach
    result["overall_score"] = round(total_achieved / total_possible * 100, 1) if total_possible else 0.0
    return result


def _compute_from_db(scores: list) -> dict:
    """Compute F/A/I/R and overall percentages from DB IndicatorScore rows (honours SME overrides)."""
    inds = _indicators()
    ind_map = {i.id: i for i in inds}
    result: dict[str, float] = {}
    total_possible = total_achieved = 0
    for p in "FAIR":
        p_inds = [i for i in inds if i.principle == p]
        p_poss = sum(i.weight * 3 for i in p_inds)
        p_ach = 0
        for row in scores:
            if row.principle == p and row.indicator_id in ind_map:
                final = row.sme_score if row.sme_score is not None else row.auto_score
                p_ach += final * ind_map[row.indicator_id].weight
        result[f"{p.lower()}_score"] = round(p_ach / p_poss * 100, 1) if p_poss else 0.0
        total_possible += p_poss
        total_achieved += p_ach
    result["overall_score"] = round(total_achieved / total_possible * 100, 1) if total_possible else 0.0
    return result


def _serialize(a: models.Assessment) -> dict:
    if a.scores and a.status == "complete":
        computed = _compute_from_db(a.scores)
    else:
        computed = {
            "overall_score": a.overall_score,
            "f_score": a.f_score,
            "a_score": a.a_score,
            "i_score": a.i_score,
            "r_score": a.r_score,
        }
    return {
        "id":                a.id,
        "dataset_id":        a.dataset_id,
        "catalog_url":       a.catalog_url,
        "llm_model":         a.llm_model,
        "assessed_by":       a.assessed_by,
        "notes":             a.notes,
        "status":            a.status,
        "error_message":     a.error_message,
        "sme_review_status": a.sme_review_status,
        "sme_approved_by":   a.sme_approved_by,
        **computed,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
        "scores": [
            {
                "indicator_id":          s.indicator_id,
                "principle":             s.principle,
                "indicator_name":        s.indicator_name,
                "priority":              s.priority,
                "weight":                s.weight,
                "auto_score":            s.auto_score,
                "auto_reasoning":        s.auto_reasoning,
                "auto_evidence_summary": s.auto_evidence_summary,
                "sme_score":             s.sme_score,
                "sme_notes":             s.sme_notes,
                "sme_approved":          s.sme_approved,
                "final_score":           s.sme_score if s.sme_score is not None else s.auto_score,
            }
            for s in sorted(a.scores, key=lambda x: (x.principle, x.indicator_id))
        ],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Background agent runner (runs in a thread via anyio)
# ─────────────────────────────────────────────────────────────────────────────

def _run_agent_sync(
    assessment_id: str,
    dataset_id: str,
    catalog_url: str,
    api_key: str,
    llm_model: str,
    q: queue.Queue,
) -> None:
    """Blocking agent run — called in a thread pool by Starlette's BackgroundTasks."""
    from fair_agent_core import FAIRAgent, INDICATORS  # noqa: PLC0415

    db = SessionLocal()
    try:
        agent = FAIRAgent(api_base_url=catalog_url, llm_model=llm_model, api_key=api_key)

        ok, msg = agent.health_check()
        if not ok:
            q.put({"type": "error", "message": f"Catalog unreachable: {msg}"})
            db.query(models.Assessment).filter(models.Assessment.id == assessment_id).update(
                {"status": "error", "error_message": msg, "updated_at": datetime.utcnow()}
            )
            db.commit()
            return

        ind_map = {i.id: i for i in INDICATORS}
        final_state: dict = {}

        for node_name, state in agent.stream(dataset_id, thread_id=assessment_id):
            msg_text, pct = NODE_MSGS.get(node_name, (f"Running {node_name} …", 50))
            q.put({"type": "progress", "node": node_name, "message": msg_text, "pct": pct})
            final_state = state  # keep last — compile_report has the full scorecard

        scorecard: list[dict] = final_state.get("scorecard", [])
        if not scorecard:
            raise ValueError("Agent produced an empty scorecard — check catalog URL and API key.")

        # Persist indicator scores
        for item in scorecard:
            ind = ind_map.get(item.get("indicator_id", ""))
            db.add(models.IndicatorScore(
                id=str(uuid4()),
                assessment_id=assessment_id,
                indicator_id=item.get("indicator_id", "?"),
                principle=item.get("principle", "?"),
                indicator_name=ind.name if ind else item.get("indicator_id", "?"),
                priority=item.get("priority", "useful"),
                weight=int(item.get("weight", 1)),
                auto_score=int(item.get("score", 0)),
                auto_reasoning=item.get("reasoning", ""),
                auto_evidence_summary=item.get("evidence_summary", ""),
            ))

        computed = _compute_from_list(scorecard)
        row = db.query(models.Assessment).filter(models.Assessment.id == assessment_id).first()
        if row:
            row.status        = "complete"
            row.overall_score = computed["overall_score"]
            row.f_score       = computed["f_score"]
            row.a_score       = computed["a_score"]
            row.i_score       = computed["i_score"]
            row.r_score       = computed["r_score"]
            row.updated_at    = datetime.utcnow()
        db.commit()
        q.put({"type": "done"})

    except Exception as exc:  # noqa: BLE001
        q.put({"type": "error", "message": str(exc)})
        try:
            db.query(models.Assessment).filter(models.Assessment.id == assessment_id).update(
                {"status": "error", "error_message": str(exc)[:500], "updated_at": datetime.utcnow()}
            )
            db.commit()
        except Exception:  # noqa: BLE001
            pass
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# CRUD endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/", status_code=201)
def create_assessment(data: schemas.AssessmentCreate, db: Session = Depends(get_db)):
    a = models.Assessment(id=str(uuid4()), **data.model_dump())
    db.add(a)
    db.commit()
    db.refresh(a)
    return _serialize(a)


@router.get("/")
def list_assessments(db: Session = Depends(get_db)):
    rows = db.query(models.Assessment).order_by(models.Assessment.created_at.desc()).all()
    return [_serialize(a) for a in rows]


@router.get("/{assessment_id}")
def get_assessment(assessment_id: str, db: Session = Depends(get_db)):
    a = db.query(models.Assessment).filter(models.Assessment.id == assessment_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return _serialize(a)


# ─────────────────────────────────────────────────────────────────────────────
# Agent run + SSE stream
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{assessment_id}/run")
def run_assessment(
    assessment_id: str,
    body: schemas.RunRequest,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    a = db.query(models.Assessment).filter(models.Assessment.id == assessment_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if a.status == "running":
        raise HTTPException(status_code=409, detail="Assessment is already running")

    # Delete old scores if re-running
    for s in list(a.scores):
        db.delete(s)

    a.status        = "running"
    a.error_message = None
    a.updated_at    = datetime.utcnow()
    db.commit()

    q: queue.Queue = queue.Queue()
    _run_registry[assessment_id] = q

    # Starlette runs sync background tasks in a thread via anyio automatically
    background.add_task(
        _run_agent_sync,
        assessment_id, a.dataset_id, a.catalog_url, body.api_key, a.llm_model, q,
    )
    return {"status": "running"}


@router.get("/{assessment_id}/stream")
async def stream_events(assessment_id: str):
    import asyncio  # noqa: PLC0415

    async def generate():
        q = _run_registry.get(assessment_id)
        if q is None:
            yield f"data: {json.dumps({'type': 'error', 'message': 'No active run for this assessment'})}\n\n"
            return

        while True:
            try:
                event = q.get_nowait()
                yield f"data: {json.dumps(event)}\n\n"
                if event.get("type") in ("done", "error"):
                    _run_registry.pop(assessment_id, None)
                    break
            except queue.Empty:
                await asyncio.sleep(0.25)
                yield ": keepalive\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ─────────────────────────────────────────────────────────────────────────────
# SME review
# ─────────────────────────────────────────────────────────────────────────────

@router.put("/{assessment_id}/sme")
def update_sme_review(
    assessment_id: str,
    review: schemas.SmeReviewIn,
    db: Session = Depends(get_db),
):
    a = db.query(models.Assessment).filter(models.Assessment.id == assessment_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Assessment not found")
    if a.status != "complete":
        raise HTTPException(status_code=400, detail="Assessment must be complete before SME review")

    score_map = {s.indicator_id: s for s in a.scores}
    for override in review.overrides:
        row = score_map.get(override.indicator_id)
        if row:
            row.sme_score    = override.sme_score
            row.sme_notes    = override.sme_notes
            row.sme_approved = override.sme_approved
            row.updated_at   = datetime.utcnow()

    reviewed = sum(1 for s in a.scores if s.sme_approved)
    if review.mark_approved:
        a.sme_review_status = "approved"
        a.sme_approved_by   = review.approved_by
    else:
        a.sme_review_status = "in_progress" if reviewed > 0 else "not_started"

    # Recompute scores with SME overrides applied
    computed = _compute_from_db(a.scores)
    a.overall_score = computed["overall_score"]
    a.f_score       = computed["f_score"]
    a.a_score       = computed["a_score"]
    a.i_score       = computed["i_score"]
    a.r_score       = computed["r_score"]
    a.updated_at    = datetime.utcnow()
    db.commit()

    return _serialize(a)


# ─────────────────────────────────────────────────────────────────────────────
# Delete
# ─────────────────────────────────────────────────────────────────────────────

@router.delete("/{assessment_id}", status_code=204)
def delete_assessment(assessment_id: str, db: Session = Depends(get_db)):
    a = db.query(models.Assessment).filter(models.Assessment.id == assessment_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Assessment not found")
    db.delete(a)
    db.commit()
