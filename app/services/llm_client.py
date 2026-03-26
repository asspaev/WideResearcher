from loguru import logger
from openai import AsyncOpenAI


class LLMClient:
    """Клиент для обращения к OpenAI-совместимым LLM API.

    Работает с любым провайдером, поддерживающим формат /chat/completions:
    OpenAI, vLLM, Ollama, LM Studio и др.
    """

    def __init__(
        self,
        model_name: str,
        base_url: str,
        api_key: str | None = None,
    ) -> None:
        """Инициализирует клиент.

        Args:
            model_name: Идентификатор модели (например, "gpt-4o", "llama3").
            base_url: Базовый URL API (например, "https://api.openai.com/v1").
            api_key: API-ключ. Если None — подставляется заглушка "none"
                     (для локальных серверов вроде Ollama, которые ключ игнорируют).
        """
        self.model_name = model_name
        self._client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key or "none",
        )

    async def generate(self, context: list[dict]) -> str:
        """Отправляет запрос в модель и возвращает текстовый ответ.

        Args:
            context: Список сообщений в формате OpenAI Chat:
                     [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}].

        Returns:
            Текст ответа модели (content первого choice).
        """
        logger.debug(f"LLMClient: generate model={self.model_name} messages={len(context)}")
        response = await self._client.chat.completions.create(
            model=self.model_name,
            messages=context,
        )
        return response.choices[0].message.content
