"""
Geographic reference endpoints — powers the governance level selector in the
post submission form. Users search and pick their city, county, or state from
real California geography data seeded at startup.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import City, County, State

router = APIRouter()


class StateResponse(BaseModel):
    id: int
    name: str
    abbreviation: str

    model_config = {"from_attributes": True}


class CountyResponse(BaseModel):
    id: int
    name: str
    state_id: int

    model_config = {"from_attributes": True}


class CityResponse(BaseModel):
    id: int
    name: str
    county_id: int

    model_config = {"from_attributes": True}


@router.get("/states", response_model=list[StateResponse])
async def get_states(db: Session = Depends(get_db)):
    return db.query(State).order_by(State.name).all()


@router.get("/counties", response_model=list[CountyResponse])
async def get_counties(state_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(County)
    if state_id is not None:
        query = query.filter(County.state_id == state_id)
    return query.order_by(County.name).all()


@router.get("/cities", response_model=list[CityResponse])
async def get_cities(county_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(City)
    if county_id is not None:
        query = query.filter(City.county_id == county_id)
    return query.order_by(City.name).all()
