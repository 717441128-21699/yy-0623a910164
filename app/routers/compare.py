import time
from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app import crud, schemas, models
from app.database import get_db
from app.services import compare_generator, hint_generator

router = APIRouter(prefix="/api/compare", tags=["对比分析"])


@router.post("/generate", response_model=schemas.CompareResponse, summary="生成对比图")
async def generate_compare(request: Request, data: schemas.CompareRequest, db: Session = Depends(get_db)):
    start_time = time.time()
    client_ip = request.client.host if request.client else ""

    try:
        patient = db.query(models.Patient).filter(
            models.Patient.patient_no == data.patient_no
        ).first()

        if not patient:
            raise HTTPException(status_code=404, detail="患者不存在")

        current_visit = crud.get_visit_by_date(db, patient.id, data.current_visit_date)
        if not current_visit:
            raise HTTPException(status_code=404, detail="本次复诊记录不存在")

        before_visit = None
        if data.compare_mode == "initial_vs_current":
            before_visit = crud.get_initial_visit(db, patient.id)
            if not before_visit:
                raise HTTPException(status_code=404, detail="未找到初诊记录")
        elif data.compare_mode == "last_vs_current":
            before_visit = crud.get_previous_visit(db, patient.id, data.current_visit_date)
            if not before_visit:
                raise HTTPException(status_code=404, detail="未找到上次复诊记录")
        else:
            raise HTTPException(status_code=400, detail="无效的对比模式")

        before_photos = crud.get_photos_by_visit(db, before_visit.id)
        after_photos = crud.get_photos_by_visit(db, current_visit.id)

        before_photo_map = {p.angle: p for p in before_photos}
        after_photo_map = {p.angle: p for p in after_photos}

        common_angles = [angle for angle in before_photo_map.keys() if angle in after_photo_map.keys()]

        photo_pairs = []
        for angle in common_angles:
            photo_pairs.append({
                "angle": angle,
                "before_path": before_photo_map[angle].file_path,
                "after_path": after_photo_map[angle].file_path
            })

        if not photo_pairs:
            raise HTTPException(status_code=404, detail="没有可对比的照片")

        result_path = compare_generator.generate_comparison_grid(
            photo_pairs=photo_pairs,
            patient_no=data.patient_no,
            before_date=before_visit.visit_date.strftime("%Y-%m-%d"),
            after_date=current_visit.visit_date.strftime("%Y-%m-%d"),
            compare_mode=data.compare_mode
        )

        ai_hint = hint_generator.generate_hint(
            photo_pairs=photo_pairs,
            compare_mode=data.compare_mode,
            before_date=before_visit.visit_date,
            after_date=current_visit.visit_date
        )

        crud.add_compare_result(
            db=db,
            patient_id=patient.id,
            compare_mode=data.compare_mode,
            before_visit_id=before_visit.id,
            after_visit_id=current_visit.id,
            result_file_path=result_path,
            ai_hint=ai_hint,
            angles_compared=len(photo_pairs)
        )

        duration_ms = int((time.time() - start_time) * 1000)
        crud.log_api_call(
            db=db,
            endpoint="/api/compare/generate",
            method="POST",
            patient_no=data.patient_no,
            visit_date=data.current_visit_date,
            status_code=200,
            duration_ms=duration_ms,
            client_ip=client_ip
        )

        return schemas.CompareResponse(
            success=True,
            patient_no=data.patient_no,
            compare_mode=data.compare_mode,
            before_visit_date=before_visit.visit_date,
            after_visit_date=current_visit.visit_date,
            compare_image_url=f"/static/compare/{result_path.split('/')[-1]}" if result_path else "",
            ai_hint=ai_hint,
            angles_compared=len(photo_pairs),
            message="对比图生成成功"
        )

    except HTTPException:
        raise
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        crud.log_api_call(
            db=db,
            endpoint="/api/compare/generate",
            method="POST",
            patient_no=data.patient_no if data else "",
            visit_date=data.current_visit_date if data else None,
            status_code=500,
            duration_ms=duration_ms,
            error_message=str(e),
            client_ip=client_ip
        )
        raise HTTPException(status_code=500, detail=str(e))
