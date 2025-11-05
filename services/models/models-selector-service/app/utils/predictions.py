import asyncio
import os
from typing import Any, Dict, Optional

from loguru import logger
from vllm import LLM, SamplingParams

from app.schemas.predictions import GenerateRequest, LoadModelRequest, PredictionOutput

llm_instance: LLM | None = None


async def _init_llm_in_thread(
    model_path: str,
    dtype: str,
    gpu_util: float = 0.7,
) -> LLM:
    """
    Loads vLLM model in a separate thread to avoid blocking event loop.

    Args:
        model_path (str): Path to the vLLM model.
        dtype (str): Data type for vLLM model.
        gpu_util (float, optional): GPU memory utilization for vLLM model. Defaults to 0.7.

    Returns:
        LLM: Loaded vLLM model.
    """
    # vLLM heavy sync init: run in thread to avoid blocking event loop
    return await asyncio.to_thread(
        LLM,
        model=model_path,
        dtype=dtype,
        gpu_memory_utilization=gpu_util,
    )


async def load_model(req: LoadModelRequest):
    """
    Loads vLLM model from a given path.

    Args:
        req (LoadModelRequest): Request with model path and dtype.

    Returns:
        dict: Status of model loading with detail if failed.
    """
    global llm_instance
    if llm_instance is not None:
        return {"status": "already_loaded"}

    model_path = req.model_path.rstrip("/")
    if not os.path.exists(model_path):
        logger.error("Model path does not exist: {}", model_path)
        return {"status": "error", "detail": "model_path_not_found"}

    try:
        logger.info("Starting model init in background thread: {}", model_path)
        llm_instance = await _init_llm_in_thread(model_path, req.dtype)
        logger.success("Model loaded: {}", model_path)
        return {"status": "model_loaded"}
    except Exception as exc:
        logger.exception("Failed to load model: {}", exc)
        llm_instance = None
        return {"status": "error", "detail": str(exc)}


def _extract_from_request_output(obj: Any) -> Dict[str, Optional[Any]]:
    req_id = getattr(obj, "request_id", None)
    prompt = getattr(obj, "prompt", None)

    outputs = getattr(obj, "outputs", None) or []
    texts = []
    for o in outputs:
        t = getattr(o, "text", None) or getattr(o, "output_text", None) or ""
        texts.append(t)
    text = "".join(texts)

    stop_reason = None
    for o in outputs:
        sr = getattr(o, "stop_reason", None)
        if sr:
            stop_reason = sr
            break
    if stop_reason is None and outputs:
        stop_reason = getattr(outputs[0], "finish_reason", None)

    logger.info(
        f"Extracted RequestOutput: request_id={req_id}, prompt_len={len(prompt) if prompt else 0}, "
        f"text_len={len(text)}, stop_reason={stop_reason!r}"
    )
    return {"request_id": req_id, "prompt": prompt, "text": text, "stop_reason": stop_reason}


async def _consume_result(obj: Any) -> str:
    """
    Собирает текст из объекта-результата (для объектов, не похожих на RequestOutput).
    Возвращает объединённый текст.
    """
    parts: list[str] = []
    try:
        logger.info(f"Start consuming result, obj_type={type(obj)}")

        # async iterator
        if hasattr(obj, "__aiter__"):
            logger.debug("Result is asynchronous iterator; iterating async")
            async for chunk in obj:
                # если chunk похож на RequestOutput — используем его repr? нет, лучше обработать текст
                # но если это RequestOutput — мы не захотим возвращать str(RequestOutput) здесь,
                # поэтому извлекаем текстовые поля, если они есть
                chunk_text = getattr(chunk, "output_text", None) or getattr(chunk, "text", None)
                if chunk_text is None and hasattr(chunk, "request_id") and hasattr(chunk, "outputs"):
                    # Встретили RequestOutput внутри стрима — извлекаем текст из него напрямую
                    extracted = _extract_from_request_output(chunk)
                    logger.debug("Found RequestOutput inside async stream; returning its text")
                    return extracted["text"]
                chunk_text = chunk_text or str(chunk)
                logger.debug(f"Got async chunk (len={len(chunk_text)}): {chunk_text[:200]!r}")
                parts.append(chunk_text)

        # sync iterator
        elif hasattr(obj, "__iter__") and not isinstance(obj, (str, bytes)):
            logger.debug("Result is synchronous iterator; iterating")
            for chunk in obj:
                chunk_text = getattr(chunk, "output_text", None) or getattr(chunk, "text", None)
                if chunk_text is None and hasattr(chunk, "request_id") and hasattr(chunk, "outputs"):
                    extracted = _extract_from_request_output(chunk)
                    logger.debug("Found RequestOutput inside sync stream; returning its text")
                    return extracted["text"]
                chunk_text = chunk_text or str(chunk)
                logger.debug(f"Got sync chunk (len={len(chunk_text)}): {chunk_text[:200]!r}")
                parts.append(chunk_text)

        else:
            text = getattr(obj, "output_text", None) or getattr(obj, "text", None) or str(obj)
            logger.debug(f"Single object result (len={len(text)}): {text[:200]!r}")
            parts.append(text)

        result = "".join(parts)
        logger.info(f"Finished consuming result, total_length={len(result)}")
        return result

    except Exception:
        logger.exception(f"Error while consuming generate result for obj_type={type(obj)}")
        raise


