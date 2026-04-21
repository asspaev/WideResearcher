"""Утилиты для конвертации Markdown-текста в типизированные сегменты."""

import re


def _apply_inline_markdown(text: str) -> str:
    """Заменяет inline Markdown разметку на теги <b> и <i>.

    Args:
        text: Строка с возможной inline разметкой.

    Returns:
        Строка с подставленными тегами <b> и <i>.
    """
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*(.+?)\*", r"<i>\1</i>", text)
    text = re.sub(r"_(.+?)_", r"<i>\1</i>", text)
    return text


def format_as_segments(text: str) -> list[dict]:
    """Конвертирует Markdown текст в список типизированных сегментов.

    Args:
        text: Markdown-форматированный текст от LLM.

    Returns:
        Список dict с ключами: type, content, is_like, is_dislike, comment.
        Поддерживаемые типы: h1, h2, h3, p, li.
    """

    def make_segment(tag: str, content: str) -> dict:
        return {
            "type": tag,
            "content": _apply_inline_markdown(content),
            "is_like": False,
            "is_dislike": False,
            "comment": None,
        }

    lines = text.splitlines()
    segments: list[dict] = []
    paragraph_lines: list[str] = []

    def flush_paragraph() -> None:
        if paragraph_lines:
            content = " ".join(paragraph_lines).strip()
            if content:
                segments.append(make_segment("p", content))
            paragraph_lines.clear()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            continue
        if stripped.startswith("###### "):
            flush_paragraph()
            segments.append(make_segment("h6", stripped[7:].strip()))
        elif stripped.startswith("##### "):
            flush_paragraph()
            segments.append(make_segment("h5", stripped[6:].strip()))
        elif stripped.startswith("#### "):
            flush_paragraph()
            segments.append(make_segment("h4", stripped[5:].strip()))
        elif stripped.startswith("### "):
            flush_paragraph()
            segments.append(make_segment("h3", stripped[4:].strip()))
        elif stripped.startswith("## "):
            flush_paragraph()
            segments.append(make_segment("h2", stripped[3:].strip()))
        elif stripped.startswith("# "):
            flush_paragraph()
            segments.append(make_segment("h1", stripped[2:].strip()))
        elif stripped.startswith(("- ", "* ", "• ")):
            flush_paragraph()
            segments.append(make_segment("li", stripped[2:].strip()))
        else:
            paragraph_lines.append(stripped)

    flush_paragraph()
    return segments
