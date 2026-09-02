"""
rule_based_scorer.py
────────────────────
Rule-based FAIR scorer: evaluates all 41 RDA FAIR Maturity indicators
from a structured metadata dictionary — no LLM or external API required.

Designed for:
  - Instant demo scoring in the FAIR Studio OSS Streamlit app
  - Batch assessment pipelines
  - Upload-and-score workflows (user uploads JSON metadata)

Usage:
    from fair_toolkit.assessors.rule_based_scorer import score_from_metadata

    result = score_from_metadata(metadata)
    print(result.overall_score)       # e.g. 72.5
    print(result.dimension_scores)    # {"F": 85.7, "A": 66.7, "I": 60.0, "R": 77.5, "Overall": 72.5}
    gaps = result.get_gaps()          # non-compliant Essential indicators
"""

from __future__ import annotations

from typing import Any

from fair_toolkit.models.rda_indicators import (
    EvidenceLevel,
    FAIRPrinciple,
    RDA_INDICATORS,
    ComplianceScore,
)
from fair_toolkit.models.scoring import (
    FAIRAssessmentResult,
    FAIRDimensionScore,
    IndicatorScore,
)

# ─────────────────────────────────────────────────────────────────────────────
# Type alias
# ─────────────────────────────────────────────────────────────────────────────

Meta = dict[str, Any]

# Short aliases for ComplianceScore levels
_FI  = ComplianceScore.FULLY_IMPLEMENTED
_II  = ComplianceScore.IN_IMPLEMENTATION
_UC  = ComplianceScore.UNDER_CONSIDERATION
_NBC = ComplianceScore.NOT_BEING_CONSIDERED

# ─────────────────────────────────────────────────────────────────────────────
# Reference sets used in scoring rules
# ─────────────────────────────────────────────────────────────────────────────

OPEN_ID_SYSTEMS        = {"DOI", "Handle", "ARK", "IGSN", "ORCID"}
OPEN_DATA_FORMATS      = {"CSV", "JSON", "JSON-LD", "RDF", "RDF/Turtle", "Parquet",
                           "HDF5", "VCF", "FASTQ", "NetCDF", "OWL", "TSV", "FASTA"}
FORMAL_META_FORMATS    = {"JSON-LD", "RDF", "RDF/Turtle", "OWL", "DCAT-AP"}
STRUCTURED_META_SCHEMAS = {"DataCite", "DCAT", "schema.org", "ISA-Tab",
                            "Dublin Core", "DDI", "DIF", "EML"}
OPEN_PROTOCOLS         = {"HTTPS", "HTTP", "SPARQL", "OAI-PMH", "FTP", "SFTP"}
OPEN_LICENSES          = {"CC0-1.0", "CC-BY-4.0", "CC-BY-SA-4.0", "ODbL-1.0",
                           "MIT", "Apache-2.0", "GPL-3.0-only"}
PROV_STANDARDS         = {"PROV-O", "W3C PROV", "ISO 8001", "OpenLineage", "PROV-N"}
COMMUNITY_STANDARDS    = {"ISA-Tab", "MIAME", "CDISC", "BIDS", "DataCite",
                           "EML", "DDI", "DIF", "ABCD", "MIMARKS", "MINSEQE"}

# ─────────────────────────────────────────────────────────────────────────────
# Metadata schema reference (use this as an upload template)
# ─────────────────────────────────────────────────────────────────────────────

