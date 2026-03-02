from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

import models
from database import engine
from limiter import limiter
from routers import labels, posts, users, votes

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

app.include_router(users.router)
app.include_router(posts.router)
app.include_router(votes.router)
app.include_router(labels.router)


@app.on_event("startup")
def create_tables():
    # Create all tables defined in models.py if they don't already exist.
    # Safe to run on every startup — does nothing if tables are already there.
    models.Base.metadata.create_all(bind=engine)


@app.get("/")
def root():
    return {"message": "Direct Democracy Cali API", "status": "running"}


@app.get("/health")
def health():
    return {"status": "healthy"}
