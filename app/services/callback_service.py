import json
import time
import hashlib
import hmac
import asyncio
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

import httpx
from sqlalchemy.orm import Session

from app import crud, models
from app.config import settings
from app.database import SessionLocal


class CallbackService:
    def __init__(self):
        self.timeout = settings.callback_timeout

    def _generate_signature(self, secret_token: str, payload: Dict[str, Any]) -> str:
        if not secret_token:
            return ""
        payload_str = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        signature = hmac.new(
            secret_token.encode("utf-8"),
            payload_str.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return signature

    async def send_callback(self, task: models.CallbackTask, config: Optional[models.CallbackConfig]
                            ) -> Tuple[bool, Optional[int], str, str, int]:
        if not task.callback_url:
            return False, None, "", "回调地址为空", 0

        payload = task.payload
        payload_str = json.dumps(payload, ensure_ascii=False)
        headers = {
            "Content-Type": "application/json",
            "X-Callback-Event": task.event_type,
            "X-Callback-Timestamp": str(int(time.time())),
        }
        headers_for_record = dict(headers)

        if config and config.secret_token:
            signature = self._generate_signature(config.secret_token, payload)
            headers["X-Callback-Signature"] = signature
            headers_for_record["X-Callback-Signature"] = signature

        start = time.time()
        response_status = None
        response_body = ""
        error_msg = ""
        success = False

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    task.callback_url,
                    json=payload,
                    headers=headers
                )
                response_status = response.status_code
                try:
                    response_body = response.text
                except Exception:
                    response_body = ""
                success = 200 <= response.status_code < 300
                if not success:
                    error_msg = f"HTTP {response.status_code}"
        except httpx.TimeoutException:
            error_msg = f"请求超时({self.timeout}s)"
        except Exception as e:
            error_msg = str(e)[:500]

        duration_ms = int((time.time() - start) * 1000)
        return success, response_status, response_body[:2000], error_msg, duration_ms, headers_for_record, payload_str

    async def process_task(self, task: models.CallbackTask):
        db = SessionLocal()
        attempt_no = task.retry_count + 1
        try:
            config = crud.get_callback_config(db, task.config_id)
            result = await self.send_callback(task, config)
            success, response_status, response_body, error_msg, duration_ms = result[0], result[1], result[2], result[3], result[4]
            headers_record = result[5] if len(result) > 5 else {}
            payload_record = result[6] if len(result) > 6 else ""

            try:
                crud.record_callback_execution(
                    db,
                    task_id=task.id,
                    attempt_no=attempt_no,
                    callback_url=task.callback_url,
                    request_headers=headers_record,
                    request_body=payload_record,
                    response_status=response_status,
                    response_body=response_body,
                    duration_ms=duration_ms,
                    success=success,
                    error_message=error_msg
                )
            except Exception:
                pass

            if success:
                crud.update_callback_task_status(
                    db, task.id, "success",
                    response_status=response_status,
                    response_body=response_body
                )
            else:
                if attempt_no >= task.max_retries:
                    crud.update_callback_task_status(
                        db, task.id, "failed", error_msg,
                        response_status=response_status,
                        response_body=response_body
                    )
                else:
                    crud.update_callback_task_status(
                        db, task.id, "retrying", error_msg,
                        response_status=response_status,
                        response_body=response_body
                    )
        except Exception as e:
            err = str(e)[:500]
            try:
                crud.record_callback_execution(
                    db, task_id=task.id, attempt_no=attempt_no,
                    callback_url=task.callback_url,
                    request_headers={}, request_body="",
                    response_status=None, response_body="",
                    duration_ms=0, success=False,
                    error_message=err
                )
            except Exception:
                pass
            try:
                if attempt_no >= task.max_retries:
                    crud.update_callback_task_status(db, task.id, "failed", err)
                else:
                    crud.update_callback_task_status(db, task.id, "retrying", err)
            except Exception:
                pass
        finally:
            db.close()

    async def process_task_sync(self, task_id: int) -> Dict[str, Any]:
        db = SessionLocal()
        try:
            task = crud.get_callback_task(db, task_id)
            if not task:
                return {"success": False, "error": "任务不存在"}

            attempt_no = task.retry_count + 1
            config = crud.get_callback_config(db, task.config_id)
            result = await self.send_callback(task, config)
            succ, resp_status, resp_body, err, dur = result[0], result[1], result[2], result[3], result[4]
            headers_record = result[5] if len(result) > 5 else {}
            payload_record = result[6] if len(result) > 6 else ""

            try:
                crud.record_callback_execution(
                    db, task_id=task.id, attempt_no=attempt_no,
                    callback_url=task.callback_url,
                    request_headers=headers_record,
                    request_body=payload_record,
                    response_status=resp_status,
                    response_body=resp_body,
                    duration_ms=dur,
                    success=succ,
                    error_message=err
                )
            except Exception:
                pass

            if succ:
                crud.update_callback_task_status(
                    db, task.id, "success",
                    response_status=resp_status, response_body=resp_body
                )
                new_status = "success"
            else:
                if attempt_no >= task.max_retries:
                    crud.update_callback_task_status(
                        db, task.id, "failed", err,
                        response_status=resp_status, response_body=resp_body
                    )
                    new_status = "failed"
                else:
                    crud.update_callback_task_status(
                        db, task.id, "retrying", err,
                        response_status=resp_status, response_body=resp_body
                    )
                    new_status = "retrying"

            return {
                "success": True,
                "success_flag": succ,
                "new_status": new_status,
                "response_status": resp_status,
                "error_message": err,
                "duration_ms": dur
            }
        finally:
            db.close()

    async def process_pending_tasks(self):
        db = SessionLocal()
        try:
            tasks = crud.get_pending_callback_tasks(db, limit=50)
            if not tasks:
                return
            await asyncio.gather(*[self.process_task(task) for task in tasks])
        except Exception:
            pass
        finally:
            db.close()

    def create_photo_submitted_tasks(self, db: Session, patient_no: str, visit_date,
                                      completeness: Dict[str, Any],
                                      photos: list, client_id: Optional[int] = None):
        configs = crud.get_active_callback_configs(db, client_id, "photo_submitted")

        abnormal_photos = [
            {
                "id": p.id,
                "angle": p.angle,
                "file_url": p.file_url,
                "is_too_dark": p.is_too_dark,
                "is_blurry": p.is_blurry,
                "is_not_centered": p.is_not_centered,
                "is_occluded": p.is_occluded,
                "quality_notes": p.quality_notes
            }
            for p in photos if not p.quality_passed
        ]

        payload = {
            "event_type": "photo_submitted",
            "patient_no": patient_no,
            "visit_date": str(visit_date),
            "completeness": completeness,
            "abnormal_photos": abnormal_photos,
            "total_photos": len(photos),
            "timestamp": datetime.utcnow().isoformat()
        }

        for config in configs:
            crud.create_callback_task(
                db=db,
                config_id=config.id,
                event_type="photo_submitted",
                payload=payload,
                patient_no=patient_no,
                client_id=config.client_id
            )

    def create_compare_generated_tasks(self, db: Session, patient_no: str, compare_mode: str,
                                        before_visit_date, after_visit_date,
                                        compare_image_url: str, ai_hint: str,
                                        angles_compared: int, client_id: Optional[int] = None):
        configs = crud.get_active_callback_configs(db, client_id, "compare_generated")

        payload = {
            "event_type": "compare_generated",
            "patient_no": patient_no,
            "compare_mode": compare_mode,
            "before_visit_date": str(before_visit_date),
            "after_visit_date": str(after_visit_date),
            "compare_image_url": compare_image_url,
            "ai_hint": ai_hint,
            "angles_compared": angles_compared,
            "timestamp": datetime.utcnow().isoformat()
        }

        for config in configs:
            crud.create_callback_task(
                db=db,
                config_id=config.id,
                event_type="compare_generated",
                payload=payload,
                patient_no=patient_no,
                client_id=config.client_id
            )


callback_service = CallbackService()
