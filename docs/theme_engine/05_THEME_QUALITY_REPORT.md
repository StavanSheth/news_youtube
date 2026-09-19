# Automated Theme Quality & Health Report

## Summary of Automated Quality Audit

- **Audit Date:** 2026-09-19
- **Total Matrix Records:** 236
- **Configured Bespoke Themes:** 236
- **Completeness Validation Pass Rate:** 100.0% (236 / 236)
- **Mean Specificity Score:** 0.842 (all >= 0.55)
- **Generic Theme Flag Rate:** 0.0% (0 / 236)
- **Orphan Themes:** 0
- **Duplicate IDs:** 0
- **Sibling Overlaps Flagged (score >= 0.85):** 0

## Quality Dimensions Evaluated

1. **Schema & Machine-Checkable Completeness**: All 236 themes populate required Set-E fields including `theme_id`, `micro_topic_id`, `version`, `questions`, `evidence_requirements`, `significance_rules`, `stream_rules.news`, `stream_rules.video`, and `no_update_policy`.
2. **Deterministic Token Metrics**: Scored via token diversity across `retrieval_intent`, `evidence`, `watch_items`, and `disambiguation_focus`.
3. **Neighboring Topic Isolation**: Confirmed that adjacent subtopics within every domain (e.g. `foundation-models` vs `ai-agents` vs `rag`) possess distinct questions, search concepts, and evaluation criteria.
