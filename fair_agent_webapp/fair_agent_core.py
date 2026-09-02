"""
fair_agent_core.py
──────────────────
Reusable FAIRAgent assessment logic, decoupled from any UI.
The agent calls a configurable REST API (mock or real catalog) and uses
an LLM (user-supplied key + model) to score 20 RDA FAIR indicators.

Usage:
    agent = FAIRAgent(
        api_base_url="http://localhost:9321",
        llm_provider="openai",
        llm_model="gpt-4o-mini",
        api_key="sk-...",
    )
    result = agent.run("STUDY-INV-001")

    # result["scorecard"]  → list of scored indicators
    # result["principle_scores"]  → {"F": 95.0, "A": 88.0, ...}
    # result["overall_pct"]  → 92.1
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Generator, TypedDict

import httpx
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph


# ─────────────────────────────────────────────────────────────────────────────
# Indicator Definitions
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class FAIRIndicator:
    id: str
    principle: str      # F / A / I / R
    priority: str       # essential / important / useful
    name: str
    question: str
    api_sources: list[str]
    evidence_keys: list[str]
    weight: int = 1


INDICATORS: list[FAIRIndicator] = [
    # ── Findable ──────────────────────────────────────────────────────────
    FAIRIndicator("RDA-F1-01M", "F", "essential",
        "Metadata has a persistent identifier",
        "Does the metadata record have a PID (DOI, ARK, Handle)?",
        ["metadata"], ["persistent_identifier", "global_identifier_system"], weight=3),
    FAIRIndicator("RDA-F1-01D", "F", "essential",
        "Data has a persistent identifier",
        "Does the data object itself have a globally unique PID?",
        ["metadata"], ["persistent_identifier", "dataset_id"], weight=3),
    FAIRIndicator("RDA-F2-01M", "F", "essential",
        "Rich metadata provided",
        "Does the metadata include rich descriptive attributes (assay type, conditions, organism)?",
        ["metadata", "schema"], ["title", "description", "owner", "vocabularies"], weight=3),
    FAIRIndicator("RDA-F3-01M", "F", "essential",
        "Metadata includes data identifier",
        "Does the metadata record explicitly reference the data PID?",
        ["metadata"], ["persistent_identifier", "catalog_url"], weight=3),
    FAIRIndicator("RDA-F4-01M", "F", "essential",
        "Metadata is harvestable/indexed",
        "Is the metadata registered in a searchable catalog or indexed by a discovery service?",
        ["metadata"], ["catalog_url"], weight=3),
    # ── Accessible ────────────────────────────────────────────────────────
    FAIRIndicator("RDA-A1-01M", "A", "important",
        "Metadata contains access information",
        "Does the metadata describe how to access the data, including any auth requirements?",
        ["metadata", "access"], ["access"], weight=2),
    FAIRIndicator("RDA-A1.1-01D", "A", "important",
        "Data accessible via open/free protocol",
        "Can the data be retrieved using an open, free, universally implementable protocol (HTTP/HTTPS)?",
        ["access"], ["protocol", "is_open_protocol"], weight=2),
    FAIRIndicator("RDA-A1.2-01D", "A", "useful",
        "Access protocol supports auth/authorisation",
        "If access is controlled, does the protocol support authentication and is the process documented?",
        ["access"], ["authentication", "access_request_url"], weight=1),
    FAIRIndicator("RDA-A2-01M", "A", "essential",
        "Metadata persists after data removal",
        "Is the metadata guaranteed to remain accessible even if the data is removed or embargoed?",
        ["metadata"], ["metadata_persists_without_data"], weight=3),
    # ── Interoperable ─────────────────────────────────────────────────────
    FAIRIndicator("RDA-I1-01M", "I", "important",
        "Metadata uses formal knowledge representation",
        "Is the metadata encoded in a standard format (JSON-LD, RDF, schema.org)?",
        ["metadata", "schema"], ["vocabularies", "community_standard"], weight=2),
    FAIRIndicator("RDA-I1-01D", "I", "important",
        "Data uses standardised format",
        "Is the data encoded in a community-recognised format (mzML, ISA-Tab, FASTA, SDF)?",
        ["metadata"], ["community_standard"], weight=2),
    FAIRIndicator("RDA-I2-01M", "I", "important",
        "Metadata uses FAIR vocabularies",
        "Do the vocabularies used in metadata have PIDs and are they openly accessible (OBI, ChEBI, GO)?",
        ["metadata", "schema"], ["vocabularies"], weight=2),
    FAIRIndicator("RDA-I2-01D", "I", "useful",
        "Data uses FAIR vocabularies",
        "Do controlled terms in the data files reference FAIR ontology identifiers?",
        ["records", "schema"], ["ontology"], weight=1),
    FAIRIndicator("RDA-I3-01M", "I", "important",
        "Metadata has qualified references",
        "Does the metadata include typed links to related datasets or publications?",
        ["metadata"], ["related_datasets"], weight=2),
    # ── Reusable ──────────────────────────────────────────────────────────
    FAIRIndicator("RDA-R1-01M", "R", "essential",
        "Rich metadata for reuse",
        "Does the metadata provide enough attributes for a new user to decide if the data is suitable for reuse?",
        ["metadata"], ["description", "title", "owner", "provenance"], weight=3),
    FAIRIndicator("RDA-R1.1-01M", "R", "essential",
        "Metadata includes licence",
        "Does the metadata explicitly specify a reuse licence?",
        ["metadata"], ["license"], weight=3),
    FAIRIndicator("RDA-R1.1-02M", "R", "important",
        "Metadata refers to standard licence",
        "Is the licence a recognised standard (CC BY, CC0, ODbL)?",
        ["metadata"], ["license"], weight=2),
    FAIRIndicator("RDA-R1.1-03M", "R", "important",
        "Licence is machine-readable",
        "Is the licence expressed using an SPDX identifier or machine-readable URI?",
        ["metadata"], ["license"], weight=2),
    FAIRIndicator("RDA-R1.2-01M", "R", "important",
        "Metadata includes provenance",
        "Does the metadata include provenance information using a cross-domain standard (W3C PROV, PAV)?",
        ["metadata", "lineage"], ["provenance"], weight=2),
    FAIRIndicator("RDA-R1.3-01M", "R", "essential",
        "Metadata complies with community standard",
        "Does the metadata structure comply with a recognised community standard for the domain?",
        ["metadata"], ["community_standard"], weight=3),
]


# ─────────────────────────────────────────────────────────────────────────────
# LangGraph State
# ─────────────────────────────────────────────────────────────────────────────

class FAIRAgentState(TypedDict):
    dataset_id: str
    raw_evidence: dict
    principle_assessments: dict
    scorecard: list
    sme_overrides: dict
    status: str
    messages: list


SYSTEM_PROMPT = """You are a FAIR data maturity assessor. Your job is to evaluate a dataset against
RDA FAIR Data Maturity indicators and assign a compliance score for each indicator.

