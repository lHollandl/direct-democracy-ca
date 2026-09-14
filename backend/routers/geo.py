"""Geography and communities (ARCHITECTURE.md §6, Foundation)."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from backend.deps import SessionDep
from backend.repositories import geography as geo_repo
from backend.repositories import officials as officials_repo
from backend.services import community as community_service

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
        for c in await geo_repo.all_counties(session)
    ]


@router.get("/geo/counties/{county_id}/cities", response_model=list[CityOut])
async def cities(county_id: int, session: SessionDep) -> list[CityOut]:
    return [
        CityOut(id=c.id, name=c.name, county_id=c.county_id, incorporated=c.incorporated)
        for c in await geo_repo.cities_in_county(session, county_id)
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
    resolved = await community_service.resolve(session, level, entity_id)
    return CommunityOut(
        **resolved.as_dict(),
        active_users=await community_service.active_user_count(session, level, entity_id),
        active_user_definition=await community_service.active_user_definition(session),
        officials=[
            OfficialOut(
                id=o.id,
                office=o.office,
                holder_name=o.holder_name,
                email=o.email,
                source=o.source,
            )
            for o in await officials_repo.for_community(session, level, entity_id)
        ],
    )


@router.get("/communities/{level}/{entity_id}/officials", response_model=list[OfficialOut])
async def officials(level: str, entity_id: int, session: SessionDep) -> list[OfficialOut]:
    await community_service.resolve(session, level, entity_id)
    return [
        OfficialOut(
            id=o.id, office=o.office, holder_name=o.holder_name, email=o.email, source=o.source
        )
        for o in await officials_repo.for_community(session, level, entity_id)
    ]
