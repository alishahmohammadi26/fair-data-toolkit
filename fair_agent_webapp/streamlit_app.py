"""
streamlit_app.py
─────────────────
FAIRAgent Web App — Streamlit multi-tab UI.

Run:
    streamlit run streamlit_app.py

Two tabs:
  1. FAIR Assessment  — point agent at any catalog API, enter LLM config, run assessment
  2. Mock Catalog     — explore the mock API, understand required fields
"""

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ─────────────────────────────────────────────────────────────────────────────
# Page config — must be first Streamlit call
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="FAIRAgent — FAIR Data Assessor",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# Lazy import agent (so the page loads even if deps are missing)
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def _import_core():
    try:
        from fair_agent_core import FAIRAgent, INDICATORS
        return FAIRAgent, INDICATORS, None
    except ImportError as e:
        return None, None, str(e)


FAIRAgentClass, INDICATORS, IMPORT_ERROR = _import_core()

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

PRINCIPLE_COLORS = {
    "F": "#3b82f6",   # blue
    "A": "#10b981",   # green
    "I": "#f59e0b",   # amber
    "R": "#ef4444",   # red
}

PRINCIPLE_LABELS = {
    "F": "Findable",
    "A": "Accessible",
    "I": "Interoperable",
    "R": "Reusable",
}

MOCK_API_URL = "http://localhost:9321"
MOCK_PROCESS_KEY = "_mock_server_proc"


def _mock_server_running() -> bool:
    try:
        httpx.get(f"{MOCK_API_URL}/", timeout=1.5)
        return True
    except Exception:
        return False


