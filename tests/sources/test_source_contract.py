"""Tests for SourceContract, SourceRole, SourceLifecycleState, FreshnessPolicy, CollectionBudget."""
from __future__ import annotations

import pytest

from intelligence.sources import (
    CollectionBudget,
    FreshnessPolicy,
    SourceAcceptanceStatus,
    SourceContract,
    SourceLifecycleState,
    SourceRole,
)


# ---------------------------------------------------------------------------
# SourceRole
# ---------------------------------------------------------------------------

class TestSourceRole:
    def test_all_required_roles_present(self):
        required = {"NEWS", "VIDEO", "RESEARCH", "OFFICIAL", "GOVERNMENT", "COMPANY", "GITHUB", "MARKET", "SPECIALIST"}
        assert required <= {r.value for r in SourceRole}

    def test_role_string_values(self):
        assert SourceRole.NEWS == "NEWS"
        assert SourceRole.VIDEO == "VIDEO"


# ---------------------------------------------------------------------------
# SourceLifecycleState
# ---------------------------------------------------------------------------

class TestSourceLifecycleState:
    def test_all_16_states_present(self):
        expected = {
            "REGISTERED", "CONFIGURED", "AUTHENTICATION_REQUIRED", "AUTHENTICATED",
            "REACHABILITY_FAILED", "COLLECTION_FAILED", "INVALID_RESPONSE", "STALE",
            "SCHEMA_INVALID", "CONTENT_UNAVAILABLE", "ROLE_INVALID", "MAPPING_INVALID",
            "EVIDENCE_INSUFFICIENT", "QUARANTINED", "DISABLED", "READY",
        }
        assert expected <= {s.value for s in SourceLifecycleState}

    def test_ready_is_terminal_success_state(self):
        assert SourceLifecycleState.READY == "READY"

    def test_quarantined_is_failure_state(self):
        assert SourceLifecycleState.QUARANTINED == "QUARANTINED"


# ---------------------------------------------------------------------------
# FreshnessPolicy
# ---------------------------------------------------------------------------

class TestFreshnessPolicy:
    def test_defaults(self):
        fp = FreshnessPolicy()
        assert fp.max_age_hours == 48
        assert fp.stale_after_hours == 72
        assert fp.schedule == "daily"

    def test_from_mapping_complete(self):
        fp = FreshnessPolicy.from_mapping({"max_age_hours": 12, "stale_after_hours": 24, "schedule": "hourly"})
        assert fp.max_age_hours == 12
        assert fp.stale_after_hours == 24
        assert fp.schedule == "hourly"

    def test_from_mapping_none_yields_defaults(self):
        assert FreshnessPolicy.from_mapping(None) == FreshnessPolicy()

    def test_to_dict_roundtrip(self):
        fp = FreshnessPolicy(max_age_hours=6, stale_after_hours=12, schedule="hourly")
        d = fp.to_dict()
        assert d["max_age_hours"] == 6
        assert d["stale_after_hours"] == 12
        assert d["schedule"] == "hourly"


# ---------------------------------------------------------------------------
# CollectionBudget
# ---------------------------------------------------------------------------

class TestCollectionBudget:
    def test_defaults(self):
        cb = CollectionBudget()
        assert cb.max_items_per_run == 25
        assert cb.max_pages == 1
        assert cb.max_bytes == 5_000_000
        assert cb.timeout_seconds == 15
        assert cb.retry_count == 2

    def test_from_mapping(self):
        cb = CollectionBudget.from_mapping({
            "max_items_per_run": 50, "max_pages": 3, "max_bytes": 1_000_000,
            "timeout_seconds": 30, "retry_count": 3,
        })
        assert cb.max_items_per_run == 50
        assert cb.max_pages == 3
        assert cb.timeout_seconds == 30

    def test_from_mapping_none_yields_defaults(self):
        assert CollectionBudget.from_mapping(None) == CollectionBudget()


# ---------------------------------------------------------------------------
# SourceContract
# ---------------------------------------------------------------------------

