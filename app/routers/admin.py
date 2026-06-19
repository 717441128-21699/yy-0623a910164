from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from app import crud, schemas, models
from app.database import get_db

router = APIRouter(prefix="/api/admin", tags=["管理员接口"])


@router.get("/logs", response_model=schemas.AdminLogsResponse, summary="获取接口调用记录")
async def get_api_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    patient_no: Optional[str] = None,
    endpoint: Optional[str] = None,
    db: Session = Depends(get_db)
):
    logs = crud.get_api_logs(db, skip=skip, limit=limit, patient_no=patient_no, endpoint=endpoint)

    total = db.query(models.ApiCallLog)
    if patient_no:
        total = total.filter(models.ApiCallLog.patient_no == patient_no)
    if endpoint:
        total = total.filter(models.ApiCallLog.endpoint.contains(endpoint))
    total_count = total.count()

    return schemas.AdminLogsResponse(
        success=True,
        total=total_count,
        logs=[schemas.ApiCallLogItem.model_validate(log) for log in logs]
    )


@router.get("/abnormal-photos", response_model=schemas.AdminAbnormalPhotosResponse, summary="获取异常照片清单")
async def get_abnormal_photos(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db)
):
    photos = crud.get_abnormal_photos(db, skip=skip, limit=limit)

    total = db.query(models.Photo).filter(models.Photo.quality_passed == False).count()

    abnormal_items = []
    for photo in photos:
        visit_record = db.query(models.VisitRecord).filter(
            models.VisitRecord.id == photo.visit_record_id
        ).first()
        patient = db.query(models.Patient).filter(
            models.Patient.id == photo.patient_id
        ).first()

        abnormal_items.append(schemas.AbnormalPhotoItem(
            id=photo.id,
            patient_no=patient.patient_no if patient else "",
            angle=photo.angle,
            visit_date=visit_record.visit_date if visit_record else None,
            is_too_dark=photo.is_too_dark,
            is_blurry=photo.is_blurry,
            is_not_centered=photo.is_not_centered,
            is_occluded=photo.is_occluded,
            quality_notes=photo.quality_notes,
            created_at=photo.created_at
        ))

    return schemas.AdminAbnormalPhotosResponse(
        success=True,
        total=total,
        photos=abnormal_items
    )


@router.get("/stats", response_model=schemas.StatsResponse, summary="获取统计数据")
async def get_statistics(db: Session = Depends(get_db)):
    stats = crud.get_stats(db)
    return schemas.StatsResponse(
        success=True,
        total_patients=stats["total_patients"],
        total_photos=stats["total_photos"],
        total_compares=stats["total_compares"],
        total_api_calls=stats["total_api_calls"],
        abnormal_photo_count=stats["abnormal_photo_count"]
    )
