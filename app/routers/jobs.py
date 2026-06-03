"""API задач: создать обработку, узнать статус, скачать результат."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Job, User
from ..parsers import ParseError, get_parser_for
from ..schemas import JobCreateIn, JobOut
from ..services.processing import run_job

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.post("", response_model=JobOut)
def create_job(
    data: JobCreateIn,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # 1) Проверяем доступ/лимит
    if not user.can_process:
        if not user.access_active:
            raise HTTPException(403, "Срок доступа истёк. Обратитесь к администратору.")
        raise HTTPException(403, "Лимит обработок исчерпан. Обратитесь к администратору.")

    # 2) Проверяем, что источник поддерживается (бросит ParseError для чужих доменов)
    try:
        parser = get_parser_for(data.url)
    except ParseError as exc:
        raise HTTPException(400, str(exc)) from exc

    # 3) Создаём задачу и ставим в фон
    job = Job(user_id=user.id, source=parser.source, url=data.url.strip(), status="pending")
    db.add(job)
    db.commit()
    db.refresh(job)

    background.add_task(run_job, job.id)
    return job


@router.get("", response_model=list[JobOut])
def list_jobs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    limit: int = 50,
):
    rows = db.scalars(
        select(Job)
        .where(Job.user_id == user.id)
        .order_by(Job.id.desc())
        .limit(min(limit, 200))
    ).all()
    return rows


@router.get("/{job_id}", response_model=JobOut)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = db.get(Job, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(404, "Задача не найдена")
    return job


@router.get("/{job_id}/download")
def download_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    job = db.get(Job, job_id)
    if not job or job.user_id != user.id:
        raise HTTPException(404, "Задача не найдена")
    if job.status != "done" or not job.result_path:
        raise HTTPException(409, "Результат ещё не готов")

    filename = f"photos_{job.id}.zip"
    return FileResponse(job.result_path, media_type="application/zip", filename=filename)
