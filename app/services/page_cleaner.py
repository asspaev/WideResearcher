"""Очистка HTML-контента до чистого текста."""

import trafilatura
from loguru import logger


class PageCleaner:
    """Извлекает чистый текст из сырого HTML через trafilatura."""

    def clean(self, html: str) -> str | None:
        """Извлекает читаемый текст из HTML-страницы.

        Args:
            html: Сырой HTML-контент страницы.

        Returns:
            Чистый текст или None если извлечение не удалось.
        """
        result = trafilatura.extract(html, include_formatting=False, no_fallback=False)
        if result is None:
            logger.debug("PageCleaner: trafilatura returned None")
        return result
