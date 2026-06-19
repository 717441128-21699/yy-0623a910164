import time
import json
from datetime import datetime
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

from fastapi import Depends, HTTPException, status, Header
from sqlalchemy.orm import Session

from app.database import get_db
from app.config import settings
from app import crud, models


def categorize_api(endpoint: str, method: str) -> str:
    if endpoint.startswith("/api/admin") or endpoint.startswith("/api/clients") or endpoint.startswith("/api/callbacks"):
        return "admin"
    elif endpoint.startswith("/api/compare"):
        return "compare"
    elif endpoint.startswith("/api/photos/submit"):
        return "submit"
    elif endpoint.startswith("/api/photos") or endpoint.startswith("/api/standard-angles"):
        return "query"
    elif endpoint.startswith("/api"):
        return "query"
    else:
        return "system"


def get_quota_type_for_endpoint(endpoint: str) -> Optional[str]:
    if endpoint.startswith("/api/compare/generate"):
        return "compare"
    if endpoint.startswith("/api/photos/submit"):
        return "photo"
    return None


class ApiLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        body_bytes = await request.body()
        request_body = ""
        try:
            if body_bytes and len(body_bytes) < 10000:
                request_body = body_bytes.decode("utf-8", errors="ignore")
        except Exception:
            pass

        async def receive():
            return {"type": "http.request", "body": body_bytes, "more_body": False}

        request = Request(request.scope, receive)
        path = request.url.path

        if path.startswith("/api/"):
            api_key = request.headers.get("X-API-Key", "")
            try:
                db = next(get_db())
                try:
                    client = None
                    if api_key:
                        client = crud.get_api_client_by_key(db, api_key)
                    client_id = client.id if client else None

                    category = categorize_api(path, request.method)
                    if category not in ["admin", "system"]:
                        quota_type = get_quota_type_for_endpoint(path)
                        if quota_type:
                            check = crud.check_quota(db, client_id, quota_type)
                            if not check["allowed"]:
                                duration_ms = int((time.time() - start_time) * 1000)
                                patient_no = ""
                                visit_date = None
                                try:
                                    if request_body and request.method in ["POST", "PUT", "PATCH"]:
                                        body_json = json.loads(request_body)
                                        patient_no = body_json.get("patient_no", "")
                                except Exception:
                                    pass
                                crud.log_api_call(
                                    db=db,
                                    endpoint=path,
                                    method=request.method,
                                    patient_no=patient_no,
                                    visit_date=visit_date,
                                    status_code=429,
                                    duration_ms=duration_ms,
                                    request_body=request_body[:2000] if len(request_body) > 2000 else request_body,
                                    error_message=check["message"],
                                    client_ip=request.client.host if request.client else "",
                                    user_agent=request.headers.get("user-agent", "")[:500],
                                    client_id=client_id,
                                    api_category=category
                                )
                                return JSONResponse(
                                    status_code=429,
                                    content={
                                        "success": False,
                                        "message": check["message"],
                                        "used": check.get("used", 0),
                                        "limit": check.get("limit", 0)
                                    }
                                )
                finally:
                    db.close()
            except Exception:
                pass

        response = await call_next(request)

        duration_ms = int((time.time() - start_time) * 1000)
        status_code = response.status_code

        if path.startswith("/api/") or path == "/" or path == "/health":
            try:
                db = next(get_db())
                api_key = request.headers.get("X-API-Key", "")
                client = None
                if api_key:
                    client = crud.get_api_client_by_key(db, api_key)

                patient_no = ""
                visit_date = None
                try:
                    if request_body and request.method in ["POST", "PUT", "PATCH"]:
                        body_json = json.loads(request_body)
                        patient_no = body_json.get("patient_no", "")
                        vd = body_json.get("visit_date") or body_json.get("current_visit_date")
                        if vd:
                            visit_date = datetime.fromisoformat(vd).date() if isinstance(vd, str) else vd
                except Exception:
                    pass

                crud.log_api_call(
                    db=db,
                    endpoint=path,
                    method=request.method,
                    patient_no=patient_no,
                    visit_date=visit_date,
                    status_code=status_code,
                    duration_ms=duration_ms,
                    request_body=request_body[:2000] if len(request_body) > 2000 else request_body,
                    error_message="",
                    client_ip=request.client.host if request.client else "",
                    user_agent=request.headers.get("user-agent", "")[:500],
                    client_id=client.id if client else None,
                    api_category=categorize_api(path, request.method)
                )
                db.close()
            except Exception:
                pass

        return response


async def get_current_client(
    x_api_key: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> Optional[models.ApiClient]:
    if not x_api_key:
        if settings.require_api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="缺少 API Key"
            )
        return crud.get_or_create_default_client(db)

    client = crud.get_api_client_by_key(db, x_api_key)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的 API Key"
        )
    if not client.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="该 API Key 已被禁用"
        )
    return client