METADATA_SCHEMA: dict[str, str] = {
    # Identity
    "dataset_id":    "string — internal or catalog identifier",
    "title":         "string — human-readable dataset title",
    "description":   "string — 1–3 sentence description of the dataset",
    "keywords":      "list[str] — controlled or free-text keywords",
    "creator":       "string — person or organisation responsible",
    "date_created":  "string — ISO 8601 date, e.g. '2024-03-15'",
    "date_modified": "string — ISO 8601 date of last update",
    "version":       "string — dataset version, e.g. '1.2.0'",
    # Findable
    "persistent_identifier":          "string | null — globally unique PID (DOI, Handle, ARK…)",
    "identifier_system":              "string | null — 'DOI' | 'Handle' | 'ARK' | 'accession' | 'UUID'",
    "catalog_indexed":                "boolean — is metadata indexed in a searchable catalog?",
    "catalog_url":                    "string | null — direct URL to catalog entry",
    "metadata_schema":                "string | null — 'DataCite' | 'DCAT' | 'schema.org' | 'ISA-Tab'",
    # Accessible
    "access_protocol":                "string | null — 'HTTPS' | 'SPARQL' | 'OAI-PMH' | 'FTP'",
    "access_authentication":          "string | null — null (open) | 'OAuth2' | 'API-key' | 'IP-restricted'",
    "access_request_documented":      "boolean — is there a documented access request process?",
    "metadata_license_open":          "boolean — is the metadata itself openly accessible?",
    "metadata_persists_if_data_removed": "boolean — does metadata remain after data deletion?",
    # Interoperable — format
    "data_format":                    "string | null — 'CSV' | 'JSON' | 'Parquet' | 'XLSX' | 'RDF' | 'VCF'…",
    "format_is_open":                 "boolean — is the data format open/non-proprietary?",
    "metadata_format":                "string | null — 'JSON-LD' | 'RDF/Turtle' | 'XML' | 'DCAT-AP'",
    # Interoperable — vocabularies
    "controlled_vocabularies":        "list[str] — ontologies/vocab used, e.g. ['OBI', 'CLO', 'ChEMBL']",
    "vocab_has_pids":                 "boolean — are vocabulary terms referenced by PIDs?",
    "community_standard":             "string | null — 'ISA-Tab' | 'MIAME' | 'CDISC' | 'BIDS' | 'DataCite'",
    "community_standard_for_data":    "boolean — does the data format follow a community standard?",
    # Links
    "links_to_related_data":          "boolean — does metadata/data link to related datasets?",
    "links_to_publications":          "boolean — does metadata link to associated publications?",
    "links_to_code":                  "boolean — does metadata link to analysis code or software?",
    "links_use_pids":                 "boolean — are outgoing links expressed as PIDs?",
    # License
    "license_spdx":                   "string | null — SPDX ID, e.g. 'CC-BY-4.0' | 'CC0-1.0' | 'MIT'",
    "license_machine_readable":       "boolean — is the license expressed in machine-readable form?",
    # Provenance
    "provenance_documented":          "boolean — is data provenance/lineage documented?",
    "provenance_standard":            "string | null — 'PROV-O' | 'W3C PROV' | 'ISO 8001'",
    "alcoa_compliant":                "boolean — is ALCOA+ traceability maintained?",
    # Quality
    "quality_criteria_documented":    "boolean — are data quality criteria documented?",
    "data_meets_community_format_std": "boolean — does data conform to community format standard?",
}


