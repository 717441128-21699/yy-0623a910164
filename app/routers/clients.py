from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import crud, schemas
from app.database import get_db

router = APIRouter(prefix="/api/clients", tags=["接入方管理"])


@router.post("", response_model=schemas.ApiClientInfo, summary="创建接入方")
async def create_client(data: schemas.ApiClientCreate, db: Session = Depends(get_db)):
    client = crud.create_api_client(db, data)
    info = schemas.ApiClientInfo.model_validate(client)
    return info


@router.get("", response_model=schemas.ApiClientListResponse, summary="获取接入方列表(含统计)")
async def list_clients(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    clients = crud.list_api_clients(db, skip=skip, limit=limit, is_active=is_active)
    total = crud.count_api_clients(db, is_active=is_active)

    result = []
    for client in clients:
        info = schemas.ApiClientInfo.model_validate(client)
        stats = crud.get_stats(db, client_id=client.id)
        info.total_api_calls = stats["total_api_calls"]
        info.total_abnormal_photos = stats["abnormal_photo_count"]
        result.append(info)

    return schemas.ApiClientListResponse(success=True, total=total, clients=result)


@router.get("/{client_id}", response_model=schemas.ApiClientInfo, summary="获取接入方详情(简单版)")
async def get_client(client_id: int, db: Session = Depends(get_db)):
    client = crud.get_api_client(db, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="接入方不存在")
    info = schemas.ApiClientInfo.model_validate(client)
    stats = crud.get_stats(db, client_id=client.id)
    info.total_api_calls = stats["total_api_calls"]
    info.total_abnormal_photos = stats["abnormal_photo_count"]
    return info


@router.put("/{client_id}", response_model=schemas.ApiClientInfo, summary="更新接入方信息(含配额和对比权限)")
async def update_client(client_id: int, data: schemas.ApiClientUpdate, db: Session = Depends(get_db)):
    client = crud.update_api_client(db, client_id, data)
    if not client:
        raise HTTPException(status_code=404, detail="接入方不存在")
    return schemas.ApiClientInfo.model_validate(client)


@router.post("/{client_id}/reset-key", summary="重置接入方 API Key")
async def reset_client_key(client_id: int, db: Session = Depends(get_db)):
    client = crud.get_api_client(db, client_id)
    if not client:
        raise HTTPException(status_code=404, detail="接入方不存在")
    new_key = crud.generate_api_key()
    client.api_key = new_key
    db.commit()
    db.refresh(client)
    return {"success": True, "api_key": new_key, "message": "API Key 已重置"}
