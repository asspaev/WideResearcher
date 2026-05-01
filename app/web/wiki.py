import re
from pathlib import Path

import markdown as md_lib
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from app.core.templates import templates
from app.schemas.user import UserCookie
from app.utils.dependencies import get_user_cookie

router = APIRouter()

WIKI_DIR = Path(__file__).parent.parent.parent / "docs" / "wiki"


def _parse_frontmatter(content: str) -> tuple[dict, str]:
    match = re.match(r"^---\n(.*?)\n---\n?", content, re.DOTALL)
    if not match:
        return {}, content
    meta = {}
    for line in match.group(1).split("\n"):
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
    return meta, content[match.end() :]


def _load_articles() -> list[dict]:
    articles = []
    if not WIKI_DIR.exists():
        return articles
    for path in sorted(WIKI_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        meta, _ = _parse_frontmatter(text)
        articles.append(
            {
                "slug": path.stem,
                "title": meta.get("title", path.stem),
                "subtitle": meta.get("subtitle", ""),
                "image": meta.get("image", ""),
            }
        )
    return articles


@router.get("/wiki", name="wiki")
async def get_wiki(
    request: Request,
    user_cookie: UserCookie = Depends(get_user_cookie),
):
    """Рендер страницы списка статей wiki."""
    articles = _load_articles()
    return templates.TemplateResponse(
        "pages/wiki.html",
        {
            "request": request,
            "user_cookie": user_cookie,
            "page": "wiki",
            "articles": articles,
        },
    )


@router.get("/articles/{slug}", name="article")
async def get_article(
    request: Request,
    slug: str,
    user_cookie: UserCookie = Depends(get_user_cookie),
):
    """Рендер страницы отдельной статьи."""
    path = WIKI_DIR / f"{slug}.md"
    if not path.exists():
        return RedirectResponse(url="/wiki", status_code=302)

    text = path.read_text(encoding="utf-8")
    meta, body = _parse_frontmatter(text)

    converter = md_lib.Markdown(extensions=["tables", "fenced_code"])
    content_html = converter.convert(body)

    return templates.TemplateResponse(
        "pages/article.html",
        {
            "request": request,
            "user_cookie": user_cookie,
            "page": "wiki",
            "title": meta.get("title", slug),
            "subtitle": meta.get("subtitle", ""),
            "image": meta.get("image", ""),
            "content_html": content_html,
        },
    )
