from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db import db
from src import config
from src.handlers_pet import router as pet_router
from src.handlers_prop import router as prop_router
from src.handlers_user import router as user_router

from db.photo_upload import router as photo_router

from pathlib import Path
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="PetCare API", lifespan=lifespan)
PHOTO_DIR = Path(__file__).resolve().parent.parent / "db" / "photo_pets"

app.mount(
    "/photos",
    StaticFiles(directory=str(PHOTO_DIR)),
    name="photos",
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    db.connect(config.DATABASE_URL)
    yield
    db.close()


app = FastAPI(title="PetCare API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.CORS_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user_router)
app.include_router(pet_router)
app.include_router(prop_router)
app.include_router(photo_router)
