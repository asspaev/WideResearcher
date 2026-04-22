from typing import Any, Coroutine, TypeVar

from loguru import logger
from openai import AsyncOpenAI
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.crud.model_output import create_model_output, update_model_output
from app.models.model_output import ModelResponseStatus

T = TypeVar("T", bound=BaseModel)


class LLMGenerationError(Exception):
    """Ошибка при генерации ответа языковой моделью."""

    def __init__(self, message: str, cause: Exception | None = None) -> None:
        super().__init__(message)
        self.cause = cause


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
            timeout=get_settings().app.llm_timeout,
        )

    async def _run_with_tracking(
        self,
        coro: Coroutine[Any, Any, Any],
        model_input: dict,
        session: AsyncSession,
        model_id: int,
        research_id: int,
        step_type: str,
    ) -> Any:
        """Выполняет корутину генерации с сохранением хода выполнения в БД.

        Создаёт запись со статусом PROCESSING до запроса к модели, после
        получения ответа обновляет её до COMPLETE или ERROR.

        Args:
            coro: Корутина, выполняющая фактический запрос к модели.
            model_input: Входные данные (сохраняются в БД).
            session: Асинхронная сессия БД.
            model_id: ID модели.
            research_id: ID исследования.
            step_type: Тип шага пайплайна.

        Returns:
            Результат корутины.

        Raises:
            LLMGenerationError: Если запрос к модели завершился ошибкой.
        """
        record = await create_model_output(
            session=session,
            model_id=model_id,
            research_id=research_id,
            step_type=step_type,
            model_input=model_input,
            model_output={},
            response_status=ModelResponseStatus.PROCESSING,
        )
        try:
            result = await coro
            output = result.model_dump() if isinstance(result, BaseModel) else {"content": result}
            await update_model_output(
                session=session,
                response_id=record.response_id,
                response_status=ModelResponseStatus.COMPLETE,
                model_output=output,
            )
            return result
        except LLMGenerationError:
            raise
        except Exception as e:
            await update_model_output(
                session=session,
                response_id=record.response_id,
                response_status=ModelResponseStatus.ERROR,
                model_output={},
                error_body=str(e),
            )
            raise LLMGenerationError(f"Ошибка при генерации ответа моделью {self.model_name}: {e}", cause=e) from e

    async def embed(self, text: str) -> list[float]:
        """Возвращает вектор эмбеддинга для переданного текста.

        Args:
            text: Текст для эмбеддинга.

        Returns:
            Вектор эмбеддинга в виде списка float.

        Raises:
            LLMGenerationError: Если запрос к модели завершился ошибкой.
        """
        try:
            response = await self._client.embeddings.create(
                model=self.model_name,
                input=text,
            )
            return response.data[0].embedding
        except Exception as e:
            raise LLMGenerationError(f"Ошибка при получении эмбеддинга моделью {self.model_name}: {e}", cause=e) from e

    async def _do_generate(self, context: list[dict]) -> str:
        logger.debug(f"LLMClient: generate model={self.model_name} base_url={self._base_url} messages={len(context)}")
        response = await self._client.chat.completions.create(
            model=self.model_name,
            messages=context,
        )
        return response.choices[0].message.content

    async def _do_generate_structured(self, context: list[dict], output_type: type[T]) -> T:
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

    async def generate(
        self,
        context: list[dict],
        session: AsyncSession,
        model_id: int,
        research_id: int,
        step_type: str,
    ) -> str:
        """Отправляет запрос в модель и возвращает текстовый ответ.

        Args:
            context: Список сообщений в формате OpenAI Chat:
                     [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}].
            session: Асинхронная сессия БД для сохранения результата.
            model_id: ID модели.
            research_id: ID исследования.
            step_type: Тип шага пайплайна.

        Returns:
            Текст ответа модели.

        Raises:
            LLMGenerationError: Если запрос завершился ошибкой.
        """
        return await self._run_with_tracking(
            coro=self._do_generate(context),
            model_input={"messages": context},
            session=session,
            model_id=model_id,
            research_id=research_id,
            step_type=step_type,
        )

    async def generate_structured(
        self,
        context: list[dict],
        output_type: type[T],
        session: AsyncSession,
        model_id: int,
        research_id: int,
        step_type: str,
    ) -> T:
        """Отправляет запрос в модель и возвращает структурированный ответ в виде Pydantic-модели.

        Args:
            context: Список сообщений в формате OpenAI Chat.
            output_type: Pydantic-модель, которую должна вернуть модель.
            session: Асинхронная сессия БД для сохранения результата.
            model_id: ID модели.
            research_id: ID исследования.
            step_type: Тип шага пайплайна.

        Returns:
            Экземпляр переданной Pydantic-модели, заполненный данными из ответа LLM.

        Raises:
            LLMGenerationError: Если запрос завершился ошибкой.
        """
        return await self._run_with_tracking(
            coro=self._do_generate_structured(context, output_type),
            model_input={"messages": context},
            session=session,
            model_id=model_id,
            research_id=research_id,
            step_type=step_type,
        )
