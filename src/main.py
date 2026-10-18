import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db import db
from db.photo_upload import router as photo_router
from src import config, telegram
from src.handlers_pet import router as pet_router
from src.handlers_prop import router as prop_router
from src.handlers_user import router as user_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.connect(config.DATABASE_URL)
    bot = asyncio.create_task(telegram.poll_updates()) if config.TELEGRAM_BOT_TOKEN else None
    yield
    if bot is not None:
        bot.cancel()
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
