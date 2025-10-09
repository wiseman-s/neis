# api/main.py
import secrets
from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict
from datetime import datetime, timedelta

from .models import APIResponse
from .utils import GEN_DF, EM_DF

# -----------------------------------
# FastAPI app
# -----------------------------------
app = FastAPI(
    title="⚡ NEIS API - National Energy Insights System",
    description="Access Kenya's national and county-level energy generation and emissions data programmatically. Protected with one-time API keys.",
    version="1.1.0",
    contact={"name": "Simon Wanyoike", "email": "symoprof83@gmail.com"}
)

# Allow CORS so frontend can fetch data
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------
# Multi-user API Key storage
# -----------------------------------
API_KEYS: Dict[str, datetime] = {}
KEY_EXPIRATION_MINUTES = 30  # each key is valid for 30 minutes

@app.get("/api/generate-key", tags=["Authentication"])
def generate_key():
    """
    Generates a new one-time API key valid for all users simultaneously.
    """
    new_key = secrets.token_urlsafe(16)
    expires_at = datetime.utcnow() + timedelta(minutes=KEY_EXPIRATION_MINUTES)
    API_KEYS[new_key] = expires_at
    return {"api_key": new_key, "expires_at": expires_at.isoformat() + "Z"}

# -----------------------------------
# Dependency to verify API key
# -----------------------------------
def verify_api_key(x_api_key: str = Header(...)):
    # Clean up expired keys before verification
    now = datetime.utcnow()
    expired_keys = [k for k, v in API_KEYS.items() if v < now]
    for k in expired_keys:
        del API_KEYS[k]

    if x_api_key not in API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid or expired API Key")

# -----------------------------------
# Prepare county data dynamically
# -----------------------------------
counties_data = {}
if 'county' in GEN_DF.columns:
    for county in GEN_DF['county'].dropna().unique():
        gen_total = float(GEN_DF[GEN_DF['county'] == county]['generation_mwh'].sum())
        em_total = float(EM_DF[EM_DF['county'] == county]['emissions_tCO2'].sum()) if 'emissions_tCO2' in EM_DF.columns else 0.0
        by_source = []
        if 'source' in GEN_DF.columns:
            for source, grp in GEN_DF[GEN_DF['county'] == county].groupby('source'):
                by_source.append({"source": source, "generation_MWh": float(grp['generation_mwh'].sum())})
        counties_data[county] = {
            "county": county,
            "total_generation": gen_total,
            "total_emissions": em_total,
            "renewable_share": 50.0,  # placeholder
            "by_source": by_source
        }

# -----------------------------------
# Endpoints
# -----------------------------------
@app.get("/api/energy/summary", response_model=APIResponse, tags=["National Data"], dependencies=[Depends(verify_api_key)])
def get_national_summary():
    """
    Returns overall national energy generation and emissions summary.
    """
    national_summary = {
        "total_generation": float(GEN_DF['generation_mwh'].sum()),
        "total_emissions": float(EM_DF['emissions_tCO2'].sum()) if 'emissions_tCO2' in EM_DF.columns else 0.0,
        "renewable_share": 65.5  # Example static value
    }
    return {"status": "success", "data": national_summary}


@app.get("/api/energy/county/{name}", response_model=APIResponse, tags=["County Data"], dependencies=[Depends(verify_api_key)])
def get_county_data(name: str):
    """
    Returns energy generation and emissions for a specific county.
    Replace `{name}` with the county name.
    """
    county_info = counties_data.get(name)
    if not county_info:
        raise HTTPException(status_code=404, detail=f"County '{name}' not found.")
    return {"status": "success", "data": county_info}


@app.get("/api/energy/examples", response_model=APIResponse, tags=["Examples"])
def get_example_usage():
    """
    Example usage URLs (requires an API key in header 'x-api-key').
    """
    examples = {
        "generate_key": "/api/generate-key",
        "national_summary": "/api/energy/summary",
        "nairobi_county": "/api/energy/county/Nairobi"
    }
    return {
        "status": "success",
        "data": examples,
        "message": "Fetch your API key from `/api/generate-key` and include it in header 'x-api-key'."
    }