class TestSourceContract:
    def _minimal_mapping(self, **overrides):
        base = {
            "id": "test-source",
            "name": "Test Source",
            "type": "rss",
            "role": "NEWS",
            "trust_tier": 1,
            "region": "global",
            "country": "GLOBAL",
            "domains": ["technology"],
            "topics": ["artificial-intelligence"],
            "micro_topics": ["foundation-models"],
            "collection_method": "rss",
            "feed_url": "https://example.com/feed.rss",
            "enabled": True,
            "license_status": "PERMITTED",
            "retention_policy": "REQUIRED",
        }
        base.update(overrides)
        return base

    def test_from_mapping_minimal(self):
        contract = SourceContract.from_mapping(self._minimal_mapping())
        assert contract.id == "test-source"
        assert contract.role == SourceRole.NEWS
        assert contract.trust_tier == 1

    def test_source_id_property(self):
        contract = SourceContract.from_mapping(self._minimal_mapping())
        assert contract.source_id == contract.id

    def test_role_inference_for_youtube_type(self):
        contract = SourceContract.from_mapping(self._minimal_mapping(type="youtube", role=""))
        assert contract.role == SourceRole.VIDEO

    def test_role_inference_for_gov_source_id(self):
        contract = SourceContract.from_mapping(self._minimal_mapping(id="white-house-gov", role=""))
        assert contract.role == SourceRole.GOVERNMENT

    def test_invalid_role_falls_back_to_news(self):
        contract = SourceContract.from_mapping(self._minimal_mapping(role="COMPLETELY_INVALID"))
        assert contract.role == SourceRole.NEWS

    def test_to_dict_roundtrip(self):
        contract = SourceContract.from_mapping(self._minimal_mapping())
        d = contract.to_dict()
        assert d["id"] == "test-source"
        assert "fields" in d
        assert "fields_list" not in d  # private field must be remapped

    def test_freshness_policy_embedded(self):
        contract = SourceContract.from_mapping(
            self._minimal_mapping(freshness_policy={"max_age_hours": 12, "stale_after_hours": 24, "schedule": "hourly"})
        )
        assert contract.freshness_policy.max_age_hours == 12

    def test_domains_topics_micro_topics_are_tuples(self):
        contract = SourceContract.from_mapping(self._minimal_mapping())
        assert isinstance(contract.domains, tuple)
        assert isinstance(contract.topics, tuple)
        assert isinstance(contract.micro_topics, tuple)

    def test_contract_is_frozen(self):
        contract = SourceContract.from_mapping(self._minimal_mapping())
        with pytest.raises((AttributeError, TypeError)):
            contract.id = "other"  # type: ignore[misc]

    def test_authentication_env_var(self):
        contract = SourceContract.from_mapping(
            self._minimal_mapping(authentication_required=True, authentication_env_var="MY_API_KEY")
        )
        assert contract.authentication_required is True
        assert contract.authentication_env_var == "MY_API_KEY"

    def test_license_and_retention_defaults(self):
        contract = SourceContract.from_mapping(self._minimal_mapping())
        assert contract.license_status == "PERMITTED"
        assert contract.retention_policy == "REQUIRED"


# ---------------------------------------------------------------------------
# SourceAcceptanceStatus
# ---------------------------------------------------------------------------

class TestSourceAcceptanceStatus:
    def test_canonical_values(self):
        assert SourceAcceptanceStatus.READY == "READY"
        assert SourceAcceptanceStatus.DISABLED == "DISABLED"
        assert SourceAcceptanceStatus.QUARANTINED == "QUARANTINED"

    def test_pass_and_ready_are_equivalent_success_values(self):
        assert SourceAcceptanceStatus.PASS.value in {"PASS", "READY"}

    def test_disable_and_disabled_present(self):
        assert SourceAcceptanceStatus.DISABLE == "DISABLE"
        assert SourceAcceptanceStatus.DISABLED == "DISABLED"

    def test_quarantine_and_quarantined_present(self):
        assert SourceAcceptanceStatus.QUARANTINE == "QUARANTINE"
        assert SourceAcceptanceStatus.QUARANTINED == "QUARANTINED"
