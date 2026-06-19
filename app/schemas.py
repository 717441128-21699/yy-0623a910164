from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import List, Optional


class QualityCheckResult(BaseModel):
    brightness: float = 0.0
    sharpness: float = 0.0
    center_offset_x: float = 0.0
    center_offset_y: float = 0.0
    is_too_dark: bool = False
    is_blurry: bool = False
    is_not_centered: bool = False
    is_occluded: bool = False
    quality_passed: bool = True
    notes: str = ""


class PhotoInfo(BaseModel):
    id: int
    angle: str
    file_name: str
    quality_passed: bool
    is_too_dark: bool
    is_blurry: bool
    is_not_centered: bool
    is_occluded: bool
    quality_notes: str
    created_at: datetime

    class Config:
        from_attributes = True


class PhotoSubmitItem(BaseModel):
    angle: str = Field(..., description="照片角度名称")
    image_base64: Optional[str] = Field(None, description="Base64编码的图片数据")


class PhotoSubmitRequest(BaseModel):
    patient_no: str = Field(..., description="患者编号")
    patient_name: Optional[str] = Field("", description="患者姓名")
    visit_date: date = Field(..., description="复诊日期")
    is_initial: bool = Field(False, description="是否初诊")
    photos: List[PhotoSubmitItem] = Field(..., description="提交的照片列表")


class CompletenessResult(BaseModel):
    total_required: int
    submitted_count: int
    missing_angles: List[str]
    quality_passed_count: int
    quality_failed_count: int


class PhotoSubmitResponse(BaseModel):
    success: bool
    patient_no: str
    visit_date: date
    completeness: CompletenessResult
    photos: List[PhotoInfo]
    message: str = ""


class CompareRequest(BaseModel):
    patient_no: str = Field(..., description="患者编号")
    compare_mode: str = Field(..., description="对比模式: initial_vs_current 或 last_vs_current")
    current_visit_date: date = Field(..., description="本次复诊日期")


class ComparePhotoPair(BaseModel):
    angle: str
    before_photo_url: str
    after_photo_url: str


class CompareResponse(BaseModel):
    success: bool
    patient_no: str
    compare_mode: str
    before_visit_date: date
    after_visit_date: date
    compare_image_url: str
    ai_hint: str
    angles_compared: int
    message: str = ""


class ApiCallLogItem(BaseModel):
    id: int
    endpoint: str
    method: str
    patient_no: str
    visit_date: Optional[date]
    status_code: int
    duration_ms: int
    error_message: str
    created_at: datetime

    class Config:
        from_attributes = True


class AbnormalPhotoItem(BaseModel):
    id: int
    patient_no: str
    angle: str
    visit_date: date
    is_too_dark: bool
    is_blurry: bool
    is_not_centered: bool
    is_occluded: bool
    quality_notes: str
    created_at: datetime


class AdminLogsResponse(BaseModel):
    success: bool
    total: int
    logs: List[ApiCallLogItem]


class AdminAbnormalPhotosResponse(BaseModel):
    success: bool
    total: int
    photos: List[AbnormalPhotoItem]


class StatsResponse(BaseModel):
    success: bool
    total_patients: int
    total_photos: int
    total_compares: int
    total_api_calls: int
    abnormal_photo_count: int