async def generate(req: GenerateRequest) -> PredictionOutput | dict[str, Any]:
    """
    Возвращает PredictionOutput (request_id, prompt, text, stop_reason)
    либо {"error": ...} в случае ошибки.
    """
    global llm_instance
    if llm_instance is None:
        preview = (req.prompt[:200] + "...") if len(req.prompt) > 200 else req.prompt
        logger.warning(f"Generate called but model not loaded. prompt_preview={preview!r}")
        return {"error": "model_not_loaded"}

    sampling_params = SamplingParams(max_tokens=req.max_tokens, temperature=req.temperature)
    logger.info(
        f"Starting generation: prompt_len={len(req.prompt)}, "
        f"max_tokens={req.max_tokens}, temperature={req.temperature}"
    )

    try:
        maybe = llm_instance.generate(req.prompt, sampling_params)

        # --- coroutine ---
        if asyncio.iscoroutine(maybe):
            logger.debug("llm_instance.generate returned coroutine -> awaiting")
            obj = await maybe
            if hasattr(obj, "request_id") and hasattr(obj, "outputs"):
                return PredictionOutput(**_extract_from_request_output(obj))
            text = await _consume_result(obj)
            return PredictionOutput(
                request_id=getattr(obj, "request_id", None),
                prompt=getattr(obj, "prompt", None),
                text=text or "",
                stop_reason=getattr(obj, "stop_reason", None) or getattr(obj, "finish_reason", None),
            )

        # --- async iterator ---
        if hasattr(maybe, "__aiter__"):
            logger.debug("llm_instance.generate returned async iterator -> iterating chunks")
            parts: list[str] = []
            async for chunk in maybe:
                if hasattr(chunk, "request_id") and hasattr(chunk, "outputs"):
                    return PredictionOutput(**_extract_from_request_output(chunk))
                chunk_text = getattr(chunk, "output_text", None) or getattr(chunk, "text", None) or str(chunk)
                parts.append(chunk_text)
            text = "".join(parts)
            return PredictionOutput(text=text or "")

        # --- sync iterator ---
        if hasattr(maybe, "__iter__") and not isinstance(maybe, (str, bytes)):
            logger.debug("llm_instance.generate returned sync iterator -> iterating chunks")
            parts: list[str] = []
            for chunk in maybe:
                if hasattr(chunk, "request_id") and hasattr(chunk, "outputs"):
                    return PredictionOutput(**_extract_from_request_output(chunk))
                chunk_text = getattr(chunk, "output_text", None) or getattr(chunk, "text", None) or str(chunk)
                parts.append(chunk_text)
            text = "".join(parts)
            return PredictionOutput(text=text or "")

        # --- single object ---
        obj = maybe
        if hasattr(obj, "request_id") and hasattr(obj, "outputs"):
            return PredictionOutput(**_extract_from_request_output(obj))

        text = await _consume_result(obj)
        return PredictionOutput(
            request_id=getattr(obj, "request_id", None),
            prompt=getattr(obj, "prompt", None),
            text=text or "",
            stop_reason=getattr(obj, "stop_reason", None) or getattr(obj, "finish_reason", None),
        )

    except Exception as exc:
        logger.exception(f"Generation failed: {exc}")
        return {"error": "generation_failed", "detail": str(exc)}
