"""Authoritative multi-stage micro-topic classification engine."""

from __future__ import annotations

from typing import Any
from ..classification import KeywordClassifier
from .decisions import MicroTopicDecision
from .scoring import compute_confidence
from .signals import group_policy_satisfied, phrase_found


def classify_micro_topics(
    item: dict[str, Any],
    entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Classify only micro-topics with independent, explainable evidence."""
    title_lower = str(item.get("title", "")).lower()
    body_lower = str(item.get("text", "")).lower()
    text_lower = f"{title_lower}\n{body_lower}"
    candidates: list[dict[str, Any]] = []

    # Step 1: Candidate evaluation across enabled catalog leaves
    for entry in entries:
        if not entry.get("enabled", True):
            continue

        positive_phrases = [
            {"phrase": alias, "strength": "strong" if len(str(alias).split()) >= 2 else "weak", "type": "positive", "source": "alias"}
            for alias in entry.get("aliases", [])
        ] + list(entry.get("positive_signals", []))

        # Positive & negative scoring using KeywordClassifier
        scored = KeywordClassifier.score(
            text_lower,
            positive_phrases,
            list(entry.get("negative_signals", [])),
            title=title_lower,
            signal_groups=entry.get("signal_groups", {}),
            disambiguators=entry.get("disambiguators", []),
        )
        signals = scored["matched_signals"]
        negative = scored["negative_signals"]
        score = scored["score"]
        threshold = float(entry.get("primary_threshold", entry.get("classification_threshold", 0.5)))
        matched_groups = scored.get("matched_signal_groups", {})
        policy = entry.get("group_policy", entry.get("required_signal_groups", []))
        groups_satisfied, missing_groups = group_policy_satisfied(policy, matched_groups)

        # Entity / Event disambiguation signals
        matched_disambiguators = [
            str(value) for value in entry.get("disambiguators", [])
            if phrase_found(str(value), text_lower)
        ]
        matched_entities = [
            str(entity) for entity in entry.get("entity_signals", [])
            if phrase_found(str(entity), text_lower)
        ]
        matched_events = [
            str(event) for event in entry.get("event_signals", [])
            if phrase_found(str(event), text_lower)
        ]

        # Signal qualification: multiple compatible signals OR strong exact signal OR entity/event + signal
        has_strong_signal = any(
            (isinstance(s, dict) and s.get("strength") == "strong") or len(str(s).split()) >= 2
            for s in signals
        )
        has_entity_event_support = bool(matched_entities or matched_events or matched_disambiguators)
        qualified_signal_structure = len(signals) >= 2 or has_strong_signal or has_entity_event_support

        # Hard negative signal exclusion
        has_hard_rejection = bool(scored.get("hard_rejection_reason")) or bool(scored.get("matched_contradictions"))

        if (
            signals
            and score >= float(entry.get("secondary_threshold", threshold))
            and groups_satisfied
            and not has_hard_rejection
            and qualified_signal_structure
        ):
            candidates.append({
                **entry,
                "signals": signals,
                "positive_signals": signals,
                "matched_negative_signals": negative,
                "matched_signal_groups": matched_groups,
                "disambiguators": matched_disambiguators,
                "entity_signals_matched": matched_entities,
                "event_signals_matched": matched_events,
                "classification_score": round(score, 3),
                "negative_penalty": scored["negative_penalty"],
                "contradiction_penalty": scored["contradiction_penalty"],
                "confidence_method": "heuristic_weighted_signal_score",
                "classification_reason": f"matched {', '.join(signals)}" + (f"; excluded by {', '.join(negative)}" if negative else ""),
                "decision_state": "MATCH",
                "topic_id": entry["topic_key"],
                "analysis_contract": entry.get("profile", {}).get("analysis_contract", {}),
            })

    # Sort deterministically by score descending, then by micro_topic slug
    candidates.sort(key=lambda match: (-match["classification_score"], str(match["micro_topic"])))
    if not candidates:
        return []

    primary = candidates[0]
    runner_up = candidates[1]["classification_score"] if len(candidates) > 1 else 0.0
    margin = round(primary["classification_score"] - runner_up, 3)
    primary_threshold = float(primary.get("primary_threshold", primary.get("classification_threshold", 0.5)))

    if primary["classification_score"] < primary_threshold:
        return []

    selected = []
    secondary_count = 0
    for index, candidate in enumerate(candidates):
        if index == 0:
            status = "PRIMARY"
        elif secondary_count >= int(primary.get("max_secondary", 1)):
            continue
        elif candidate["classification_score"] < float(candidate.get("secondary_threshold", 0.5)) or (
            margin < float(primary.get("runner_up_margin", 0.05))
            and not candidate.get("disambiguators")
            and not candidate.get("matched_signal_groups")
        ):
            continue
        else:
            status = "SECONDARY"
            secondary_count += 1

        confidence = compute_confidence(
            candidate["classification_score"],
            margin,
            candidate["signals"],
            candidate["contradiction_penalty"],
        )
        missing_groups = [
            group for group in candidate.get("required_signal_groups", [])
            if not candidate.get("matched_signal_groups", {}).get(group)
        ]

        decision = MicroTopicDecision(
            micro_topic_id=str(candidate.get("micro_topic_id", candidate.get("micro_topic", ""))),
            domain_id=str(candidate.get("domain", "")),
            topic_id=str(candidate.get("topic_id", candidate.get("topic_key", ""))),
            confidence=confidence,
            classification_score=float(candidate["classification_score"]),
            runner_up_score=runner_up,
            margin=margin,
            matched_signals=tuple(candidate["signals"]),
            negative_matches=tuple(candidate.get("matched_negative_signals", ())),
            classification_status=status,
            significance=float(candidate["classification_score"]),
            event_ids=tuple(candidate.get("event_signals_matched", ())),
            entity_ids=tuple(candidate.get("entity_signals_matched", ())),
            evidence_scope_id=f"scope-{candidate.get('micro_topic', '')}",
            threshold=primary_threshold if index == 0 else float(candidate.get("secondary_threshold", 0.5)),
            matched_signal_groups=candidate.get("matched_signal_groups", {}),
            missing_signal_groups=tuple(missing_groups),
            distractors=tuple(candidate.get("matched_distractors", ())),
            contradictions=tuple(candidate.get("matched_contradictions", ())),
            exclusions=tuple(candidate.get("matched_exclusions", ())),
            profile_origin=candidate.get("profile_origin_code", candidate.get("profile_origin")),
        )

        candidate.update({
            "classification_status": status,
            "decision": status,
            "positive_evidence": candidate["signals"],
            "negative_evidence": candidate.get("matched_negative_signals", []),
            "missing_signal_groups": missing_groups,
            "primary_score": primary["classification_score"],
            "runner_up_score": runner_up,
            "runner_up_topic": candidates[1].get("micro_topic") if len(candidates) > 1 else None,
            "margin": margin,
            "threshold": primary_threshold if index == 0 else float(candidate.get("secondary_threshold", 0.5)),
            "classification_confidence": confidence,
            "routing_confidence": confidence,
            "confidence": confidence,
            "decision_contract": decision.to_dict(),
        })
        selected.append(candidate)

    return selected


class MicroTopicClassificationEngine:
    """Authoritative classification engine mapping source items to MicroTopicDecision contracts."""

    def __init__(self, catalog_entries: list[dict[str, Any]] | None = None) -> None:
        self.entries = list(catalog_entries) if catalog_entries is not None else []

    def classify(
        self,
        item: dict[str, Any],
        entries: list[dict[str, Any]] | None = None,
    ) -> list[MicroTopicDecision]:
        """Classify item and return strictly typed MicroTopicDecision contracts."""
        target_entries = entries if entries is not None else self.entries
        matches = classify_micro_topics(item, target_entries)
        decisions: list[MicroTopicDecision] = []
        for match in matches:
            contract_data = match.get("decision_contract")
            if contract_data:
                decisions.append(MicroTopicDecision.from_mapping(contract_data))
            else:
                decisions.append(
                    MicroTopicDecision(
                        micro_topic_id=str(match.get("micro_topic_id", match.get("micro_topic", ""))),
                        domain_id=str(match.get("domain", "")),
                        topic_id=str(match.get("topic_id", match.get("topic_key", ""))),
                        confidence=float(match.get("confidence", 0)),
                        classification_score=float(match.get("classification_score", 0)),
                        classification_status=str(match.get("decision", "PRIMARY")),
                        threshold=float(match.get("threshold", 0.5)),
                        margin=float(match.get("margin", 0)),
                        matched_signals=tuple(match.get("signals", [])),
                    )
                )
        return decisions
