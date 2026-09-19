"""Analysis contract instructions."""

from typing import Any

def build_analysis_prompt(contract: dict[str, Any], micro_topic: str) -> str:
    return f"""ANALYSIS CONTRACT FOR MICRO-TOPIC: {micro_topic}
Objective: Assess {micro_topic} using source-grounded evidence.
Distinguish verifiable FACTS from strategic INFERENCES.
Cite source URLs and evidence IDs for all material factual claims.
"""
