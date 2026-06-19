from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas, models
from app.database import get_db

router = APIRouter(prefix="/api/admin", tags=["管理员接口"])


@router.get("/logs", response_model=schemas.AdminLogsResponse, summary="获取接口调用记录")
async def get_api_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    patient_no: Optional[str] = None,
    endpoint: Optional[str] = None,
    status_code: Optional[int] = Query(None, description="精确状态码(如200)或状态类别(如2表示2xx, 4表示4xx)"),
    client_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    api_category: Optional[str] = Query(None, description="接口分类: query, submit, compare, admin, system"),
    db: Session = Depends(get_db)
):
    logs = crud.get_api_logs(
        db, skip=skip, limit=limit, patient_no=patient_no, endpoint=endpoint,
        status_code=status_code, client_id=client_id,
        date_from=date_from, date_to=date_to, api_category=api_category
    )
    total = crud.count_api_logs(
        db, patient_no=patient_no, endpoint=endpoint, status_code=status_code,
        client_id=client_id, date_from=date_from, date_to=date_to,
        api_category=api_category
    )

    log_items = []
    for log in logs:
        client_name = log.client.name if log.client else ""
        item_data = schemas.ApiCallLogItem.model_validate(log).model_dump()
        item_data["client_name"] = client_name
        log_items.append(schemas.ApiCallLogItem(**item_data))

    return schemas.AdminLogsResponse(
        success=True,
        total=total,
        logs=log_items
    )


@router.get("/abnormal-photos", response_model=schemas.AdminAbnormalPhotosResponse, summary="获取异常照片清单")
async def get_abnormal_photos(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    client_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    photos = crud.get_abnormal_photos(db, skip=skip, limit=limit, client_id=client_id)
    total = crud.count_abnormal_photos(db, client_id=client_id)

    photo_items = []
    for photo in photos:
        visit_record = db.query(models.VisitRecord).filter(
            models.VisitRecord.id == photo.visit_record_id
        ).first()
        patient = db.query(models.Patient).filter(
            models.Patient.id == photo.patient_id
        ).first()

        photo_items.append(schemas.AbnormalPhotoItem(
            id=photo.id,
            patient_no=patient.patient_no if patient else "",
            angle=photo.angle,
            file_url=photo.file_url,
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
        photos=photo_items
    )


@router.get("/stats", response_model=schemas.StatsResponse, summary="获取全局统计数据")
async def get_statistics(
    client_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    stats = crud.get_stats(db, client_id=client_id)
    return schemas.StatsResponse(
        success=True,
        total_patients=stats["total_patients"],
        total_photos=stats["total_photos"],
        total_compares=stats["total_compares"],
        total_api_calls=stats["total_api_calls"],
        abnormal_photo_count=stats["abnormal_photo_count"]
    )


@router.get("/client-stats", response_model=schemas.ClientStatsResponse, summary="按接入方维度统计")
async def get_client_statistics(db: Session = Depends(get_db)):
    stats_list = crud.get_client_stats(db)
    items = [schemas.ClientStatsItem(**s) for s in stats_list]
    return schemas.ClientStatsResponse(
        success=True,
        total=len(items),
        stats=items
    )
