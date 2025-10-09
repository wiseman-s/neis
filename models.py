# api/models.py
from pydantic import BaseModel
from typing import List, Optional

class EnergySummary(BaseModel):
    total_generation: float
    total_emissions: float
    renewable_share: float

class BySourceItem(BaseModel):
    source: str
    generation_MWh: float

class CountyEnergy(BaseModel):
    county: str
    total_generation: float
    total_emissions: float
    renewable_share: float
    by_source: Optional[List[BySourceItem]] = []

class APIResponse(BaseModel):
    status: str
    data: Optional[dict] = None
    message: Optional[str] = None
