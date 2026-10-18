from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import models  # Ensure SQLAlchemy models are registered
from app.routes.auth import router as auth_router
from app.routes.password_reset import router as password_reset_router
from app.routes.media import router as media_router
from app.routes.message import router as message_router
from app.routes.notifications import router as notifications_router
from app.routes.relationship import router as relationship_router
from app.routes.websocket import router as websocket_router
import os

app = FastAPI(
    title="LoveChat API",
    description="Private two-person chat application",
    version="0.1.0",
)


FRONTEND_URL = os.getenv("FRONTEND_URL", "")

allowed_origins = [
    "http://localhost:8081",
    "http://127.0.0.1:8081",
]

if FRONTEND_URL:
    allowed_origins.append(FRONTEND_URL)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(password_reset_router)
app.include_router(media_router)
app.include_router(relationship_router)
app.include_router(message_router)
app.include_router(notifications_router)
app.include_router(websocket_router)


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "message": "LoveChat API is running",
    }
