"""
catalog_browser_app.py
──────────────────────
Standalone Streamlit app — Data Catalog Browser only.
Helps users explore the mock catalog API and understand what endpoints
their real catalog must expose for the FAIR Studio to work.
"""
import json
import httpx
import streamlit as st

st.set_page_config(
    page_title="FAIR Catalog Browser",
    page_icon="📋",
    layout="wide",
)

st.title("📋 FAIR Data Catalog Browser")
st.caption(
    "Explore the mock catalog API and learn what endpoints your real catalog "
    "must expose to work with the FAIR Studio."
)

# ─────────────────────────────────────────────────────────────────────────────
# Sidebar — server config
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Catalog API")
    catalog_url = st.text_input("Base URL", value="http://localhost:9321")
    st.divider()
    st.markdown("""
**To start the mock catalog:**
```bash
python mock_catalog_api.py
```
Then browse its Swagger UI at:
[localhost:9321/docs](http://localhost:9321/docs)
    """)

# ─────────────────────────────────────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────────────────────────────────────
col1, col2 = st.columns([3, 1])
with col2:
    if st.button("🔍 Test Connection", use_container_width=True):
        try:
            r = httpx.get(f"{catalog_url}/", timeout=5)
            if r.status_code == 200:
                st.success("✓ Catalog reachable")
            else:
                st.error(f"HTTP {r.status_code}")
        except Exception as e:
            st.error(f"Connection failed: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# Endpoint explorer
# ─────────────────────────────────────────────────────────────────────────────
ENDPOINTS = {
    "/ (health)":                "/",
    "/catalog (dataset list)":   "/catalog",
    "/metadata (full metadata)": "/metadata",
    "/schema (DB schema)":       "/schema",
    "/records (sample data)":    "/records?limit=5",
    "/lineage (provenance)":     "/lineage",
    "/access (access protocol)": "/access",
    "/fields-guide (required fields for real catalogs)": "/fields-guide",
}

st.subheader("🔎 Endpoint Explorer")
selected = st.selectbox("Choose an endpoint", list(ENDPOINTS.keys()))
endpoint = ENDPOINTS[selected]

if st.button(f"Fetch  {endpoint}", type="primary"):
    try:
        r = httpx.get(f"{catalog_url}{endpoint}", timeout=10)
        data = r.json()
        st.json(data)
        st.caption(f"HTTP {r.status_code} · {len(r.content)} bytes")
    except Exception as e:
        st.error(f"Request failed: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# Required fields reference
# ─────────────────────────────────────────────────────────────────────────────
st.divider()
st.subheader("📐 Required Fields for Real Catalog Integration")
try:
    r = httpx.get(f"{catalog_url}/fields-guide", timeout=5)
    fields = r.json()
    import pandas as pd
    rows = []
    for ep, spec in fields.items():
        for field in spec.get("fields", []):
            rows.append({
                "Endpoint":    ep,
                "Field":       field["name"],
                "Type":        field["type"],
                "Required":    "✓" if field.get("required") else "○",
                "Description": field.get("description", ""),
            })
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
except Exception:
    st.info("Start the mock catalog server to view the fields guide.")

# ─────────────────────────────────────────────────────────────────────────────
# Code examples
# ─────────────────────────────────────────────────────────────────────────────
st.divider()
st.subheader("💡 Code Examples")
tab1, tab2 = st.tabs(["curl", "Python (httpx)"])
with tab1:
    st.code(f"""
# Health check
curl {catalog_url}/

# Full metadata
curl {catalog_url}/metadata | python -m json.tool

# Schema
curl {catalog_url}/schema | python -m json.tool

# Sample records
curl "{catalog_url}/records?limit=3"
""", language="bash")

with tab2:
    st.code(f"""
import httpx

BASE = "{catalog_url}"

meta    = httpx.get(f"{{BASE}}/metadata").json()
schema  = httpx.get(f"{{BASE}}/schema").json()
records = httpx.get(f"{{BASE}}/records", params={{"limit": 5}}).json()
lineage = httpx.get(f"{{BASE}}/lineage").json()
access  = httpx.get(f"{{BASE}}/access").json()

print("PID:", meta["persistent_identifier"])
print("License:", meta["license"]["spdx"])
print("Tables:", [t["name"] for t in schema["tables"]])
""", language="python")
