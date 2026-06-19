import asyncio
import os
import shutil
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings, COMPARE_DIR, PHOTO_DIR
from app.database import engine, Base, SessionLocal
from app.routers import photos_router, compare_router, admin_router, clients_router, callbacks_router
from app.middleware import ApiLoggingMiddleware
from app.services import callback_service
from app import crud, schemas


def init_default_client():
    db = SessionLocal()
    try:
        default_client = crud.get_or_create_default_client(db)
        if default_client:
            print(f"已加载默认接入方: {default_client.name}, ID={default_client.id}, is_default={default_client.is_default}")
        clients = crud.list_api_clients(db, limit=1)
        if not clients:
            print("警告：未找到任何接入方")
    except Exception as e:
        print(f"初始化默认接入方失败: {e}")
    finally:
        db.close()


_callback_task = None


async def callback_worker():
    while True:
        try:
            await callback_service.process_pending_tasks()
        except Exception:
            pass
        await asyncio.sleep(30)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _callback_task
    Base.metadata.create_all(bind=engine)
    init_default_client()
    _callback_task = asyncio.create_task(callback_worker())
    yield
    if _callback_task:
        _callback_task.cancel()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="正畸复诊拍照对比后端服务 v1.3.0：提供照片质量检查、对比图生成、智能提示、接入方(API Key)隔离与管理、配额限流(含照片批量额度)、回调通知(含详细执行记录)，无Key请求归入默认接入方，可无缝嵌入现有口腔管理系统。",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(ApiLoggingMiddleware)

app.mount(settings.photo_url_prefix, StaticFiles(directory=str(PHOTO_DIR)), name="photos")
app.mount(settings.compare_url_prefix, StaticFiles(directory=str(COMPARE_DIR)), name="compare")

app.include_router(photos_router)
app.include_router(compare_router)
app.include_router(admin_router)
app.include_router(clients_router)
app.include_router(callbacks_router)


@app.get("/", tags=["系统"])
async def root():
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "require_api_key": settings.require_api_key,
        "standard_angles": settings.standard_angles,
        "features": [
            "access_control: API Key 接入方隔离",
            "data_isolation: 患者/照片/对比按接入方隔离",
            "quota_control: 每日API/照片配额 + 对比开关 + 照片批量额度检查",
            "callback_notifications: 详细执行记录 + 同步/异步重试",
            "public_urls: 静态公开URL访问照片与对比图",
            "admin_dashboard: 接入方维度统计 + 调用/回调/异常详情",
            "default_client: 无Key请求归入默认接入方"
        ]
    }


@app.get("/health", tags=["系统"])
async def health_check():
    return {"status": "healthy"}


@app.get("/api/standard-angles", tags=["系统"])
async def get_standard_angles():
    return {
        "success": True,
        "angles": settings.standard_angles
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
