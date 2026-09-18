"""Deterministic ContextBudgeter enforcing hard character and token limits on retrieved evidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def estimate_tokens(text: str) -> int:
    """Estimate token count deterministically using whitespace and punctuation heuristics."""
    if not text:
        return 0
    # Safe rule of thumb: ~4 characters per token or word-based count * 1.3
    words = len(text.split())
    char_estimate = max(1, len(text) // 4)
    return max(int(words * 1.25), char_estimate)


@dataclass(frozen=True)
class BudgetTrace:
    """Diagnostic trace recording context budget enforcement."""

    chars_budget: int
    chars_used: int
    tokens_budget: int
    tokens_used: int
    items_budget: int
    items_selected: int
    items_dropped: int
    truncated_items: int = 0
    details: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "chars_budget": self.chars_budget,
            "chars_used": self.chars_used,
            "tokens_budget": self.tokens_budget,
            "tokens_used": self.tokens_used,
            "items_budget": self.items_budget,
            "items_selected": self.items_selected,
            "items_dropped": self.items_dropped,
            "truncated_items": self.truncated_items,
            "details": list(self.details),
        }


@dataclass(frozen=True)
class ContextBudgeter:
    """Authoritative deterministic budgeter enforcing hard character, token, and item limits."""

    max_chars: int = 12000
    max_tokens: int = 3000
    max_items: int = 4

    def enforce_budget(
        self, chunks: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Apply strict multi-constraint budget enforcement to candidate chunks."""
        bounded_chunks: list[dict[str, Any]] = []
        cur_chars = 0
        cur_tokens = 0
        items_dropped = 0
        truncated_count = 0
        details: list[dict[str, Any]] = []

        for index, chunk in enumerate(chunks):
            if len(bounded_chunks) >= self.max_items:
                items_dropped += 1
                details.append({
                    "chunk_id": chunk.get("id"),
                    "action": "DROPPED_MAX_ITEMS",
                    "reason": f"Reached max item count {self.max_items}",
                })
                continue

            text = chunk.get("text", "") or ""
            chunk_len = len(text)
            chunk_tokens = estimate_tokens(text)

            # Check if chunk fits within remaining character and token budget
            fits_chars = (cur_chars + chunk_len) <= self.max_chars
            fits_tokens = (cur_tokens + chunk_tokens) <= self.max_tokens

            if fits_chars and fits_tokens:
                bounded_chunks.append(chunk)
                cur_chars += chunk_len
                cur_tokens += chunk_tokens
                details.append({
                    "chunk_id": chunk.get("id"),
                    "action": "INCLUDED",
                    "chars": chunk_len,
                    "tokens": chunk_tokens,
                })
            elif not bounded_chunks:
                # If even the first chunk exceeds budget, truncate it to fit within max_chars
                allowed_chars = min(self.max_chars, int(self.max_tokens * 3.5))
                truncated_text = text[:allowed_chars]
                truncated_chunk = {
                    **chunk,
                    "text": truncated_text,
                    "metadata": {
                        **chunk.get("metadata", {}),
                        "truncated_for_budget": True,
                        "original_length": chunk_len,
                    },
                }
                bounded_chunks.append(truncated_chunk)
                cur_chars += len(truncated_text)
                cur_tokens += estimate_tokens(truncated_text)
                truncated_count += 1
                details.append({
                    "chunk_id": chunk.get("id"),
                    "action": "TRUNCATED_TO_FIT",
                    "chars": len(truncated_text),
                    "tokens": cur_tokens,
                })
            else:
                # Subsequent chunk exceeds budget; drop it to guarantee hard limits
                items_dropped += 1
                details.append({
                    "chunk_id": chunk.get("id"),
                    "action": "DROPPED_BUDGET_EXCEEDED",
                    "reason": f"Exceeded limits (chars: {cur_chars + chunk_len}/{self.max_chars}, tokens: {cur_tokens + chunk_tokens}/{self.max_tokens})",
                })

        trace = BudgetTrace(
            chars_budget=self.max_chars,
            chars_used=cur_chars,
            tokens_budget=self.max_tokens,
            tokens_used=cur_tokens,
            items_budget=self.max_items,
            items_selected=len(bounded_chunks),
            items_dropped=items_dropped,
            truncated_items=truncated_count,
            details=details,
        )

        return bounded_chunks, trace.to_dict()
