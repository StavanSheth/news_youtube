"""Comprehensive test validating every single one of the 236 bespoke micro-topic themes."""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from intelligence.config import load_config
from intelligence.themes import (
    ThemeContract,
    is_generic_theme,
    theme_specificity_score,
    validate_theme_completeness,
)

ROOT = Path(__file__).resolve().parent.parent.parent

with (ROOT / "config" / "microtopic_matrix.json").open(encoding="utf-8-sig") as f:
    _records = json.load(f)["records"]

_config = load_config(ROOT)
_theme_by_domain_mt = {
    (t.get("domain"), t.get("micro_topic_id") or t.get("micro_topic")): t
    for t in _config.themes
    if t.get("micro_topic_id") or (t.get("micro_topic") not in {"any", "*", None})
}


@pytest.mark.parametrize("record", _records, ids=[f"{r['domain']}::{r['id']}" for r in _records])
def test_each_microtopic_has_complete_bespoke_theme(record: dict):
    mt_id = record["id"]
    domain = record["domain"]
    theme = _theme_by_domain_mt.get((domain, mt_id))
    assert theme is not None, f"Missing bespoke theme for micro-topic: {domain}/{mt_id}"

    # 1. Machine-checkable completeness per Set E Section 5
    ok, errors, warnings = validate_theme_completeness(theme)
    assert ok, f"Theme for {mt_id} failed completeness: {errors}"

    # 2. Specificity score
    spec = theme_specificity_score(theme)
    assert spec >= 0.55, f"Theme for {mt_id} has low specificity: {spec:.3f}"

    # 3. Not generic
    assert not is_generic_theme(theme), f"Theme for {mt_id} flagged as generic"

    # 4. Questions count and relevance
    questions = theme.get("questions", [])
    assert len(questions) >= 4, f"Theme for {mt_id} has fewer than 4 questions"

    # 5. Contract model conversion and Set-E validation
    contract = ThemeContract.from_dict(theme)
    assert contract.theme_id != ""
    assert contract.micro_topic_id == mt_id
    assert contract.domain_id == record["domain"]
    contract_ok, contract_errs = contract.validate_set_e_completeness()
    assert contract_ok, f"ThemeContract validation failed for {mt_id}: {contract_errs}"
