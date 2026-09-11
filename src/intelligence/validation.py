from __future__ import annotations

from typing import Any

from .themes import theme_fingerprint


def validate_microtopic_matrix(matrix: dict[str, Any]) -> None:
    records = matrix.get("records", [])
    if not isinstance(records, list) or len(records) != 236:
        raise ValueError("Micro-topic matrix must contain exactly 236 records")
    keys = [(record.get("domain"), record.get("id")) for record in records]
    if any(not domain or not micro_topic for domain, micro_topic in keys) or len(keys) != len(set(keys)):
        raise ValueError("Micro-topic matrix records require unique domain/id pairs")
    required = {"name", "evaluation", "required_evidence", "resources", "important_output"}
    for record in records:
        if required - record.keys() or any(not str(record[field]).strip() for field in required):
            raise ValueError(f"Incomplete matrix record: {record.get('domain')}/{record.get('id')}")


def validate_normalization_registry(registry: dict[str, Any], matrix: dict[str, Any]) -> None:
    records = registry.get("records", [])
    if len(records) != len(matrix.get("records", [])):
        raise ValueError("Normalization registry must preserve every matrix row")
    ids = [record.get("original_id") for record in records]
    if ids != list(range(1, len(records) + 1)):
        raise ValueError("Normalization registry original IDs must be contiguous 1..N")
    allowed_statuses = {"KEEP", "MERGE", "HIERARCHY", "EVENT", "ENTITY", "CONTENT", "ATTRIBUTE", "OPPORTUNITY", "CATEGORY", "DEPRECATE", "SPLIT"}
    allowed_types = {"MICRO_TOPIC", "CATEGORY", "EVENT_TYPE", "ENTITY_TYPE", "CONTENT_TYPE", "ATTRIBUTE", "OPPORTUNITY_TYPE"}
    for record in records:
        if record.get("status") not in allowed_statuses or record.get("record_type") not in allowed_types or not record.get("canonical_id"):
            raise ValueError(f"Invalid normalization record: {record.get('original_id')}")


def validate_dimensions(dimensions: dict[str, Any]) -> None:
    for key in ("event_types", "entity_types", "content_types", "attributes"):
        values = dimensions.get(key)
        if not isinstance(values, list) or not values or len(values) != len(set(values)):
            raise ValueError(f"Dimensions field {key!r} must be a unique non-empty list")
    geography = dimensions.get("geography", {})
    if not geography.get("regions") or not geography.get("countries"):
        raise ValueError("Dimensions geography requires regions and countries")


def validate_profile_templates(matrix: dict[str, Any], templates: dict[str, Any]) -> None:
    available = templates.get("templates", templates)
    unknown = sorted({record.get("template") for record in matrix.get("records", []) if record.get("template") not in available})
    if unknown:
        raise ValueError(f"Unknown profile templates: {unknown}")


def validate_microtopic_profiles(config: dict[str, Any], taxonomy: dict[str, Any], matrix: dict[str, Any], themes: list[dict[str, Any]], templates: dict[str, Any]) -> None:
    """Validate the executable registry without treating analysis prose as signals."""
    matrix_keys = {(row.get("domain"), row.get("id")) for row in matrix.get("records", [])}
    matrix_domains = {domain for domain, _ in matrix_keys}
    taxonomy_domains = set(taxonomy.get("domains", {}))
    if not matrix_domains <= taxonomy_domains:
        raise ValueError(f"Taxonomy and micro-topic matrix disagree; unknown matrix domains={sorted(matrix_domains - taxonomy_domains)}")
    theme_keys = {(theme.get("domain"), theme.get("micro_topic")) for theme in themes if theme.get("micro_topic") not in {None, "any", "*"}}
    available = templates.get("templates", templates)
    for row in matrix.get("records", []):
        domain, micro_topic = row["domain"], row["id"]
        explicit = config.get("domains", {}).get(domain, {}).get("overrides", {}).get(micro_topic, {})
        template_id = row.get("template")
        if template_id not in available:
            raise ValueError(f"Invalid template for {domain}/{micro_topic}: {template_id}")
        signals = list(explicit.get("positive_signals", []))
        if not signals:
            signals = [f"{row.get('name', micro_topic)} release", f"{row.get('name', micro_topic)} announcement"]
        if not any(len(str(value.get("phrase", "") if isinstance(value, dict) else value).split()) >= 2 for value in signals):
            raise ValueError(f"Micro-topic has no specific positive signal: {domain}/{micro_topic}")
        threshold = explicit.get("primary_threshold", explicit.get("classification_threshold", 0.5))
        if not 0 <= float(threshold) <= 1:
            raise ValueError(f"Invalid profile threshold: {domain}/{micro_topic}")
        contract = explicit.get("analysis_contract", config.get("defaults", {}).get("analysis_contract", {}))
        if not contract:
            raise ValueError(f"Missing analysis contract: {domain}/{micro_topic}")
        if (domain, micro_topic) not in theme_keys:
            raise ValueError(f"Missing exact theme: {domain}/{micro_topic}")


