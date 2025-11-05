from loguru import logger

from app.schemas.predictions import GenerateRequest, InputPredict, LoadModelRequest, PredictionOutput
from app.utils.predictions import generate, load_model


async def run_predict(input_predict: InputPredict) -> PredictionOutput:
    """
    Runs a prediction using the currently loaded model.

    Args:
        input_predict: InputPredict

    Returns:
        str: The generated text.

    Raises:
        RuntimeError: If the model load or generation fails for any reason.
    """
    # TODO get model from settings of research and other settings
    model_path: str = "/models/misair-cotype-nano"
    max_tokens: int = input_predict.max_tokens
    temperature: float = input_predict.temperature

    # load model
    loaded_model = await load_model(LoadModelRequest(model_path=model_path))
    logger.debug("Load model result: {}", loaded_model)
    if loaded_model.get("status") != "model_loaded" and loaded_model.get("status") != "already_loaded":
        logger.error("Cannot proceed: model not loaded: {}", loaded_model)
        raise RuntimeError("Model load failed: " + str(loaded_model))

    # send prompt to model for generation
    gen_req = GenerateRequest(
        prompt=input_predict.prompt,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    gen_res = await generate(gen_req)
    if "error" in gen_res:
        logger.error("Generation returned error: {}", gen_res)
        raise RuntimeError("Generation error: " + str(gen_res))

    # return generated output
    return gen_res
