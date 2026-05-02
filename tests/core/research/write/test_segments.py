import pytest

from app.core.research.write.segments import _apply_markdown_links, format_as_segments


@pytest.mark.parametrize(
    "text, expected",
    [
        # --- без ссылок — текст не меняется ---
        ("", ""),
        ("Обычный текст без ссылок.", "Обычный текст без ссылок."),
        # --- простая ссылка ---
        (
            "[текст](https://example.com)",
            '<a href="https://example.com" target="_blank" rel="noopener noreferrer">текст</a>',
        ),
        # --- цитата вида [[1]](url) ---
        (
            "[[1]](https://ru.wikipedia.org/wiki/ARPANET)",
            '<a href="https://ru.wikipedia.org/wiki/ARPANET" target="_blank" rel="noopener noreferrer">[1]</a>',
        ),
        # --- несколько цитат в одной строке ---
        (
            "Факт [[1]](https://a.com) и ещё факт [[2]](https://b.com).",
            'Факт <a href="https://a.com" target="_blank" rel="noopener noreferrer">[1]</a>'
            ' и ещё факт <a href="https://b.com" target="_blank" rel="noopener noreferrer">[2]</a>.',
        ),
        # --- ссылка в начале строки ---
        (
            "[[1]](https://a.com) — первый источник.",
            '<a href="https://a.com" target="_blank" rel="noopener noreferrer">[1]</a> — первый источник.',
        ),
        # --- ссылка в конце строки ---
        (
            "Это утверждение требует источника [[3]](https://c.com)",
            'Это утверждение требует источника <a href="https://c.com" target="_blank" rel="noopener noreferrer">[3]</a>',
        ),
        # --- URL с query-параметрами ---
        (
            "[[1]](https://example.com/page?id=42&lang=ru)",
            '<a href="https://example.com/page?id=42&lang=ru" target="_blank" rel="noopener noreferrer">[1]</a>',
        ),
        # --- URL с якорем ---
        (
            "[[1]](https://example.com/page#section)",
            '<a href="https://example.com/page#section" target="_blank" rel="noopener noreferrer">[1]</a>',
        ),
        # --- обычная ссылка с текстом вперемешку с цитатой ---
        (
            "Подробнее на [сайте](https://example.com) и источник [[2]](https://b.com).",
            'Подробнее на <a href="https://example.com" target="_blank" rel="noopener noreferrer">сайт'
            'е</a> и источник <a href="https://b.com" target="_blank" rel="noopener noreferrer">[2]</a>.',
        ),
        # --- пустой текст ссылки ---
        (
            "[](https://example.com)",
            '<a href="https://example.com" target="_blank" rel="noopener noreferrer"></a>',
        ),
        # --- скобки в тексте ссылки не захватываются лишнего ---
        (
            "см. [[10]](https://x.com) далее",
            'см. <a href="https://x.com" target="_blank" rel="noopener noreferrer">[10]</a> далее',
        ),
    ],
)
def test_apply_markdown_links(text, expected):
    assert _apply_markdown_links(text) == expected


# ---------------------------------------------------------------------------
# Вспомогательная функция для краткости
# ---------------------------------------------------------------------------


def seg(type_: str, content: str) -> dict:
    return {"type": type_, "content": content, "is_like": False, "is_dislike": False, "comment": None}


# ---------------------------------------------------------------------------
# format_as_segments
# ---------------------------------------------------------------------------


def test_format_as_segments_empty():
    assert format_as_segments("") == []


def test_format_as_segments_blank_lines_only():
    assert format_as_segments("\n\n   \n") == []


def test_format_as_segments_single_paragraph():
    result = format_as_segments("Простой абзац.")
    assert result == [seg("p", "Простой абзац.")]


def test_format_as_segments_multiline_paragraph_joined():
    """Несколько строк подряд без пустых строк объединяются в один абзац через пробел."""
    text = "Строка первая.\nСтрока вторая.\nСтрока третья."
    result = format_as_segments(text)
    assert result == [seg("p", "Строка первая. Строка вторая. Строка третья.")]


def test_format_as_segments_two_paragraphs():
    text = "Первый абзац.\n\nВторой абзац."
    result = format_as_segments(text)
    assert result == [
        seg("p", "Первый абзац."),
        seg("p", "Второй абзац."),
    ]


