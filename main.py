# main.py
import secrets
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Optional
from datetime import datetime, timedelta

from models import APIResponse
from utils import GEN_DF, EM_DF

# -----------------------------------
# FastAPI app
# -----------------------------------
app = FastAPI(
    title="⚡ National Energy Insights System (NEIS)",
    description=(
        "NEIS is a data-driven platform for monitoring, estimating, and auditing "
        "energy generation and carbon emissions across Kenya at national and "
        "county levels. The system supports automated emissions estimation, "
        "manual data overrides, and transparent audit tracking for research, "
        "policy analysis, and climate reporting."
    ),
    version="1.2.0",
    contact={"name": "Simon Wanyoike", "email": "symoprof83@gmail.com"}
)

# -----------------------------------
# CORS
# -----------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------
# API Key Management
# -----------------------------------
API_KEYS: Dict[str, datetime] = {}
KEY_EXPIRATION_MINUTES = 30


@app.get("/api/generate-key", tags=["Authentication"])
def generate_key():
    new_key = secrets.token_urlsafe(16)
    expires_at = datetime.utcnow() + timedelta(minutes=KEY_EXPIRATION_MINUTES)
    API_KEYS[new_key] = expires_at
    return {
        "api_key": new_key,
        "expires_at": expires_at.isoformat() + "Z"
    }


def verify_api_key(x_api_key: str = Header(...)):
    now = datetime.utcnow()
    expired = [k for k, v in API_KEYS.items() if v < now]
    for k in expired:
        del API_KEYS[k]

    if x_api_key not in API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid or expired API key")


# -----------------------------------
# HOME / OVERVIEW
# -----------------------------------
@app.get("/", tags=["Overview"])
def overview():
    return {
        "system": "National Energy Insights System (NEIS)",
        "overview": (
            "NEIS integrates national datasets with user-supplied inputs to "
            "deliver transparent energy and emissions intelligence. "
            "Users can enable or disable automatic emissions estimation, "
            "manually override values, and trace the origin of reported figures "
            "through built-in audit flags."
        ),
        "capabilities": [
            "National & county-level energy insights",
            "Automatic emissions estimation",
            "Manual emissions override",
            "Audit flags for data transparency",
            "API-first architecture for dashboards & research tools"
        ],
        "documentation": "/docs"
    }


# -----------------------------------
# In-memory manual override store
# (replace with DB later)
# -----------------------------------
MANUAL_EMISSIONS_OVERRIDE: Dict[str, float] = {}

# -----------------------------------
# Prepare generation-only county data
# -----------------------------------
counties_data = {}

if "county" in GEN_DF.columns:
    for county in GEN_DF["county"].dropna().unique():
        gen_total = float(
            GEN_DF[GEN_DF["county"] == county]["generation_mwh"].sum()
        )

        by_source = []
        if "source" in GEN_DF.columns:
            for source, grp in GEN_DF[GEN_DF["county"] == county].groupby("source"):
                by_source.append({
                    "source": source,
                    "generation_MWh": float(grp["generation_mwh"].sum())
                })

        counties_data[county] = {
            "county": county,
            "total_generation": gen_total,
            "by_source": by_source
        }


# -----------------------------------
# NATIONAL SUMMARY
# -----------------------------------
@app.get(
    "/api/energy/summary",
    response_model=APIResponse,
    tags=["National Data"],
    dependencies=[Depends(verify_api_key)]
)
def national_summary(
    estimate_emissions: bool = True,
    use_manual_override: bool = True
):
    """
    estimate_emissions:
        Linked directly to frontend checkbox.
    use_manual_override:
        Allows user-entered emissions to override calculations.
    """

    if not estimate_emissions:
        total_emissions = 0.0
        source = "disabled"

    elif use_manual_override and "national" in MANUAL_EMISSIONS_OVERRIDE:
        total_emissions = MANUAL_EMISSIONS_OVERRIDE["national"]
        source = "user_entered"

    else:
        total_emissions = (
            float(EM_DF["emissions_tCO2"].sum())
            if "emissions_tCO2" in EM_DF.columns
            else 0.0
        )
        source = "calculated"

    data = {
        "total_generation": float(GEN_DF["generation_mwh"].sum()),
        "total_emissions": total_emissions,
        "emissions_source": source,
        "renewable_share": 65.5
    }

    return {"status": "success", "data": data}


# -----------------------------------
# COUNTY INSIGHTS (BUG FIXED HERE)
# -----------------------------------
@app.get(
    "/api/energy/county/{name}",
    response_model=APIResponse,
    tags=["County Data"],
    dependencies=[Depends(verify_api_key)]
)
def county_insights(
    name: str,
    estimate_emissions: bool = True,
    use_manual_override: bool = True
):
    county = counties_data.get(name)
    if not county:
        raise HTTPException(status_code=404, detail="County not found")

    if not estimate_emissions:
        emissions = 0.0
        source = "disabled"

    elif use_manual_override and name in MANUAL_EMISSIONS_OVERRIDE:
        emissions = MANUAL_EMISSIONS_OVERRIDE[name]
        source = "user_entered"

    else:
        emissions = float(
            EM_DF[EM_DF["county"] == name]["emissions_tCO2"].sum()
        ) if "emissions_tCO2" in EM_DF.columns else 0.0
        source = "calculated"

    result = {
        **county,
        "total_emissions": emissions,
        "emissions_source": source
    }

    return {"status": "success", "data": result}


# -----------------------------------
# MANUAL EMISSIONS OVERRIDE ENDPOINT
# -----------------------------------
@app.post(
    "/api/energy/manual-emissions",
    tags=["Manual Input"],
    dependencies=[Depends(verify_api_key)]
)
def set_manual_emissions(
    scope: str,
    value: float
):
    """
    scope:
        'national' or county name (e.g. Nairobi)
    value:
        Emissions in tCO2 entered by user
    """

    if value < 0:
        raise HTTPException(status_code=400, detail="Value must be >= 0")

    MANUAL_EMISSIONS_OVERRIDE[scope] = value

    return {
        "status": "success",
        "message": f"Manual emissions override set for {scope}",
        "value": value
    }


# -----------------------------------
# EXAMPLES
# -----------------------------------
@app.get("/api/energy/examples", tags=["Examples"])
def examples():
    return {
        "checkbox_linking": {
            "enabled": "/api/energy/summary?estimate_emissions=true",
            "disabled": "/api/energy/summary?estimate_emissions=false"
        },
        "manual_override": {
            "set_national": "POST /api/energy/manual-emissions?scope=national&value=123.4",
            "set_county": "POST /api/energy/manual-emissions?scope=Nairobi&value=56.7"
        },
        "audit_flags": [
            "calculated",
            "user_entered",
            "disabled"
        ]
    }
