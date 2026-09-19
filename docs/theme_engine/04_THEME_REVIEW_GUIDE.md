# Theme Engine Human Review Guide

## Overview

This guide establishes the human review criteria and lifecycle management for all 236 bespoke micro-topic themes.

## Review Status Lifecycle

Themes transition through four formal states:

```text
UNREVIEWED → AI_VALIDATED → HUMAN_REVIEWED → APPROVED
```

1. **`UNREVIEWED`**: Draft specification imported from external templates.
2. **`AI_VALIDATED`**: Passes automated machine-checkable completeness (`validate_theme_completeness`), specificity thresholds (score >= 0.55), and sibling isolation tests.
3. **`HUMAN_REVIEWED`**: Domain specialist has verified that questions, evidence requirements, and significance rules accurately reflect field practice.
4. **`APPROVED`**: Final signoff deployed to production newsletter generation.

## Review Checklist

For each theme undergoing human review:

- [ ] **Analytical Depth**: Do the questions probe real technical/business mechanics rather than shallow summaries?
- [ ] **Evidence Adequacy**: Are the required evidence classes sufficient to prevent misinformation?
- [ ] **Significance Calibrated**: Do `significant_if` rules exclude routine minor updates and include actual structural breakthroughs?
- [ ] **Stream Appropriateness**: Are video requirements calibrated for visual and demonstration-heavy content?
- [ ] **No-Update Integrity**: Is the `NO_MAJOR_UPDATE` message sufficiently informative to explain why no story was published?
