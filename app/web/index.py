from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from jinja2 import TemplateNotFound, TemplateSyntaxError

from app.core.templates import templates

router = APIRouter()


@router.get("/", name="index", response_class=HTMLResponse)
async def index(request: Request):
    try:
        return templates.TemplateResponse("pages/login.html", {"request": request})
    except TemplateNotFound as e:
        print("Template not found:", e)
    except TemplateSyntaxError as e:
        print("Template syntax error:", e)
