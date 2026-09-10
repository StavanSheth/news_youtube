# Set E Phase 1 Audit

This audit covers the Phase 1 foundation and contract-alignment scope from the Set E final freeze. Later intelligence-engine redesigns are intentionally outside this phase.

| Requirement | Before | Implemented | Verification | Evidence |
| --- | --- | --- | --- | --- |
| Canonical identifiers | IDs were mixed across source, content, and evidence paths. | Added deterministic domain-specific ID builders for source, content, event, entity, micro-topic, theme, evidence, edition, run, publication, and delivery records. Source IDs retain a readable slug plus a collision-resistant digest. | Phase 1.1 identity tests pass, including collision and idempotence checks. | `src/intelligence/identity.py` |
| Edition and run context | Runs had no shared edition/run contract. | Added timezone-aware `EditionContext` and `RunContext`, including stable edition keys and stage transitions. | Cutoff, key stability, and stage tests pass. | `src/intelligence/contracts.py`, `src/intelligence/production.py` |
| Edition key | Output identity was based on timestamp folders. | Edition identity is `YYYY-MM-DD|EDITION|TIMEZONE`; filesystem paths use a safe representation. | Persistence path tests pass; fixture run persists the key. | `src/intelligence/identity.py`, `src/intelligence/persistence.py` |
| Time and cutoff contract | `utcnow()` and implicit timestamps were present in the runtime. | `SourceItem` now carries `SourceTimestamps`; normalized mappings record valid/missing/invalid publication state; eligibility requires a valid timestamp inside the edition window. | Aware/naive, missing/malformed/future, and cutoff tests pass. | `src/intelligence/contracts.py`, `src/intelligence/models.py`, `src/intelligence/production.py` |
| Provenance | Retrieved metadata existed but was not a shared contract. | Normalized source items and retrieval chunks attach validated provenance; provider evidence carries the provenance serialization and identity chain. | Source-item, retrieval, and provider provenance tests pass. | `src/intelligence/contracts.py`, `src/intelligence/models.py`, `src/intelligence/retrieval.py`, `src/intelligence/provider.py` |
| Status vocabulary | Status strings were distributed across modules. | Added shared intelligence, validation, publication, delivery, pipeline-stage, and source-status enums; runtime delivery and source validation use them. | Vocabulary and production compatibility tests pass. | `src/intelligence/statuses.py`, `src/intelligence/production.py`, `src/intelligence/source_validation.py` |
| Version contracts | Taxonomy versioning existed without a complete runtime contract. | Added `config/version.yaml`, validated it during config loading, and persist versions with each run. | Config/version tests pass; fixture output includes versions. | `config/version.yaml`, `src/intelligence/config.py` |
| Persistence paths | Root-relative paths were assembled in orchestration code. | Added a single `PersistencePaths` contract for data, raw, normalized, RAG, events, entities, state, runs, edition output, and archive locations; production initializes the logical directories and uses the contract for state files. | Logical-area, path, and production fixture tests pass. | `src/intelligence/persistence.py`, `src/intelligence/production.py` |
| Pipeline stages | Legacy and production paths were easy to confuse. | `production.py` is authoritative; `pipeline.py` delegates only for compatibility. The canonical Set E stage order is now machine-represented without claiming later stages are fully implemented. | Stage-order and delegation regression tests pass. | `src/intelligence/statuses.py`, `src/intelligence/production.py`, `src/intelligence/pipeline.py` |
| Duplicate ownership | Compatibility modules could appear to own separate behavior. | Kept compatibility adapters while documenting authoritative modules and preserving existing imports. | Full regression suite passes. | `src/intelligence/ai.py`, `src/intelligence/pipeline.py` |
| Security and configuration | Secrets are runtime inputs rather than repository data. | Continued environment-only secret loading; no keys or SMTP credentials are added to tracked files. | Secret scan and repository diff review performed. | `.env.example`, `.github/workflows/intelligence.yml` |
| Regression protection | Baseline was 23 passing tests. | Added 14 foundation and closure tests without breaking existing behavior. | 37 tests pass; Ruff passes. | `tests/test_phase1_foundation.py` |

## Validation

- `pytest`: 37 passed.
- `ruff check . --no-cache`: passed.
- Deterministic fixture run in a fresh writable copy: passed with quality score 100, 8 eligible items, 7 processed fixture items, and all 8 publication timestamps classified as valid.
- Source validation applies its configured timeout to the default HTTP fetch; injected parsers remain available for deterministic tests.
- A repository-local `compileall` attempt was blocked by existing read-only `__pycache__` files; syntax is covered by pytest imports and an in-memory compile validation.
- No type-checker is configured in the repository, so no type-check command was available to run.

## Phase Boundary

Phase 1.1 closure is complete. Micro-topic expansion, retrieval redesign beyond bounded provenance, new theme logic, newsletter redesign, and additional architecture work remain governed by their later phase contracts and were not introduced as part of this foundation pass.
