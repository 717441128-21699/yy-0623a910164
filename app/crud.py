from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import date, datetime
from typing import List, Optional

from app import models, schemas
from app.config import settings


def get_or_create_patient(db: Session, patient_no: str, patient_name: str = "") -> models.Patient:
    patient = db.query(models.Patient).filter(models.Patient.patient_no == patient_no).first()
    if not patient:
        patient = models.Patient(patient_no=patient_no, name=patient_name)
        db.add(patient)
        db.commit()
        db.refresh(patient)
    elif patient_name and patient.name != patient_name:
        patient.name = patient_name
        db.commit()
        db.refresh(patient)
    return patient


def get_or_create_visit_record(db: Session, patient_id: int, visit_date: date,
                                is_initial: bool = False) -> models.VisitRecord:
    record = db.query(models.VisitRecord).filter(
        models.VisitRecord.patient_id == patient_id,
        models.VisitRecord.visit_date == visit_date
    ).first()

    if not record:
        record = models.VisitRecord(
            patient_id=patient_id,
            visit_date=visit_date,
            is_initial=is_initial
        )
        db.add(record)
        db.commit()
        db.refresh(record)
    elif is_initial and not record.is_initial:
        record.is_initial = True
        db.commit()
        db.refresh(record)

    return record


def get_visit_by_date(db: Session, patient_id: int, visit_date: date) -> Optional[models.VisitRecord]:
    return db.query(models.VisitRecord).filter(
        models.VisitRecord.patient_id == patient_id,
        models.VisitRecord.visit_date == visit_date
    ).first()


def get_initial_visit(db: Session, patient_id: int) -> Optional[models.VisitRecord]:
    return db.query(models.VisitRecord).filter(
        models.VisitRecord.patient_id == patient_id,
        models.VisitRecord.is_initial == True
    ).order_by(models.VisitRecord.visit_date.asc()).first()


def get_previous_visit(db: Session, patient_id: int, current_date: date) -> Optional[models.VisitRecord]:
    return db.query(models.VisitRecord).filter(
        models.VisitRecord.patient_id == patient_id,
        models.VisitRecord.visit_date < current_date
    ).order_by(desc(models.VisitRecord.visit_date)).first()


def add_photo(db: Session, patient_id: int, visit_record_id: int,
              angle: str, file_path: str, file_name: str,
              file_size: int, content_type: str,
              quality_result: dict) -> models.Photo:
    photo = models.Photo(
        patient_id=patient_id,
        visit_record_id=visit_record_id,
        angle=angle,
        file_path=file_path,
        file_name=file_name,
        file_size=file_size,
        content_type=content_type,
        brightness=quality_result["brightness"],
        sharpness=quality_result["sharpness"],
        center_offset_x=quality_result["center_offset_x"],
        center_offset_y=quality_result["center_offset_y"],
        has_occlusion=quality_result["is_occluded"],
        is_too_dark=quality_result["is_too_dark"],
        is_blurry=quality_result["is_blurry"],
        is_not_centered=quality_result["is_not_centered"],
        is_occluded=quality_result["is_occluded"],
        quality_passed=quality_result["quality_passed"],
        quality_notes=quality_result["notes"]
    )
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return photo


def get_photos_by_visit(db: Session, visit_record_id: int) -> List[models.Photo]:
    return db.query(models.Photo).filter(
        models.Photo.visit_record_id == visit_record_id
    ).all()


def log_api_call(db: Session, endpoint: str, method: str, patient_no: str = "",
                 visit_date: Optional[date] = None, status_code: int = 200,
                 duration_ms: int = 0, request_body: str = "",
                 error_message: str = "", client_ip: str = "") -> models.ApiCallLog:
    log = models.ApiCallLog(
        endpoint=endpoint,
        method=method,
        patient_no=patient_no,
        visit_date=visit_date,
        status_code=status_code,
        duration_ms=duration_ms,
        request_body=request_body,
        error_message=error_message,
        client_ip=client_ip
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def get_api_logs(db: Session, skip: int = 0, limit: int = 100,
                 patient_no: str = None, endpoint: str = None) -> List[models.ApiCallLog]:
    query = db.query(models.ApiCallLog)
    if patient_no:
        query = query.filter(models.ApiCallLog.patient_no == patient_no)
    if endpoint:
        query = query.filter(models.ApiCallLog.endpoint.contains(endpoint))
    return query.order_by(desc(models.ApiCallLog.created_at)).offset(skip).limit(limit).all()


def get_abnormal_photos(db: Session, skip: int = 0, limit: int = 100) -> List[models.Photo]:
    return db.query(models.Photo).filter(
        models.Photo.quality_passed == False
    ).order_by(desc(models.Photo.created_at)).offset(skip).limit(limit).all()


def get_stats(db: Session) -> dict:
    total_patients = db.query(models.Patient).count()
    total_photos = db.query(models.Photo).count()
    total_compares = db.query(models.CompareResult).count()
    total_api_calls = db.query(models.ApiCallLog).count()
    abnormal_photos = db.query(models.Photo).filter(
        models.Photo.quality_passed == False
    ).count()

    return {
        "total_patients": total_patients,
        "total_photos": total_photos,
        "total_compares": total_compares,
        "total_api_calls": total_api_calls,
        "abnormal_photo_count": abnormal_photos
    }


def add_compare_result(db: Session, patient_id: int, compare_mode: str,
                       before_visit_id: int, after_visit_id: int,
                       result_file_path: str, ai_hint: str,
                       angles_compared: int) -> models.CompareResult:
    result = models.CompareResult(
        patient_id=patient_id,
        compare_mode=compare_mode,
        before_visit_id=before_visit_id,
        after_visit_id=after_visit_id,
        result_file_path=result_file_path,
        ai_hint=ai_hint,
        angles_compared=angles_compared
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return result


def check_missing_angles(db: Session, visit_record_id: int) -> List[str]:
    photos = get_photos_by_visit(db, visit_record_id)
    existing_angles = [p.angle for p in photos]
    missing = [angle for angle in settings.standard_angles if angle not in existing_angles]
    return missing
