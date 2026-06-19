import base64
import os
import time
import uuid
from pathlib import Path
from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db
from app.config import settings, PHOTO_DIR
from app.services import quality_checker

router = APIRouter(prefix="/api/photos", tags=["照片管理"])


@router.post("/submit", response_model=schemas.PhotoSubmitResponse, summary="提交复诊照片")
async def submit_photos(request: Request, data: schemas.PhotoSubmitRequest, db: Session = Depends(get_db)):
    start_time = time.time()
    client_ip = request.client.host if request.client else ""

    try:
        patient = crud.get_or_create_patient(db, data.patient_no, data.patient_name)
        visit_record = crud.get_or_create_visit_record(
            db, patient.id, data.visit_date, data.is_initial
        )

        saved_photos = []
        quality_failed_count = 0

        patient_dir = PHOTO_DIR / data.patient_no / data.visit_date.strftime("%Y%m%d")
        patient_dir.mkdir(parents=True, exist_ok=True)

        for photo_item in data.photos:
            if not photo_item.image_base64:
                continue

            try:
                image_data = base64.b64decode(photo_item.image_base64)
            except Exception:
                continue

            file_ext = ".jpg"
            file_name = f"{photo_item.angle}_{uuid.uuid4().hex[:8]}{file_ext}"
            file_path = patient_dir / file_name

            with open(file_path, "wb") as f:
                f.write(image_data)

            quality_result = quality_checker.analyze(str(file_path), photo_item.angle)

            if not quality_result["quality_passed"]:
                quality_failed_count += 1

            photo = crud.add_photo(
                db=db,
                patient_id=patient.id,
                visit_record_id=visit_record.id,
                angle=photo_item.angle,
                file_path=str(file_path),
                file_name=file_name,
                file_size=len(image_data),
                content_type="image/jpeg",
                quality_result=quality_result
            )
            saved_photos.append(photo)

        missing_angles = crud.check_missing_angles(db, visit_record.id)

        completeness = schemas.CompletenessResult(
            total_required=len(settings.standard_angles),
            submitted_count=len(saved_photos),
            missing_angles=missing_angles,
            quality_passed_count=len(saved_photos) - quality_failed_count,
            quality_failed_count=quality_failed_count
        )

        photo_infos = [schemas.PhotoInfo.model_validate(p) for p in saved_photos]

        duration_ms = int((time.time() - start_time) * 1000)
        crud.log_api_call(
            db=db,
            endpoint="/api/photos/submit",
            method="POST",
            patient_no=data.patient_no,
            visit_date=data.visit_date,
            status_code=200,
            duration_ms=duration_ms,
            client_ip=client_ip
        )

        message = "照片提交成功"
        if missing_angles:
            message += f"，缺少 {len(missing_angles)} 个标准角度"
        if quality_failed_count > 0:
            message += f"，有 {quality_failed_count} 张照片质量待改善"

        return schemas.PhotoSubmitResponse(
            success=True,
            patient_no=data.patient_no,
            visit_date=data.visit_date,
            completeness=completeness,
            photos=photo_infos,
            message=message
        )

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        crud.log_api_call(
            db=db,
            endpoint="/api/photos/submit",
            method="POST",
            patient_no=data.patient_no if data else "",
            visit_date=data.visit_date if data else None,
            status_code=500,
            duration_ms=duration_ms,
            error_message=str(e),
            client_ip=client_ip
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list/{patient_no}/{visit_date}", summary="获取指定复诊日期的照片列表")
async def get_visit_photos(patient_no: str, visit_date: date, db: Session = Depends(get_db)):
    patient = db.query(crud.models.Patient).filter(
        crud.models.Patient.patient_no == patient_no
    ).first()

    if not patient:
        raise HTTPException(status_code=404, detail="患者不存在")

    visit_record = crud.get_visit_by_date(db, patient.id, visit_date)
    if not visit_record:
        raise HTTPException(status_code=404, detail="复诊记录不存在")

    photos = crud.get_photos_by_visit(db, visit_record.id)

    return {
        "success": True,
        "patient_no": patient_no,
        "visit_date": visit_date,
        "photos": [schemas.PhotoInfo.model_validate(p) for p in photos]
    }
