import asyncio
import json
from typing import Any, Awaitable, Callable, Coroutine, TypeVar

from loguru import logger
from openai import AsyncOpenAI
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.sql import get_sql
from app.crud.model_output import create_model_output, update_model_output
from app.models.model_output import ModelResponseStatus

T = TypeVar("T", bound=BaseModel)

LLM_JSON_RETRIES = 3
LLM_JSON_RETRY_BACKOFF = 1.0


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
        n_async: int = 1,
    ) -> None:
        """Инициализирует клиент.

        Args:
            model_name: Идентификатор модели (например, "gpt-4o", "llama3").
            base_url: Базовый URL API (например, "https://api.openai.com/v1").
            api_key: API-ключ. Если None — подставляется заглушка "none"
                     (для локальных серверов вроде Ollama, которые ключ игнорируют).
            n_async: Максимальное число одновременно выполняемых запросов в
                методах ``*_many`` (управление конкурентностью через семафор).
        """
        self.model_name = model_name
        self.n_async = max(1, int(n_async))
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

    async def _run_with_tracking_isolated(
        self,
        coro_factory: Callable[[], Awaitable[Any]],
        model_input: dict,
        model_id: int,
        research_id: int,
        step_type: str,
    ) -> Any:
        """Аналог ``_run_with_tracking``, но открывает свою AsyncSession.

        Нужен для параллельных вызовов: одна сессия SQLAlchemy не может
        безопасно использоваться из нескольких корутин одновременно, поэтому
        каждая задача в ``*_many`` методах получает свою независимую сессию.

        Args:
            coro_factory: Фабрика корутины — вызывается внутри сессии, чтобы
                ленив создавать корутину (важно для повторных запусков).
            model_input: Данные запроса для сохранения в БД.
            model_id: ID модели.
            research_id: ID исследования.
            step_type: Тип шага пайплайна.

        Returns:
            Результат корутины.

        Raises:
            LLMGenerationError: При ошибке запроса к модели.
        """
        session_factory = get_sql().session_factory
        async with session_factory() as session:
            return await self._run_with_tracking(
                coro=coro_factory(),
                model_input=model_input,
                session=session,
                model_id=model_id,
                research_id=research_id,
                step_type=step_type,
            )

    async def _call_with_json_retry(self, coro_factory: Callable[[], Awaitable[Any]]) -> Any:
        """Запускает корутину с ретраями на json.JSONDecodeError.

        Некоторые провайдеры (например, OpenRouter) изредка возвращают 200 OK
        с невалидным телом (HTML/пробелы) — OpenAI SDK сам такие случаи не
        ретраит, и единичный плохой ответ роняет весь шаг исследования.

        Args:
            coro_factory: Фабрика, которая на каждый вызов создаёт новую корутину
                с HTTP-запросом (нельзя re-await один и тот же объект).

        Returns:
            Результат успешной попытки.

        Raises:
            json.JSONDecodeError: Если все LLM_JSON_RETRIES попытки вернули битый JSON.
        """
        last_exc: json.JSONDecodeError | None = None
        for attempt in range(1, LLM_JSON_RETRIES + 1):
            try:
                return await coro_factory()
            except json.JSONDecodeError as e:
                last_exc = e
                logger.warning(
                    f"LLMClient: malformed JSON from {self.model_name} " f"(attempt {attempt}/{LLM_JSON_RETRIES}): {e}"
                )
                if attempt < LLM_JSON_RETRIES:
                    await asyncio.sleep(LLM_JSON_RETRY_BACKOFF * attempt)
        assert last_exc is not None
        raise last_exc

    async def _do_embed(self, text: str) -> list[float]:
        response = await self._call_with_json_retry(
            lambda: self._client.embeddings.create(
                model=self.model_name,
                input=text,
            )
        )
        return response.data[0].embedding

    async def embed(
        self,
        text: str,
        session: AsyncSession,
        model_id: int,
        research_id: int,
        step_type: str,
    ) -> list[float]:
        """Возвращает вектор эмбеддинга для переданного текста с сохранением в model_outputs.

        Args:
            text: Текст для эмбеддинга.
            session: Асинхронная сессия БД для сохранения результата.
            model_id: ID модели.
            research_id: ID исследования.
            step_type: Тип шага пайплайна.

        Returns:
            Вектор эмбеддинга в виде списка float.

        Raises:
            LLMGenerationError: Если запрос к модели завершился ошибкой.
        """
        return await self._run_with_tracking(
            coro=self._do_embed(text),
            model_input={"text": text},
            session=session,
            model_id=model_id,
            research_id=research_id,
            step_type=step_type,
        )

    async def _do_generate(self, context: list[dict]) -> str:
        logger.debug(f"LLMClient: generate model={self.model_name} base_url={self._base_url} messages={len(context)}")
        response = await self._call_with_json_retry(
            lambda: self._client.chat.completions.create(
                model=self.model_name,
                messages=context,
            )
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

    async def _gather_many(
        self,
        items: list[Any],
        call_for: Callable[[Any], Awaitable[Any]],
        model_input_for: Callable[[Any], dict],
        model_id: int,
        research_id: int,
        step_type: str,
        return_exceptions: bool,
    ) -> list[Any]:
        """Запускает корутины параллельно с ограничением ``self.n_async`` и трекингом.

        Args:
            items: Список входных данных, по одному элементу на запрос.
            call_for: Функция, по элементу собирающая Awaitable с запросом.
            model_input_for: Функция, по элементу формирующая dict для записи в БД.
            model_id: ID модели.
            research_id: ID исследования.
            step_type: Тип шага пайплайна.
            return_exceptions: Если True — исключения возвращаются как элементы
                списка результатов; иначе первое исключение перевыбрасывается.

        Returns:
            Список результатов в порядке ``items``. При ``return_exceptions=True``
            на месте упавших задач — экземпляры ``LLMGenerationError``.
        """
        if not items:
            return []

        semaphore = asyncio.Semaphore(self.n_async)

        async def _task(item: Any) -> Any:
            async with semaphore:
                return await self._run_with_tracking_isolated(
                    coro_factory=lambda it=item: call_for(it),
                    model_input=model_input_for(item),
                    model_id=model_id,
                    research_id=research_id,
                    step_type=step_type,
                )

        logger.debug(
            f"LLMClient: gather_many model={self.model_name} step={step_type} "
            f"items={len(items)} n_async={self.n_async}"
        )
        return await asyncio.gather(*(_task(it) for it in items), return_exceptions=return_exceptions)

    async def generate_many(
        self,
        contexts: list[list[dict]],
        model_id: int,
        research_id: int,
        step_type: str,
        return_exceptions: bool = True,
    ) -> list[str | LLMGenerationError]:
        """Параллельно отправляет несколько запросов на генерацию текста.

        Ожидает завершения всех ``len(contexts)`` запросов, прежде чем вернуть
        результат. Конкурентность ограничена ``self.n_async``.

        Args:
            contexts: Список контекстов (каждый — список сообщений OpenAI Chat).
            model_id: ID модели.
            research_id: ID исследования.
            step_type: Тип шага пайплайна.
            return_exceptions: Если True (по умолчанию) — ошибки возвращаются
                как ``LLMGenerationError`` в соответствующих позициях.

        Returns:
            Список текстов (или исключений) в порядке ``contexts``.
        """
        return await self._gather_many(
            items=contexts,
            call_for=lambda ctx: self._do_generate(ctx),
            model_input_for=lambda ctx: {"messages": ctx},
            model_id=model_id,
            research_id=research_id,
            step_type=step_type,
            return_exceptions=return_exceptions,
        )

    async def embed_many(
        self,
        texts: list[str],
        model_id: int,
        research_id: int,
        step_type: str,
        return_exceptions: bool = True,
    ) -> list[list[float] | LLMGenerationError]:
        """Параллельно получает эмбеддинги для нескольких текстов.

        Ожидает завершения всех ``len(texts)`` запросов, прежде чем вернуть
        результат. Конкурентность ограничена ``self.n_async``.

        Args:
            texts: Список текстов для эмбеддинга.
            model_id: ID модели.
            research_id: ID исследования.
            step_type: Тип шага пайплайна.
            return_exceptions: Если True (по умолчанию) — ошибки возвращаются
                как ``LLMGenerationError`` в соответствующих позициях.

        Returns:
            Список векторов (или исключений) в порядке ``texts``.
        """
        return await self._gather_many(
            items=texts,
            call_for=lambda t: self._do_embed(t),
            model_input_for=lambda t: {"text": t},
            model_id=model_id,
            research_id=research_id,
            step_type=step_type,
            return_exceptions=return_exceptions,
        )

    async def generate_structured_many(
        self,
        contexts: list[list[dict]],
        output_type: type[T],
        model_id: int,
        research_id: int,
        step_type: str,
        return_exceptions: bool = True,
    ) -> list[T | LLMGenerationError]:
        """Параллельно отправляет несколько запросов на структурированный ответ.

        Ожидает завершения всех ``len(contexts)`` запросов, прежде чем вернуть
        результат. Конкурентность ограничена ``self.n_async``.

        Args:
            contexts: Список контекстов в формате OpenAI Chat.
            output_type: Pydantic-модель, которую возвращает каждая генерация.
            model_id: ID модели.
            research_id: ID исследования.
            step_type: Тип шага пайплайна.
            return_exceptions: Если True (по умолчанию) — ошибки возвращаются
                как ``LLMGenerationError`` в соответствующих позициях.

        Returns:
            Список экземпляров ``output_type`` (или исключений) в порядке ``contexts``.
        """
        return await self._gather_many(
            items=contexts,
            call_for=lambda ctx: self._do_generate_structured(ctx, output_type),
            model_input_for=lambda ctx: {"messages": ctx},
            model_id=model_id,
            research_id=research_id,
            step_type=step_type,
            return_exceptions=return_exceptions,
        )
