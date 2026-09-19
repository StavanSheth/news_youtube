# Theme Engine Design Rules & Specification Contract

## 1. Architectural Principles

1. **Exact Overrides Over Generic Fallbacks**: Every micro-topic in the 236-topic matrix MUST resolve to an explicit, bespoke theme rather than falling back to family or global templates.
2. **Determinism and Reproducibility**: Theme resolution, question assembly, and evidence checking are 100% deterministic with zero LLM dependence during validation.
3. **Observability**: Every resolved theme carries an explicit `theme_resolution` record documenting the exact requested level, resolved level, fallback flag, fallback reason, and specificity score.
4. **Stream Separation**: While themes share analytical core objectives across news and video streams, stream-specific operational parameters (freshness, preferred channels, demonstration requirements) MUST diverge.

## 2. Machine-Checkable Theme Completeness Contract

A theme definition is valid under Set-E Section 5 if and only if all of the following conditions hold:

```text
theme_id != null
micro_topic_id != null
version != null
questions >= 1 (non-generic, topic-tailored)
evidence_requirements >= 1 (verified source types)
significance_rules.significant_if >= 1
significance_rules.insignificant_if >= 1
stream_rules.news != null (freshness, preferred sources, focus)
stream_rules.video != null (relevant video types, questions, focus)
no_update_policy.NO_MAJOR_UPDATE != null (informative prose)
no_update_policy.INSUFFICIENT_EVIDENCE != null
output.report_type in taxonomy.report_types
output.sections >= 3
```

## 3. Specificity & Sibling Isolation Rules

1. **Fingerprint Uniqueness**: The deterministic hash `theme_fingerprint(theme)` MUST be unique across all themes in the engine.
2. **Lexical Overlap Cap**: Sibling themes belonging to the same domain MUST maintain lexical overlap `< 0.85` to prevent cookie-cutter substitutions.
3. **Specificity Threshold**: Every bespoke theme MUST achieve a `theme_specificity_score >= 0.55`.

## 4. Evidence Hierarchy

For each finding produced by a theme:
- Primary source documentation (papers, SEC filings, official advisories, release tags) is REQUIRED.
- Speculative claims and uncorroborated commentary are prohibited as sole evidence.
- Inference MUST be tagged separately from verified factual disclosures.
