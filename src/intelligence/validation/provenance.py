"""Claim-level provenance validation for micro-topic findings."""

from __future__ import annotations

from typing import Any


def verify_provenance(claim: dict[str, Any], context_packet: Any | None = None) -> tuple[bool, list[str]]:
    """Verify deep provenance integrity: claim -> evidence_id -> content_id -> source_id -> URL."""
    errors = []
    evidence_ids = claim.get("evidence_ids", [])
    if isinstance(claim.get("evidence_id"), str) and claim["evidence_id"] not in evidence_ids:
        evidence_ids = [*evidence_ids, claim["evidence_id"]]

    if not context_packet:
        claim_type = str(claim.get("claim_type", "FACT")).upper()
        if claim_type in {"FACT", "REPORTED", "OFFICIAL"} and not claim.get("inference") and not claim.get("speculation"):
            return False, ["Material claim cannot be verified without ContextPacket (fail-closed)"]
        return True, []

    chunk_map: dict[str, dict[str, Any]] = {}
    valid_eids: set[str] = set()
    if isinstance(context_packet, dict):
        for eid in context_packet.get("evidence_ids", []):
            valid_eids.add(str(eid))
        for chunk in context_packet.get("retrieved_evidence", []):
            cid = chunk.get("id") or chunk.get("metadata", {}).get("evidence_id")
            if cid:
                chunk_map[str(cid)] = chunk
                valid_eids.add(str(cid))
    elif hasattr(context_packet, "retrieved_evidence"):
        for chunk in context_packet.retrieved_evidence:
            cid = chunk.get("id") or chunk.get("metadata", {}).get("evidence_id")
            if cid:
                chunk_map[str(cid)] = chunk
                valid_eids.add(str(cid))
    if hasattr(context_packet, "evidence_ids"):
        for eid in context_packet.evidence_ids:
            valid_eids.add(str(eid))

    for eid in evidence_ids:
        if valid_eids and str(eid) not in valid_eids:
            errors.append(f"Referenced evidence_id '{eid}' does not exist in context packet")
            continue
        chunk = chunk_map.get(str(eid))
        if not chunk:
            continue
        meta = chunk.get("metadata", {})
        expected_content_id = meta.get("content_id")
        expected_source_id = meta.get("source_id") or meta.get("source")

        if "content_id" in claim and expected_content_id and claim["content_id"] != expected_content_id:
            errors.append(
                f"Provenance mismatch: claim specifies content_id '{claim['content_id']}' "
                f"but evidence '{eid}' belongs to content_id '{expected_content_id}'"
            )
        if "source_id" in claim and expected_source_id and claim["source_id"] != expected_source_id:
            errors.append(
                f"Provenance mismatch: claim specifies source_id '{claim['source_id']}' "
                f"but evidence '{eid}' belongs to source_id '{expected_source_id}'"
            )

    return len(errors) == 0, errors


def validate_claim_provenance(
    analysis: dict[str, Any],
    context_packet: Any | None = None,
) -> tuple[bool, list[str]]:
    """Enforce claim-level provenance and citation integrity with fail-closed guarantee."""
    errors = []
    if not analysis:
        return False, ["Analysis payload is empty"]

    # Fail-closed check: Material claims without context packet must fail
    claims = analysis.get("claims", [])
    facts = analysis.get("facts", [])
    has_material_claims = any(
        isinstance(c, dict)
        and str(c.get("claim_type", "FACT")).upper() in {"FACT", "REPORTED", "OFFICIAL"}
        and not bool(c.get("inference", False))
        and not bool(c.get("speculation", False))
        for c in (claims if isinstance(claims, list) else [])
    ) or (isinstance(facts, list) and bool(facts) and not bool(analysis.get("evidence")))

    if not context_packet and has_material_claims:
        return False, ["Material factual claim cannot be verified: no ContextPacket provided (fail-closed)"]

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
    if isinstance(claims, list) and claims:
        for claim in claims:
            if not isinstance(claim, dict):
                continue
            claim_type = str(claim.get("claim_type", "FACT")).upper()
            is_inference = bool(claim.get("inference", False))
            is_speculation = bool(claim.get("speculation", False))
            evidence_ids = claim.get("evidence_ids", [])
            if isinstance(claim.get("evidence_id"), str) and claim["evidence_id"] not in evidence_ids:
                evidence_ids = [*evidence_ids, claim["evidence_id"]]

            if claim_type in {"FACT", "REPORTED", "OFFICIAL"} and not is_inference and not is_speculation:
                if not evidence_ids:
                    errors.append(f"Material claim '{claim.get('text', '')[:40]}' lacks required evidence_ids citation")
                elif available_evidence_ids:
                    unknown_ids = set(evidence_ids) - available_evidence_ids
                    if unknown_ids:
                        errors.append(f"Claim references evidence IDs not present in context packet: {unknown_ids}")

            # Verify deep provenance integrity
            deep_ok, deep_errs = verify_provenance(claim, context_packet)
            if not deep_ok:
                errors.extend(deep_errs)

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
