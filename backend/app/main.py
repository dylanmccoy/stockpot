from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.routers import recipes


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Barebones scaffold: create tables on startup. Swap for Alembic migrations later.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Recipe API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(recipes.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
