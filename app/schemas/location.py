
from pydantic import BaseModel, ConfigDict, Field


class CoordinatesResponse(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class NearbyAttractionResponse(BaseModel):
    name: str
    type: str
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    distance_km: float = Field(ge=0)


class NearbyAttractionsResponse(BaseModel):
    hotel_id: int
    radius_m: int
    attractions: list[NearbyAttractionResponse]