def _start_mock_server():
    """Start the mock catalog API in a subprocess."""
    api_path = Path(__file__).parent / "mock_catalog_api.py"
    proc = subprocess.Popen(
        [sys.executable, str(api_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # Give it a moment to bind
    for _ in range(8):
        time.sleep(0.5)
        if _mock_server_running():
            break
    return proc


def _radar_chart(principle_scores: dict[str, float], dataset_id: str, overall: float) -> go.Figure:
    cats = ["Findable", "Accessible", "Interoperable", "Reusable"]
    vals = [principle_scores.get(p, 0) for p in "FAIR"]
    vals_c = vals + [vals[0]]

    fig = go.Figure(go.Scatterpolar(
        r=vals_c,
        theta=cats + [cats[0]],
        fill="toself",
        fillcolor="rgba(99,102,241,0.2)",
        line=dict(color="#6366f1", width=2.5),
        marker=dict(size=9, color="#6366f1"),
        name="FAIR Score",
    ))
    fig.update_layout(
        polar=dict(
            radialaxis=dict(range=[0, 100], ticksuffix="%", gridcolor="#e5e7eb"),
            angularaxis=dict(gridcolor="#e5e7eb"),
        ),
        title=dict(
            text=f"<b>{dataset_id}</b><br><sup>Overall: {overall}%</sup>",
            font=dict(size=15),
            x=0.5,
        ),
        margin=dict(t=80, b=40, l=40, r=40),
        paper_bgcolor="white",
        showlegend=False,
        height=420,
    )
    return fig


def _scorecard_df(scorecard: list) -> pd.DataFrame:
    df = pd.DataFrame(scorecard)
    if df.empty:
        return df
    df["weighted_score"] = df["score"] * df["weight"]
    df["weighted_max"]   = df["max_score"] * df["weight"]
    df["score_%"]        = (df["weighted_score"] / df["weighted_max"] * 100).round(1)
    return df[[
        "indicator_id", "principle", "priority", "weight",
        "score", "score_%", "reasoning", "evidence_summary",
    ]]


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar — LLM Configuration
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ⚙️ LLM Configuration")
    st.caption("Your API key is never stored or logged.")

    llm_provider = st.selectbox(
        "Provider",
        ["OpenAI", "Azure OpenAI (coming soon)", "Anthropic (coming soon)"],
        index=0,
    )
    api_key = st.text_input(
        "API Key",
        type="password",
        placeholder="sk-...",
        help="Enter your OpenAI API key. It is only used in this browser session.",
    )
    llm_model = st.text_input(
        "Model",
        value="gpt-4o-mini",
        help="OpenAI model name, e.g. gpt-4o-mini, gpt-4o, gpt-4-turbo",
    )

    st.divider()
    st.markdown("## 📡 Catalog API")
    api_base_url = st.text_input(
        "Catalog API Base URL",
        value=MOCK_API_URL,
        help="Base URL of your data catalog REST API. Use the mock server for testing.",
    )
    dataset_id = st.text_input(
        "Dataset ID",
        value="STUDY-INV-001",
        help="The dataset identifier that will appear in the report.",
    )

    st.divider()
    st.markdown(
        "<small>FAIRAgent is powered by LangGraph + LangChain.<br>"
        "Assessment takes ~30–60 s per dataset.</small>",
        unsafe_allow_html=True,
    )

# ─────────────────────────────────────────────────────────────────────────────
# Main area — tabs
# ─────────────────────────────────────────────────────────────────────────────

tab1, tab2 = st.tabs(["⚖️  FAIR Assessment", "🗄️  Mock Catalog API"])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — FAIR Assessment
# ══════════════════════════════════════════════════════════════════════════════

with tab1:
    st.title("⚖️ FAIR Data Maturity Assessment")
    st.markdown(
        "Assess any dataset against the **RDA FAIR Data Maturity Indicators** (20 indicators across F / A / I / R). "
        "The agent calls your catalog API, gathers evidence, and uses the LLM to score each indicator."
    )

    if IMPORT_ERROR:
        st.error(f"❌ Could not import agent core: `{IMPORT_ERROR}`\n\n"
                 "Install dependencies: `pip install -r requirements.txt`")
        st.stop()

    # ── Pre-flight checks ────────────────────────────────────────────────

    col_check1, col_check2 = st.columns(2)
    with col_check1:
        if not api_key or api_key == "sk-...":
            st.warning("⚠️ Enter your OpenAI API key in the sidebar.")
        else:
            st.success("✅ API key provided")
    with col_check2:
        if st.button("🔌 Test catalog connection", use_container_width=True):
            try:
                r = httpx.get(f"{api_base_url.rstrip('/')}/metadata", timeout=5)
                r.raise_for_status()
                st.success(f"✅ Catalog reachable — dataset: `{r.json().get('title', '?')}`")
            except Exception as e:
                st.error(f"❌ Cannot reach catalog: {e}")

    st.divider()

    # ── Run button ────────────────────────────────────────────────────────

    run_btn = st.button(
        "▶ Run FAIR Assessment",
        type="primary",
        disabled=(not api_key or api_key == "sk-..."),
        use_container_width=True,
    )

    if run_btn:
        if not api_key or api_key == "sk-...":
            st.error("Please enter your OpenAI API key in the sidebar.")
            st.stop()

        agent = FAIRAgentClass(
            api_base_url=api_base_url,
            llm_model=llm_model,
            api_key=api_key,
        )

        # Verify connectivity first
        ok, msg = agent.health_check()
        if not ok:
            st.error(f"❌ Catalog API unreachable: {msg}\n\n"
                     "Start the mock server from the **Mock Catalog API** tab, or check your URL.")
            st.stop()

        # ── Streaming progress ─────────────────────────────────────────

        progress_bar = st.progress(0, text="Starting assessment…")
        log_container = st.empty()
        logs: list[str] = []

        NODE_LABELS = {
            "discover":       ("🔍 Fetching evidence",       15),
            "assess_F":       ("🤖 Assessing Findability",   35),
            "assess_A":       ("🤖 Assessing Accessibility", 55),
            "assess_I":       ("🤖 Assessing Interoperability", 75),
            "assess_R":       ("🤖 Assessing Reusability",   90),
            "compile_report": ("📊 Compiling scorecard",     100),
        }

        final_result = {}
        try:
            for event in agent.stream(dataset_id):
                node_name = list(event.keys())[0]
                label, pct = NODE_LABELS.get(node_name, (node_name, 50))
                progress_bar.progress(pct, text=label)
                logs.append(f"✓ {label}")
                log_container.markdown("\n".join(f"- {l}" for l in logs))

                if node_name == "compile_report":
                    state = event[node_name]
                    scorecard = state.get("scorecard", [])
                    principle_scores: dict[str, float] = {}
                    for p in "FAIR":
                        sub = [r for r in scorecard if r["principle"] == p]
                        if sub:
                            ws = sum(r["score"] * r["weight"] for r in sub)
                            wm = sum(r["max_score"] * r["weight"] for r in sub)
                            principle_scores[p] = round(ws / wm * 100, 1) if wm else 0.0
                        else:
                            principle_scores[p] = 0.0
                    total_w  = sum(r["score"] * r["weight"] for r in scorecard)
                    total_wm = sum(r["max_score"] * r["weight"] for r in scorecard)
                    overall  = round(total_w / total_wm * 100, 1) if total_wm else 0.0
                    final_result = {
                        "dataset_id": dataset_id,
                        "scorecard": scorecard,
                        "principle_scores": principle_scores,
                        "overall_pct": overall,
                    }

        except Exception as e:
            st.error(f"❌ Assessment failed: {e}")
            st.stop()

        progress_bar.empty()
        log_container.empty()

        if not final_result:
            st.warning("Assessment completed but no scorecard was generated.")
            st.stop()

        # ── Results display ────────────────────────────────────────────

        st.success(f"✅ Assessment complete — Overall FAIR score: **{final_result['overall_pct']}%**")

        col_radar, col_scores = st.columns([1, 1])

        with col_radar:
            fig = _radar_chart(
                final_result["principle_scores"],
                final_result["dataset_id"],
                final_result["overall_pct"],
            )
            st.plotly_chart(fig, use_container_width=True)

        with col_scores:
            st.markdown("### Per-Principle Scores")
            for p, label in PRINCIPLE_LABELS.items():
                score = final_result["principle_scores"].get(p, 0)
                color = PRINCIPLE_COLORS[p]
                st.markdown(
                    f"<div style='display:flex;align-items:center;margin-bottom:8px'>"
                    f"<span style='width:140px;font-weight:600;color:{color}'>{label}</span>"
                    f"<div style='flex:1;background:#f3f4f6;border-radius:6px;height:22px;margin:0 10px'>"
                    f"<div style='width:{score}%;background:{color};height:100%;border-radius:6px'></div></div>"
                    f"<span style='font-weight:700;color:{color}'>{score}%</span></div>",
                    unsafe_allow_html=True,
                )
            st.metric("Overall FAIR Score", f"{final_result['overall_pct']}%")

        # ── Scorecard table ─────────────────────────────────────────────

        st.divider()
        st.markdown("### 📋 Detailed Scorecard")

        df = _scorecard_df(final_result["scorecard"])

        # Colour-code by principle
        def _style_principle(val: str) -> str:
            return f"color: {PRINCIPLE_COLORS.get(val, '#000')};font-weight:bold"

        styled = df.style.applymap(_style_principle, subset=["principle"])
        st.dataframe(styled, use_container_width=True, height=420)

        # ── Download ────────────────────────────────────────────────────

        st.divider()
        col_dl1, col_dl2 = st.columns(2)
        with col_dl1:
            st.download_button(
                "⬇ Download CSV",
                data=df.to_csv(index=False).encode(),
                file_name=f"fair_scorecard_{dataset_id}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with col_dl2:
            st.download_button(
                "⬇ Download JSON",
                data=json.dumps(final_result, indent=2).encode(),
                file_name=f"fair_report_{dataset_id}.json",
                mime="application/json",
                use_container_width=True,
            )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Mock Catalog API
# ══════════════════════════════════════════════════════════════════════════════

with tab2:
    st.title("🗄️ Mock Catalog API")
    st.markdown(
        "A local **FastAPI** server that simulates a real data catalog + database. "
        "Use it to test the FAIRAgent and learn exactly what your real catalog must expose."
    )

    # ── Server status + start ─────────────────────────────────────────────

    col_status, col_start = st.columns([2, 1])

    with col_status:
        running = _mock_server_running()
        if running:
            st.success(f"✅ Mock server is running at **{MOCK_API_URL}**")
            st.markdown(
                f"[📖 Swagger UI]({MOCK_API_URL}/docs)  ·  "
                f"[📋 ReDoc]({MOCK_API_URL}/redoc)",
                unsafe_allow_html=False,
            )
        else:
            st.warning("⚠️  Mock server is not running.")

    with col_start:
        if st.button(
            "🚀 Start Mock Server" if not running else "🔄 Restart Server",
            use_container_width=True,
        ):
            with st.spinner("Starting mock catalog server…"):
                proc = _start_mock_server()
                if _mock_server_running():
                    st.success("Server started!")
                    st.rerun()
                else:
                    st.error("Failed to start server. Try running manually:\n"
                             "`python mock_catalog_api.py`")

    st.markdown(
        "> **Alternative**: open a terminal and run `python mock_catalog_api.py` from the "
        "`fair_agent_webapp/` directory. Then point the sidebar **Catalog API Base URL** at "
        f"`{MOCK_API_URL}`."
    )

    st.divider()

    # ── Live endpoint browser ─────────────────────────────────────────────

    st.markdown("### 🔍 Browse Endpoints Live")

    ENDPOINTS = {
        "GET /":             "Health check + endpoint list",
        "GET /catalog":      "List all datasets",
        "GET /schema":       "Database schema (tables, columns, types, ontology refs)",
        "GET /metadata":     "Full catalog metadata (PID, license, access, provenance…)",
        "GET /records":      "Sample data rows",
        "GET /lineage":      "ETL provenance chain",
        "GET /access":       "Access protocol details",
        "GET /fields-guide": "Required fields guide for real catalog integration",
    }

    selected_endpoint = st.selectbox(
        "Select an endpoint to inspect:",
        list(ENDPOINTS.keys()),
        format_func=lambda x: f"{x}  —  {ENDPOINTS[x]}",
    )

    if st.button("📥 Fetch response", use_container_width=False):
        path = selected_endpoint.split(" ")[1]
        try:
            resp = httpx.get(f"{MOCK_API_URL}{path}", timeout=5)
            st.json(resp.json())
            st.caption(f"HTTP {resp.status_code} · {resp.elapsed.total_seconds()*1000:.0f} ms")
        except Exception as e:
            st.error(f"Could not reach {MOCK_API_URL}{path}: {e}\n\nStart the mock server first.")

    st.divider()

    # ── Required fields guide ─────────────────────────────────────────────

    st.markdown("### 📋 What Your Real Catalog API Must Expose")
    st.markdown(
        "To assess your **own** dataset, your catalog API must expose these fields. "
        "Click an endpoint below to see the full required field spec."
    )

    FIELD_TABLE = {
        "Endpoint": [
            "/schema", "/metadata", "/metadata", "/metadata",
            "/metadata", "/metadata", "/metadata",
            "/records", "/lineage", "/access",
        ],
        "Field": [
            "tables[].columns[].ontology",
            "persistent_identifier",
            "license.spdx + license.machine_readable",
            "access.protocol + is_open_protocol",
            "metadata_persists_without_data",
            "vocabularies",
            "community_standard + related_datasets",
            "records[].values (ontology IRIs)",
            "steps[].actor + timestamp",
            "access_request_url",
        ],
        "FAIR Indicator(s)": [
            "I2 — Metadata uses FAIR vocabularies",
            "F1 — Persistent identifier",
            "R1.1 — Licence",
            "A1.1 — Open protocol",
            "A2 — Metadata persistence",
            "I2 — FAIR vocabularies",
            "I3, R1.3 — References, community standard",
            "I2 — Data uses FAIR vocabularies",
            "R1.2 — Provenance",
            "A1.2 — Auth/authorisation",
        ],
        "Priority": [
            "important", "essential", "essential", "important",
            "essential", "important", "important",
            "useful", "important", "useful",
        ],
    }
    st.dataframe(pd.DataFrame(FIELD_TABLE), use_container_width=True, hide_index=True)

    st.divider()

    # ── curl / httpx examples ─────────────────────────────────────────────

    st.markdown("### 🖥️ Example API Calls")
    st.code(f"""
# Health check
curl {MOCK_API_URL}/

# Get catalog metadata (most important for FAIR assessment)
curl {MOCK_API_URL}/metadata | python3 -m json.tool

# Get database schema
curl {MOCK_API_URL}/schema | python3 -m json.tool

# Get sample records (limit=3)
curl "{MOCK_API_URL}/records?limit=3"

# Get lineage / provenance
curl {MOCK_API_URL}/lineage

# Get required fields guide
curl {MOCK_API_URL}/fields-guide | python3 -m json.tool
""", language="bash")

    st.markdown("### 🐍 Python (httpx)")
    st.code(f"""
import httpx

BASE = "{MOCK_API_URL}"

metadata = httpx.get(f"{{BASE}}/metadata").json()
schema   = httpx.get(f"{{BASE}}/schema").json()
lineage  = httpx.get(f"{{BASE}}/lineage").json()

print(metadata["persistent_identifier"])   # https://doi.org/10.99999/study-inv-001
print(schema["tables"][0]["name"])         # compounds
print(len(lineage["steps"]))               # 4
""", language="python")
