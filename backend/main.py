from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from limiter import limiter
from routers import labels, posts, users, votes

app = FastAPI(title="Direct Democracy Cali API")

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.include_router(users.router)
app.include_router(posts.router)
app.include_router(votes.router)
app.include_router(labels.router)


@app.get("/")
def root():
    return {"message": "Direct Democracy Cali API", "status": "running"}


@app.get("/health")
def health():
    return {"status": "healthy"}
