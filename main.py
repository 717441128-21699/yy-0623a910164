from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings, COMPARE_DIR, PHOTO_DIR
from app.database import engine, Base
from app.routers import photos_router, compare_router, admin_router

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="正畸复诊拍照对比后端服务，提供照片质量检查、对比图生成和智能提示功能，可无缝嵌入现有口腔管理系统。"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(photos_router)
app.include_router(compare_router)
app.include_router(admin_router)


@app.get("/", tags=["系统"])
async def root():
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "standard_angles": settings.standard_angles
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
