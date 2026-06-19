from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, ForeignKey, Text, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


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
    angle = Column(String(50), nullable=False, index=True)
    file_path = Column(String(255), nullable=False)
    file_name = Column(String(255), nullable=False)
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
    endpoint = Column(String(200), nullable=False, index=True)
    method = Column(String(20), default="POST")
    patient_no = Column(String(50), index=True, default="")
    visit_date = Column(Date, index=True, nullable=True)
    status_code = Column(Integer, default=200)
    duration_ms = Column(Integer, default=0)
    request_body = Column(Text, default="")
    error_message = Column(Text, default="")
    client_ip = Column(String(50), default="")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class CompareResult(Base):
    __tablename__ = "compare_results"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False)
    compare_mode = Column(String(50), nullable=False)
    before_visit_id = Column(Integer, ForeignKey("visit_records.id"), nullable=False)
    after_visit_id = Column(Integer, ForeignKey("visit_records.id"), nullable=False)
    result_file_path = Column(String(255), nullable=False)
    ai_hint = Column(Text, default="")
    angles_compared = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
