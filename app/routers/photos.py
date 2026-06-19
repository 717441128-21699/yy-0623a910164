import base64
import uuid
from pathlib import Path
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas, models
from app.database import get_db
from app.config import settings, PHOTO_DIR, get_photo_public_url
from app.services import quality_checker, callback_service
from app.middleware import get_current_client

router = APIRouter(prefix="/api/photos", tags=["照片管理"])


@router.post("/submit", response_model=schemas.PhotoSubmitResponse, summary="提交复诊照片")
async def submit_photos(
    data: schemas.PhotoSubmitRequest,
    db: Session = Depends(get_db),
    current_client: Optional[models.ApiClient] = Depends(get_current_client)
):
    client_id = current_client.id if current_client else None

    patient = crud.get_or_create_patient(db, data.patient_no, data.patient_name, client_id)
    visit_record = crud.get_or_create_visit_record(
        db, patient.id, data.visit_date, data.is_initial, client_id
    )

    saved_photos = []
    quality_failed_count = 0

    relative_dir = Path(data.patient_no) / data.visit_date.strftime("%Y%m%d")
    patient_dir = PHOTO_DIR / relative_dir
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
        relative_path = f"{relative_dir.as_posix()}/{file_name}"
        file_url = get_photo_public_url(relative_path)

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
            file_url=file_url,
            file_size=len(image_data),
            content_type="image/jpeg",
            quality_result=quality_result,
            client_id=client_id
        )
        saved_photos.append(photo)

    missing_angles = crud.check_missing_angles(db, visit_record.id)

    completeness_dict = {
        "total_required": len(settings.standard_angles),
        "submitted_count": len(saved_photos),
        "missing_angles": missing_angles,
        "quality_passed_count": len(saved_photos) - quality_failed_count,
        "quality_failed_count": quality_failed_count
    }

    completeness = schemas.CompletenessResult(**completeness_dict)

    photo_infos = [schemas.PhotoInfo.model_validate(p) for p in saved_photos]

    callback_service.create_photo_submitted_tasks(
        db=db,
        patient_no=data.patient_no,
        visit_date=data.visit_date,
        completeness=completeness_dict,
        photos=saved_photos,
        client_id=client_id
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


@router.get("/list/{patient_no}/{visit_date}", summary="获取指定复诊日期的照片列表")
async def get_visit_photos(
    patient_no: str,
    visit_date: date,
    db: Session = Depends(get_db),
    current_client: Optional[models.ApiClient] = Depends(get_current_client)
):
    patient = db.query(models.Patient).filter(
        models.Patient.patient_no == patient_no
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
