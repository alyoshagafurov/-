"""Отдача HTML-страниц (Jinja2). Защищённые разделы редиректят на /login."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..config import BASE_DIR
from ..deps import COOKIE_NAME, get_current_user_optional
from ..models import User

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


def render(request: Request, name: str, user: User | None, **extra):
    context = {"user": user}
    context.update(extra)
    return templates.TemplateResponse(request=request, name=name, context=context)


@router.get("/", response_class=HTMLResponse)
def index(request: Request, user: User | None = Depends(get_current_user_optional)):
    return render(request, "index.html", user)


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, user: User | None = Depends(get_current_user_optional)):
    if user:
        return RedirectResponse("/dashboard", status_code=302)
    return render(request, "login.html", user)


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request, user: User | None = Depends(get_current_user_optional)):
    if user:
        return RedirectResponse("/dashboard", status_code=302)
    return render(request, "register.html", user)


@router.get("/tariffs", response_class=HTMLResponse)
def tariffs_page(request: Request, user: User | None = Depends(get_current_user_optional)):
    return render(request, "tariffs.html", user)


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request, user: User | None = Depends(get_current_user_optional)):
    if not user:
        return RedirectResponse("/login", status_code=302)
    return render(request, "dashboard.html", user)


@router.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request, user: User | None = Depends(get_current_user_optional)):
    if not user:
        return RedirectResponse("/login", status_code=302)
    if not user.is_admin:
        return RedirectResponse("/dashboard", status_code=302)
    return render(request, "admin.html", user)


@router.get("/api-docs", response_class=HTMLResponse)
def api_docs_page(request: Request, user: User | None = Depends(get_current_user_optional)):
    return render(request, "api_docs.html", user)


@router.get("/logout")
def logout_page():
    resp = RedirectResponse("/", status_code=302)
    resp.delete_cookie(COOKIE_NAME, path="/")
    return resp
