# main.py
import secrets
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict
from datetime import datetime, timedelta

from models import APIResponse
from utils import GEN_DF, EM_DF

# -----------------------------------
# TAG METADATA (THIS FIXES VISIBILITY)
# -----------------------------------
tags_metadata = [
    {
        "name": "Overview",
        "description": (
            "National Energy Insights System (NEIS) is an API-first platform for "
            "analyzing Kenya’s national and county-level energy generation and "
            "carbon emissions. The system supports automatic estimation, "
            "manual overrides, and audit flags for transparent reporting."
        ),
    },
    {
        "name": "National Data",
        "description": (
            "Provides national-level energy generation and emissions summaries. "
            "Emissions calculations are controlled by a frontend checkbox."
        ),
    },
    {
        "name": "County Data",
        "description": (
            "County-level energy insights. Emissions are conditionally calculated "
            "based on user selection and may be manually overridden."
        ),
    },
    {
        "name": "Manual Input",
        "description": (
            "Endpoints allowing users to manually override calculated emissions. "
            "Overrides are tracked using audit flags."
        ),
    },
    {
        "name": "Authentication",
        "description": "Generate and validate time-limited API keys."
    },
]

# -----------------------------------
# FASTAPI APP
# -----------------------------------
app = FastAPI(
    title="⚡ National Energy Insights System (NEIS)",
    description=(
        "A transparent, auditable system for national and county-level "
        "energy and emissions intelligence in Kenya."
    ),
    version="1.2.1",
    openapi_tags=tags_metadata,
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
# API KEY MANAGEMENT
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
# OVERVIEW (VISIBLE AT / AND /DOCS)
# -----------------------------------
@app.get("/", tags=["Overview"])
def overview():
    return {
        "system": "National Energy Insights System (NEIS)",
        "description": (
            "NEIS integrates national datasets with user-entered inputs to deliver "
            "transparent energy generation and carbon emissions intelligence. "
            "Users can enable or disable automatic emissions estimation, "
            "manually override values, and audit the origin of reported figures."
        ),
        "features": [
            "Automatic emissions estimation",
            "Manual emissions override",
            "County & national insights",
            "Audit flags for transparency",
            "API-first design"
        ],
        "documentation": "/docs"
    }


# -----------------------------------
# IN-MEMORY MANUAL OVERRIDES
# -----------------------------------
MANUAL_EMISSIONS_OVERRIDE: Dict[str, float] = {}

# -----------------------------------
# COUNTY GENERATION DATA (NO EMISSIONS)
# -----------------------------------
counties_data = {}

if "county" in GEN_DF.columns:
    for county in GEN_DF["county"].dropna().unique():
        counties_data[county] = {
            "county": county,
            "total_generation": float(
                GEN_DF[GEN_DF["county"] == county]["generation_mwh"].sum()
            ),
            "by_source": [
                {
                    "source": src,
                    "generation_MWh": float(grp["generation_mwh"].sum())
                }
                for src, grp in GEN_DF[GEN_DF["county"] == county].groupby("source")
            ] if "source" in GEN_DF.columns else []
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
def national_summary(estimate_emissions: bool = True, use_manual_override: bool = True):

    if not estimate_emissions:
        emissions = 0.0
        source = "disabled"

    elif use_manual_override and "national" in MANUAL_EMISSIONS_OVERRIDE:
        emissions = MANUAL_EMISSIONS_OVERRIDE["national"]
        source = "user_entered"

    else:
        emissions = float(EM_DF["emissions_tCO2"].sum()) if "emissions_tCO2" in EM_DF.columns else 0.0
        source = "calculated"

    return {
        "status": "success",
        "data": {
            "total_generation": float(GEN_DF["generation_mwh"].sum()),
            "total_emissions": emissions,
            "emissions_source": source,
            "renewable_share": 65.5
        }
    }


# -----------------------------------
# COUNTY INSIGHTS (FIXED)
# -----------------------------------
@app.get(
    "/api/energy/county/{name}",
    response_model=APIResponse,
    tags=["County Data"],
    dependencies=[Depends(verify_api_key)]
)
def county_insights(name: str, estimate_emissions: bool = True, use_manual_override: bool = True):

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

    return {
        "status": "success",
        "data": {
            **county,
            "total_emissions": emissions,
            "emissions_source": source
        }
    }


# -----------------------------------
# MANUAL EMISSIONS OVERRIDE
# -----------------------------------
@app.post(
    "/api/energy/manual-emissions",
    tags=["Manual Input"],
    dependencies=[Depends(verify_api_key)]
)
def set_manual_emissions(scope: str, value: float):
    if value < 0:
        raise HTTPException(status_code=400, detail="Value must be non-negative")

    MANUAL_EMISSIONS_OVERRIDE[scope] = value
    return {
        "status": "success",
        "scope": scope,
        "value": value
    }
