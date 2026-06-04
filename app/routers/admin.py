"""Админка: управление пользователями, тарифами, лимитами, комментариями."""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_admin
from ..models import Comment, Job, PaymentRequest, Tariff, User, utcnow
from ..schemas import AssignTariffIn, CommentIn, TariffIn

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def _user_brief(u: User) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "is_admin": u.is_admin,
        "is_active": u.is_active,
        "tariff": u.tariff.name if u.tariff else None,
        "tariff_id": u.tariff_id,
        "limit_count": u.limit_count,
        "used_count": u.used_count,
        "remaining": u.remaining,
        "access_until": u.access_until.isoformat() if u.access_until else None,
        "access_active": u.access_active,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


# ── Пользователи ───────────────────────────────────────────
@router.get("/users")
def list_users(db: Session = Depends(get_db), q: str = "", limit: int = 100):
    stmt = select(User).order_by(User.id.desc())
    if q.strip():
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(or_(func.lower(User.email).like(like)))
    rows = db.scalars(stmt.limit(min(limit, 500))).all()
    return [_user_brief(u) for u in rows]


@router.get("/users/{user_id}")
def user_detail(user_id: int, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "Пользователь не найден")

    jobs = db.scalars(
        select(Job).where(Job.user_id == user_id).order_by(Job.id.desc()).limit(50)
    ).all()
    comments = db.scalars(
        select(Comment).where(Comment.user_id == user_id).order_by(Comment.id.desc())
    ).all()

    data = _user_brief(user)
    data["jobs"] = [
        {
            "id": j.id,
            "source": j.source,
            "url": j.url,
            "status": j.status,
            "title": j.title,
            "photo_count": j.photo_count,
            "error": j.error,
            "created_at": j.created_at.isoformat() if j.created_at else None,
        }
        for j in jobs
    ]
    data["comments"] = [
        {
            "id": c.id,
            "author": c.author,
            "text": c.text,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in comments
    ]
    return data


@router.post("/users/{user_id}/tariff")
def assign_tariff(user_id: int, data: AssignTariffIn, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "Пользователь не найден")

    # Назначение тарифа из шаблона: tariff_id=0 → отвязать
    if data.tariff_id is not None:
        if data.tariff_id == 0:
            user.tariff_id = None
        else:
            tariff = db.get(Tariff, data.tariff_id)
            if not tariff:
                raise HTTPException(404, "Тариф не найден")
            user.tariff_id = tariff.id
            user.limit_count = tariff.limit_count
            user.access_until = utcnow() + timedelta(days=tariff.duration_days)
            user.used_count = 0

    # Ручные переопределения
    if data.limit_count is not None:
        user.limit_count = max(0, data.limit_count)
    if data.extra_days is not None:
        base = user.access_until if user.access_active else utcnow()
        if base.tzinfo is None:
            from datetime import timezone

            base = base.replace(tzinfo=timezone.utc)
        user.access_until = base + timedelta(days=data.extra_days)
    if data.reset_used:
        user.used_count = 0

    db.commit()
    db.refresh(user)
    return _user_brief(user)


@router.post("/users/{user_id}/toggle")
def toggle_user(user_id: int, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "Пользователь не найден")
    if user.is_admin:
        raise HTTPException(400, "Нельзя заблокировать администратора")
    user.is_active = not user.is_active
    db.commit()
    return {"id": user.id, "is_active": user.is_active}


@router.post("/users/{user_id}/comment")
def add_comment(user_id: int, data: CommentIn, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "Пользователь не найден")
    comment = Comment(user_id=user_id, text=data.text.strip(), author="admin")
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return {
        "id": comment.id,
        "author": comment.author,
        "text": comment.text,
        "created_at": comment.created_at.isoformat(),
    }


@router.delete("/users/{user_id}/comment/{comment_id}")
def delete_comment(user_id: int, comment_id: int, db: Session = Depends(get_db)):
    comment = db.get(Comment, comment_id)
    if not comment or comment.user_id != user_id:
        raise HTTPException(404, "Комментарий не найден")
    db.delete(comment)
    db.commit()
    return {"ok": True}


# ── Тарифы (CRUD) ──────────────────────────────────────────
def _tariff_dict(t: Tariff) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "price": t.price,
        "limit_count": t.limit_count,
        "duration_days": t.duration_days,
        "description": t.description,
        "is_active": t.is_active,
        "sort_order": t.sort_order,
    }


@router.get("/tariffs")
def admin_list_tariffs(db: Session = Depends(get_db)):
    rows = db.scalars(select(Tariff).order_by(Tariff.sort_order, Tariff.id)).all()
    return [_tariff_dict(t) for t in rows]


@router.post("/tariffs")
def create_tariff(data: TariffIn, db: Session = Depends(get_db)):
    if db.scalar(select(Tariff).where(Tariff.name == data.name)):
        raise HTTPException(400, "Тариф с таким названием уже есть")
    tariff = Tariff(**data.model_dump())
    db.add(tariff)
    db.commit()
    db.refresh(tariff)
    return _tariff_dict(tariff)


@router.put("/tariffs/{tariff_id}")
def update_tariff(tariff_id: int, data: TariffIn, db: Session = Depends(get_db)):
    tariff = db.get(Tariff, tariff_id)
    if not tariff:
        raise HTTPException(404, "Тариф не найден")
    for key, value in data.model_dump().items():
        setattr(tariff, key, value)
    db.commit()
    db.refresh(tariff)
    return _tariff_dict(tariff)


@router.delete("/tariffs/{tariff_id}")
def delete_tariff(tariff_id: int, db: Session = Depends(get_db)):
    tariff = db.get(Tariff, tariff_id)
    if not tariff:
        raise HTTPException(404, "Тариф не найден")
    # Отвязываем тариф от пользователей, лимиты у них сохраняются
    for u in list(tariff.users):
        u.tariff_id = None
    db.delete(tariff)
    db.commit()
    return {"ok": True}


# ── Заявки на оплату ───────────────────────────────────────
def _request_dict(r: PaymentRequest) -> dict:
    return {
        "id": r.id,
        "tariff_name": r.tariff_name,
        "email": r.email,
        "phone": r.phone,
        "status": r.status,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


@router.get("/payment-requests")
def list_payment_requests(db: Session = Depends(get_db)):
    rows = db.scalars(
        select(PaymentRequest).order_by(PaymentRequest.id.desc()).limit(200)
    ).all()
    new_count = sum(1 for r in rows if r.status == "new")
    return {"items": [_request_dict(r) for r in rows], "new_count": new_count}


@router.post("/payment-requests/{req_id}/done")
def mark_request_done(req_id: int, db: Session = Depends(get_db)):
    req = db.get(PaymentRequest, req_id)
    if not req:
        raise HTTPException(404, "Заявка не найдена")
    req.status = "done" if req.status == "new" else "new"
    db.commit()
    return _request_dict(req)


@router.delete("/payment-requests/{req_id}")
def delete_request(req_id: int, db: Session = Depends(get_db)):
    req = db.get(PaymentRequest, req_id)
    if not req:
        raise HTTPException(404, "Заявка не найдена")
    db.delete(req)
    db.commit()
    return {"ok": True}
