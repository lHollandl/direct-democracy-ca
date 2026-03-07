"""
Geographic seed data for Direct Democracy Cali.

Populates the State, County, and City reference tables with California data.
Every post, umbrella issue, and solution on the platform is anchored to this
geography, so this data must exist before any civic content can be created.

Safe to run multiple times — all inserts are guarded by existence checks.
Called automatically from main.py on startup when the states table is empty.
"""

from sqlalchemy.orm import Session

from models import City, County, State

CALIFORNIA_COUNTIES = [
    "Alameda", "Alpine", "Amador", "Butte", "Calaveras", "Colusa",
    "Contra Costa", "Del Norte", "El Dorado", "Fresno", "Glenn",
    "Humboldt", "Imperial", "Inyo", "Kern", "Kings", "Lake", "Lassen",
    "Los Angeles", "Madera", "Marin", "Mariposa", "Mendocino", "Merced",
    "Modoc", "Mono", "Monterey", "Napa", "Nevada", "Orange", "Placer",
    "Plumas", "Riverside", "Sacramento", "San Benito", "San Bernardino",
    "San Diego", "San Francisco", "San Joaquin", "San Luis Obispo",
    "San Mateo", "Santa Barbara", "Santa Clara", "Santa Cruz", "Shasta",
    "Sierra", "Siskiyou", "Solano", "Sonoma", "Stanislaus", "Sutter",
    "Tehama", "Trinity", "Tulare", "Tuolumne", "Ventura", "Yolo", "Yuba",
]

# Each entry is (city name, county name it belongs to)
CALIFORNIA_CITIES = [
    ("San Jose",      "Santa Clara"),
    ("San Francisco", "San Francisco"),
    ("Los Angeles",   "Los Angeles"),
    ("San Diego",     "San Diego"),
    ("Sacramento",    "Sacramento"),
    ("Oakland",       "Alameda"),
    ("Fresno",        "Fresno"),
    ("Long Beach",    "Los Angeles"),
    ("Bakersfield",   "Kern"),
    ("Anaheim",       "Orange"),
]


def seed_california(db: Session) -> None:
    """
    Insert California state, all 58 counties, and initial major cities.
    Skips any row that already exists — safe to call on every app startup.
    """
    # --- State ---
    california = db.query(State).filter_by(abbreviation="CA").first()
    if california is None:
        california = State(name="California", abbreviation="CA")
        db.add(california)
        db.flush()  # Assigns california.id without committing, needed for FK below

    # --- Counties ---
    existing_county_names = {
        row.name for row in db.query(County.name).filter_by(state_id=california.id)
    }
    new_counties = [
        County(name=name, state_id=california.id)
        for name in CALIFORNIA_COUNTIES
        if name not in existing_county_names
    ]
    if new_counties:
        db.add_all(new_counties)
        db.flush()  # Assigns county ids before we look them up for cities

    # Build a name → id lookup for all CA counties to resolve city FKs
    county_by_name: dict[str, int] = {
        row.name: row.id
        for row in db.query(County.name, County.id).filter_by(state_id=california.id)
    }

    # --- Cities ---
    # Collect all city names already seeded into CA counties to avoid duplicates
    ca_county_ids = set(county_by_name.values())
    existing_city_names = {
        row.name
        for row in db.query(City).filter(City.county_id.in_(ca_county_ids))
    }

    new_cities = [
        City(name=city_name, county_id=county_by_name[county_name])
        for city_name, county_name in CALIFORNIA_CITIES
        if city_name not in existing_city_names and county_name in county_by_name
    ]
    if new_cities:
        db.add_all(new_cities)

    db.commit()
