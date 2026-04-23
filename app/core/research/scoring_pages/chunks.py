import tiktoken

# text-embedding-3-small и большинство LLM-reranker поддерживают до 8 192 токенов
_MAX_TOKENS_PER_CHUNK = 7_000
_EMBED_ENCODING = "cl100k_base"


def chunk_text(text: str, max_tokens: int = _MAX_TOKENS_PER_CHUNK) -> list[str]:
    """Разбивает текст на чанки по количеству токенов.

    Args:
        text: Исходный текст для нарезки.
        max_tokens: Максимальное число токенов в одном чанке.

    Returns:
        Список строк-чанков, каждый не превышает max_tokens токенов.
    """
    enc = tiktoken.get_encoding(_EMBED_ENCODING)
    tokens = enc.encode(text)
    chunks = []
    for i in range(0, len(tokens), max_tokens):
        chunks.append(enc.decode(tokens[i : i + max_tokens]))
    return chunks
