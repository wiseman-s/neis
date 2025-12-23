# main.py
import secrets
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict
from datetime import datetime, timedelta

# Local imports
from models import APIResponse
from utils import GEN_DF, EM_DF

# -----------------------------------
# FastAPI app
# -----------------------------------
app = FastAPI(
    title="⚡ NEIS API - National Energy Insights System",
    description=(
        "NEIS is a data-driven platform for accessing Kenya’s national and "
        "county-level energy generation and carbon emissions data. "
        "It supports emissions estimation, renewable energy insights, "
        "and evidence-based climate reporting."
    ),
    version="1.1.0",
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
# API Key storage
# -----------------------------------
API_KEYS: Dict[str, datetime] = {}
KEY_EXPIRATION_MINUTES = 30


@app.get("/api/generate-key", tags=["Authentication"])
def generate_key():
    """
    Generates a new one-time API key valid for 30 minutes.
    """
    new_key = secrets.token_urlsafe(16)
    expires_at = datetime.utcnow() + timedelta(minutes=KEY_EXPIRATION_MINUTES)
    API_KEYS[new_key] = expires_at
    return {
        "api_key": new_key,
        "expires_at": expires_at.isoformat() + "Z"
    }


def verify_api_key(x_api_key: str = Header(...)):
    """
    Verifies API key and removes expired keys.
    """
    now = datetime.utcnow()

    expired_keys = [k for k, v in API_KEYS.items() if v < now]
    for k in expired_keys:
        del API_KEYS[k]

    if x_api_key not in API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid or expired API Key")


# -----------------------------------
# HOME ENDPOINT (Project description)
# -----------------------------------
@app.get("/", tags=["Home"])
def home():
    return {
        "project": "National Energy Insights System (NEIS)",
        "description": (
            "NEIS provides programmatic access to Kenya’s national and "
            "county-level energy generation and carbon emissions data. "
            "The system supports emissions estimation, renewable energy analysis, "
            "and climate reporting for research, policy, and innovation."
        ),
        "version": "1.1.0",
        "documentation": "/docs"
    }


# -----------------------------------
# Prepare county data (generation only)
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
            "total_emissions": 0.0,  # emissions applied conditionally
            "renewable_share": 50.0,  # placeholder
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
def get_national_summary(estimate_emissions: bool = True):
    """
    Returns national energy generation summary.
    Emissions are included ONLY if estimate_emissions=true.
    """

    total_emissions = (
        float(EM_DF["emissions_tCO2"].sum())
        if estimate_emissions and "emissions_tCO2" in EM_DF.columns
        else 0.0
    )

    national_summary = {
        "total_generation": float(GEN_DF["generation_mwh"].sum()),
        "total_emissions": total_emissions,
        "renewable_share": 65.5
    }

    return {"status": "success", "data": national_summary}


# -----------------------------------
# COUNTY DATA
# -----------------------------------
@app.get(
    "/api/energy/county/{name}",
    response_model=APIResponse,
    tags=["County Data"],
    dependencies=[Depends(verify_api_key)]
)
def get_county_data(name: str, estimate_emissions: bool = True):
    """
    Returns energy generation and emissions for a specific county.
    Emissions are zero if estimate_emissions=false.
    """

    county_info = counties_data.get(name)

    if not county_info:
        raise HTTPException(
            status_code=404,
            detail=f"County '{name}' not found."
        )

    result = county_info.copy()

    if estimate_emissions and "emissions_tCO2" in EM_DF.columns:
        result["total_emissions"] = float(
            EM_DF[EM_DF["county"] == name]["emissions_tCO2"].sum()
        )
    else:
        result["total_emissions"] = 0.0

    return {"status": "success", "data": result}


# -----------------------------------
# EXAMPLES
# -----------------------------------
@app.get("/api/energy/examples", response_model=APIResponse, tags=["Examples"])
def get_example_usage():
    return {
        "status": "success",
        "data": {
            "generate_key": "/api/generate-key",
            "national_summary": "/api/energy/summary?estimate_emissions=true",
            "national_no_emissions": "/api/energy/summary?estimate_emissions=false",
            "nairobi_county": "/api/energy/county/Nairobi?estimate_emissions=true"
        },
        "message": (
            "Generate an API key and include it in header 'x-api-key'. "
            "Use estimate_emissions=false to disable emissions calculation."
        )
    }
