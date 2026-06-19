import secrets
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_, func
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any

from app import models, schemas
from app.config import settings


def generate_api_key() -> str:
    return "ak_" + secrets.token_hex(24)


def get_or_create_patient(db: Session, patient_no: str, patient_name: str = "",
                           client_id: Optional[int] = None) -> models.Patient:
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
                                is_initial: bool = False,
                                client_id: Optional[int] = None) -> models.VisitRecord:
    record = db.query(models.VisitRecord).filter(
        models.VisitRecord.patient_id == patient_id,
        models.VisitRecord.visit_date == visit_date
    ).first()

    if not record:
        record = models.VisitRecord(
            patient_id=patient_id,
            visit_date=visit_date,
            is_initial=is_initial,
            client_id=client_id
        )
        db.add(record)
        db.commit()
        db.refresh(record)
    else:
        updated = False
        if is_initial and not record.is_initial:
            record.is_initial = True
            updated = True
        if client_id and not record.client_id:
            record.client_id = client_id
            updated = True
        if updated:
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
              angle: str, file_path: str, file_name: str, file_url: str,
              file_size: int, content_type: str,
              quality_result: dict, client_id: Optional[int] = None) -> models.Photo:
    photo = models.Photo(
        patient_id=patient_id,
        visit_record_id=visit_record_id,
        client_id=client_id,
        angle=angle,
        file_path=file_path,
        file_name=file_name,
        file_url=file_url,
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
                 error_message: str = "", client_ip: str = "",
                 user_agent: str = "", client_id: Optional[int] = None,
                 api_category: str = "") -> models.ApiCallLog:
    log = models.ApiCallLog(
        client_id=client_id,
        endpoint=endpoint,
        method=method,
        api_category=api_category,
        patient_no=patient_no,
        visit_date=visit_date,
        status_code=status_code,
        duration_ms=duration_ms,
        request_body=request_body,
        error_message=error_message,
        client_ip=client_ip,
        user_agent=user_agent
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def get_api_logs(db: Session, skip: int = 0, limit: int = 100,
                 patient_no: str = None, endpoint: str = None,
                 status_code: int = None, client_id: int = None,
                 date_from: Optional[date] = None,
                 date_to: Optional[date] = None,
                 api_category: str = None) -> List[models.ApiCallLog]:
    query = db.query(models.ApiCallLog)
    if patient_no:
        query = query.filter(models.ApiCallLog.patient_no == patient_no)
    if endpoint:
        query = query.filter(models.ApiCallLog.endpoint.contains(endpoint))
    if status_code is not None:
        if status_code < 10:
            query = query.filter(models.ApiCallLog.status_code.between(status_code * 100, (status_code + 1) * 100 - 1))
        else:
            query = query.filter(models.ApiCallLog.status_code == status_code)
    if client_id:
        query = query.filter(models.ApiCallLog.client_id == client_id)
    if date_from:
        query = query.filter(func.date(models.ApiCallLog.created_at) >= date_from)
    if date_to:
        query = query.filter(func.date(models.ApiCallLog.created_at) <= date_to)
    if api_category:
        query = query.filter(models.ApiCallLog.api_category == api_category)
    return query.order_by(desc(models.ApiCallLog.created_at)).offset(skip).limit(limit).all()


def count_api_logs(db: Session, patient_no: str = None, endpoint: str = None,
                   status_code: int = None, client_id: int = None,
                   date_from: Optional[date] = None,
                   date_to: Optional[date] = None,
                   api_category: str = None) -> int:
    query = db.query(models.ApiCallLog)
    if patient_no:
        query = query.filter(models.ApiCallLog.patient_no == patient_no)
    if endpoint:
        query = query.filter(models.ApiCallLog.endpoint.contains(endpoint))
    if status_code is not None:
        if status_code < 10:
            query = query.filter(models.ApiCallLog.status_code.between(status_code * 100, (status_code + 1) * 100 - 1))
        else:
            query = query.filter(models.ApiCallLog.status_code == status_code)
    if client_id:
        query = query.filter(models.ApiCallLog.client_id == client_id)
    if date_from:
        query = query.filter(func.date(models.ApiCallLog.created_at) >= date_from)
    if date_to:
        query = query.filter(func.date(models.ApiCallLog.created_at) <= date_to)
    if api_category:
        query = query.filter(models.ApiCallLog.api_category == api_category)
    return query.count()


def get_abnormal_photos(db: Session, skip: int = 0, limit: int = 100,
                        client_id: Optional[int] = None) -> List[models.Photo]:
    query = db.query(models.Photo).filter(models.Photo.quality_passed == False)
    if client_id:
        query = query.filter(models.Photo.client_id == client_id)
    return query.order_by(desc(models.Photo.created_at)).offset(skip).limit(limit).all()


def count_abnormal_photos(db: Session, client_id: Optional[int] = None) -> int:
    query = db.query(models.Photo).filter(models.Photo.quality_passed == False)
    if client_id:
        query = query.filter(models.Photo.client_id == client_id)
    return query.count()


def get_stats(db: Session, client_id: Optional[int] = None) -> dict:
    patient_q = db.query(models.Patient)
    photo_q = db.query(models.Photo)
    compare_q = db.query(models.CompareResult)
    log_q = db.query(models.ApiCallLog)
    abnormal_q = db.query(models.Photo).filter(models.Photo.quality_passed == False)

    if client_id:
        photo_q = photo_q.filter(models.Photo.client_id == client_id)
        compare_q = compare_q.filter(models.CompareResult.client_id == client_id)
        log_q = log_q.filter(models.ApiCallLog.client_id == client_id)
        abnormal_q = abnormal_q.filter(models.Photo.client_id == client_id)

    return {
        "total_patients": patient_q.count(),
        "total_photos": photo_q.count(),
        "total_compares": compare_q.count(),
        "total_api_calls": log_q.count(),
        "abnormal_photo_count": abnormal_q.count()
    }


def add_compare_result(db: Session, patient_id: int, compare_mode: str,
                       before_visit_id: int, after_visit_id: int,
                       result_file_path: str, result_file_url: str,
                       ai_hint: str, angles_compared: int,
                       client_id: Optional[int] = None) -> models.CompareResult:
    result = models.CompareResult(
        patient_id=patient_id,
        client_id=client_id,
        compare_mode=compare_mode,
        before_visit_id=before_visit_id,
        after_visit_id=after_visit_id,
        result_file_path=result_file_path,
        result_file_url=result_file_url,
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


def create_api_client(db: Session, data: schemas.ApiClientCreate) -> models.ApiClient:
    api_key = generate_api_key()
    client = models.ApiClient(
        name=data.name,
        api_key=api_key,
        client_type=data.client_type,
        contact_name=data.contact_name,
        contact_phone=data.contact_phone,
        contact_email=data.contact_email,
        settings=data.settings or {},
        is_active=data.is_active
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def update_api_client(db: Session, client_id: int, data: schemas.ApiClientUpdate) -> Optional[models.ApiClient]:
    client = db.query(models.ApiClient).filter(models.ApiClient.id == client_id).first()
    if not client:
        return None
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(client, key, value)
    db.commit()
    db.refresh(client)
    return client


def get_api_client(db: Session, client_id: int) -> Optional[models.ApiClient]:
    return db.query(models.ApiClient).filter(models.ApiClient.id == client_id).first()


def get_api_client_by_key(db: Session, api_key: str) -> Optional[models.ApiClient]:
    return db.query(models.ApiClient).filter(models.ApiClient.api_key == api_key).first()


def list_api_clients(db: Session, skip: int = 0, limit: int = 100,
                      is_active: Optional[bool] = None) -> List[models.ApiClient]:
    query = db.query(models.ApiClient)
    if is_active is not None:
        query = query.filter(models.ApiClient.is_active == is_active)
    return query.order_by(desc(models.ApiClient.created_at)).offset(skip).limit(limit).all()


def count_api_clients(db: Session, is_active: Optional[bool] = None) -> int:
    query = db.query(models.ApiClient)
    if is_active is not None:
        query = query.filter(models.ApiClient.is_active == is_active)
    return query.count()


def create_callback_config(db: Session, data: schemas.CallbackConfigCreate) -> models.CallbackConfig:
    config = models.CallbackConfig(
        client_id=data.client_id,
        event_type=data.event_type,
        callback_url=data.callback_url,
        secret_token=data.secret_token,
        max_retries=data.max_retries,
        retry_interval=data.retry_interval,
        is_active=data.is_active
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


def update_callback_config(db: Session, config_id: int, data: schemas.CallbackConfigUpdate) -> Optional[models.CallbackConfig]:
    config = db.query(models.CallbackConfig).filter(models.CallbackConfig.id == config_id).first()
    if not config:
        return None
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(config, key, value)
    db.commit()
    db.refresh(config)
    return config


def get_callback_config(db: Session, config_id: int) -> Optional[models.CallbackConfig]:
    return db.query(models.CallbackConfig).filter(models.CallbackConfig.id == config_id).first()


def list_callback_configs(db: Session, client_id: Optional[int] = None,
                           event_type: Optional[str] = None,
                           skip: int = 0, limit: int = 100) -> List[models.CallbackConfig]:
    query = db.query(models.CallbackConfig)
    if client_id:
        query = query.filter(models.CallbackConfig.client_id == client_id)
    if event_type:
        query = query.filter(models.CallbackConfig.event_type == event_type)
    return query.order_by(desc(models.CallbackConfig.created_at)).offset(skip).limit(limit).all()


def count_callback_configs(db: Session, client_id: Optional[int] = None,
                            event_type: Optional[str] = None) -> int:
    query = db.query(models.CallbackConfig)
    if client_id:
        query = query.filter(models.CallbackConfig.client_id == client_id)
    if event_type:
        query = query.filter(models.CallbackConfig.event_type == event_type)
    return query.count()


def get_active_callback_configs(db: Session, client_id: Optional[int],
                                 event_type: str) -> List[models.CallbackConfig]:
    query = db.query(models.CallbackConfig).filter(
        models.CallbackConfig.is_active == True,
        models.CallbackConfig.event_type == event_type
    )
    if client_id:
        query = query.filter(models.CallbackConfig.client_id == client_id)
    return query.all()


def create_callback_task(db: Session, config_id: int, event_type: str,
                          payload: Dict[str, Any], patient_no: str = "",
                          client_id: Optional[int] = None) -> models.CallbackTask:
    config = get_callback_config(db, config_id)
    max_retries = config.max_retries if config else settings.callback_max_retries
    retry_interval = config.retry_interval if config else settings.callback_retry_interval
    callback_url = config.callback_url if config else ""

    task = models.CallbackTask(
        config_id=config_id,
        event_type=event_type,
        client_id=client_id,
        patient_no=patient_no,
        payload=payload,
        status="pending",
        retry_count=0,
        max_retries=max_retries,
        callback_url=callback_url,
        next_retry_at=datetime.utcnow()
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def update_callback_task_status(db: Session, task_id: int, status: str,
                                 error_message: str = "") -> Optional[models.CallbackTask]:
    task = db.query(models.CallbackTask).filter(models.CallbackTask.id == task_id).first()
    if not task:
        return None
    task.status = status
    task.last_error = error_message
    task.last_sent_at = datetime.utcnow()
    if status == "retrying":
        task.retry_count += 1
        config = get_callback_config(db, task.config_id)
        interval = config.retry_interval if config else settings.callback_retry_interval
        task.next_retry_at = datetime.utcnow() + timedelta(seconds=interval)
    elif status == "success":
        task.next_retry_at = None
    elif status == "failed" and task.retry_count >= task.max_retries:
        task.next_retry_at = None
    db.commit()
    db.refresh(task)
    return task


def get_pending_callback_tasks(db: Session, limit: int = 50) -> List[models.CallbackTask]:
    now = datetime.utcnow()
    return db.query(models.CallbackTask).filter(
        or_(
            models.CallbackTask.status == "pending",
            and_(
                models.CallbackTask.status == "retrying",
                models.CallbackTask.next_retry_at <= now
            )
        )
    ).order_by(models.CallbackTask.created_at.asc()).limit(limit).all()


def list_callback_tasks(db: Session, client_id: Optional[int] = None,
                         status: Optional[str] = None,
                         event_type: Optional[str] = None,
                         skip: int = 0, limit: int = 100) -> List[models.CallbackTask]:
    query = db.query(models.CallbackTask)
    if client_id:
        query = query.filter(models.CallbackTask.client_id == client_id)
    if status:
        query = query.filter(models.CallbackTask.status == status)
    if event_type:
        query = query.filter(models.CallbackTask.event_type == event_type)
    return query.order_by(desc(models.CallbackTask.created_at)).offset(skip).limit(limit).all()


def count_callback_tasks(db: Session, client_id: Optional[int] = None,
                          status: Optional[str] = None,
                          event_type: Optional[str] = None) -> int:
    query = db.query(models.CallbackTask)
    if client_id:
        query = query.filter(models.CallbackTask.client_id == client_id)
    if status:
        query = query.filter(models.CallbackTask.status == status)
    if event_type:
        query = query.filter(models.CallbackTask.event_type == event_type)
    return query.count()


def get_client_stats(db: Session) -> List[Dict[str, Any]]:
    clients = list_api_clients(db)
    result = []
    for client in clients:
        total_calls = count_api_logs(db, client_id=client.id)
        success_calls = count_api_logs(db, client_id=client.id, status_code=2)
        failed_calls = total_calls - success_calls
        total_photos = db.query(models.Photo).filter(models.Photo.client_id == client.id).count()
        abnormal_photos = count_abnormal_photos(db, client_id=client.id)
        total_compares = db.query(models.CompareResult).filter(models.CompareResult.client_id == client.id).count()

        result.append({
            "client_id": client.id,
            "client_name": client.name,
            "client_type": client.client_type,
            "total_api_calls": total_calls,
            "success_calls": success_calls,
            "failed_calls": failed_calls,
            "total_photos": total_photos,
            "abnormal_photos": abnormal_photos,
            "total_compares": total_compares
        })
    return result
