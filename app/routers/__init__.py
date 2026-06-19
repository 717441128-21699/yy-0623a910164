from app.routers.photos import router as photos_router
from app.routers.compare import router as compare_router
from app.routers.admin import router as admin_router
from app.routers.clients import router as clients_router
from app.routers.callbacks import router as callbacks_router

__all__ = ["photos_router", "compare_router", "admin_router", "clients_router", "callbacks_router"]
