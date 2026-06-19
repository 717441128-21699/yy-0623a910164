from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import List, Optional, Dict, Any


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
    file_url: str = ""
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
    client_id: Optional[int] = None
    client_name: str = ""
    endpoint: str
    method: str
    api_category: str = ""
    patient_no: str
    visit_date: Optional[date]
    status_code: int
    duration_ms: int
    error_message: str
    client_ip: str
    created_at: datetime

    class Config:
        from_attributes = True


class AbnormalPhotoItem(BaseModel):
    id: int
    patient_no: str
    angle: str
    file_url: str = ""
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


class ApiClientBase(BaseModel):
    name: str = Field(..., description="接入方名称")
    client_type: str = Field("clinic", description="类型: clinic-诊所, vendor-软件商")
    contact_name: str = ""
    contact_phone: str = ""
    contact_email: str = ""
    settings: Optional[Dict[str, Any]] = None
    is_active: bool = True


class ApiClientCreate(ApiClientBase):
    pass


class ApiClientUpdate(BaseModel):
    name: Optional[str] = None
    client_type: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None
    settings: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class ApiClientInfo(BaseModel):
    id: int
    name: str
    api_key: str
    client_type: str
    contact_name: str = ""
    contact_phone: str = ""
    contact_email: str = ""
    is_active: bool
    settings: Dict[str, Any] = {}
    created_at: datetime
    updated_at: Optional[datetime] = None
    total_api_calls: int = 0
    total_abnormal_photos: int = 0

    class Config:
        from_attributes = True


class ApiClientListResponse(BaseModel):
    success: bool
    total: int
    clients: List[ApiClientInfo]


class CallbackConfigBase(BaseModel):
    event_type: str = Field(..., description="事件类型: photo_submitted, compare_generated")
    callback_url: str = Field(..., description="回调地址")
    secret_token: str = ""
    max_retries: int = 3
    retry_interval: int = 60
    is_active: bool = True


class CallbackConfigCreate(CallbackConfigBase):
    client_id: int = Field(..., description="接入方ID")


class CallbackConfigUpdate(BaseModel):
    callback_url: Optional[str] = None
    secret_token: Optional[str] = None
    max_retries: Optional[int] = None
    retry_interval: Optional[int] = None
    is_active: Optional[bool] = None


class CallbackConfigInfo(BaseModel):
    id: int
    client_id: int
    client_name: str = ""
    event_type: str
    callback_url: str
    secret_token: str = ""
    max_retries: int
    retry_interval: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CallbackTaskItem(BaseModel):
    id: int
    client_id: Optional[int] = None
    event_type: str
    patient_no: str
    status: str
    retry_count: int
    max_retries: int
    last_error: str
    callback_url: str
    last_sent_at: Optional[datetime] = None
    next_retry_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class CallbackListResponse(BaseModel):
    success: bool
    total: int
    configs: List[CallbackConfigInfo]


class CallbackTaskListResponse(BaseModel):
    success: bool
    total: int
    tasks: List[CallbackTaskItem]


class ClientStatsItem(BaseModel):
    client_id: int
    client_name: str
    client_type: str
    total_api_calls: int
    success_calls: int
    failed_calls: int
    total_photos: int
    abnormal_photos: int
    total_compares: int


class ClientStatsResponse(BaseModel):
    success: bool
    total: int
    stats: List[ClientStatsItem]
