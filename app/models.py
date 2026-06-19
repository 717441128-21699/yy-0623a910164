from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, ForeignKey, Text, Date, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class ApiClient(Base):
    __tablename__ = "api_clients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, comment="接入方名称")
    api_key = Column(String(64), unique=True, index=True, nullable=False, comment="API Key")
    api_secret = Column(String(128), default="", comment="API Secret(可选)")
    client_type = Column(String(20), default="clinic", comment="类型: clinic-诊所, vendor-软件商")
    contact_name = Column(String(50), default="")
    contact_phone = Column(String(30), default="")
    contact_email = Column(String(100), default="")
    is_active = Column(Boolean, default=True)
    settings = Column(JSON, default=dict, comment="接入方自定义配置(JSON)")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    callback_configs = relationship("CallbackConfig", back_populates="client")
    logs = relationship("ApiCallLog", back_populates="client")


class CallbackConfig(Base):
    __tablename__ = "callback_configs"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("api_clients.id"), nullable=False)
    event_type = Column(String(50), nullable=False, index=True, comment="事件类型: photo_submitted, compare_generated")
    callback_url = Column(String(500), nullable=False, comment="回调地址")
    secret_token = Column(String(200), default="", comment="回调签名密钥")
    max_retries = Column(Integer, default=3, comment="最大重试次数")
    retry_interval = Column(Integer, default=60, comment="重试间隔(秒)")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    client = relationship("ApiClient", back_populates="callback_configs")
    tasks = relationship("CallbackTask", back_populates="config")


class CallbackTask(Base):
    __tablename__ = "callback_tasks"

    id = Column(Integer, primary_key=True, index=True)
    config_id = Column(Integer, ForeignKey("callback_configs.id"), nullable=False)
    event_type = Column(String(50), nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("api_clients.id"), nullable=True, index=True)
    patient_no = Column(String(50), index=True, default="")
    payload = Column(JSON, nullable=False, comment="回调数据(JSON)")
    status = Column(String(20), default="pending", index=True, comment="pending-待发送, success-成功, failed-失败, retrying-重试中")
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    last_error = Column(Text, default="")
    callback_url = Column(String(500), default="")
    last_sent_at = Column(DateTime(timezone=True), nullable=True)
    next_retry_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    config = relationship("CallbackConfig", back_populates="tasks")


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    patient_no = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(100), default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    records = relationship("VisitRecord", back_populates="patient")
    photos = relationship("Photo", back_populates="patient")


class VisitRecord(Base):
    __tablename__ = "visit_records"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("api_clients.id"), nullable=True)
    visit_date = Column(Date, nullable=False, index=True)
    is_initial = Column(Boolean, default=False)
    notes = Column(Text, default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    patient = relationship("Patient", back_populates="records")
    photos = relationship("Photo", back_populates="visit_record")


class Photo(Base):
    __tablename__ = "photos"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    visit_record_id = Column(Integer, ForeignKey("visit_records.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("api_clients.id"), nullable=True)
    angle = Column(String(50), nullable=False, index=True)
    file_path = Column(String(255), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_url = Column(String(500), default="", comment="公开访问URL")
    file_size = Column(Integer, default=0)
    content_type = Column(String(50), default="")

    brightness = Column(Float, default=0.0)
    sharpness = Column(Float, default=0.0)
    center_offset_x = Column(Float, default=0.0)
    center_offset_y = Column(Float, default=0.0)
    has_occlusion = Column(Boolean, default=False)

    is_too_dark = Column(Boolean, default=False)
    is_blurry = Column(Boolean, default=False)
    is_not_centered = Column(Boolean, default=False)
    is_occluded = Column(Boolean, default=False)
    quality_passed = Column(Boolean, default=True)
    quality_notes = Column(Text, default="")

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    patient = relationship("Patient", back_populates="photos")
    visit_record = relationship("VisitRecord", back_populates="photos")


class ApiCallLog(Base):
    __tablename__ = "api_call_logs"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("api_clients.id"), nullable=True, index=True)
    endpoint = Column(String(200), nullable=False, index=True)
    method = Column(String(20), default="POST")
    api_category = Column(String(30), default="", index=True, comment="接口分类: query, submit, compare, admin, system")
    patient_no = Column(String(50), index=True, default="")
    visit_date = Column(Date, index=True, nullable=True)
    status_code = Column(Integer, default=200, index=True)
    duration_ms = Column(Integer, default=0)
    request_body = Column(Text, default="")
    error_message = Column(Text, default="")
    client_ip = Column(String(50), default="")
    user_agent = Column(String(500), default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    client = relationship("ApiClient", back_populates="logs")


class CompareResult(Base):
    __tablename__ = "compare_results"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("api_clients.id"), nullable=True)
    compare_mode = Column(String(50), nullable=False)
    before_visit_id = Column(Integer, ForeignKey("visit_records.id"), nullable=False)
    after_visit_id = Column(Integer, ForeignKey("visit_records.id"), nullable=False)
    result_file_path = Column(String(255), nullable=False)
    result_file_url = Column(String(500), default="", comment="公开访问URL")
    ai_hint = Column(Text, default="")
    angles_compared = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
