# Theme Engine Changelog

## [1.0.0] - 2026-09-19

### Added
- **236 Bespoke Micro-Topic Themes**: Completed full production analytical specifications across all 21 taxonomy domains.
- **Config Architecture Refactor**: Decomposed `config/themes.yaml` into domain files under `config/themes/` indexed by `config/themes/registry.yaml`.
- **Set-E Contract Extension**: Extended `ThemeContract` with significance rules, news and video stream rules, entity and event extraction configurations, no-update policies, and snapshot persistence.
- **Theme Template Registry & Inheritance**: Implemented `ThemeTemplateRegistry` in `src/intelligence/themes/inheritance.py` for layered resolution and origin inspection.
- **Theme Snapshot Persistence**: Implemented deterministic fingerprinting and snapshot verification in `src/intelligence/themes/snapshots.py`.
- **Theme Coverage Validator & CLI**: Implemented `python -m intelligence.themes.coverage` with `--all`, `--json`, `--specificity`, and `--source` modes.
- **Theme Engine Test Suite**: Implemented 18 test files in `tests/themes/` covering contract validation, bidirectional coverage, specificity, isolation, questions, evidence, significance, and stream rules.
- **Machine-Readable Artifacts**: Generated `data/theme_coverage.json`, `data/theme_health.json`, and `data/theme_validation.json`.
- **CI Enforcement**: Integrated 236 theme coverage and specificity checks into `.github/workflows/ci.yml`.
