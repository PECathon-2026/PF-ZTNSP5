from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.health import router as health_router
from app.api.missions import router as missions_router
from app.api.repositories import router as repositories_router
from app.api.guild import router as guild_router
from app.api.events import router as events_router
from app.api.history import router as history_router
from app.api.recovery import router as recovery_router
from app.settings import get_settings
from app.storage.database import get_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle handler."""
    settings = get_settings()
    settings.ensure_directories()
    db = get_database()
    await db.init_db()
    from app.services import guild_service
    controller = guild_service.get_guild_controller()
    if controller.db is not db:
        controller = guild_service.GuildController(database=db)
        guild_service._controller = controller
    await controller.store.recover()
    from app.services.patch_application import PatchApplication
    await PatchApplication(controller).recover_pending()
    try:
        yield
    finally:
        await controller.close()


app = FastAPI(
    title="KAGE AI / DevPilot Guild",
    description="Autonomous Multi-Agent AI Engineering Guild Backend (PS-001)",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API Routers
app.include_router(health_router)
app.include_router(missions_router)
app.include_router(repositories_router)
app.include_router(guild_router)
app.include_router(events_router)
app.include_router(history_router)
app.include_router(recovery_router)

# Mount frontend static files if directory exists
frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"
if frontend_dir.exists() and (frontend_dir / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=settings.debug)
