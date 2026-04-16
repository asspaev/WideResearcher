from typing import TypeVar

from loguru import logger
from openai import AsyncOpenAI
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider

T = TypeVar("T", bound=BaseModel)


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
        self._base_url = base_url
        self._api_key = api_key or "none"
        self._client = AsyncOpenAI(
            base_url=base_url,
            api_key=self._api_key,
        )

    async def generate(self, context: list[dict]) -> str:
        """Отправляет запрос в модель и возвращает текстовый ответ.

        Args:
            context: Список сообщений в формате OpenAI Chat:
                     [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}].

        Returns:
            Текст ответа модели (content первого choice).
        """
        logger.debug(f"LLMClient: generate model={self.model_name} base_url={self._base_url} messages={len(context)}")
        response = await self._client.chat.completions.create(
            model=self.model_name,
            messages=context,
        )
        return response.choices[0].message.content

    async def generate_structured(self, context: list[dict], output_type: type[T]) -> T:
        """Отправляет запрос в модель и возвращает структурированный ответ в виде Pydantic-модели.

        Args:
            context: Список сообщений в формате OpenAI Chat.
            output_type: Pydantic-модель, которую должна вернуть модель.

        Returns:
            Экземпляр переданной Pydantic-модели, заполненный данными из ответа LLM.
        """
        logger.debug(
            f"LLMClient: generate_structured model={self.model_name} "
            f"messages={len(context)} output_type={output_type.__name__}"
        )
        provider = OpenAIProvider(base_url=self._base_url, api_key=self._api_key)
        model = OpenAIModel(self.model_name, provider=provider)
        agent: Agent[None, T] = Agent(model=model, output_type=output_type)

        system_messages = [m["content"] for m in context if m["role"] == "system"]
        user_messages = [m["content"] for m in context if m["role"] == "user"]

        system_prompt = "\n".join(system_messages) if system_messages else None
        user_prompt = "\n".join(user_messages)

        if system_prompt:
            agent = Agent(model=model, output_type=output_type, system_prompt=system_prompt)

        result = await agent.run(user_prompt)
        return result.output
