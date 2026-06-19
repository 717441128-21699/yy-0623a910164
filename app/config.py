from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    app_name: str = "正畸复诊拍照对比服务"
    app_version: str = "1.0.0"
    
    database_url: str = "sqlite:///./data/ortho_service.db"
    
    photo_storage_path: str = "./data/photos"
    compare_output_path: str = "./data/compare_results"
    
    max_upload_size: int = 10 * 1024 * 1024
    allowed_image_types: list = ["image/jpeg", "image/png", "image/jpg"]
    
    quality_brightness_threshold: int = 50
    quality_blur_threshold: float = 100.0
    
    standard_angles: list = [
        "正面面相",
        "侧面面相",
        "45°侧面面相",
        "口内正面像",
        "口内左侧面像",
        "口内右侧面像",
        "上颌牙合面像",
        "下颌牙合面像",
    ]

    class Config:
        env_file = ".env"


settings = Settings()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PHOTO_DIR = DATA_DIR / "photos"
COMPARE_DIR = DATA_DIR / "compare_results"

PHOTO_DIR.mkdir(parents=True, exist_ok=True)
COMPARE_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)
