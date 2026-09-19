"""Tests for micro-topic coverage across the production source registry and 236-node microtopic matrix."""
from __future__ import annotations

import json
from pathlib import Path
import pytest
import yaml

from intelligence.sources import ProductionSourceRegistry

ROOT = Path(__file__).parents[2]


class TestMicrotopicCoverage:
    @pytest.fixture()
    def microtopic_matrix(self) -> dict:
        matrix_path = ROOT / "config" / "microtopic_matrix.json"
        assert matrix_path.exists(), "microtopic_matrix.json must exist"
        with open(matrix_path, "r", encoding="utf-8") as f:
            return json.load(f)

    @pytest.fixture()
    def taxonomy(self) -> dict:
        tax_path = ROOT / "config" / "taxonomy.yaml"
        assert tax_path.exists(), "taxonomy.yaml must exist"
        with open(tax_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    @pytest.fixture()
    def source_registry(self) -> ProductionSourceRegistry:
        return ProductionSourceRegistry.load_from_config(ROOT / "config")

    def test_canonical_matrix_has_236_records(self, microtopic_matrix):
        records = microtopic_matrix.get("records", [])
        assert len(records) == 236
        for record in records:
            assert "domain" in record
            assert "id" in record
            assert "name" in record
            assert "evaluation" in record

    def test_source_registry_loaded_sources_count(self, source_registry):
        sources = source_registry.sources
        assert len(sources) >= 40, f"Expected at least 40 sources, found {len(sources)}"

    def test_sources_cover_major_domains(self, source_registry):
        domains = set()
        for source in source_registry.sources:
            domains.update(source.domains)
        expected_domains = {"geopolitics", "finance", "artificial-intelligence"}
        assert expected_domains.issubset(domains)

    def test_matrix_records_have_valid_domain(self, microtopic_matrix, taxonomy):
        valid_domains = set(taxonomy.get("domains", {}).keys())
        for record in microtopic_matrix["records"]:
            domain = record["domain"].strip()
            assert domain in valid_domains, f"Matrix domain '{domain}' not in taxonomy"

    def test_source_registry_domains_and_topics_valid(self, taxonomy, source_registry):
        valid_domains = set(taxonomy.get("domains", {}).keys())
        valid_topics = {t for d in taxonomy.get("domains", {}).values() for t in d.get("topics", [])}

        for source in source_registry.sources:
            for domain in source.domains:
                assert domain in valid_domains, f"Source {source.id} has unknown domain {domain}"
            for topic in source.topics:
                assert topic in valid_topics, f"Source {source.id} has unknown topic {topic}"

    def test_coverage_summary_computation(self, microtopic_matrix, source_registry):
        matrix_records = microtopic_matrix["records"]
        total_matrix_microtopics = len(matrix_records)

        covered_domains = set()
        covered_topics = set()
        covered_microtopics = set()

        for source in source_registry.sources:
            covered_domains.update(source.domains)
            covered_topics.update(source.topics)
            covered_microtopics.update(source.micro_topics)

        assert len(covered_domains) > 0
        assert len(covered_topics) > 0
        assert total_matrix_microtopics == 236
