import json
import time
import hashlib
import hmac
import asyncio
from typing import Optional, Dict, Any
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

    async def send_callback(self, task: models.CallbackTask, config: Optional[models.CallbackConfig]) -> bool:
        if not task.callback_url:
            return False

        payload = task.payload
        headers = {
            "Content-Type": "application/json",
            "X-Callback-Event": task.event_type,
            "X-Callback-Timestamp": str(int(time.time())),
        }

        if config and config.secret_token:
            signature = self._generate_signature(config.secret_token, payload)
            headers["X-Callback-Signature"] = signature

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    task.callback_url,
                    json=payload,
                    headers=headers
                )
                return 200 <= response.status_code < 300
        except Exception as e:
            return False

    async def process_task(self, task: models.CallbackTask):
        db = SessionLocal()
        try:
            config = crud.get_callback_config(db, task.config_id)
            success = await self.send_callback(task, config)

            if success:
                crud.update_callback_task_status(db, task.id, "success", "")
            else:
                if task.retry_count + 1 >= task.max_retries:
                    crud.update_callback_task_status(db, task.id, "failed", "达到最大重试次数")
                else:
                    crud.update_callback_task_status(db, task.id, "retrying", "")
        except Exception as e:
            try:
                if task.retry_count + 1 >= task.max_retries:
                    crud.update_callback_task_status(db, task.id, "failed", str(e))
                else:
                    crud.update_callback_task_status(db, task.id, "retrying", str(e))
            except Exception:
                pass
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
