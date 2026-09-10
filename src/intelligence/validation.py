from __future__ import annotations

from typing import Any


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


def validate_themes(themes: list[dict[str, Any]], taxonomy: dict[str, Any]) -> None:
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
