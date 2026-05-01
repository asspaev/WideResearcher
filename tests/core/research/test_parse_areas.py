import pytest

from app.core.research.search import _parse_areas


@pytest.mark.parametrize(
    "areas_str, expected_specific, expected_domains",
    [
        # --- пустые входные данные ---
        (None, [], []),
        ("", [], []),
        ("   ", [], []),
        (",,,", [], []),
        # --- конкретные URL (есть путь) ---
        (
            "https://www.youtube.com/shorts/gAJa-G2ved4",
            ["https://www.youtube.com/shorts/gAJa-G2ved4"],
            [],
        ),
        (
            "https://habr.com/ru/post/12345",
            ["https://habr.com/ru/post/12345"],
            [],
        ),
        (
            "http://example.com/page/deep",
            ["http://example.com/page/deep"],
            [],
        ),
        # --- корневые URL → домены ---
        ("https://www.youtube.com/", [], ["www.youtube.com"]),
        ("https://facebook.com/", [], ["facebook.com"]),
        ("http://example.com", [], ["example.com"]),
        # путь только из слэша считается корневым
        ("https://habr.com/", [], ["habr.com"]),
        # --- домены без схемы ---
        ("facebook.com", [], ["facebook.com"]),
        ("sub.domain.co.uk", [], ["sub.domain.co.uk"]),
        # --- невалидные значения (пропускаются) ---
        ("ютуб", [], []),
        ("youtube", [], []),  # нет точки
        ("just text", [], []),
        ("not a domain!", [], []),
        # --- смешанный ввод из примера в задаче ---
        (
            "https://www.youtube.com/shorts/gAJa-G2ved4, https://www.youtube.com/, ютуб, facebook.com",
            ["https://www.youtube.com/shorts/gAJa-G2ved4"],
            ["www.youtube.com", "facebook.com"],
        ),
        # --- несколько доменов ---
        (
            "habr.com, reddit.com, medium.com",
            [],
            ["habr.com", "reddit.com", "medium.com"],
        ),
        # --- несколько конкретных URL ---
        (
            "https://site.com/a, https://site.com/b",
            ["https://site.com/a", "https://site.com/b"],
            [],
        ),
        # --- дубликаты: функция их не убирает, это зона вызывающего кода ---
        (
            "habr.com, habr.com",
            [],
            ["habr.com", "habr.com"],
        ),
        # --- лишние пробелы вокруг элементов ---
        (
            "  habr.com  ,   reddit.com   ",
            [],
            ["habr.com", "reddit.com"],
        ),
    ],
)
def test_parse_areas(areas_str, expected_specific, expected_domains):
    specific, domains = _parse_areas(areas_str)
    assert specific == expected_specific
    assert domains == expected_domains
