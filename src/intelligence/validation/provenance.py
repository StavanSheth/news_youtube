"""Claim-level provenance validation for micro-topic findings."""

from __future__ import annotations

from typing import Any


def validate_claim_provenance(
    analysis: dict[str, Any],
    context_packet: Any | None = None,
) -> tuple[bool, list[str]]:
    """Enforce claim-level provenance and citation integrity."""
    errors = []
    if not analysis:
        return True, []

    available_evidence_ids: set[str] = set()
    if context_packet:
        if isinstance(context_packet, dict):
            available_evidence_ids = set(context_packet.get("evidence_ids", []))
            for chunk in context_packet.get("retrieved_evidence", []):
                chunk_id = chunk.get("id") or chunk.get("metadata", {}).get("evidence_id")
                if chunk_id:
                    available_evidence_ids.add(str(chunk_id))
        elif hasattr(context_packet, "evidence_ids"):
            available_evidence_ids = set(context_packet.evidence_ids)

    # 1. Inspect claims if explicitly structured
    claims = analysis.get("claims", [])
    if isinstance(claims, list) and claims:
        for claim in claims:
            if not isinstance(claim, dict):
                continue
            claim_type = str(claim.get("claim_type", "FACT")).upper()
            is_inference = bool(claim.get("inference", False))
            is_speculation = bool(claim.get("speculation", False))
            evidence_ids = claim.get("evidence_ids", [])

            if claim_type in {"FACT", "REPORTED", "OFFICIAL"} and not is_inference and not is_speculation:
                if not evidence_ids:
                    errors.append(f"Material claim '{claim.get('text', '')[:40]}' lacks required evidence_ids citation")
                elif available_evidence_ids:
                    unknown_ids = set(evidence_ids) - available_evidence_ids
                    if unknown_ids:
                        errors.append(f"Claim references evidence IDs not present in context packet: {unknown_ids}")

    # 2. Inspect 'facts' list vs 'evidence' list in classic schema
    facts = analysis.get("facts", [])
    evidence = analysis.get("evidence", [])
    if isinstance(facts, list) and facts:
        # If facts exist, evidence citations must not be empty
        if not evidence and not claims:
            errors.append("Analysis contains factual claims but zero evidence citations")
        elif evidence:
            for item in evidence:
                if isinstance(item, dict):
                    if not item.get("text") and not item.get("source"):
                        errors.append("Evidence citation missing text or source link")

    return len(errors) == 0, errors
