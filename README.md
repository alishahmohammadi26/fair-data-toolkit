# fair-data-toolkit

**FAIR Data Maturity Framework for Pharmaceutical R&D**  
*From RDA indicators to agentic AI scoring*

[![CI](https://github.com/alishahmohammadi22/fair-data-toolkit/actions/workflows/ci.yml/badge.svg)](https://github.com/alishahmohammadi22/fair-data-toolkit/actions/workflows/ci.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue?logo=python&logoColor=white)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Last Commit](https://img.shields.io/github/last-commit/alishahmohammadi22/fair-data-toolkit)](https://github.com/alishahmohammadi22/fair-data-toolkit/commits/main)
[![Made with Python](https://img.shields.io/badge/Made%20with-Python-1f425f.svg?logo=python)](https://www.python.org)
[![Jupyter](https://img.shields.io/badge/Notebooks-Jupyter-orange?logo=jupyter)](https://nbviewer.org/github/alishahmohammadi22/fair-data-toolkit/tree/main/notebooks/)
[![GitHub Pages](https://img.shields.io/badge/docs-GitHub%20Pages-informational?logo=github)](https://alishahmohammadi22.github.io/fair-data-toolkit)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20274083.svg)](https://doi.org/10.5281/zenodo.20274083)
[![Vue 3](https://img.shields.io/badge/webapp-Vue%203%20%2B%20FastAPI-42b883?logo=vue.js&logoColor=white)](webapp/)
[![Podman](https://img.shields.io/badge/containers-Podman-892ca0?logo=podman&logoColor=white)](webapp/podman-compose.yml)

---

## Overview

`fair-data-toolkit` is a Python package and article series that provides a structured, measurable approach to FAIR data maturity in pharmaceutical and life sciences organisations.

It implements two complementary frameworks:

- **RDA FAIR Maturity Model (2020)** — 41 indicators across F/A/I/R with Essential / Important / Useful priority levels  
- **Pistoia Alliance FAIR Maturity Matrix (v1.1)** — 6-level (L0–L5) × 7-dimension organisational maturity model for life science organisations

The toolkit enables you to conduct a full manual FAIR assessment, score all 41 indicators, generate a gap analysis, and build a prioritised remediation roadmap.

---

## Article Series

| # | Article | Description |
|---|---------|-------------|
| 01 | [Introduction to FAIR Data Principles](notebooks/01_introduction_to_fair.ipynb) | The 15 FAIR sub-principles, FAIR vs Open, pharma context, key stakeholders |
| 02 | [RDA FAIR Maturity Model](notebooks/02_rda_fair_maturity_model.ipynb) | All 41 RDA indicators, scoring system, worked gap analysis |
| 03 | [Pistoia Alliance FAIR Maturity Matrix](notebooks/03_pistoia_fair_maturity_matrix.ipynb) | 6 levels (L0–L5) × 7 organisational dimensions; self-assessment walkthrough |
| 04 | [Manual FAIR Assessment Walkthrough](notebooks/04_manual_fair_assessment_walkthrough.ipynb) | Full assessment of a CAR-T viability dataset, export, remediation roadmap |
| 05 | [FAIR Score Calculator](notebooks/05_fair_score_calculator.ipynb) | Semi-automated scoring from Zenodo API; agentic scorer architecture sketch |

> **Coming next:** `fair_agent/` — a LangGraph + GPT agentic system that scores all 41 RDA indicators given any database REST API endpoint.

---

## Installation

```bash
pip install fair-data-toolkit
```

With notebook dependencies:

```bash
pip install "fair-data-toolkit[notebooks]"
```

From source:

```bash
git clone https://github.com/alishahmohammadi22/fair-data-toolkit.git
cd fair-data-toolkit
pip install -e ".[notebooks]"
```

---

## Quick Start

```python
from fair_toolkit import ManualFAIRAssessor, ComplianceScore

# Initialise an assessment
assessor = ManualFAIRAssessor(
    dataset_id="DS-001",
    dataset_title="CAR-T Cell Viability Assay",
    assessed_by="Ali Shahmohammadi",
)

# Score indicators using the 4-level implementation status model
assessor.score("RDA-F1-01D", ComplianceScore.NOT_BEING_CONSIDERED,
               evidence="Only internal LIMS ID, no global PID")
assessor.score("RDA-F2-01M", ComplianceScore.UNDER_CONSIDERATION,
               evidence="Basic metadata present; assay conditions missing")
assessor.score("RDA-A1.2-01D", ComplianceScore.FULLY_IMPLEMENTED,
               evidence="Azure AD OAuth 2.0 controls access")

# Generate scorecard
assessor.print_scorecard()

# Build result and analyse gaps
result = assessor.build_result()
print(f"Overall FAIR score: {result.overall_score}%")

essential_gaps = result.get_gaps(EvidenceLevel.ESSENTIAL)
for gap in essential_gaps:
    print(f"  ✗ {gap.indicator_id}: {gap.indicator_name}")
```

---

## Web Application

A full-stack web app that wraps `fair_toolkit` in a modern, user-friendly interface — designed for data stewards, scientists, and governance teams who want to run FAIR assessments without writing code.

```
┌─────────────────────────────────────────────────────────┐
│                   Browser :3000                          │
│   Vue 3 + Vite + Tailwind CSS                           │
│   • Home — assessment dashboard + new assessment form   │
│   • Assess — F / A / I / R tabbed questionnaire UI      │
│     (auto-saves every 1.2 s, per-tab progress meter)    │
│   • Results — scorecard gauges + gap analysis table     │
└────────────────────┬────────────────────────────────────┘
                     │ /api/* (nginx proxy)
┌────────────────────▼────────────────────────────────────┐
│                   FastAPI :8000                          │
│   Python 3.11 · SQLAlchemy 2.0 · psycopg2               │
│   Reuses fair_toolkit directly — no code duplication    │
│   Routes:                                               │
│     GET  /api/health                                    │
│     GET  /api/indicators/                               │
│     GET  /api/indicators/by-principle/{F|A|I|R}        │
│     POST /api/assessments/                              │
│     GET  /api/assessments/                              │
│     GET  /api/assessments/{id}                          │
│     PUT  /api/assessments/{id}/scores  (bulk upsert)   │
│     DELETE /api/assessments/{id}                        │
└────────────────────┬────────────────────────────────────┘
                     │ SQLAlchemy / psycopg2
┌────────────────────▼────────────────────────────────────┐
│                PostgreSQL 16 :5432                       │
│   Tables: assessments · indicator_scores                │
│   Health-checked before API container starts            │
└─────────────────────────────────────────────────────────┘
```

### Key Features

| Feature | Details |
|---|---|
| **38 RDA indicators** | All indicators loaded from `fair_toolkit` at runtime — single source of truth |
| **F/A/I/R tabbed UI** | Each principle on its own tab with a live completion % in the header |
| **Auto-save** | Changes debounced and persisted to PostgreSQL every 1.2 s — no Save button needed |
| **Compliance colours** | Card border and background change in real time (green = compliant, red = non-compliant, amber = partial) |
| **Collapsible guidance** | Each indicator card expands to show the full RDA question and assessment guidance |
| **Score gauges** | Animated SVG circular gauges for Overall, F, A, I, R dimensions on the Results page |
| **Essential gap list** | Results page highlights all unmet Essential-priority indicators with remediation links |
| **All scores table** | Sortable per-indicator compliance table with evidence previews |
| **REST API** | Full OpenAPI docs at `http://localhost:8080/docs` |

### Running with Podman (recommended)

```bash
git clone https://github.com/alishahmohammadi22/fair-data-toolkit.git
cd fair-data-toolkit/webapp
podman-compose up --build
```

Then open **http://localhost:3000** in your browser.

> **Docker users:** the same `podman-compose.yml` is valid `docker-compose` syntax — replace `podman-compose` with `docker compose`.

### Running locally (development)

```bash
# Terminal 1 — API
cd fair-data-toolkit
pip install -e "."
pip install -r webapp/api/requirements.txt
DATABASE_URL=postgresql://fair:fairpass@localhost:5432/fair_toolkit uvicorn webapp.api.main:app --reload --port 8080

# Terminal 2 — Frontend
cd fair-data-toolkit/webapp/frontend
npm install
npm run dev   # http://localhost:3000
```

### Webapp project structure

```
webapp/
├── podman-compose.yml          # Orchestrates db + api + frontend
├── api/
│   ├── Dockerfile              # python:3.11-slim, installs fair_toolkit + FastAPI
│   ├── requirements.txt        # fastapi, uvicorn, sqlalchemy, psycopg2-binary
│   ├── main.py                 # FastAPI app, CORS, lifespan startup
│   ├── database.py             # SQLAlchemy engine + session factory
│   ├── models.py               # Assessment + IndicatorScore ORM tables
│   ├── schemas.py              # Pydantic request/response models
│   ├── init_db.py              # create_all() called on container start
│   └── routers/
│       ├── indicators.py       # GET /api/indicators/*
│       └── assessments.py      # CRUD + bulk score upsert + _compute_scores()
└── frontend/
    ├── Dockerfile              # node:20-alpine build → nginx:alpine serve
    ├── nginx.conf              # SPA routing + /api/ proxy to FastAPI
    ├── package.json            # Vue 3.4, vue-router 4, axios, Tailwind CSS 3
    ├── vite.config.js          # Vite 5, dev proxy
    ├── tailwind.config.js      # Custom FAIR colours (F=blue, A=emerald, I=violet, R=amber)
    └── src/
        ├── main.js             # Vue app + vue-router bootstrap
        ├── App.vue             # Root layout with branded navbar
        ├── api/client.js       # Axios instance with all 7 endpoint helpers
        ├── views/
        │   ├── HomeView.vue    # Dashboard: list assessments, create new
        │   ├── AssessView.vue  # F/A/I/R tabbed questionnaire with auto-save
        │   └── ResultView.vue  # Scorecard + gap analysis + indicators table
        └── components/
            ├── IndicatorCard.vue  # Per-indicator card (dropdown + evidence + notes)
            └── ScoreGauge.vue     # Animated SVG circular score gauge
```

---

## Package Structure

```
fair_toolkit/
├── models/
│   ├── rda_indicators.py    # All 41 RDA FAIR Maturity Model indicators
│   ├── pistoia_matrix.py    # Pistoia Alliance 6-level × 7-dimension FAIR Maturity Matrix
│   └── scoring.py           # IndicatorScore, FAIRDimensionScore, FAIRAssessmentResult
└── assessors/
    └── manual_assessor.py   # ManualFAIRAssessor — interactive assessment tool
```

### Key Classes

**`ManualFAIRAssessor`**  
Full manual assessment workflow. Score indicators one by one or in batch, print a rich scorecard, and export the result.

**`FAIRAssessmentResult`**  
Container for a complete assessment. Holds dimension scores for F/A/I/R, calculates the overall score, and provides gap analysis by priority level.

**`RDA_INDICATORS`**  
List of all 41 `RDAIndicator` objects with id, principle, sub-principle, scope, priority, question, guidance, and examples.

**`PISTOIA_MATRIX`**  
List of all 42 `MatrixCell` objects (7 dimensions × 6 levels L0–L5). Each cell describes the
organisational state across FAIR data, leadership, strategy, roles, processes, knowledge, and tools.

---

## FAIR Frameworks Implemented

### RDA FAIR Maturity Model (2020)

| Dimension | Indicators | Priority breakdown |
|-----------|------------|-------------------|
| Findable | 7 | 4 Essential, 2 Important, 1 Useful |
| Accessible | 9 | 3 Essential, 4 Important, 2 Useful |
| Interoperable | 12 | 2 Essential, 6 Important, 4 Useful |
| Reusable | 13 | 3 Essential, 7 Important, 3 Useful |
| **Total** | **41** | **12 Essential, 19 Important, 10 Useful** |

Compliance levels: `Not Applicable` / `Not Assessed` / `Not Compliant` / `Partially Compliant` / `Compliant`

### Pistoia Alliance FAIR Maturity Matrix (v1.1, 2025)

An **organisational** maturity model for FAIR implementation. Structured as a **7 dimensions × 6 levels** matrix.
Descriptive, not prescriptive. Created by 20+ experts across the life science ecosystem.

| Level | Nickname | Metaphor | Key Features |
|-------|----------|----------|--------------|
| L0 | Life is unFAIR | Junkyard | No awareness; data silos; no metadata standards |
| L1 | Started the FAIR journey | Flea market | Awareness starts; first pilots; identifiers emerging |
| L2 | Getting FAIR | Street Market | Pilots in place; data cataloged; local model conformance |
| L3 | Pretty FAIR | Specialized Local Markets | Domain-level models; machine interpretation locally |
| L4 | Really FAIR | Hyper Market | FAIR pervasive; GUPRIs; cross-domain standards |
| L5 | FAIRest of them all | Digital Online Store | Aspirational; self-describing objects; ecosystem interoperability |

**7 Dimensions:** FAIR data · FAIR leadership · FAIR strategy · FAIR roles · FAIR processes · FAIR knowledge · FAIR tools & infrastructures

Source: https://pistoiaalliance.github.io/FAIRMaturityMatrix/ (CC BY 4.0)

---

## Roadmap

### Phase 1 — Manual Assessment Toolkit (this release)
- [x] All 41 RDA FAIR Maturity Model indicators as Pydantic models
- [x] Pistoia Alliance FAIR Maturity Matrix: 6 levels (L0–L5) × 7 organisational dimensions
- [x] `ManualFAIRAssessor` with Rich scorecard output
- [x] Gap analysis by priority level
- [x] 5-article Jupyter notebook series
- [x] Vue 3 + FastAPI + PostgreSQL web application (containerised with Podman/Docker)
- [x] Published to Zenodo with citable DOI (10.5281/zenodo.20274083)

### Phase 2 — Agentic FAIR Scorer (`fair_agent/`)
- [ ] `MetadataFetcherAgent` — fetches and parses metadata from any REST API
- [ ] `StructuralAssessorAgent` — auto-scores ~20 structural indicators
- [ ] `ContentAnalysisAgent` (GPT) — scores semantic/content indicators
- [ ] `ExternalVerifierAgent` — validates ontology terms via BioPortal/OLS
- [ ] `GovernanceReporterAgent` — compiles result and routes gaps for human review
- [ ] Full LangGraph pipeline — accepts any API endpoint, returns `FAIRAssessmentResult`

---

## References

- Wilkinson, M. D. et al. (2016). The FAIR Guiding Principles for scientific data management and stewardship. *Scientific Data*, 3, 160018. https://doi.org/10.1038/sdata.2016.18
- RDA FAIR Data Maturity Model Working Group (2020). FAIR Data Maturity Model: specification and guidelines. https://doi.org/10.15497/rda00050
- Pistoia Alliance FAIR Maturity Matrix (2025). https://pistoiaalliance.github.io/FAIRMaturityMatrix/ (CC BY 4.0)

---

## License

MIT License — see [LICENSE](LICENSE)

---

*Developed by Ali Shahmohammadi, Ph.D. — Takeda Pharmaceutical*

---

_Maintained on [alishahmohammadi26](https://github.com/alishahmohammadi26)._