def validate_theme_specificity(themes: list[dict[str, Any]]) -> dict[str, Any]:
    fingerprints: dict[str, list[str]] = {}
    for theme in themes:
        if theme.get("id") == "domain-fallback":
            continue
        fingerprints.setdefault(theme_fingerprint(theme), []).append(str(theme.get("id")))
    duplicates = [ids for ids in fingerprints.values() if len(ids) > 1]
    if duplicates:
        raise ValueError(f"Duplicate meaningful theme fingerprints: {duplicates[:3]}")
    generic = [theme.get("id") for theme in themes if theme.get("id") != "domain-fallback" and len(theme_fingerprint(theme)) < 80]
    return {"total": len(themes), "unique_fingerprints": len(fingerprints), "duplicate_fingerprints": duplicates, "generic": generic}


def validate_taxonomy(taxonomy: dict[str, Any]) -> None:
    required = {"domains", "priorities", "event_types", "report_types"}
    missing = required - taxonomy.keys()
    if missing:
        raise ValueError(f"Taxonomy missing required fields: {sorted(missing)}")
    for field in ("priorities", "event_types", "entity_types", "report_types", "regions", "countries"):
        values = taxonomy.get(field, [])
        if not isinstance(values, list) or not values or not all(isinstance(value, str) and value for value in values):
            raise ValueError(f"Taxonomy field {field!r} must be a non-empty list of strings")
        if len(values) != len(set(values)):
            raise ValueError(f"Taxonomy field {field!r} contains duplicates")
    domains = taxonomy["domains"]
    if not isinstance(domains, dict) or not domains:
        raise ValueError("Taxonomy domains must be a non-empty mapping")
    for domain, definition in domains.items():
        if not isinstance(definition, dict) or not definition.get("topics"):
            raise ValueError(f"Domain {domain!r} must define topics")
        topics = definition["topics"]
        if len(topics) != len(set(topics)):
            raise ValueError(f"Domain {domain!r} contains duplicate topics")


def validate_topics(topics: list[dict[str, Any]], taxonomy: dict[str, Any]) -> None:
    keys = [topic.get("key", topic.get("id")) for topic in topics]
    if any(not key for key in keys) or len(keys) != len(set(keys)):
        raise ValueError("Topics must have unique non-empty keys")
    for topic in topics:
        threshold = float(topic.get("classification_threshold", 0.25))
        if not 0 <= threshold <= 1:
            raise ValueError(f"Invalid classification threshold for {topic.get('name')}")
        report_type = topic.get("report_type")
        if report_type and report_type not in taxonomy["report_types"]:
            raise ValueError(f"Invalid report type: {report_type}")


