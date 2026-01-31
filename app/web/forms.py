from fastapi import APIRouter, Form, Request
from loguru import logger

from app.config import get_settings
from app.core.templates import templates

router = APIRouter(prefix=get_settings().prefix.form, tags=["form"])


@router.get("/model-options", name="model_options")
async def get_form_model_options(
    request: Request,
    model_type: str,
):
    if model_type.lower() == "api":
        return templates.TemplateResponse(
            "includes/forms/model_api_options.html",
            {"request": request},
        )
    elif model_type.lower() == "vllm":
        return templates.TemplateResponse(
            "includes/forms/model_vllm_options.html",
            {"request": request},
        )

    return templates.TemplateResponse(
        "includes/forms/model_api_options.html",
        {"request": request},
    )
