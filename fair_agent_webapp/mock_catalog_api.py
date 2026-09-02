"""
mock_catalog_api.py
────────────────────
Standalone FastAPI mock data catalog + database.

Run it:  python mock_catalog_api.py
         → API at http://localhost:9321
         → Interactive docs at http://localhost:9321/docs

This serves as BOTH:
  1. A testable API that the FAIRAgent web app can assess
  2. A reference spec showing exactly what your real catalog API must expose

Endpoints
─────────
GET /              – health check / welcome
GET /catalog       – list all datasets in the catalog
GET /schema        – database schema (tables, columns, types, FK/PKs, ontology refs)
GET /metadata      – dataset-level metadata (PID, license, access, provenance…)
GET /records       – sample data rows
GET /lineage       – ETL provenance chain
GET /access        – access protocol + auth details
GET /fields-guide  – machine-readable guide to required fields for real assessments
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# ─────────────────────────────────────────────────────────────────────────────
# Mock Data
# ─────────────────────────────────────────────────────────────────────────────

MOCK_SCHEMA = {
    "dataset_id": "STUDY-INV-001",
    "database": "pharma_research_db",
    "tables": [
        {
            "name": "compounds",
            "description": "Registered chemical compounds under investigation",
            "columns": [
                {"name": "compound_id",   "type": "VARCHAR(50)",  "primary_key": True,  "nullable": False, "ontology": "ChEMBL:CHEMBL25",    "description": "Internal compound registry identifier"},
                {"name": "compound_name", "type": "VARCHAR(200)", "primary_key": False, "nullable": False, "ontology": None,                  "description": "Common or IUPAC compound name"},
                {"name": "smiles",        "type": "TEXT",         "primary_key": False, "nullable": True,  "ontology": "CHEMINF:000018",      "description": "Canonical SMILES string (CHEMINF:000018)"},
                {"name": "inchi_key",     "type": "VARCHAR(27)",  "primary_key": False, "nullable": True,  "ontology": "CHEMINF:000399",      "description": "Standard InChIKey (CHEMINF:000399)"},
                {"name": "target_gene",   "type": "VARCHAR(50)",  "primary_key": False, "nullable": True,  "ontology": "HGNC:1097",           "description": "Target gene symbol (HGNC ID)"},
            ],
        },
        {
            "name": "assay_results",
            "description": "Measured biological activity values per compound",
            "columns": [
                {"name": "result_id",   "type": "UUID",          "primary_key": True,  "nullable": False, "ontology": None,             "description": "Unique result UUID"},
                {"name": "compound_id", "type": "VARCHAR(50)",   "primary_key": False, "nullable": False, "foreign_key": "compounds.compound_id", "ontology": None, "description": "FK → compounds.compound_id"},
                {"name": "assay_type",  "type": "VARCHAR(100)",  "primary_key": False, "nullable": False, "ontology": "OBI:0001318",    "description": "OBI assay class (OBI:0001318 = cell viability)"},
                {"name": "value",       "type": "FLOAT",         "primary_key": False, "nullable": False, "ontology": None,             "description": "Measured activity value"},
                {"name": "unit",        "type": "VARCHAR(20)",   "primary_key": False, "nullable": False, "ontology": "UO:0000064",     "description": "Unit (UO:0000064 = nanomolar)"},
                {"name": "cell_line",   "type": "VARCHAR(100)",  "primary_key": False, "nullable": True,  "ontology": "CLO:0000019",    "description": "Cell line used (CLO term)"},
                {"name": "created_at",  "type": "TIMESTAMP",     "primary_key": False, "nullable": False, "ontology": None,             "description": "ISO 8601 creation timestamp"},
                {"name": "created_by",  "type": "VARCHAR(100)",  "primary_key": False, "nullable": False, "ontology": None,             "description": "Operator name / ID (ALCOA attribution)"},
            ],
        },
    ],
}

MOCK_METADATA = {
    "dataset_id": "STUDY-INV-001",
    "title": "In-vitro PD Assay Panel — Compound Series Alpha",
    "description": "IC50 measurements for 48 compounds against EGFR using HeLa cell viability assay. Part of the Series Alpha lead optimisation campaign.",
    "owner": "Dr. Jane Smith <jane.smith@example.org>",
    "department": "Computational Chemistry & Biology, Takeda Research",
    "created_at": "2024-03-15T09:00:00Z",
    "modified_at": "2024-11-20T14:30:00Z",
    # ── Findable (F1 / F4) ────────────────────────────────────────────────
    "persistent_identifier": "https://doi.org/10.99999/study-inv-001",
    "global_identifier_system": "DOI",
    "catalog_url": "https://datacatalog.example.org/datasets/STUDY-INV-001",
    # ── Accessible (A1 / A1.1 / A1.2 / A2) ──────────────────────────────
    "access": {
        "protocol": "HTTPS",
        "endpoint": "https://api.example.org/datasets/STUDY-INV-001",
        "authentication": "OAuth2 / API token",
        "is_open_protocol": True,
        "access_request_url": "https://dac.example.org/request",
    },
    "metadata_persists_without_data": True,
    # ── Interoperable (I2 / R1.3) ─────────────────────────────────────────
    "vocabularies": ["OBI", "ChEMBL", "CLO", "UO", "HGNC", "CHEMINF"],
    "community_standard": "ISA-Tab",
    # ── Reusable (R1.1 / R1.2) ───────────────────────────────────────────
    "license": {
        "name": "CC BY 4.0",
        "url": "https://creativecommons.org/licenses/by/4.0/",
        "spdx": "CC-BY-4.0",
        "machine_readable": True,
    },
    "provenance": {
        "source": "Internal ELN (Benchling) — signed audit trail",
        "transformation": "ETL pipeline v2.3",
        "alcoa_compliant": True,
        "prov_standard": "W3C PROV-O",
    },
    "related_datasets": [
        {
            "id": "STUDY-INV-000",
            "relation": "IsPreviousVersionOf",
            "url": "https://doi.org/10.99999/study-inv-000",
        },
        {
            "id": "STUDY-CLINIC-007",
            "relation": "IsSupplementTo",
            "url": "https://doi.org/10.99999/study-clinic-007",
        },
    ],
}

MOCK_RECORDS = {
    "dataset_id": "STUDY-INV-001",
    "table": "assay_results",
    "total_rows": 48,
    "records": [
        {"compound_id": "CMPD-001", "assay_type": "OBI:0001318", "value": 12.4, "unit": "nM", "cell_line": "CLO:0000019", "created_by": "JS/2024-03-15"},
        {"compound_id": "CMPD-002", "assay_type": "OBI:0001318", "value": 85.1, "unit": "nM", "cell_line": "CLO:0000019", "created_by": "JS/2024-03-15"},
        {"compound_id": "CMPD-003", "assay_type": "OBI:0001318", "value":  3.2, "unit": "nM", "cell_line": "CLO:0000019", "created_by": "JS/2024-03-15"},
        {"compound_id": "CMPD-004", "assay_type": "OBI:0001318", "value": 47.9, "unit": "nM", "cell_line": "CLO:0000019", "created_by": "JS/2024-03-16"},
        {"compound_id": "CMPD-005", "assay_type": "OBI:0001318", "value": 210.0,"unit": "nM", "cell_line": "CLO:0000019", "created_by": "JS/2024-03-16"},
    ],
}

MOCK_LINEAGE = {
    "dataset_id": "STUDY-INV-001",
    "standard": "W3C PROV-O",
    "steps": [
        {
            "step": 1,
            "label": "Raw instrument output",
            "description": "Vi-CELL XR counter exports raw CSV per plate",
            "actor": "Vi-CELL XR instrument (SN: VCX-4821)",
            "timestamp": "2024-03-15T08:30:00Z",
            "output_format": "CSV",
        },
        {
            "step": 2,
            "label": "ELN capture",
            "description": "Raw data imported into Benchling ELN with ALCOA+ fields. Signed electronically.",
            "actor": "Dr. Jane Smith <jane.smith@example.org>",
            "timestamp": "2024-03-15T09:00:00Z",
            "output_format": "Benchling ELN record",
        },
        {
            "step": 3,
            "label": "ETL normalisation",
            "description": "Automated pipeline maps units to UO ontology terms, compounds to ChEMBL IDs, assays to OBI terms.",
            "actor": "ETL pipeline v2.3 (GitHub Actions CI run #4821)",
            "timestamp": "2024-03-16T02:00:00Z",
            "output_format": "Parquet (Bronze layer)",
        },
        {
            "step": 4,
            "label": "Data lake load",
            "description": "Validated Parquet promoted to Silver layer. Schema versioned in Glue Catalog.",
            "actor": "DataOps team / automated quality gate",
            "timestamp": "2024-03-17T10:00:00Z",
            "output_format": "Parquet (Silver layer) + Glue Catalog entry",
        },
    ],
}

FIELDS_GUIDE = {
    "description": (
        "This guide describes every field your real catalog API must expose "
        "for the FAIRAgent to perform a complete assessment."
    ),
    "endpoints": {
        "/schema": {
            "purpose": "Database schema inspection — covers F1, F2, I1, I2 indicators",
            "required_fields": {
                "dataset_id": "string — unique dataset identifier",
                "tables[].name": "string — table name",
                "tables[].columns[].name": "string — column name",
                "tables[].columns[].type": "string — SQL data type",
                "tables[].columns[].primary_key": "bool",
                "tables[].columns[].ontology": "string | null — ontology term IRI (e.g. OBI:0001318)",
            },
        },
        "/metadata": {
            "purpose": "Dataset-level catalog metadata — covers all FAIR indicators",
            "required_fields": {
                "persistent_identifier": "string — DOI / ARK / Handle URI  [F1]",
                "global_identifier_system": "string — 'DOI' | 'ARK' | 'Handle'  [F1]",
                "title": "string  [F2]",
                "description": "string  [F2, R1]",
                "owner": "string — name + email  [R1]",
                "catalog_url": "string — URL of dataset in the catalog  [F4]",
                "access.protocol": "string — 'HTTPS' | 'FTP' etc.  [A1.1]",
                "access.is_open_protocol": "bool  [A1.1]",
                "access.authentication": "string — auth method description  [A1.2]",
                "access.access_request_url": "string — URL to request access  [A1.2]",
                "metadata_persists_without_data": "bool  [A2]",
                "vocabularies": "list[string] — ontology prefixes used  [I2]",
                "community_standard": "string — e.g. 'ISA-Tab', 'MIAME'  [R1.3]",
                "license.spdx": "string — SPDX identifier e.g. 'CC-BY-4.0'  [R1.1]",
                "license.machine_readable": "bool  [R1.1]",
                "provenance.source": "string  [R1.2]",
                "provenance.alcoa_compliant": "bool  [R1.2]",
                "related_datasets": "list[{id, relation, url}]  [I3]",
            },
        },
        "/records": {
            "purpose": "Sample data rows — covers A1, I1, I2 indicators",
            "required_fields": {
                "records": "list[dict] — sample rows from the dataset",
                "note": "Values should use ontology term IRIs where applicable (e.g. OBI:0001318)",
            },
        },
        "/lineage": {
            "purpose": "Data provenance chain — covers R1.2 indicator",
            "required_fields": {
                "steps": "list[{step, description, actor, timestamp}]",
                "standard": "string — W3C PROV-O | PAV | custom",
            },
        },
        "/access": {
            "purpose": "Access protocol details — covers A1, A1.1, A1.2",
            "required_fields": {
                "protocol": "string",
                "is_open_protocol": "bool",
                "authentication": "string",
                "access_request_url": "string | null",
                "endpoint": "string — data retrieval URL",
            },
        },
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="FAIRAgent Mock Catalog API",
    description=(
        "A mock data catalog + database API for testing the FAIRAgent web app.\n\n"
        "Point your FAIRAgent at `http://localhost:9321` to run an assessment against "
        "this sample pharma in-vitro PD dataset.\n\n"
        "See `GET /fields-guide` to understand what your real catalog must expose."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/", tags=["Health"])
def root():
    return {
        "status": "ok",
        "service": "FAIRAgent Mock Catalog API",
        "dataset": "STUDY-INV-001 (In-vitro PD Assay Panel — Compound Series Alpha)",
        "docs": "/docs",
        "endpoints": ["/schema", "/metadata", "/records", "/lineage", "/access", "/catalog", "/fields-guide"],
    }


@app.get("/catalog", tags=["Catalog"])
def list_datasets():
    """List all datasets available in this mock catalog."""
    return {
        "total": 1,
        "datasets": [
            {
                "dataset_id": MOCK_METADATA["dataset_id"],
                "title": MOCK_METADATA["title"],
                "owner": MOCK_METADATA["owner"],
                "created_at": MOCK_METADATA["created_at"],
                "persistent_identifier": MOCK_METADATA["persistent_identifier"],
            }
        ],
    }


@app.get("/schema", tags=["Database"])
def get_schema():
    """Return the database schema: tables, columns, types, PK/FK, ontology annotations."""
    return MOCK_SCHEMA


@app.get("/metadata", tags=["Catalog"])
def get_metadata():
    """Return the full catalog metadata record for the dataset (PID, license, access, provenance…)."""
    return MOCK_METADATA


@app.get("/records", tags=["Database"])
def get_records(limit: int = Query(default=5, ge=1, le=50)):
    """Return sample data rows. Use `limit` to control how many rows are returned."""
    result = dict(MOCK_RECORDS)
    result["records"] = MOCK_RECORDS["records"][:limit]
    result["returned"] = len(result["records"])
    return result


@app.get("/lineage", tags=["Catalog"])
def get_lineage():
    """Return the dataset's provenance/lineage chain (W3C PROV-O format)."""
    return MOCK_LINEAGE


@app.get("/access", tags=["Catalog"])
def get_access():
    """Return access protocol details for the dataset."""
    return MOCK_METADATA["access"]


@app.get("/fields-guide", tags=["Reference"])
def get_fields_guide():
    """
    Machine-readable guide showing exactly what fields your real catalog API must
    expose in order for the FAIRAgent to perform a complete FAIR assessment.
    """
    return FIELDS_GUIDE


# ─────────────────────────────────────────────────────────────────────────────
# Run
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  FAIRAgent Mock Catalog API")
    print("  http://localhost:9321")
    print("  Swagger docs: http://localhost:9321/docs")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=9321, reload=False)