Score scale (0–3):
  3 = Fully implemented
  2 = In implementation / mostly compliant
  1 = Under consideration / partial evidence
  0 = Not implemented / no evidence

For each indicator:
1. Call the relevant tool(s) to retrieve evidence
2. Analyse the evidence against the indicator criteria
3. Return a JSON array with one object per indicator:
   {"indicator_id": "...", "score": 0-3, "reasoning": "...", "evidence_summary": "..."}

Be concise and evidence-based. Do not hallucinate evidence.
Always return ONLY a valid JSON array — no prose before or after it."""


# ─────────────────────────────────────────────────────────────────────────────
# FAIRAgent Class
# ─────────────────────────────────────────────────────────────────────────────

class FAIRAgent:
    """
    Configurable FAIRAgent.  Accepts any REST catalog API base URL, any
    OpenAI-compatible LLM (key + model), and runs the full assessment.
    """

    def __init__(
        self,
        api_base_url: str,
        llm_model: str,
        api_key: str,
        llm_provider: str = "openai",
        timeout: float = 15.0,
    ):
        self.api_base_url = api_base_url.rstrip("/")
        self.timeout = timeout
        self.llm = ChatOpenAI(model=llm_model, api_key=api_key, temperature=0)
        self._tools = self._build_tools()
        self._tool_map = {t.name: t for t in self._tools}
        self._llm_with_tools = self.llm.bind_tools(self._tools)
        self._graph = self._build_graph()

    # ── API accessor ──────────────────────────────────────────────────────

    def fetch(self, endpoint: str) -> dict:
        """Call the catalog API. Raises httpx.HTTPError on failure."""
        resp = httpx.get(
            f"{self.api_base_url}/{endpoint}",
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def health_check(self) -> tuple[bool, str]:
        """Returns (ok, message) — call this before running assessment."""
        try:
            self.fetch("metadata")
            return True, "API reachable ✓"
        except httpx.ConnectError:
            return False, f"Cannot connect to {self.api_base_url}"
        except httpx.HTTPStatusError as e:
            return False, f"API returned {e.response.status_code}"
        except Exception as e:
            return False, str(e)

    # ── Tool factory (captures self.fetch in closure) ──────────────────────

    def _build_tools(self) -> list:
        fetch = self.fetch  # capture for closure

        @tool
        def check_persistent_identifier() -> dict:
            """Check whether the dataset has a globally unique PID (DOI, ARK, Handle)."""
            meta = fetch("metadata")
            return {
                "persistent_identifier": meta.get("persistent_identifier"),
                "identifier_system": meta.get("global_identifier_system"),
                "has_pid": bool(meta.get("persistent_identifier")),
            }

        @tool
        def check_rich_metadata() -> dict:
            """Check whether the metadata is rich and descriptive enough for discovery."""
            meta = fetch("metadata")
            schema = fetch("schema")
            ontology_cols = [
                c["name"] for t in schema.get("tables", [])
                for c in t["columns"] if c.get("ontology")
            ]
            return {
                "title": meta.get("title"),
                "description": meta.get("description"),
                "owner": meta.get("owner"),
                "vocabularies_used": meta.get("vocabularies", []),
                "columns_with_ontology_links": ontology_cols,
                "total_columns": sum(len(t["columns"]) for t in schema.get("tables", [])),
            }

        @tool
        def check_catalog_registration() -> dict:
            """Check whether the metadata is registered in a searchable catalog."""
            meta = fetch("metadata")
            return {
                "catalog_url": meta.get("catalog_url"),
                "is_indexed": bool(meta.get("catalog_url")),
            }

        @tool
        def check_access_protocol() -> dict:
            """Check the data access protocol and whether it is open, free, and documented."""
            access = fetch("access")
            return {
                "protocol": access.get("protocol"),
                "is_open_protocol": access.get("is_open_protocol"),
                "authentication": access.get("authentication"),
                "access_request_url": access.get("access_request_url"),
                "endpoint": access.get("endpoint"),
            }

        @tool
        def check_metadata_persistence() -> dict:
            """Check whether the metadata persists even if the data is removed."""
            meta = fetch("metadata")
            return {
                "metadata_persists_without_data": meta.get("metadata_persists_without_data"),
            }

        @tool
        def check_interoperability() -> dict:
            """Check community standards, FAIR vocabularies, and ontology use in data."""
            meta = fetch("metadata")
            schema = fetch("schema")
            records = fetch("records")
            ontology_values = any(
                str(v).startswith(("OBI:", "CLO:", "UO:", "CHEMINF:", "HGNC:", "ChEMBL:", "GO:", "CHEBI:"))
                for row in records.get("records", [])
                for v in row.values()
            )
            return {
                "community_standard": meta.get("community_standard"),
                "vocabularies": meta.get("vocabularies", []),
                "ontology_values_in_records": ontology_values,
                "related_datasets": meta.get("related_datasets", []),
            }

        @tool
        def check_license_and_reuse() -> dict:
            """Check whether the metadata includes a clear, machine-readable licence."""
            meta = fetch("metadata")
            lic = meta.get("license", {})
            return {
                "license_name": lic.get("name"),
                "license_url": lic.get("url"),
                "spdx_identifier": lic.get("spdx"),
                "machine_readable": lic.get("machine_readable"),
                "is_standard_license": lic.get("spdx") is not None,
            }

        @tool
        def check_provenance() -> dict:
            """Check whether metadata includes detailed provenance (W3C PROV, ALCOA+, audit trail)."""
            meta = fetch("metadata")
            lineage = fetch("lineage")
            return {
                "provenance_source": meta.get("provenance", {}).get("source"),
                "alcoa_compliant": meta.get("provenance", {}).get("alcoa_compliant"),
                "lineage_steps": len(lineage.get("steps", [])),
                "lineage_details": lineage.get("steps", []),
            }

        return [
            check_persistent_identifier,
            check_rich_metadata,
            check_catalog_registration,
            check_access_protocol,
            check_metadata_persistence,
            check_interoperability,
            check_license_and_reuse,
            check_provenance,
        ]

    # ── LLM tool-use loop ─────────────────────────────────────────────────

    def _assess_principle(self, principle: str) -> list[dict]:
        indicators = [i for i in INDICATORS if i.principle == principle]
        indicator_list = "\n".join(
            f"- {i.id}: {i.name} — {i.question}" for i in indicators
        )
        messages: list[Any] = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=(
                f"Please assess the following FAIR indicators for principle {principle}:\n\n"
                f"{indicator_list}\n\n"
                "Use the available tools to gather evidence, then return ONLY a JSON array "
                "with keys: indicator_id, score (0-3), reasoning, evidence_summary."
            )),
        ]

        for _ in range(12):
            response = self._llm_with_tools.invoke(messages)
            messages.append(response)
            if not response.tool_calls:
                break
            for tc in response.tool_calls:
                fn = self._tool_map.get(tc["name"])
                if fn:
                    result = fn.invoke(tc["args"])
                    messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))

        final_text = getattr(response, "content", str(response))
        try:
            s, e = final_text.find("["), final_text.rfind("]") + 1
            if s >= 0 and e > s:
                return json.loads(final_text[s:e])
        except json.JSONDecodeError:
            pass

        # Fallback
        return [
            {"indicator_id": i.id, "score": 1,
             "reasoning": "Could not parse LLM response",
             "evidence_summary": final_text[:300]}
            for i in indicators
        ]

    # ── Graph nodes ───────────────────────────────────────────────────────

    def _build_graph(self) -> Any:
        def discover(state: FAIRAgentState) -> FAIRAgentState:
            evidence = {}
            for ep in ["schema", "metadata", "records", "lineage", "access"]:
                evidence[ep] = self.fetch(ep)
            state["raw_evidence"] = evidence
            state["status"] = "assessing"
            return state

        def assess_f(state: FAIRAgentState) -> FAIRAgentState:
            state["principle_assessments"]["F"] = self._assess_principle("F")
            return state

        def assess_a(state: FAIRAgentState) -> FAIRAgentState:
            state["principle_assessments"]["A"] = self._assess_principle("A")
            return state

        def assess_i(state: FAIRAgentState) -> FAIRAgentState:
            state["principle_assessments"]["I"] = self._assess_principle("I")
            return state

        def assess_r(state: FAIRAgentState) -> FAIRAgentState:
            state["principle_assessments"]["R"] = self._assess_principle("R")
            return state

        def compile_report(state: FAIRAgentState) -> FAIRAgentState:
            scorecard = []
            for principle, items in state["principle_assessments"].items():
                for item in items:
                    ind = next((i for i in INDICATORS if i.id == item.get("indicator_id")), None)
                    scorecard.append({
                        "indicator_id":     item.get("indicator_id", "?"),
                        "principle":        principle,
                        "priority":         ind.priority if ind else "?",
                        "weight":           ind.weight if ind else 1,
                        "score":            item.get("score", 0),
                        "max_score":        3,
                        "reasoning":        item.get("reasoning", ""),
                        "evidence_summary": item.get("evidence_summary", ""),
                        "sme_approved":     False,
                        "sme_comment":      "",
                    })
            state["scorecard"] = scorecard
            state["status"] = "awaiting_sme"
            return state

        builder = StateGraph(FAIRAgentState)
        builder.add_node("discover",       discover)
        builder.add_node("assess_F",       assess_f)
        builder.add_node("assess_A",       assess_a)
        builder.add_node("assess_I",       assess_i)
        builder.add_node("assess_R",       assess_r)
        builder.add_node("compile_report", compile_report)

        builder.add_edge(START,           "discover")
        builder.add_edge("discover",      "assess_F")
        builder.add_edge("assess_F",      "assess_A")
        builder.add_edge("assess_A",      "assess_I")
        builder.add_edge("assess_I",      "assess_R")
        builder.add_edge("assess_R",      "compile_report")
        builder.add_edge("compile_report", END)

        return builder.compile(checkpointer=MemorySaver())

    # ── Streaming run ─────────────────────────────────────────────────────

    def stream(self, dataset_id: str, thread_id: str = "run-001") -> Generator:
        """
        Yield (node_name, state_updates) tuples as the graph executes.
        Normalises LangGraph 1.x dict output {node: updates} into (node, updates) tuples
        so callers can always do: for node_name, state in agent.stream(dataset_id)
        """
        initial: FAIRAgentState = {
            "dataset_id": dataset_id,
            "raw_evidence": {},
            "principle_assessments": {},
            "scorecard": [],
            "sme_overrides": {},
            "status": "starting",
            "messages": [],
        }
        config = {"configurable": {"thread_id": thread_id}}
        for item in self._graph.stream(initial, config=config):
            if isinstance(item, dict):
                for node_name, state in item.items():
                    yield (node_name, state)
            else:
                yield item

    def run(self, dataset_id: str, thread_id: str = "run-001") -> dict:
        """
        Run the full assessment synchronously.
        Returns a dict with: scorecard, principle_scores, overall_pct, raw_evidence.
        """
        final: dict = {}
        for _, state in self.stream(dataset_id, thread_id):
            final = state

        scorecard = final.get("scorecard", [])
        principle_scores: dict[str, float] = {}
        for p in "FAIR":
            sub = [r for r in scorecard if r["principle"] == p]
            if sub:
                w_score = sum(r["score"] * r["weight"] for r in sub)
                w_max   = sum(r["max_score"] * r["weight"] for r in sub)
                principle_scores[p] = round(w_score / w_max * 100, 1) if w_max else 0.0
            else:
                principle_scores[p] = 0.0

        total_w  = sum(r["score"] * r["weight"] for r in scorecard)
        total_wm = sum(r["max_score"] * r["weight"] for r in scorecard)
        overall  = round(total_w / total_wm * 100, 1) if total_wm else 0.0

        return {
            "dataset_id":       dataset_id,
            "scorecard":        scorecard,
            "principle_scores": principle_scores,
            "overall_pct":      overall,
            "raw_evidence":     final.get("raw_evidence", {}),
        }
