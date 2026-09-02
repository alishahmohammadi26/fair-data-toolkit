"""
app.py — FAIR Studio OSS
─────────────────────────
Hugging Face Spaces / Streamlit entry point.

Run locally:
    streamlit run app.py

Three tabs:
  🚀 Demo        — instant FAIR score for three built-in pharma datasets (no config needed)
  📋 Upload       — score your own dataset by uploading a JSON metadata file
  🤖 Agent Mode   — full LangGraph agent (requires OpenAI API key)
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ── Make sure `fair_toolkit` is importable when running from repo root ────────
sys.path.insert(0, str(Path(__file__).parent))

from fair_toolkit.assessors.rule_based_scorer import (
    METADATA_SCHEMA,
    get_metadata_template,
    score_from_metadata,
)
from fair_toolkit.models.rda_indicators import ComplianceScore, EvidenceLevel
from fair_toolkit.models.scoring import FAIRAssessmentResult

# ─────────────────────────────────────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="FAIR Studio OSS — FAIR Data Maturity Scorer",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─────────────────────────────────────────────────────────────────────────────
# Colour palette (mirrors portfolio design system)
# ─────────────────────────────────────────────────────────────────────────────

COLOURS = {
    "F": "#2563EB",   # blue
    "A": "#16A34A",   # green
    "I": "#D97706",   # amber
    "R": "#7C3AED",   # purple
    "radar_fill": "rgba(37,99,235,0.15)",
    "radar_line": "#2563EB",
}

PRINCIPLE_LABELS = {"F": "Findable", "A": "Accessible", "I": "Interoperable", "R": "Reusable"}

COMPLIANCE_EMOJI = {
    ComplianceScore.FULLY_IMPLEMENTED:    "✅ Fully implemented",
    ComplianceScore.IN_IMPLEMENTATION:    "🔄 In implementation",
    ComplianceScore.UNDER_CONSIDERATION:  "⚠️ Under consideration",
    ComplianceScore.NOT_BEING_CONSIDERED: "❌ Not being considered",
    ComplianceScore.NOT_APPLICABLE:       "➖ Not applicable",
    ComplianceScore.NOT_ASSESSED:         "❓ Not assessed",
}

PRIORITY_BADGE = {
    EvidenceLevel.ESSENTIAL:  "🔴 Essential",
    EvidenceLevel.IMPORTANT:  "🟡 Important",
    EvidenceLevel.USEFUL:     "🟢 Useful",
}

# ─────────────────────────────────────────────────────────────────────────────
# Built-in demo datasets
# ─────────────────────────────────────────────────────────────────────────────

DEMO_DATASETS: dict[str, dict] = {

    "CAR-T Cell Viability Panel (Developing FAIR — ~72%)": {
        "dataset_id": "CAR-T-VIAL-001",
        "title": "CAR-T Cell Viability Assessment — CD19 Construct Panel",
        "description": (
            "Longitudinal viability measurements for 6 CAR-T cell constructs over 14-day GMP culture. "
            "Assessed using NucleoCounter NC-200 (PI staining). "
            "Part of clinical manufacturing batch-release QC for a Phase I trial."
        ),
        "keywords": ["CAR-T", "cell viability", "CD19", "cell therapy", "GMP"],
        "creator": "Cell Therapy Platform, Takeda Pharmaceuticals",
        "date_created": "2024-09-12",
        "date_modified": "",
        "version": "",
        # Findable — DOI registered, indexed in internal catalog
        "persistent_identifier": "https://doi.org/10.5281/zenodo.12345678",
        "identifier_system": "DOI",
        "catalog_indexed": True,
        "catalog_url": "https://datacatalog.example.org/datasets/CAR-T-VIAL-001",
        "metadata_schema": "DataCite",
        # Accessible — HTTPS with API-key auth; no tombstone policy yet
        "access_protocol": "HTTPS",
        "access_authentication": "API-key",
        "access_request_documented": True,
        "metadata_license_open": True,
        "metadata_persists_if_data_removed": False,
        # Interoperable — CSV, 2 vocabularies, no formal metadata format yet
        "data_format": "CSV",
        "format_is_open": True,
        "metadata_format": None,
        "controlled_vocabularies": ["OBI", "CLO"],
        "vocab_has_pids": False,
        "community_standard": None,
        "community_standard_for_data": False,
        # Links — links to publications but no PIDs or code
        "links_to_related_data": False,
        "links_to_publications": True,
        "links_to_code": False,
        "links_use_pids": False,
        # License — CC-BY-4.0 but not machine-readable yet
        "license_spdx": "CC-BY-4.0",
        "license_machine_readable": False,
        # Provenance — ALCOA-compliant ELN but no formal provenance standard
        "provenance_documented": True,
        "provenance_standard": None,
        "alcoa_compliant": True,
        # Quality
        "quality_criteria_documented": True,
        "data_meets_community_format_std": False,
    },

    "Open Genomics Cohort (Best Practice FAIR — ~98%)": {
        "dataset_id": "GENOMICS-COHORT-042",
        "title": "Whole-Genome Sequencing — Phase III Oncology Cohort",
        "description": (
            "WGS data (30× coverage) for 842 de-identified patients enrolled in a Phase III oncology trial. "
            "Processed with GATK 4.3 haplotype calling. Variants annotated against dbSNP 155 and ClinVar. "
            "Data deposited to EGA under managed access."
        ),
        "keywords": ["whole-genome sequencing", "WGS", "oncology", "clinical trial", "SNP", "GATK"],
        "creator": "Oncology Genomics Consortium — Data Coordinating Center",
        "date_created": "2023-11-01",
        "date_modified": "2024-06-15",
        "version": "2.1.0",
        # Findable
        "persistent_identifier": "https://doi.org/10.12688/open.genomics.042",
        "identifier_system": "DOI",
        "catalog_indexed": True,
        "catalog_url": "https://ega-archive.org/datasets/EGAD00001012345",
        "metadata_schema": "DataCite",
        # Accessible
        "access_protocol": "HTTPS",
        "access_authentication": "OAuth2",
        "access_request_documented": True,
        "metadata_license_open": True,
        "metadata_persists_if_data_removed": True,
        # Interoperable
        "data_format": "VCF",
        "format_is_open": True,
        "metadata_format": "JSON-LD",
        "controlled_vocabularies": ["SO", "HPO", "OMIM", "SNOMED CT", "NCBITaxon", "EFO"],
        "vocab_has_pids": True,
        "community_standard": "BIDS",
        "community_standard_for_data": True,
        # Links
        "links_to_related_data": True,
        "links_to_publications": True,
        "links_to_code": True,
        "links_use_pids": True,
        # License
        "license_spdx": "CC0-1.0",
        "license_machine_readable": True,
        # Provenance
        "provenance_documented": True,
        "provenance_standard": "PROV-O",
        "alcoa_compliant": True,
        # Quality
        "quality_criteria_documented": True,
        "data_meets_community_format_std": True,
    },

    "Legacy ELN Export — Compound Screening (Early Stage FAIR — ~11%)": {
        "dataset_id": "ELN-EXPORT-2019-Q3",
        "title": "Compound Screening Results Q3 2019",
        "description": "Export from legacy ELN. IC50 values for compound series.",
        "keywords": [],
        "creator": "",
        "date_created": "",
        "date_modified": "",
        "version": "",
        # Findable
        "persistent_identifier": None,
        "identifier_system": None,
        "catalog_indexed": False,
        "catalog_url": None,
        "metadata_schema": None,
        # Accessible
        "access_protocol": "HTTPS",
        "access_authentication": "IP-restricted",
        "access_request_documented": False,
        "metadata_license_open": False,
        "metadata_persists_if_data_removed": False,
        # Interoperable
        "data_format": "XLSX",
        "format_is_open": False,
        "metadata_format": None,
        "controlled_vocabularies": [],
        "vocab_has_pids": False,
        "community_standard": None,
        "community_standard_for_data": False,
        # Links
        "links_to_related_data": False,
        "links_to_publications": False,
        "links_to_code": False,
        "links_use_pids": False,
        # License
        "license_spdx": None,
        "license_machine_readable": False,
        # Provenance
        "provenance_documented": False,
        "provenance_standard": None,
        "alcoa_compliant": False,
        # Quality
        "quality_criteria_documented": False,
        "data_meets_community_format_std": False,
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# Visualisation helpers
# ─────────────────────────────────────────────────────────────────────────────

def _radar_chart(dim_scores: dict[str, float], overall: float, title: str) -> go.Figure:
    cats = [PRINCIPLE_LABELS[p] for p in "FAIR"]
    vals = [dim_scores.get(p, 0.0) for p in "FAIR"]
    vals_closed = vals + [vals[0]]
    cats_closed  = cats  + [cats[0]]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=vals_closed,
        theta=cats_closed,
        fill="toself",
        fillcolor=COLOURS["radar_fill"],
        line=dict(color=COLOURS["radar_line"], width=2.5),
        marker=dict(size=9, color=COLOURS["radar_line"]),
        name="FAIR Score",
    ))
    fig.update_layout(
        polar=dict(
            radialaxis=dict(range=[0, 100], ticksuffix="%", gridcolor="#E5E7EB", tickfont=dict(size=11)),
            angularaxis=dict(gridcolor="#E5E7EB", tickfont=dict(size=13)),
        ),
        title=dict(
            text=f"<b>{title}</b><br><sup>Overall FAIR score: <b>{overall:.1f}%</b></sup>",
            font=dict(size=14),
            x=0.5,
        ),
        margin=dict(t=90, b=30, l=40, r=40),
        paper_bgcolor="white",
        showlegend=False,
        height=420,
    )
    return fig


def _score_color(pct: float) -> str:
    if pct >= 80:
        return "#16A34A"  # green
    if pct >= 55:
        return "#D97706"  # amber
    return "#DC2626"      # red


def _metric_card(label: str, pct: float, color: str, n_indicators: int) -> None:
    st.markdown(
        f"""
        <div style="border:1px solid {color}30; border-radius:10px; padding:16px 12px;
                    background:{color}08; text-align:center;">
            <div style="font-size:11px; font-weight:600; color:{color}; text-transform:uppercase;
                        letter-spacing:.08em; margin-bottom:4px;">{label}</div>
            <div style="font-size:34px; font-weight:700; color:{color};">{pct:.0f}%</div>
            <div style="font-size:11px; color:#6B7280; margin-top:2px;">{n_indicators} indicators</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _overall_badge(overall: float) -> None:
    color = _score_color(overall)
    label = "Excellent" if overall >= 80 else ("Developing" if overall >= 55 else "Early Stage")
    st.markdown(
        f"""
        <div style="text-align:center; padding:28px 0 20px;">
            <div style="font-size:13px; color:#6B7280; letter-spacing:.08em; text-transform:uppercase;">
                Overall FAIR Maturity
            </div>
            <div style="font-size:72px; font-weight:800; color:{color}; line-height:1.1;">
                {overall:.1f}%
            </div>
            <div style="display:inline-block; background:{color}18; color:{color};
                        border-radius:20px; padding:4px 18px; font-weight:600; font-size:14px;">
                {label}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _build_scorecard_df(result: FAIRAssessmentResult) -> pd.DataFrame:
    rows = []
    for dim in (result.f_score, result.a_score, result.i_score, result.r_score):
        for s in dim.indicator_scores:
            w = s.priority_weight
            earned = s.numeric_score
            max_pts = w  # weight × 1.0
            pct = round(earned / max_pts * 100, 0) if max_pts else 0
            rows.append({
                "ID": s.indicator_id,
                "Principle": f"{s.principle.value} — {PRINCIPLE_LABELS[s.principle.value]}",
                "Priority": PRIORITY_BADGE.get(s.priority, str(s.priority)),
                "Status": COMPLIANCE_EMOJI.get(s.compliance, str(s.compliance)),
                "Score %": pct,
                "Evidence / Reasoning": s.evidence or "",
            })
    return pd.DataFrame(rows)


def _build_csv(result: FAIRAssessmentResult) -> str:
    df = _build_scorecard_df(result)
    header = pd.DataFrame([{
        "ID": "Summary",
        "Principle": result.dataset_title,
        "Priority": f"Assessed: {result.assessed_at.strftime('%Y-%m-%d')}",
        "Status": f"Overall: {result.overall_score:.1f}%",
        "Score %": "",
        "Evidence / Reasoning": (
            f"F={result.f_score.percentage:.1f}% | "
            f"A={result.a_score.percentage:.1f}% | "
            f"I={result.i_score.percentage:.1f}% | "
            f"R={result.r_score.percentage:.1f}%"
        ),
    }])
    return pd.concat([header, df], ignore_index=True).to_csv(index=False)


# ─────────────────────────────────────────────────────────────────────────────
# Shared results renderer
# ─────────────────────────────────────────────────────────────────────────────

def _render_results(result: FAIRAssessmentResult) -> None:
    dim = result.dimension_scores  # {"F": 85.7, "A": 66.7, ...}

    # ── Overall badge ─────────────────────────────────────────────────────
    _overall_badge(result.overall_score)
    st.divider()

    # ── Four principle cards ──────────────────────────────────────────────
    cols = st.columns(4)
    for col, p in zip(cols, "FAIR"):
        pct = dim[p]
        n   = len(getattr(result, f"{p.lower()}_score").indicator_scores)
        with col:
            _metric_card(PRINCIPLE_LABELS[p], pct, COLOURS[p], n)

    st.markdown("")  # spacing

    # ── Radar + gap analysis side-by-side ─────────────────────────────────
    col_radar, col_gaps = st.columns([1, 1], gap="large")

    with col_radar:
        st.plotly_chart(
            _radar_chart(dim, result.overall_score, result.dataset_title),
            use_container_width=True,
        )

    with col_gaps:
        st.markdown("### 🔍 Priority Gaps")
        essential_gaps = result.get_gaps(EvidenceLevel.ESSENTIAL)
        important_gaps = result.get_gaps(EvidenceLevel.IMPORTANT)
        # show only gaps not already in essential
        essential_ids  = {g.indicator_id for g in essential_gaps}
        important_only = [g for g in important_gaps if g.indicator_id not in essential_ids]

        if not essential_gaps and not important_only:
            st.success("✅ No Essential or Important gaps — excellent FAIR maturity!")
        else:
            if essential_gaps:
                st.markdown("**🔴 Essential (must fix)**")
                for gap in essential_gaps[:6]:
                    with st.expander(f"{gap.indicator_id} — {gap.indicator_name}"):
                        st.write(gap.evidence or "No evidence recorded")
                        st.caption(f"Status: {COMPLIANCE_EMOJI.get(gap.compliance, str(gap.compliance))}")

            if important_only:
                st.markdown("**🟡 Important (should fix)**")
                for gap in important_only[:4]:
                    with st.expander(f"{gap.indicator_id} — {gap.indicator_name}"):
                        st.write(gap.evidence or "No evidence recorded")
                        st.caption(f"Status: {COMPLIANCE_EMOJI.get(gap.compliance, str(gap.compliance))}")

    st.divider()

    # ── Full scorecard table ──────────────────────────────────────────────
    with st.expander("📋 Full Indicator Scorecard (all 41 indicators)", expanded=False):
        df = _build_scorecard_df(result)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Score %": st.column_config.ProgressColumn(
                    "Score %", min_value=0, max_value=100, format="%.0f%%"
                ),
                "Evidence / Reasoning": st.column_config.TextColumn(
                    "Evidence / Reasoning", width="large"
                ),
            },
        )

    # ── Download ──────────────────────────────────────────────────────────
    csv_data = _build_csv(result)
    col_dl1, col_dl2, _ = st.columns([1, 1, 2])
    with col_dl1:
        st.download_button(
            label="⬇️ Download CSV report",
            data=csv_data,
            file_name=f"fair_report_{result.dataset_id}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with col_dl2:
        json_data = json.dumps(result.dimension_scores | {"dataset_id": result.dataset_id,
                                                          "title": result.dataset_title}, indent=2)
        st.download_button(
            label="⬇️ Download JSON summary",
            data=json_data,
            file_name=f"fair_scores_{result.dataset_id}.json",
            mime="application/json",
            use_container_width=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# Page header
# ─────────────────────────────────────────────────────────────────────────────

st.markdown(
    """
    <div style="padding:32px 0 8px; max-width:760px;">
        <div style="font-size:12px; font-weight:600; color:#2563EB; letter-spacing:.1em;
                    text-transform:uppercase; margin-bottom:8px;">
            FAIR Studio OSS
        </div>
        <h1 style="font-size:36px; font-weight:800; margin:0 0 12px; line-height:1.2;">
            FAIR Data Maturity Scorer
        </h1>
        <p style="font-size:16px; color:#4B5563; max-width:640px; line-height:1.6; margin:0;">
            Assess any dataset against all <strong>41 RDA FAIR Maturity Indicators</strong>
            (Findable · Accessible · Interoperable · Reusable) —
            no LLM or API key required for the demo and upload modes.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown("")

# ─────────────────────────────────────────────────────────────────────────────
# Tabs
# ─────────────────────────────────────────────────────────────────────────────

tab_demo, tab_upload, tab_agent, tab_about = st.tabs([
    "🚀 Demo — Try it now",
    "📋 Upload your metadata",
    "🤖 Agent Mode (Pro)",
    "ℹ️ About / Schema",
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — DEMO
# ══════════════════════════════════════════════════════════════════════════════

with tab_demo:
    st.markdown(
        "Choose one of three built-in pharma datasets — scoring is instant. "
        "Use the **Upload** tab to score your own metadata."
    )

    dataset_name = st.radio(
        "Select a dataset:",
        options=list(DEMO_DATASETS.keys()),
        index=0,
        horizontal=False,
    )
    meta = DEMO_DATASETS[dataset_name]

    with st.expander("🔎 View raw metadata for this dataset", expanded=False):
        st.json(meta)

    if st.button("▶ Score this dataset", type="primary", use_container_width=False):
        with st.spinner("Scoring against 41 RDA indicators…"):
            result = score_from_metadata(meta)
        _render_results(result)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — UPLOAD
# ══════════════════════════════════════════════════════════════════════════════

with tab_upload:
    st.markdown(
        "Upload a JSON file that follows the FAIR Studio metadata schema. "
        "Download the template below, fill it in, and upload to score."
    )

    # Template download
    template = get_metadata_template()
    template["dataset_id"]  = "your-dataset-id"
    template["title"]       = "Your Dataset Title"
    template["description"] = "One to three sentence description of what this dataset contains."
    template["keywords"]    = ["keyword1", "keyword2"]

    col_tmpl, _ = st.columns([1, 2])
    with col_tmpl:
        st.download_button(
            label="⬇️ Download metadata template (JSON)",
            data=json.dumps(template, indent=2),
            file_name="fair_metadata_template.json",
            mime="application/json",
            use_container_width=True,
        )

    st.divider()

    uploaded = st.file_uploader(
        "Upload your metadata JSON",
        type=["json"],
        help="Must match the FAIR Studio schema. Download the template above.",
    )

    if uploaded is not None:
        try:
            user_meta = json.load(io.BytesIO(uploaded.read()))
        except json.JSONDecodeError as exc:
            st.error(f"❌ Could not parse JSON: {exc}")
            user_meta = None

        if user_meta is not None:
            with st.expander("🔎 Parsed metadata", expanded=False):
                st.json(user_meta)

            if st.button("▶ Score uploaded metadata", type="primary"):
                with st.spinner("Scoring…"):
                    result = score_from_metadata(user_meta)
                _render_results(result)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — AGENT MODE
# ══════════════════════════════════════════════════════════════════════════════

with tab_agent:
    st.markdown(
        """
        ### LangGraph Agent Mode (Pro)

        The full **FAIRAgent** uses a LangGraph + LangChain pipeline to score your data catalog
        via a REST API, with LLM reasoning for each of 20 core RDA indicators and streaming
        progress updates.

        **Requirements:** OpenAI API key · A catalog REST API endpoint (or the built-in mock server)

        Run the agent UI locally:
        ```bash
        cd fair_agent_webapp
        python mock_catalog_api.py &     # start mock catalog (optional)
        streamlit run streamlit_app.py
        ```
        Or see the [GitHub repository](https://github.com/alishahmohammadi22/fair-data-toolkit)
        for full setup instructions.
        """
    )

    st.info(
        "💡 The rule-based scorer in the **Demo** and **Upload** tabs covers all 41 RDA indicators "
        "and is sufficient for most FAIR maturity assessments. "
        "Agent mode adds LLM reasoning and direct API integration for automated pipeline use.",
        icon="ℹ️",
    )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — ABOUT / SCHEMA
# ══════════════════════════════════════════════════════════════════════════════

with tab_about:
    st.markdown(
        """
        ### About FAIR Studio OSS

        **FAIR Studio OSS** is the open-source implementation of the FAIR data maturity assessment
        framework developed as part of Pistoia Alliance FAIR Studio. It implements:

        - **RDA FAIR Data Maturity Model (2020)** — all 41 indicators across F / A / I / R,
          with Essential / Important / Useful priority levels
        - **Pistoia Alliance FAIR Maturity Matrix (v1.1)** — 6-level (L0–L5) × 7-dimension
          organisational maturity model

        **How scoring works (rule-based mode)**

        Each indicator maps to one or more metadata fields. The scorer evaluates field
        presence/content and assigns one of four compliance levels:

        | Level | Fraction of weight earned |
        |---|---|
        | ✅ Fully Implemented | 100% |
        | 🔄 In Implementation | 50% |
        | ⚠️ Under Consideration | 10% |
        | ❌ Not Being Considered | 0% |

        Priority weights: Essential = 3 pts · Important = 2 pts · Useful = 1 pt

        The dimension score (F / A / I / R) is the weighted percentage of points earned.
        The overall score is the mean of the four dimension scores.

        ---
        ### Metadata Schema Reference
        """
    )

    schema_rows = [{"Field": k, "Expected value": v} for k, v in METADATA_SCHEMA.items()]
    st.dataframe(
        pd.DataFrame(schema_rows),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown(
        """
        ---
        **References**

        - RDA FAIR Data Maturity Model Working Group (2020). *FAIR Data Maturity Model: Specification and Guidelines.*
          [doi:10.15497/rda00050](https://doi.org/10.15497/rda00050)
        - Pistoia Alliance FAIR Metrics Working Group (2023). *FAIR Maturity Matrix v1.1.*
          [pistoia-alliance.org](https://www.pistoiaalliance.org/projects/current-projects/fair-data/)
        - Wilkinson et al. (2016). *The FAIR Guiding Principles for scientific data management and stewardship.*
          Scientific Data 3, 160018. [doi:10.1038/sdata.2016.18](https://doi.org/10.1038/sdata.2016.18)

        **Source code:** [github.com/alishahmohammadi22/fair-data-toolkit](https://github.com/alishahmohammadi22/fair-data-toolkit)
        · **License:** MIT
        """
    )
