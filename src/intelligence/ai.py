from __future__ import annotations

import json
from typing import Any


def chunks(text: str, size: int, maximum: int) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)][:maximum] or [""]


class GeminiAnalyzer:
    def __init__(
        self, api_key: str, prompts: dict[str, str], chunk_size: int, max_chunks: int
    ) -> None:
        from google import genai

        self.client = genai.Client(api_key=api_key)
        self.prompts, self.chunk_size, self.max_chunks = prompts, chunk_size, max_chunks

    def _json(self, prompt: str) -> dict[str, Any]:
        response = self.client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        payload = json.loads(response.text)
        if not isinstance(payload, dict):
            raise ValueError("Gemini returned a non-object JSON response")
        return payload

    def analyze(self, item, topic: dict) -> dict[str, Any]:
        extracted = []
        for chunk in chunks(item.text, self.chunk_size, self.max_chunks):
            extracted.append(
                self._json(f"{self.prompts['chunk_extraction']}\n\nSOURCE CHUNK:\n{chunk}")
            )
        facts = list(
            dict.fromkeys(fact for result in extracted for fact in result.get("facts", []))
        )
        prompt = f"{self.prompts['topic_analysis']}\n\nTOPIC:\n{json.dumps(topic)}\n\nSOURCE METADATA:\n{item.title} {item.url}\n\nEXTRACTED FACTS:\n{json.dumps(facts)}"
        result = self._json(prompt)
        result["facts"] = list(dict.fromkeys(result.get("facts", []) + facts))
        return result
