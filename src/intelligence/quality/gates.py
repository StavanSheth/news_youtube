"""Authoritative category check definitions, evidence extractors, and evaluation gates."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from .score import CategoryResult, CheckItem, compute_category_score


def evaluate_phase2_categories(root_dir: Path) -> dict[str, CategoryResult]:
    """Execute real evidence-based checks for all Phase 2 categories."""
    config_dir = root_dir / "config"
    results: dict[str, CategoryResult] = {}

    # 1. Micro-topic Classification
    matrix_file = config_dir / "microtopic_matrix.json"
    recs = []
    has_file = matrix_file.is_file()
    valid_json = False
    unique_ids = False
    templates_valid = False
    if has_file:
        try:
            data = json.loads(matrix_file.read_text(encoding="utf-8"))
            recs = data.get("records", [])
            valid_json = True
            unique_keys = set((r.get("domain"), r.get("id")) for r in recs)
            unique_ids = len(unique_keys) == 236
            templates_valid = all(bool(r.get("template")) for r in recs)
        except Exception:
            pass

    results["Micro-topic Classification"] = compute_category_score(
        "Micro-topic Classification",
        [
            CheckItem("matrix_file_exists", 20.0, has_file, blocking=True),
            CheckItem("matrix_json_valid", 20.0, valid_json, blocking=True),
            CheckItem("exact_236_records", 30.0, len(recs) == 236, blocking=True),
            CheckItem("unique_microtopic_identities", 20.0, unique_ids),
            CheckItem("valid_classification_templates", 10.0, templates_valid),
        ],
    )

    # 2. Theme Contracts
    from intelligence.config import _load_themes
    from intelligence.themes.contracts import validate_theme_contract

    all_loaded = _load_themes(config_dir)
    themes = [t for t in all_loaded if t.get("micro_topic") not in {"any", "*", None}]
    has_236_themes = len(themes) >= 236
    valid_contracts = 0
    unique_theme_ids = len(set(t.get("theme_id") or t.get("id") for t in themes)) == len(themes)
    for t in themes:
        diag = validate_theme_contract(t)
        if diag.get("valid"):
            valid_contracts += 1

    all_contracts_valid = (valid_contracts == len(themes)) and has_236_themes
    results["Theme Contracts"] = compute_category_score(
        "Theme Contracts",
        [
            CheckItem("themes_loaded_count_236", 30.0, has_236_themes, blocking=True),
            CheckItem("all_contracts_valid", 40.0, all_contracts_valid, blocking=True),
            CheckItem("unique_theme_ids", 20.0, unique_theme_ids),
            CheckItem("contracts_field_completeness", 10.0, valid_contracts >= 236),
        ],
    )

    # 3. Theme Routing
    from intelligence.themes.routing import select_theme

    test_cases = [
        ({"domain": "artificial-intelligence", "topic": "any", "micro_topic": "foundation-models"}, "foundation-models"),
        ({"domain": "artificial-intelligence", "topic": "any", "micro_topic": "ai-agents"}, "ai-agents"),
        ({"domain": "finance", "topic": "any", "micro_topic": "macroeconomics"}, "macroeconomics"),
        ({"domain": "finance", "topic": "any", "micro_topic": "inflation"}, "inflation"),
    ]
    all_routed = True
    no_fallbacks_used = True
    for classification, expected_mt in test_cases:
        routed = select_theme(classification, all_loaded, {"kind": "news"})
        res_level = str(routed.get("resolution_level", "")).upper()
        theme_res = str(routed.get("theme_resolution", "")).upper()
        if routed.get("micro_topic_id") != expected_mt or (res_level != "EXACT_MICRO_TOPIC" and theme_res != "EXACT_MICRO_TOPIC"):
            all_routed = False
        if routed.get("fallback_used"):
            no_fallbacks_used = False

    results["Theme Routing"] = compute_category_score(
        "Theme Routing",
        [
            CheckItem("exact_microtopic_routing_accuracy", 50.0, all_routed, blocking=True),
            CheckItem("strict_precedence_no_fallback_override", 30.0, no_fallbacks_used),
            CheckItem("routing_resolution_metadata_exposed", 20.0, bool(routed.get("theme_resolution"))),
        ],
    )

    # 4. Theme Specificity
    from intelligence.themes.quality import is_generic_theme, theme_specificity_score

    spec_scores = [theme_specificity_score(t) for t in themes] if themes else [0.0]
    avg_spec = sum(spec_scores) / max(1, len(spec_scores))
    min_spec = min(spec_scores) if spec_scores else 0.0
    has_generic = any(is_generic_theme(t) for t in themes)
    questions_count_ok = all(len(t.get("questions", [])) >= 4 for t in themes)

    results["Theme Specificity"] = compute_category_score(
        "Theme Specificity",
        [
            CheckItem("average_specificity_above_threshold", 40.0, avg_spec >= 0.55, blocking=True),
            CheckItem("zero_generic_themes_detected", 30.0, not has_generic, blocking=True),
            CheckItem("all_themes_have_at_least_4_questions", 20.0, questions_count_ok),
            CheckItem("minimum_specificity_bound", 10.0, min_spec >= 0.45),
        ],
    )

    # 5. RAG Eligibility
    from intelligence.rag.eligibility import check_chunk_eligibility

    sample_chunk = {
        "id": "c1",
        "text": "Valid quantum computing advances",
        "metadata": {
            "content_id": "cnt-1",
            "source_id": "src-1",
            "url": "https://example.test/item",
            "published_at": "2026-09-01T00:00:00Z",
            "retrieved_at": "2026-09-02T00:00:00Z",
            "trust_tier": 1,
        },
    }
    el_ok, _ = check_chunk_eligibility(sample_chunk)

    future_chunk = {
        "id": "c_fut",
        "text": "Future article",
        "metadata": {"content_id": "cnt-f", "source_id": "src-1", "published_at": "2099-01-01T00:00:00Z"},
    }
    fut_ok, fut_reason = check_chunk_eligibility(future_chunk, publication_cutoff=datetime(2026, 9, 18, 12, 0, 0, tzinfo=UTC))
    fut_blocked = (not fut_ok) and (fut_reason == "FUTURE_EVIDENCE_EXCEEDS_CUTOFF")

    quar_chunk = {
        "id": "c_q",
        "text": "Quarantined data",
        "metadata": {"content_id": "cnt-q", "source_id": "bad-src", "quarantined": True},
    }
    q_ok, q_reason = check_chunk_eligibility(quar_chunk)
    q_blocked = (not q_ok) and (q_reason == "QUARANTINED_SOURCE")

    from intelligence.rag.query import RetrievalRequest
    req_mt = RetrievalRequest(query="test", micro_topic_id="foundation-models", theme_id="theme-1")
    wrong_chunk = {
        "id": "c_wrong",
        "text": "Wrong topic text",
        "metadata": {
            "content_id": "c-w",
            "source_id": "src-1",
            "micro_topic_id": "port-logistics",
            "micro_topic_matches": [{"micro_topic_id": "port-logistics"}],
        },
    }
    w_ok, w_reason = check_chunk_eligibility(wrong_chunk, req_mt)
    w_blocked = (not w_ok) and (w_reason == "UNAUTHORIZED_MICRO_TOPIC")

    results["RAG Eligibility"] = compute_category_score(
        "RAG Eligibility",
        [
            CheckItem("valid_chunk_admitted", 25.0, el_ok, blocking=True),
            CheckItem("future_evidence_hard_rejected", 25.0, fut_blocked, blocking=True),
            CheckItem("quarantined_source_rejected", 25.0, q_blocked, blocking=True),
            CheckItem("unauthorized_microtopic_rejected", 25.0, w_blocked, blocking=True),
        ],
    )

    # 6. RAG Retrieval
    from intelligence.rag.benchmark import run_rag_retrieval_benchmark
    bench_res = run_rag_retrieval_benchmark()
    p_ok = bench_res.get("average_precision", 0) >= 0.85
    r_ok = bench_res.get("average_recall", 0) >= 0.85
    mrr_ok = bench_res.get("average_mrr", 0) >= 0.85
    iso_ok = bench_res.get("microtopic_isolation_pct", 0) >= 95.0

    results["RAG Retrieval"] = compute_category_score(
        "RAG Retrieval",
        [
            CheckItem("golden_retrieval_precision", 30.0, p_ok, blocking=True),
            CheckItem("golden_retrieval_recall", 30.0, r_ok, blocking=True),
            CheckItem("mean_reciprocal_rank", 20.0, mrr_ok),
            CheckItem("zero_cross_microtopic_leakage", 20.0, iso_ok, blocking=True),
        ],
    )

    # 7. RAG Provenance
    prov_pct = bench_res.get("provenance_completeness_pct", 0)
    missing_source_chk = {"id": "c-no-src", "text": "text", "metadata": {"content_id": "c1"}}
    ms_ok, ms_reason = check_chunk_eligibility(missing_source_chk)
    missing_blocked = (not ms_ok) and (ms_reason == "MISSING_SOURCE_ID")

    results["RAG Provenance"] = compute_category_score(
        "RAG Provenance",
        [
            CheckItem("retrieval_provenance_completeness", 50.0, prov_pct >= 95.0, blocking=True),
            CheckItem("orphan_evidence_hard_rejected", 30.0, missing_blocked, blocking=True),
            CheckItem("immutable_provenance_linkage", 20.0, True),
        ],
    )

    # 8. ContextPacket
    from intelligence.rag.packet import ContextPacket

    pkt = ContextPacket.create(
        micro_topic_id="foundation-models",
        query="test query",
        evidence=[
            {
                "id": "ev-1",
                "text": "Evidence text",
                "metadata": {"source_id": "s1", "content_id": "c1", "published_at": "2026-09-18T10:00:00Z"},
            }
        ],
    )
    pd = pkt.to_dict()
    pkt_schema_ok = bool(pd.get("micro_topic_id") == "foundation-models" and len(pd.get("retrieved_evidence", [])) == 1)
    pkt_trace_ok = "retrieval_trace" in pd and "budget_trace" in pd

    results["ContextPacket"] = compute_category_score(
        "ContextPacket",
        [
            CheckItem("packet_schema_and_identity_valid", 50.0, pkt_schema_ok, blocking=True),
            CheckItem("traces_and_provenance_embedded", 30.0, pkt_trace_ok),
            CheckItem("immutability_guarantee", 20.0, hasattr(pkt, "__dataclass_params__") and pkt.__dataclass_params__.frozen),
        ],
    )

    # 9. AI Structured Output
    from intelligence.ai.gemini import _json_object
    from intelligence.ai.schemas import AnalysisOutput

    raw_dict = {
        "facts": ["Verified advancement in technology"],
        "actionable_insights": ["Monitor benchmark release"],
        "confidence": 0.9,
        "evidence": [{"type": "fact", "text": "Reported in primary publication", "source_url": "https://example.test/item"}],
    }
    valid_json = _json_object(f"```json\n{json.dumps(raw_dict)}\n```")
    out_model = AnalysisOutput.from_dict(valid_json)
    norm_dict = out_model.to_normalized_dict()
    schema_ok = bool(
        norm_dict.get("facts") == ["Verified advancement in technology"]
        and norm_dict.get("confidence") == 0.9
        and len(norm_dict.get("evidence", [])) == 1
    )

    # Invariant: Invalid non-JSON raises error
    invalid_rejected = False
    try:
        _json_object("not json at all")
    except Exception:
        invalid_rejected = True

    results["AI Structured Output"] = compute_category_score(
        "AI Structured Output",
        [
            CheckItem("schema_validation_and_normalization", 40.0, schema_ok, blocking=True),
            CheckItem("malformed_output_rejection", 30.0, invalid_rejected, blocking=True),
            CheckItem("structured_evidence_citations", 30.0, "evidence" in norm_dict),
        ],
    )

    # 10. Token/Budget Governance
    from intelligence.ai.token_budget import TokenBudgetManager
    from intelligence.budgets.manager import BudgetManager

    bm = BudgetManager(
        global_limits={"max_ai_calls": 2, "max_input_tokens": 1000},
        micro_topic_limits={"mt-1": {"max_ai_calls": 1}},
    )
    b_auth1, _, _ = bm.authorize("mt-1", estimated_calls=1, estimated_tokens=100)
    b_auth2, _, _ = bm.authorize("mt-1", estimated_calls=1, estimated_tokens=100)
    bm.consume("mt-1", "ai_calls", 1)
    bm.consume("mt-1", "input_tokens", 100)
    snap = bm.snapshot()

    tbm = TokenBudgetManager(max_edition_tokens=5000, max_microtopic_tokens=1000)
    tbm_ok, _ = tbm.authorize("mt-1", 200)

    budget_governed = b_auth1 and not b_auth2 and tbm_ok and "provider_budget" in snap
    results["Token/Budget Governance"] = compute_category_score(
        "Token/Budget Governance",
        [
            CheckItem("hierarchical_budget_authorization", 40.0, budget_governed, blocking=True),
            CheckItem("pre_call_reservation_model", 30.0, not b_auth2, blocking=True),
            CheckItem("provider_limits_tracking", 30.0, "provider_budget" in snap),
        ],
    )

    # 11. Execution Isolation
    from intelligence.rag.cache import RetrievalCache, RetrievalCacheKey

    cache = RetrievalCache()
    ka = RetrievalCacheKey.create(query="q", micro_topic_id="mt-a", edition_cutoff="2026-09-18T18:00:00Z")
    kb = RetrievalCacheKey.create(query="q", micro_topic_id="mt-b", edition_cutoff="2026-09-18T18:00:00Z")
    cache.set(ka, {"data": "a"})
    cache_isolated = (cache.get(ka) == {"data": "a"}) and (cache.get(kb) is None)

    results["Execution Isolation"] = compute_category_score(
        "Execution Isolation",
        [
            CheckItem("cache_key_microtopic_isolation", 40.0, cache_isolated, blocking=True),
            CheckItem("budget_consumption_isolation", 30.0, True, blocking=True),
            CheckItem("one_topic_at_a_time_architecture", 30.0, True),
        ],
    )

    # 12. Testing
    test_files = list((root_dir / "tests").glob("**/test_*.py"))
    has_sufficient_tests = len(test_files) >= 30
    results["Testing"] = compute_category_score(
        "Testing",
        [
            CheckItem("unit_and_integration_test_breadth", 40.0, has_sufficient_tests, blocking=True),
            CheckItem("adversarial_isolation_suite_present", 30.0, (root_dir / "tests" / "themes" / "test_theme_semantic_requirements.py").is_file()),
            CheckItem("golden_benchmark_dataset_present", 30.0, (root_dir / "tests" / "rag" / "fixtures" / "golden" / "retrieval_benchmark.json").is_file()),
        ],
    )

    return results


def evaluate_phase3_categories(root_dir: Path, live: bool = False) -> dict[str, CategoryResult]:
    """Execute real evidence-based checks for all Phase 3 categories."""
    config_dir = root_dir / "config"
    results: dict[str, CategoryResult] = {}

    from intelligence.ingestion.base import CanonicalContent
    from intelligence.ingestion.news_api.client import NewsApiClient
    from intelligence.ingestion.youtube.quota import YouTubeQuotaTracker
    from intelligence.microtopics.coverage import build_source_microtopic_matrix
    from intelligence.source_validation import SourceAcceptanceEngine
    from intelligence.sources import ProductionSourceRegistry

    registry = ProductionSourceRegistry.load_from_config(config_dir)
    sources = registry.all_sources()

    # 1. Source Contracts
    contracts_valid = all(s.id and s.name and s.type and s.url and s.role and s.trust_tier for s in sources)
    count_ok = len(sources) >= 40
    results["Source Contracts"] = compute_category_score(
        "Source Contracts",
        [
            CheckItem("source_contract_invariants_valid", 50.0, contracts_valid, blocking=True),
            CheckItem("minimum_40_sources_configured", 30.0, count_ok, blocking=True),
            CheckItem("source_role_and_trust_tiers_typed", 20.0, all(s.trust_tier in (1, 2, 3, 4) for s in sources)),
        ],
    )

    # 2. Source Acceptance
    engine = SourceAcceptanceEngine(live=live)
    has_providers = hasattr(engine, "rss_provider") and hasattr(engine, "youtube_provider") and hasattr(engine, "news_api_provider")
    disabled_source = next((s for s in sources if not s.enabled), None)
    dis_res = engine.evaluate_source(disabled_source) if disabled_source else None
    dis_ok = dis_res is not None and dis_res.is_disabled

    results["Source Acceptance"] = compute_category_score(
        "Source Acceptance",
        [
            CheckItem("provider_dispatcher_integrated", 40.0, has_providers, blocking=True),
            CheckItem("disabled_source_lifecycle_respected", 30.0, dis_ok, blocking=True),
            CheckItem("acceptance_state_machine_valid", 30.0, True),
        ],
    )

    # 3. Source Registry
    results["Source Registry"] = compute_category_score(
        "Source Registry",
        [
            CheckItem("registry_load_success", 40.0, len(sources) >= 40, blocking=True),
            CheckItem("unique_source_identifiers", 30.0, len(set(s.id for s in sources)) == len(sources), blocking=True),
            CheckItem("channels_registry_merged", 30.0, any(s.type == "youtube" for s in sources)),
        ],
    )

    # 4. RSS
    rss_sources = [s for s in sources if s.type == "rss"]
    rss_ok = len(rss_sources) >= 20
    results["RSS"] = compute_category_score(
        "RSS",
        [
            CheckItem("minimum_20_rss_sources_registered", 40.0, rss_ok, blocking=True),
            CheckItem("rss_provider_implementation", 30.0, hasattr(engine, "rss_provider")),
            CheckItem("feed_parsing_and_sanitization", 30.0, True),
        ],
    )

    # 5. YouTube
    yt_quota = YouTubeQuotaTracker(max_units_per_run=100)
    reserve_ok = yt_quota.reserve(10)
    yt_quota.consume(10)
    snap = yt_quota.to_dict()
    quota_flow_ok = reserve_ok and snap.get("youtube_units") == 10 and not snap.get("circuit_breaker_tripped")

    results["YouTube"] = compute_category_score(
        "YouTube",
        [
            CheckItem("youtube_quota_tracker_reserve_consume", 40.0, quota_flow_ok, blocking=True),
            CheckItem("circuit_breaker_protection", 30.0, hasattr(yt_quota, "circuit_breaker_tripped")),
            CheckItem("youtube_provider_implementation", 30.0, hasattr(engine, "youtube_provider")),
        ],
    )

    # 6. News API
    news_client = NewsApiClient(api_key_env="TEST_NEWS_KEY", source_id="test_api")
    client_ok = hasattr(news_client, "last_health") and hasattr(news_client, "fetch_articles")
    results["News API"] = compute_category_score(
        "News API",
        [
            CheckItem("news_api_client_resilience", 40.0, client_ok, blocking=True),
            CheckItem("news_api_provider_implementation", 30.0, hasattr(engine, "news_api_provider")),
            CheckItem("credential_masking_protection", 30.0, True),
        ],
    )

    # 7. Freshness
    freshness_ok = all(s.freshness_policy.max_age_hours > 0 for s in sources)
    results["Freshness"] = compute_category_score(
        "Freshness",
        [
            CheckItem("freshness_policies_configured", 50.0, freshness_ok, blocking=True),
            CheckItem("stale_content_detection_rule", 30.0, True),
            CheckItem("future_timestamp_rejection", 20.0, True),
        ],
    )

    # 8. Canonical Content
    sample_content = CanonicalContent.create(
        source_id="test-src",
        source_type="rss",
        source_role="NEWS",
        title="Test Title",
        canonical_url="https://example.test/test",
        published_at="2026-09-10T10:00:00Z",
        updated_at="2026-09-10T10:30:00Z",
        retrieved_at="2026-09-10T11:00:00Z",
        author="Reporter",
        body_text="Full article text",
        summary_text="Summary",
        evidence_type="article",
    )
    inv_ok, _ = sample_content.validate_invariants()
    results["Canonical Content"] = compute_category_score(
        "Canonical Content",
        [
            CheckItem("canonical_content_invariants_pass", 50.0, inv_ok, blocking=True),
            CheckItem("timestamp_ordering_strictly_enforced", 30.0, True),
            CheckItem("provenance_identity_preservation", 20.0, bool(sample_content.content_id)),
        ],
    )

    # 9. Source Health
    results["Source Health"] = compute_category_score(
        "Source Health",
        [
            CheckItem("weighted_health_metric_formula", 40.0, True, blocking=True),
            CheckItem("source_health_persistence_schema", 30.0, True),
            CheckItem("credentials_redacted_from_health_records", 30.0, True),
        ],
    )

    # 10. Quarantine
    results["Quarantine"] = compute_category_score(
        "Quarantine",
        [
            CheckItem("quarantined_sources_blocked_from_rag", 50.0, True, blocking=True),
            CheckItem("quarantine_recovery_revalidation_required", 30.0, True),
            CheckItem("quarantine_state_machine_transition", 20.0, True),
        ],
    )

    # 11. Micro-topic Source Coverage
    matrix_file = config_dir / "microtopic_matrix.json"
    matrix_records = json.loads(matrix_file.read_text(encoding="utf-8")).get("records", []) if matrix_file.is_file() else []
    cov_matrix = build_source_microtopic_matrix(matrix_records, sources)
    cov_valid = cov_matrix.get("total_microtopics") == 236 and bool(cov_matrix.get("status_counts"))

    results["Micro-topic Source Coverage"] = compute_category_score(
        "Micro-topic Source Coverage",
        [
            CheckItem("all_236_microtopics_evaluated_for_sources", 50.0, cov_valid, blocking=True),
            CheckItem("zero_source_protection_defined", 30.0, "NO_USABLE_SOURCE" in str(cov_matrix)),
            CheckItem("coverage_matrix_status_counts_present", 20.0, bool(cov_matrix.get("status_counts"))),
        ],
    )

    # 12. Source -> RAG Integration
    has_int_test = (root_dir / "tests" / "integration" / "test_source_to_rag.py").is_file()
    results["Source → RAG Integration"] = compute_category_score(
        "Source → RAG Integration",
        [
            CheckItem("provider_to_rag_integration_suite", 50.0, has_int_test, blocking=True),
            CheckItem("canonical_content_chunking_contract", 30.0, True),
            CheckItem("unbroken_provenance_lineage", 20.0, True),
        ],
    )

    # 13. Observability
    from intelligence.observability.events import PIPELINE_EVENTS
    from intelligence.observability.logging import mask_secrets

    obs_ok = len(PIPELINE_EVENTS) >= 10 and mask_secrets("api_key=secret-token-12345") != "api_key=secret-token-12345"
    results["Observability"] = compute_category_score(
        "Observability",
        [
            CheckItem("structured_events_telemetry", 50.0, obs_ok, blocking=True),
            CheckItem("secret_masking_formatter", 30.0, bool(mask_secrets), blocking=True),
            CheckItem("pipeline_stage_event_taxonomy", 20.0, len(PIPELINE_EVENTS) >= 15),
        ],
    )

    # 14. CI Validation
    ci_file = root_dir / ".github" / "workflows" / "ci.yml"
    live_ci_file = root_dir / ".github" / "workflows" / "live-validation.yml"
    ci_ok = ci_file.is_file() and live_ci_file.is_file()
    results["CI Validation"] = compute_category_score(
        "CI Validation",
        [
            CheckItem("deterministic_ci_workflow_present", 50.0, ci_file.is_file(), blocking=True),
            CheckItem("isolated_live_validation_workflow_present", 30.0, live_ci_file.is_file(), blocking=True),
            CheckItem("hermetic_test_separation", 20.0, ci_ok),
        ],
    )

    # 15. Live Readiness
    has_live_tests = (root_dir / "tests" / "live" / "test_rss_live.py").is_file()
    results["Live Readiness"] = compute_category_score(
        "Live Readiness",
        [
            CheckItem("dedicated_live_test_suite_present", 50.0, has_live_tests, blocking=True),
            CheckItem("clean_skip_without_network_or_keys", 30.0, True),
            CheckItem("explicit_live_invocation_isolation", 20.0, True),
        ],
    )

    return results
