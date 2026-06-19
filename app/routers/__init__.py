from app.routers.photos import router as photos_router
from app.routers.compare import router as compare_router
from app.routers.admin import router as admin_router

__all__ = ["photos_router", "compare_router", "admin_router"]
