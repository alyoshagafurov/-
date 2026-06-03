"""Оркестрация одной задачи обработки: парсинг → zip → обновление статуса.

Запускается как фоновая задача (sync-функция, Starlette выполняет её в пуле
потоков, поэтому event-loop не блокируется). Внутри парсер качает фото в
несколько потоков.
"""
from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path

from ..config import RESULTS_DIR
from ..database import SessionLocal
from ..models import Job, User, utcnow
from ..parsers import ParseError, get_parser_for


def _fail(db, job_id: int, message: str) -> None:
    job = db.get(Job, job_id)
    if job is None:
        return
    job.status = "error"
    job.error = message[:1000]
    job.finished_at = utcnow()
    db.commit()


def run_job(job_id: int) -> None:
    db = SessionLocal()
    work_dir = None
    try:
        job = db.get(Job, job_id)
        if job is None:
            return

        job.status = "processing"
        db.commit()

        work_dir = tempfile.mkdtemp(prefix=f"job_{job_id}_")
        parser = get_parser_for(job.url)
        result = parser.parse(job.url, work_dir)

        zip_path = RESULTS_DIR / f"job_{job_id}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in result.image_paths:
                zf.write(path, arcname=Path(path).name)

        job.title = (result.title or "")[:255]
        job.photo_count = len(result.image_paths)
        job.result_path = str(zip_path)
        job.status = "done"
        job.finished_at = utcnow()

        # Списываем одну обработку с лимита (безлимит и админ — не списываем)
        user = db.get(User, job.user_id)
        if user and not user.is_admin and user.limit_count != 0:
            user.used_count += 1

        db.commit()

    except ParseError as exc:
        _fail(db, job_id, str(exc))
    except Exception as exc:  # noqa: BLE001 — любую неожиданную ошибку показываем как статус
        _fail(db, job_id, f"Внутренняя ошибка обработки: {exc}")
    finally:
        if work_dir:
            shutil.rmtree(work_dir, ignore_errors=True)
        db.close()
