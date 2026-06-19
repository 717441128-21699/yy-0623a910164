from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session

from app import crud, schemas, models
from app.database import get_db
from app.services import callback_service

router = APIRouter(prefix="/api/callbacks", tags=["回调通知管理"])


@router.post("/configs", response_model=schemas.CallbackConfigInfo, summary="创建回调配置")
async def create_callback_config(data: schemas.CallbackConfigCreate, db: Session = Depends(get_db)):
    client = crud.get_api_client(db, data.client_id)
    if not client:
        raise HTTPException(status_code=404, detail="接入方不存在")
    config = crud.create_callback_config(db, data)
    info = schemas.CallbackConfigInfo.model_validate(config)
    info.client_name = client.name
    return info


@router.get("/configs", response_model=schemas.CallbackListResponse, summary="获取回调配置列表")
async def list_callback_configs(
    client_id: Optional[int] = None,
    event_type: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    configs = crud.list_callback_configs(db, client_id=client_id, event_type=event_type, skip=skip, limit=limit)
    total = crud.count_callback_configs(db, client_id=client_id, event_type=event_type)

    result = []
    for config in configs:
        info = schemas.CallbackConfigInfo.model_validate(config)
        info.client_name = config.client.name if config.client else ""
        result.append(info)

    return schemas.CallbackListResponse(success=True, total=total, configs=result)


@router.get("/configs/{config_id}", response_model=schemas.CallbackConfigInfo, summary="获取回调配置详情")
async def get_callback_config(config_id: int, db: Session = Depends(get_db)):
    config = crud.get_callback_config(db, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="回调配置不存在")
    info = schemas.CallbackConfigInfo.model_validate(config)
    info.client_name = config.client.name if config.client else ""
    return info


@router.put("/configs/{config_id}", response_model=schemas.CallbackConfigInfo, summary="更新回调配置")
async def update_callback_config(config_id: int, data: schemas.CallbackConfigUpdate, db: Session = Depends(get_db)):
    config = crud.update_callback_config(db, config_id, data)
    if not config:
        raise HTTPException(status_code=404, detail="回调配置不存在")
    info = schemas.CallbackConfigInfo.model_validate(config)
    info.client_name = config.client.name if config.client else ""
    return info


@router.get("/tasks", response_model=schemas.CallbackTaskListResponse, summary="获取回调任务列表(含执行详情)")
async def list_callback_tasks(
    client_id: Optional[int] = None,
    status: Optional[str] = Query(None, description="pending, success, failed, retrying"),
    event_type: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db)
):
    tasks = crud.list_callback_tasks(db, client_id=client_id, status=status, event_type=event_type,
                                      skip=skip, limit=limit, include_executions=True)
    total = crud.count_callback_tasks(db, client_id=client_id, status=status, event_type=event_type)

    task_items = []
    for t in tasks:
        item = schemas.CallbackTaskItem.model_validate(t)
        if t.executions:
            item.executions = [schemas.CallbackExecutionRecordItem.model_validate(e) for e in t.executions[:20]]
        task_items.append(item)

    return schemas.CallbackTaskListResponse(success=True, total=total, tasks=task_items)


@router.get("/tasks/{task_id}", response_model=schemas.CallbackTaskDetailResponse, summary="获取回调任务详情(含所有执行记录)")
async def get_callback_task_detail(task_id: int, db: Session = Depends(get_db)):
    task = crud.get_callback_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="回调任务不存在")
    executions = crud.get_callback_executions(db, task_id)
    exec_items = [schemas.CallbackExecutionRecordItem.model_validate(e) for e in executions]
    task_item = schemas.CallbackTaskItem.model_validate(task)
    task_item.executions = exec_items
    return schemas.CallbackTaskDetailResponse(success=True, task=task_item, executions=exec_items)


@router.post("/tasks/retry/{task_id}", response_model=schemas.CallbackRetryResponse, summary="立即同步重发回调任务")
async def retry_callback_task_now(task_id: int, db: Session = Depends(get_db)):
    task = crud.get_callback_task(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="回调任务不存在")

    result = await callback_service.process_task_sync(task_id)

    if not result.get("success"):
        return schemas.CallbackRetryResponse(
            success=False,
            task_id=task_id,
            new_status="",
            message=result.get("error", "操作失败")
        )

    message = "回调重发成功" if result.get("success_flag") else f"回调重发失败: {result.get('error_message', '未知错误')}"

    return schemas.CallbackRetryResponse(
        success=True,
        task_id=task_id,
        new_status=result.get("new_status", ""),
        success_flag=result.get("success_flag", False),
        response_status=result.get("response_status"),
        error_message=result.get("error_message", ""),
        message=message
    )


@router.post("/tasks/retry/{task_id}/async", summary="异步重发回调任务(排队)")
async def retry_callback_task(task_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    task = db.query(models.CallbackTask).filter(models.CallbackTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="回调任务不存在")

    crud.update_callback_task_status(db, task_id, "retrying", "手动触发异步重试")

    return {"success": True, "message": "已加入重试队列，将在下次调度时执行", "task_id": task_id}


@router.post("/tasks/process-pending", summary="触发处理所有待发送回调")
async def process_pending_callbacks(db: Session = Depends(get_db)):
    import asyncio
    loop = asyncio.get_event_loop()
    loop.create_task(callback_service.process_pending_tasks())
    return {"success": True, "message": "已触发回调处理"}
