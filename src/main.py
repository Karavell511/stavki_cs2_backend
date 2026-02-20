from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import admin, auth, bets, streams
from src.core.config import get_settings
from src.core.logging import setup_logging
from src.websocket.chat import router as chat_router

setup_logging()
settings = get_settings()

app = FastAPI(title="Stream Betting Backend", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(streams.router)
app.include_router(bets.router)
app.include_router(admin.router)
app.include_router(chat_router)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}