def get_metadata_template() -> Meta:
    """Return an empty metadata template dict with all expected fields and sensible defaults."""
    return {
        "dataset_id": "",
        "title": "",
        "description": "",
        "keywords": [],
        "creator": "",
        "date_created": "",
        "date_modified": "",
        "version": "",
        "persistent_identifier": None,
        "identifier_system": None,
        "catalog_indexed": False,
        "catalog_url": None,
        "metadata_schema": None,
        "access_protocol": None,
        "access_authentication": None,
        "access_request_documented": False,
        "metadata_license_open": False,
        "metadata_persists_if_data_removed": False,
        "data_format": None,
        "format_is_open": False,
        "metadata_format": None,
        "controlled_vocabularies": [],
        "vocab_has_pids": False,
        "community_standard": None,
        "community_standard_for_data": False,
        "links_to_related_data": False,
        "links_to_publications": False,
        "links_to_code": False,
        "links_use_pids": False,
        "license_spdx": None,
        "license_machine_readable": False,
        "provenance_documented": False,
        "provenance_standard": None,
        "alcoa_compliant": False,
        "quality_criteria_documented": False,
        "data_meets_community_format_std": False,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Internal scoring engine
# ─────────────────────────────────────────────────────────────────────────────

def _score_all(meta: Meta) -> dict[str, tuple[ComplianceScore, str]]:
    """
    Evaluate all 41 RDA indicators from metadata fields.
    Returns {indicator_id: (ComplianceScore, reasoning_string)}.
    """
    # ── Unpack metadata fields with safe defaults ─────────────────────────
    pid           = meta.get("persistent_identifier") or ""
    id_system     = meta.get("identifier_system") or ""
    cat_indexed   = bool(meta.get("catalog_indexed"))
    cat_url       = meta.get("catalog_url") or ""
    meta_schema   = meta.get("metadata_schema") or ""

    access_proto  = meta.get("access_protocol") or ""
    auth          = meta.get("access_authentication")   # None = open
    access_doc    = bool(meta.get("access_request_documented"))
    meta_open     = bool(meta.get("metadata_license_open"))
    meta_persists = bool(meta.get("metadata_persists_if_data_removed"))

    data_fmt      = meta.get("data_format") or ""
    fmt_open      = bool(meta.get("format_is_open"))
    meta_fmt      = meta.get("metadata_format") or ""
    vocabs        = list(meta.get("controlled_vocabularies") or [])
    vocab_pids    = bool(meta.get("vocab_has_pids"))
    comm_std      = meta.get("community_standard") or ""
    comm_std_data = bool(meta.get("community_standard_for_data"))

    links_data    = bool(meta.get("links_to_related_data"))
    links_pubs    = bool(meta.get("links_to_publications"))
    links_code    = bool(meta.get("links_to_code"))
    links_pids    = bool(meta.get("links_use_pids"))

    lic_spdx      = meta.get("license_spdx") or ""
    lic_mr        = bool(meta.get("license_machine_readable"))

    prov_doc      = bool(meta.get("provenance_documented"))
    prov_std      = meta.get("provenance_standard") or ""
    alcoa         = bool(meta.get("alcoa_compliant"))

    qual_doc      = bool(meta.get("quality_criteria_documented"))
    data_meets    = bool(meta.get("data_meets_community_format_std"))

    title         = meta.get("title") or ""
    description   = meta.get("description") or ""
    keywords      = list(meta.get("keywords") or [])
    creator       = meta.get("creator") or ""
    date_created  = meta.get("date_created") or ""
    version       = meta.get("version") or ""

    S: dict[str, tuple[ComplianceScore, str]] = {}

    # ══════════════════════════════════════════════════════════════════════
    # F — FINDABLE
    # ══════════════════════════════════════════════════════════════════════

    # F1-01M: Metadata identified by a persistent identifier
    if pid and id_system in OPEN_ID_SYSTEMS:
        S["RDA-F1-01M"] = (_FI, f"Metadata carries a {id_system} PID: {pid}")
    elif pid:
        S["RDA-F1-01M"] = (_II, f"PID exists ({pid}) but '{id_system}' is not a globally recognised scheme — use DOI, Handle, or ARK")
    else:
        S["RDA-F1-01M"] = (_NBC, "No persistent identifier found in metadata")

    # F1-01D: Data identified by a globally unique persistent identifier
    if pid and id_system in OPEN_ID_SYSTEMS:
        S["RDA-F1-01D"] = (_FI, f"Data carries a {id_system} PID: {pid}")
    elif pid:
        S["RDA-F1-01D"] = (_II, "PID exists but not from a globally recognised scheme")
    else:
        S["RDA-F1-01D"] = (_NBC, "No PID for data — cannot be reliably cited or re-discovered")

    # F1-02M: Metadata PID is globally unique and uses a well-established scheme
    if id_system in OPEN_ID_SYSTEMS:
        S["RDA-F1-02M"] = (_FI, f"PID uses {id_system} — a globally maintained, unique scheme")
    elif pid:
        S["RDA-F1-02M"] = (_UC, f"PID exists but '{id_system}' is not a well-established global scheme (prefer DOI/Handle/ARK)")
    else:
        S["RDA-F1-02M"] = (_NBC, "No PID — cannot assess global uniqueness")

    # F1-02D: Data PID is globally unique and uses a well-established scheme
    if id_system in OPEN_ID_SYSTEMS:
        S["RDA-F1-02D"] = (_FI, f"Data PID uses {id_system} — globally unique and maintained")
    elif pid:
        S["RDA-F1-02D"] = (_UC, "PID exists but not using a well-established global scheme")
    else:
        S["RDA-F1-02D"] = (_NBC, "No data PID")

    # F2-01M: Data described with rich metadata
    rich_present = [f for f in [title, description, ", ".join(keywords), creator, date_created, version] if f]
    n_rich = len(rich_present)
    if n_rich >= 5:
        S["RDA-F2-01M"] = (_FI, f"Rich metadata: {n_rich}/6 key fields populated (title, description, keywords, creator, date, version)")
    elif n_rich >= 3:
        missing = [f for f, v in [("version", version), ("keywords", ", ".join(keywords)),
                                   ("creator", creator), ("date_created", date_created)] if not v]
        S["RDA-F2-01M"] = (_II, f"Adequate metadata ({n_rich}/6 fields). Missing: {', '.join(missing) or 'none'}")
    elif n_rich >= 1:
        S["RDA-F2-01M"] = (_UC, f"Minimal metadata ({n_rich}/6 fields) — significant enrichment needed")
    else:
        S["RDA-F2-01M"] = (_NBC, "No descriptive metadata found")

    # F3-01M: Metadata includes reference to the data it describes (PID in metadata)
    if pid:
        S["RDA-F3-01M"] = (_FI, f"Metadata contains a PID ({pid}) that references the data")
    else:
        S["RDA-F3-01M"] = (_NBC, "No PID in metadata — consumers cannot identify the data object from metadata alone")

    # F4-01M: Metadata indexed in a searchable resource
    if cat_indexed and cat_url:
        S["RDA-F4-01M"] = (_FI, f"Metadata indexed in a searchable catalog: {cat_url}")
    elif cat_url:
        S["RDA-F4-01M"] = (_II, f"Catalog URL provided ({cat_url}) but indexing not confirmed")
    elif meta_schema:
        S["RDA-F4-01M"] = (_UC, f"Metadata schema ({meta_schema}) exists but no catalog registration confirmed")
    else:
        S["RDA-F4-01M"] = (_NBC, "Metadata not indexed in any searchable resource")

    # ══════════════════════════════════════════════════════════════════════
    # A — ACCESSIBLE
    # ══════════════════════════════════════════════════════════════════════

    # A1-01M: Metadata retrievable by PID using standardised protocol
    if pid and access_proto in OPEN_PROTOCOLS:
        S["RDA-A1-01M"] = (_FI, f"Metadata retrievable via {access_proto} using PID {pid}")
    elif pid:
        S["RDA-A1-01M"] = (_II, "PID exists but retrieval protocol is not standardised or documented")
    else:
        S["RDA-A1-01M"] = (_NBC, "No PID — metadata cannot be retrieved by identifier")

    # A1-02D: Data accessible through a standardised protocol
    if pid and access_proto in OPEN_PROTOCOLS:
        S["RDA-A1-02D"] = (_FI, f"Data retrievable via {access_proto} using PID")
    elif access_proto in OPEN_PROTOCOLS:
        S["RDA-A1-02D"] = (_II, f"{access_proto} access exists but no PID to retrieve by")
    else:
        S["RDA-A1-02D"] = (_NBC, "No standardised access protocol documented")

    # A1-02M: Metadata accessible through a standardised protocol
    if access_proto in OPEN_PROTOCOLS:
        S["RDA-A1-02M"] = (_FI, f"Metadata retrievable via {access_proto}")
    elif access_proto:
        S["RDA-A1-02M"] = (_II, f"Protocol '{access_proto}' exists but is not a widely recognised standard")
    else:
        S["RDA-A1-02M"] = (_NBC, "No standardised communication protocol for metadata retrieval")

    # A1-03D: Data can be read by machines
    if data_fmt in OPEN_DATA_FORMATS or fmt_open:
        S["RDA-A1-03D"] = (_FI, f"Data in machine-readable open format: {data_fmt}")
    elif data_fmt:
        S["RDA-A1-03D"] = (_II, f"Data in format '{data_fmt}' — limited machine-readability (prefer CSV/JSON/RDF/Parquet)")
    else:
        S["RDA-A1-03D"] = (_UC, "Data format not specified — machine-readability cannot be assessed")

    # A1-03M: Metadata can be read by machines
    if meta_fmt in FORMAL_META_FORMATS:
        S["RDA-A1-03M"] = (_FI, f"Metadata in formal machine-readable format: {meta_fmt}")
    elif meta_schema in STRUCTURED_META_SCHEMAS or meta_fmt:
        S["RDA-A1-03M"] = (_II, f"Structured schema/format present ({meta_schema or meta_fmt}) — consider upgrading to JSON-LD or RDF")
    else:
        S["RDA-A1-03M"] = (_UC, "Metadata format not specified — machine-readability unknown")

    # A1-04D: Data accessible via free/open protocol
    if fmt_open and access_proto in OPEN_PROTOCOLS:
        S["RDA-A1-04D"] = (_FI, f"Data accessible via {access_proto} in open format {data_fmt}")
    elif access_proto in OPEN_PROTOCOLS:
        S["RDA-A1-04D"] = (_II, f"Open protocol ({access_proto}) but data format may be proprietary")
    elif access_proto:
        S["RDA-A1-04D"] = (_UC, f"Protocol exists ({access_proto}) but openness not confirmed")
    else:
        S["RDA-A1-04D"] = (_NBC, "No open access protocol documented")

    # A1-04M: Metadata accessible via free/open protocol
    if meta_open and access_proto in OPEN_PROTOCOLS:
        S["RDA-A1-04M"] = (_FI, f"Metadata openly accessible via {access_proto}")
    elif access_proto in OPEN_PROTOCOLS:
        S["RDA-A1-04M"] = (_II, "Open protocol but metadata openness not confirmed")
    else:
        S["RDA-A1-04M"] = (_UC, "Open protocol for metadata not confirmed")

    # A1-05D: Data physically accessible (documented process even if restricted)
    if access_doc or auth == "OAuth2":
        S["RDA-A1-05D"] = (_FI, "Data access process is documented — users know how to request access")
    elif access_proto:
        S["RDA-A1-05D"] = (_II, "Access protocol exists but the request process is not explicitly documented")
    else:
        S["RDA-A1-05D"] = (_NBC, "No access process documented")

    # A1.1-01M: Metadata accessible using open, free, universally implementable protocol
    if meta_open and access_proto in OPEN_PROTOCOLS:
        S["RDA-A1.1-01M"] = (_FI, f"Metadata openly accessible via {access_proto} at no cost")
    elif meta_open:
        S["RDA-A1.1-01M"] = (_II, "Metadata is open but protocol not confirmed to be universally free")
    elif access_proto in OPEN_PROTOCOLS:
        S["RDA-A1.1-01M"] = (_UC, "Open protocol used but metadata openness not confirmed")
    else:
        S["RDA-A1.1-01M"] = (_NBC, "Metadata access is not open or free")

    # A1.1-01D: Data accessible using open, free, universally implementable protocol
    if fmt_open and access_proto in OPEN_PROTOCOLS:
        S["RDA-A1.1-01D"] = (_FI, f"Data accessible via {access_proto} in open format {data_fmt}")
    elif access_proto in OPEN_PROTOCOLS:
        S["RDA-A1.1-01D"] = (_II, f"Open protocol ({access_proto}) but data format may be proprietary")
    else:
        S["RDA-A1.1-01D"] = (_UC, "Open+free access protocol not confirmed")

    # A1.2-01D: Data accessible using open authentication protocol
    if auth is None:
        S["RDA-A1.2-01D"] = (_FI, "Data is openly accessible — no authentication required")
    elif auth == "OAuth2":
        S["RDA-A1.2-01D"] = (_II, "OAuth2 is an open standard — partially meets this indicator")
    elif auth == "API-key":
        S["RDA-A1.2-01D"] = (_UC, "API-key access is not a fully open authentication protocol")
    else:
        S["RDA-A1.2-01D"] = (_NBC, f"Authentication '{auth}' is restrictive and not an open protocol")

    # A2-01M: Metadata accessible even when data is no longer available
    if meta_persists:
        S["RDA-A2-01M"] = (_FI, "Metadata confirmed to persist after data removal (tombstone/archive policy in place)")
    else:
        S["RDA-A2-01M"] = (_NBC, "No metadata persistence policy confirmed — metadata may be lost with data")

    # ══════════════════════════════════════════════════════════════════════
    # I — INTEROPERABLE
    # ══════════════════════════════════════════════════════════════════════

    # I1-01M: Metadata uses a formal, accessible, shared knowledge representation language
    if meta_fmt in FORMAL_META_FORMATS:
        S["RDA-I1-01M"] = (_FI, f"Metadata uses formal knowledge representation: {meta_fmt}")
    elif meta_schema in STRUCTURED_META_SCHEMAS:
        S["RDA-I1-01M"] = (_II, f"Structured schema ({meta_schema}) present — upgrade to JSON-LD or RDF for full compliance")
    elif meta_fmt:
        S["RDA-I1-01M"] = (_UC, f"Metadata format '{meta_fmt}' exists but formal knowledge representation level is unclear")
    else:
        S["RDA-I1-01M"] = (_NBC, "No formal metadata representation language found")

    # I1-01D: Data uses a formal, accessible, shared knowledge representation language
    formal_data_fmts = {"RDF", "JSON-LD", "OWL", "RDF/Turtle"}
    if data_fmt in formal_data_fmts:
        S["RDA-I1-01D"] = (_FI, f"Data uses formal knowledge representation: {data_fmt}")
    elif data_fmt in OPEN_DATA_FORMATS:
        S["RDA-I1-01D"] = (_II, f"Data in open format ({data_fmt}) — not fully formal knowledge representation (consider RDF/JSON-LD)")
    elif data_fmt:
        S["RDA-I1-01D"] = (_UC, f"Data format '{data_fmt}' has limited formal knowledge representation")
    else:
        S["RDA-I1-01D"] = (_NBC, "Data format not specified")

    # I1-02M: Metadata uses FAIR vocabularies
    if len(vocabs) >= 3 and vocab_pids:
        S["RDA-I1-02M"] = (_FI, f"Metadata uses {len(vocabs)} FAIR vocabularies with PIDs: {', '.join(vocabs[:5])}")
    elif len(vocabs) >= 2:
        S["RDA-I1-02M"] = (_II, f"{len(vocabs)} vocabularies used ({', '.join(vocabs)}) — verify PID referencing")
    elif len(vocabs) == 1:
        S["RDA-I1-02M"] = (_UC, f"Only 1 vocabulary ({vocabs[0]}) — broaden coverage")
    else:
        S["RDA-I1-02M"] = (_NBC, "No controlled vocabularies referenced in metadata")

    # I1-02D: Data uses FAIR vocabularies
    if len(vocabs) >= 3 and vocab_pids:
        S["RDA-I1-02D"] = (_FI, f"Data values reference FAIR vocabularies: {', '.join(vocabs[:5])}")
    elif len(vocabs) >= 2:
        S["RDA-I1-02D"] = (_II, "Some vocabularies used in data — verify PID referencing")
    elif len(vocabs) == 1:
        S["RDA-I1-02D"] = (_UC, "Only 1 vocabulary in data — limited interoperability")
    else:
        S["RDA-I1-02D"] = (_NBC, "No controlled vocabularies used in data")

    # I2-01M: Metadata uses FAIR vocab for its own metadata elements
    if vocab_pids and vocabs:
        S["RDA-I2-01M"] = (_FI, "Metadata elements referenced using FAIR vocabulary PIDs")
    elif vocabs:
        S["RDA-I2-01M"] = (_II, "Vocabularies used but not confirmed PID-referenced — ensure vocab terms use persistent URIs")
    else:
        S["RDA-I2-01M"] = (_NBC, "No FAIR vocabularies used for metadata element definitions")

    # I2-01D: Data uses standardised formats that enable machine processing
    if comm_std_data and data_fmt:
        S["RDA-I2-01D"] = (_FI, f"Data follows community standard '{comm_std}' in format '{data_fmt}'")
    elif data_fmt in OPEN_DATA_FORMATS:
        S["RDA-I2-01D"] = (_II, f"Interoperable format ({data_fmt}) — align with community standard for full marks")
    elif data_fmt:
        S["RDA-I2-01D"] = (_UC, f"Data format '{data_fmt}' specified but interoperability limited")
    else:
        S["RDA-I2-01D"] = (_NBC, "Data format not specified — machine interoperability cannot be assessed")

    # I3-01M: Metadata includes qualified references to other metadata
    if links_data and links_pids:
        S["RDA-I3-01M"] = (_FI, "Metadata contains PID-qualified links to related datasets")
    elif links_data or links_pubs:
        S["RDA-I3-01M"] = (_II, "Metadata links to related resources but links may not be PID-qualified")
    else:
        S["RDA-I3-01M"] = (_NBC, "No links to related data or publications in metadata")

    # I3-01D: Data includes qualified references to other data
    if links_data and links_pids:
        S["RDA-I3-01D"] = (_FI, "Data contains PID-qualified references to related datasets")
    elif links_data:
        S["RDA-I3-01D"] = (_II, "Data links to related resources — use PIDs for those links")
    else:
        S["RDA-I3-01D"] = (_NBC, "No cross-references to other data found")

    # I3-02M: Metadata includes qualified cross-references to related metadata
    if links_data and links_pids:
        S["RDA-I3-02M"] = (_FI, "Metadata has PID-qualified cross-references to related metadata records")
    elif links_pubs and links_pids:
        S["RDA-I3-02M"] = (_II, "Metadata links to publications via PIDs — extend to related data records")
    elif links_data or links_pubs:
        S["RDA-I3-02M"] = (_UC, "Links to related resources exist but not PID-qualified")
    else:
        S["RDA-I3-02M"] = (_NBC, "No qualified metadata cross-references")

    # I3-02D: Data includes qualified cross-references to other data
    if links_data and links_pids:
        S["RDA-I3-02D"] = (_FI, "Data cross-references related datasets using PIDs")
    elif links_data:
        S["RDA-I3-02D"] = (_II, "Data links to other datasets — use PIDs for those links")
    else:
        S["RDA-I3-02D"] = (_NBC, "No qualified data cross-references")

    # I3-03M: Metadata includes qualified references to associated code/software
    if links_code:
        S["RDA-I3-03M"] = (_FI, "Metadata links to associated analysis code or software")
    else:
        S["RDA-I3-03M"] = (_NBC, "No links to code or software — add a GitHub/Zenodo link to analysis scripts")

    # I3-04M: Metadata outgoing links use PIDs
    if links_pids and (links_data or links_pubs):
        S["RDA-I3-04M"] = (_FI, "Metadata outgoing links use PIDs (DOI/Handle)")
    elif links_data or links_pubs:
        S["RDA-I3-04M"] = (_II, "Links exist but not confirmed to use PIDs — prefer DOI/Handle links")
    else:
        S["RDA-I3-04M"] = (_NBC, "No outgoing links in metadata")

    # ══════════════════════════════════════════════════════════════════════
    # R — REUSABLE
    # ══════════════════════════════════════════════════════════════════════

    # R1-01M: Plurality of accurate and relevant attributes
    r1_fields = [title, description, ", ".join(keywords), creator,
                 date_created, version, comm_std, lic_spdx]
    r1_count = sum(1 for f in r1_fields if f)
    if r1_count >= 6:
        S["RDA-R1-01M"] = (_FI, f"Rich attribute set ({r1_count}/8 fields) — enables reuse with full context")
    elif r1_count >= 4:
        missing_r1 = [f for f, v in [("version", version), ("community_standard", comm_std),
                                      ("license_spdx", lic_spdx), ("keywords", ", ".join(keywords))] if not v]
        S["RDA-R1-01M"] = (_II, f"Adequate attributes ({r1_count}/8). Add: {', '.join(missing_r1) or 'none'}")
    elif r1_count >= 2:
        S["RDA-R1-01M"] = (_UC, f"Only {r1_count}/8 key attributes — significant enrichment needed")
    else:
        S["RDA-R1-01M"] = (_NBC, "Insufficient metadata attributes to support reuse")

    # R1.1-01M: License information accessible
    if lic_spdx:
        S["RDA-R1.1-01M"] = (_FI, f"License information present: {lic_spdx}")
    elif access_doc:
        S["RDA-R1.1-01M"] = (_II, "Access conditions documented but no formal license — add an SPDX license identifier")
    else:
        S["RDA-R1.1-01M"] = (_NBC, "No license information — reusers cannot determine how to use the data")

    # R1.1-02M: Clear reuse rights / open license
    if lic_spdx in OPEN_LICENSES:
        S["RDA-R1.1-02M"] = (_FI, f"Open license ({lic_spdx}) — clear reuse rights communicated")
    elif lic_spdx:
        S["RDA-R1.1-02M"] = (_II, f"License '{lic_spdx}' specified — verify it clearly communicates reuse permissions")
    else:
        S["RDA-R1.1-02M"] = (_NBC, "No license — reuse rights are undefined")

    # R1.1-03M: Machine-readable license
    if lic_mr and lic_spdx:
        S["RDA-R1.1-03M"] = (_FI, f"Machine-readable license ({lic_spdx}) — processable by software agents")
    elif lic_spdx:
        S["RDA-R1.1-03M"] = (_II, "SPDX license ID present — add machine-readable form (e.g. SPDX expression in schema.org metadata)")
    else:
        S["RDA-R1.1-03M"] = (_NBC, "No machine-readable license")

    # R1.2-01M: Provenance documented
    if prov_doc:
        S["RDA-R1.2-01M"] = (_FI, "Data provenance documented (origin, transformations, audit trail)")
    elif alcoa:
        S["RDA-R1.2-01M"] = (_II, "ALCOA+ traceability indicates provenance — make it explicit in metadata records")
    else:
        S["RDA-R1.2-01M"] = (_NBC, "No provenance information — reusers cannot assess data trustworthiness")

    # R1.2-02M: Provenance follows a community standard
    if prov_std in PROV_STANDARDS:
        S["RDA-R1.2-02M"] = (_FI, f"Provenance follows community standard: {prov_std}")
    elif prov_doc:
        S["RDA-R1.2-02M"] = (_II, "Provenance documented but not following a named standard — adopt PROV-O or W3C PROV")
    else:
        S["RDA-R1.2-02M"] = (_NBC, "No community-standard provenance")

    # R1.3-01M: Metadata meets domain-relevant community standards
    if comm_std in COMMUNITY_STANDARDS:
        S["RDA-R1.3-01M"] = (_FI, f"Metadata follows domain community standard: {comm_std}")
    elif meta_schema in STRUCTURED_META_SCHEMAS:
        S["RDA-R1.3-01M"] = (_II, f"Structured schema ({meta_schema}) used — map to a domain standard (ISA-Tab, BIDS, CDISC)")
    else:
        S["RDA-R1.3-01M"] = (_NBC, "No domain community standard for metadata identified")

    # R1.3-01D: Data meets domain-relevant community standards
    if comm_std_data and comm_std in COMMUNITY_STANDARDS:
        S["RDA-R1.3-01D"] = (_FI, f"Data conforms to community standard: {comm_std}")
    elif comm_std:
        S["RDA-R1.3-01D"] = (_II, f"Community standard '{comm_std}' identified — confirm data conforms to it")
    else:
        S["RDA-R1.3-01D"] = (_NBC, "No community standard applied to data")

    # R1.3-02M: Metadata follows community standards for data handling/sharing
    if qual_doc and comm_std:
        S["RDA-R1.3-02M"] = (_FI, "Quality criteria documented in alignment with community standards")
    elif qual_doc:
        S["RDA-R1.3-02M"] = (_II, "Quality criteria documented — align with community standard data-handling practices")
    else:
        S["RDA-R1.3-02M"] = (_NBC, "No data quality criteria documented")

    # R1.3-02D: Data meets domain-relevant community standards for content
    if data_meets:
        S["RDA-R1.3-02D"] = (_FI, "Data content confirmed to meet community format and content standards")
    elif comm_std_data:
        S["RDA-R1.3-02D"] = (_II, "Community standard format used — validate that content also meets standards")
    else:
        S["RDA-R1.3-02D"] = (_UC, "Community standard compliance for data content not confirmed")

    return S


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def score_from_metadata(
    meta: Meta,
    dataset_id: str | None = None,
    title: str | None = None,
    assessed_by: str = "FAIR Studio OSS (automated rule engine)",
) -> FAIRAssessmentResult:
    """
    Score a dataset's FAIR maturity from its metadata dictionary.

    Parameters
    ----------
    meta:         Metadata dict — see ``METADATA_SCHEMA`` or ``get_metadata_template()``.
    dataset_id:   Override for the dataset ID (defaults to ``meta['dataset_id']``).
    title:        Override for the title (defaults to ``meta['title']``).
    assessed_by:  Label for the assessor.

    Returns
    -------
    FAIRAssessmentResult
        Use ``.overall_score``, ``.dimension_scores``, ``.get_gaps()`` on the result.
    """
    did    = dataset_id or meta.get("dataset_id") or "UNKNOWN"
    dtitle = title      or meta.get("title")      or "Untitled Dataset"

    raw_scores = _score_all(meta)

    # Group IndicatorScore objects by principle
    by_principle: dict[str, list[IndicatorScore]] = {p: [] for p in "FAIR"}

    for ind in RDA_INDICATORS:
        compliance, reasoning = raw_scores.get(ind.id, (_UC, "Not evaluated"))
        by_principle[ind.principle.value].append(
            IndicatorScore(
                indicator_id=ind.id,
                indicator_name=ind.name,
                principle=ind.principle,
                priority=ind.priority,
                compliance=compliance,
                evidence=reasoning,
            )
        )

    return FAIRAssessmentResult(
        dataset_id=did,
        dataset_title=dtitle,
        assessed_by=assessed_by,
        assessment_method="automated",
        f_score=FAIRDimensionScore(principle=FAIRPrinciple.F, indicator_scores=by_principle["F"]),
        a_score=FAIRDimensionScore(principle=FAIRPrinciple.A, indicator_scores=by_principle["A"]),
        i_score=FAIRDimensionScore(principle=FAIRPrinciple.I, indicator_scores=by_principle["I"]),
        r_score=FAIRDimensionScore(principle=FAIRPrinciple.R, indicator_scores=by_principle["R"]),
    )
