import time
import json
from datetime import datetime
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

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
        response = await call_next(request)

        duration_ms = int((time.time() - start_time) * 1000)
        status_code = response.status_code

        if request.url.path.startswith("/api/") or request.url.path == "/" or request.url.path == "/health":
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
                    endpoint=request.url.path,
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
                    api_category=categorize_api(request.url.path, request.method)
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
        return None

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
