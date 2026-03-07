import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from database import SessionLocal
from limiter import limiter
from routers import auth, labels, locations, posts, solutions, umbrella_issues, users, votes
from seed_data import seed_california
import models

logger = logging.getLogger(__name__)

app = FastAPI(title="Direct Democracy Cali API")

# Allow the Next.js dev server to call this API during local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(posts.router)
app.include_router(votes.router)
app.include_router(labels.router)
app.include_router(locations.router)
app.include_router(solutions.router)
app.include_router(umbrella_issues.router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Log the full error server-side so it can be debugged without ever
    # exposing stack traces, database errors, or internal details to clients.
    # Constitution §7: internal error details must never reach the client.
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please try again."},
    )


@app.on_event("startup")
def startup():
    # Schema is now managed by Alembic — run 'alembic upgrade head' before starting
    # the server. create_all is NOT called here; Alembic owns all schema changes.

    # Seed California geographic reference data if the states table is empty.
    db = SessionLocal()
    try:
        if db.query(models.State).count() == 0:
            seed_california(db)
    finally:
        db.close()


@app.get("/")
def root():
    return {"message": "Direct Democracy Cali API", "status": "running"}


@app.get("/health")
def health():
    return {"status": "healthy"}
