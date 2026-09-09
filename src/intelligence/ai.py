from .provider import GeminiProvider


def chunks(text: str, size: int, maximum: int) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)][:maximum] or [""]


class GeminiAnalyzer(GeminiProvider):
    """Backward-compatible adapter for the retired legacy pipeline."""

    def __init__(self, api_key: str, prompts: dict[str, str], chunk_size: int, max_chunks: int) -> None:
        super().__init__(api_key, {"model": "gemini-3.6-flash", "max_output_tokens": 4096}, prompts)

    def analyze(self, item, topic: dict) -> dict:
        payload = item.to_dict() if hasattr(item, "to_dict") else item
        return self.analyze_micro_topic(payload, {"topic": topic}, [{"text": payload.get("text", ""), "metadata": {}}])