def validate_microtopics(config: dict[str, Any], taxonomy: dict[str, Any]) -> None:
    """Validate the profile overlay used for every taxonomy micro-topic."""
    defaults = config.get("defaults")
    if not isinstance(defaults, dict):
        raise ValueError("Micro-topic configuration requires defaults")
    required = {"classification_threshold", "analysis_contract", "no_update_policy"}
    if required - defaults.keys():
        raise ValueError(f"Micro-topic defaults missing: {sorted(required - defaults.keys())}")
    report_types = set(taxonomy["report_types"])
    for domain, definition in config.get("domains", {}).items():
        if domain not in taxonomy["domains"]:
            raise ValueError(f"Invalid micro-topic profile domain: {domain}")
        for micro_topic, profile in definition.get("overrides", {}).items():
            if micro_topic not in taxonomy["domains"][domain].get("topics", []):
                raise ValueError(f"Invalid micro-topic override: {domain}/{micro_topic}")
            threshold = float(profile.get("classification_threshold", defaults["classification_threshold"]))
            if not 0 <= threshold <= 1:
                raise ValueError(f"Invalid micro-topic threshold: {domain}/{micro_topic}")
            configured_reports = profile.get("report_types", defaults.get("report_types", []))
            if not configured_reports or not set(configured_reports) <= report_types:
                raise ValueError(f"Invalid micro-topic report types: {domain}/{micro_topic}")
            if len(profile.get("aliases", [])) != len(set(profile.get("aliases", []))):
                raise ValueError(f"Duplicate micro-topic aliases: {domain}/{micro_topic}")


def validate_themes(themes: list[dict[str, Any]], taxonomy: dict[str, Any], matrix: dict[str, Any] | None = None) -> None:
    ids = [theme.get("id") for theme in themes]
    if any(not theme_id for theme_id in ids) or len(ids) != len(set(ids)):
        raise ValueError("Themes must have unique non-empty ids")
    valid_domains = set(taxonomy["domains"]) | {"all"}
    valid_reports = set(taxonomy["report_types"])
    valid_micro_topics = {
        micro_topic
        for definition in taxonomy["domains"].values()
        for micro_topic in definition.get("topics", [])
    }
    valid_micro_topics.update(record.get("id") for record in (matrix or {}).get("records", []))
    route_keys: set[tuple[Any, ...]] = set()
    for theme in themes:
        if theme.get("domain", "all") not in valid_domains:
            raise ValueError(f"Invalid theme domain: {theme.get('domain')}")
        report_type = theme.get("output", {}).get("report_type")
        if report_type and report_type not in valid_reports:
            raise ValueError(f"Invalid theme report type: {report_type}")
        micro_topic = theme.get("micro_topic", "any")
        if micro_topic not in {"any", "*"} and micro_topic not in valid_micro_topics:
            raise ValueError(f"Invalid theme micro-topic: {micro_topic}")
        if theme.get("id") == "domain-fallback" and theme.get("micro_topic", "any") not in {"any", "*"}:
            raise ValueError("domain-fallback must be global")
        if theme.get("id") != "domain-fallback" and not theme.get("questions"):
            raise ValueError(f"Theme {theme.get('id')} requires analysis questions")
        route_key = (theme.get("domain", "all"), theme.get("topic", "any"), micro_topic, tuple(theme.get("content_stream", ["all"]) if isinstance(theme.get("content_stream", ["all"]), list) else [theme.get("content_stream")]))
        if route_key in route_keys:
            raise ValueError(f"Ambiguous theme routing: {route_key}")
        route_keys.add(route_key)


def validate_sources(sources: list[dict[str, Any]]) -> None:
    required = {"id", "name", "type", "region", "country", "domains", "topics", "micro_topics", "trust_tier", "enabled", "collection_method", "fields", "refresh"}
    ids = []
    for source in sources:
        missing = required - source.keys()
        if missing:
            raise ValueError(f"Source {source.get('name', '<unknown>')} missing: {sorted(missing)}")
        ids.append(source["id"])
        if source["type"] == "rss" and not (source.get("url") or source.get("feed_url")):
            raise ValueError(f"RSS source {source['id']} needs url or feed_url")
        if not 1 <= int(source["trust_tier"]) <= 4:
            raise ValueError(f"Invalid trust tier for source {source['id']}")
    if len(ids) != len(set(ids)):
        raise ValueError("Source ids must be unique")
