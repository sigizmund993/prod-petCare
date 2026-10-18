from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db import db
from db.migrate import migrate
from db.photo_upload import router as photo_router
from src import config
from src.handlers_community import router as community_router
from src.handlers_message import router as message_router
from src.handlers_notification import router as notification_router
from src.handlers_pet import router as pet_router
from src.handlers_prop import router as prop_router
from src.handlers_user import router as user_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    migrate(config.DATABASE_URL)
    db.connect(config.DATABASE_URL)
    yield
    db.close()


app = FastAPI(title="PetCare API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?" if config.CORS_ALLOW_LOCALHOST else None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(user_router)
app.include_router(pet_router)
app.include_router(prop_router)
app.include_router(photo_router)
app.include_router(notification_router)
app.include_router(community_router)
app.include_router(message_router)