@pytest.mark.parametrize(
    "prefix, tag",
    [
        ("# ", "h1"),
        ("## ", "h2"),
        ("### ", "h3"),
        ("#### ", "h4"),
        ("##### ", "h5"),
        ("###### ", "h6"),
    ],
)
def test_format_as_segments_headings(prefix, tag):
    result = format_as_segments(f"{prefix}Заголовок")
    assert result == [seg(tag, "Заголовок")]


@pytest.mark.parametrize("bullet", ["- ", "* ", "• "])
def test_format_as_segments_list_items(bullet):
    result = format_as_segments(f"{bullet}Элемент списка")
    assert result == [seg("li", "Элемент списка")]


def test_format_as_segments_multiple_list_items():
    text = "- Первый\n- Второй\n- Третий"
    result = format_as_segments(text)
    assert result == [
        seg("li", "Первый"),
        seg("li", "Второй"),
        seg("li", "Третий"),
    ]


def test_format_as_segments_heading_flushes_paragraph():
    """Заголовок сбрасывает накопленные строки абзаца перед собой."""
    text = "Абзац перед заголовком.\n## Заголовок"
    result = format_as_segments(text)
    assert result == [
        seg("p", "Абзац перед заголовком."),
        seg("h2", "Заголовок"),
    ]


def test_format_as_segments_mixed_structure():
    text = (
        "# Заголовок\n"
        "\n"
        "Первый абзац.\n"
        "\n"
        "## Раздел\n"
        "\n"
        "Второй абзац.\n"
        "Продолжение второго абзаца.\n"
        "\n"
        "- Пункт один\n"
        "- Пункт два\n"
    )
    result = format_as_segments(text)
    assert result == [
        seg("h1", "Заголовок"),
        seg("p", "Первый абзац."),
        seg("h2", "Раздел"),
        seg("p", "Второй абзац. Продолжение второго абзаца."),
        seg("li", "Пункт один"),
        seg("li", "Пункт два"),
    ]


def test_format_as_segments_inline_bold():
    result = format_as_segments("Текст с **жирным** словом.")
    assert result == [seg("p", "Текст с <b>жирным</b> словом.")]


def test_format_as_segments_inline_italic_asterisk():
    result = format_as_segments("Текст с *курсивом*.")
    assert result == [seg("p", "Текст с <i>курсивом</i>.")]


def test_format_as_segments_inline_italic_underscore():
    result = format_as_segments("Текст с _курсивом_.")
    assert result == [seg("p", "Текст с <i>курсивом</i>.")]


def test_format_as_segments_citation_link():
    """[[N]](url) превращается в <a>-тег, а не ломается inline-markdown."""
    text = "Факт из источника [[1]](https://ru.wikipedia.org/wiki/ARPANET)."
    result = format_as_segments(text)
    assert result == [
        seg(
            "p",
            'Факт из источника <a href="https://ru.wikipedia.org/wiki/ARPANET"'
            ' target="_blank" rel="noopener noreferrer">[1]</a>.',
        )
    ]


def test_format_as_segments_url_with_underscore_not_italicized():
    """Подчёркивание в URL не должно интерпретироваться как курсив."""
    text = "Источник [[1]](https://example.com/wiki/История_Интернета)."
    result = format_as_segments(text)
    assert result == [
        seg(
            "p",
            'Источник <a href="https://example.com/wiki/История_Интернета"'
            ' target="_blank" rel="noopener noreferrer">[1]</a>.',
        )
    ]


def test_format_as_segments_inline_and_citation_combined():
    """Жирный текст и цитата в одном абзаце обрабатываются корректно."""
    text = "**Важный** факт [[2]](https://b.com)."
    result = format_as_segments(text)
    assert result == [
        seg(
            "p",
            '<b>Важный</b> факт <a href="https://b.com"' ' target="_blank" rel="noopener noreferrer">[2]</a>.',
        )
    ]


def test_format_as_segments_segment_defaults():
    """Каждый сегмент имеет is_like=False, is_dislike=False, comment=None."""
    segments = format_as_segments("Абзац.\n\n## Заголовок\n\n- Пункт")
    for s in segments:
        assert s["is_like"] is False
        assert s["is_dislike"] is False
        assert s["comment"] is None
