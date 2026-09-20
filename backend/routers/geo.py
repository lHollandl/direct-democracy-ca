"""Geography and communities (ARCHITECTURE.md §6, Foundation)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from backend.deps import SessionDep
from backend.services import communities as community_service
from backend.services import geography as geography_service

router = APIRouter(tags=["geography"])


class CountyOut(BaseModel):
    id: int
    name: str
    fips: str


class CityOut(BaseModel):
    id: int
    name: str
    county_id: int
    incorporated: bool


@router.get("/geo/counties", response_model=list[CountyOut])
async def counties(session: SessionDep) -> list[CountyOut]:
    return [
        CountyOut(id=c.id, name=c.name, fips=c.fips)
        for c in await geography_service.all_counties(session)
    ]


@router.get("/geo/counties/{county_id}/cities", response_model=list[CityOut])
async def cities(county_id: int, session: SessionDep) -> list[CityOut]:
    return [
        CityOut(id=c.id, name=c.name, county_id=c.county_id, incorporated=c.incorporated)
        for c in await geography_service.cities_in_county(session, county_id)
    ]


class OfficialOut(BaseModel):
    id: int
    office: str
    holder_name: str | None
    email: str
    source: str


class CommunityOut(BaseModel):
    level: str
    entity_id: int
    name: str
    label: str
    active_users: int
    active_user_definition: str
    officials: list[OfficialOut]


@router.get("/communities/{level}/{entity_id}", response_model=CommunityOut)
async def community(level: str, entity_id: int, session: SessionDep) -> CommunityOut:
    return CommunityOut(**await community_service.detail_view(session, level, entity_id))


@router.get("/communities/{level}/{entity_id}/officials", response_model=list[OfficialOut])
async def officials(level: str, entity_id: int, session: SessionDep) -> list[OfficialOut]:
    return [
        OfficialOut(**o) for o in await community_service.officials_list(session, level, entity_id)
    ]
