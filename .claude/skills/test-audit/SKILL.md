---
name: test-audit
description: "Audits the pytest test suite for coverage gaps, inflated counts, and unprotected source modules. Use when assessing the value of the existing tests or deciding what to write next."
---

You are acting as the pytest-suite-guardian auditing the Midas test suite. Your job is to give an honest picture of what the tests actually protect — not just report a count.

## Step 1 — Collect test stats

Run:
```bash
bash .claude/skills/test-audit/scripts/count.sh
```

Then break down counts by test class:
```bash
bash .claude/skills/test-audit/scripts/breakdown.sh
```

## Step 2 — Cross-reference source modules

List all `.py` files under `src/` (excluding `__init__.py`) and check which ones have a corresponding test file or are covered by an existing test file. Flag any source module with **zero test coverage**.

```bash
bash .claude/skills/test-audit/scripts/source-modules.sh
```

## Step 3 — Analyse and report

Organise your findings into four sections:

### Well-covered areas
List source modules or layers that have thorough tests. Be specific — name the test classes and what they exercise.

### Coverage gaps
For each untested or undertested source module, report:

```
[SEVERITY] Source: <file path>
Test file: <none | sparse — N tests in TestClassName>
Risk: <what kind of regression would go undetected>
```

Use 🔴 for zero coverage on a non-trivial module, 🟡 for sparse coverage (fewer tests than the module has logical branches), 🔵 for informational notes.

### Count inflation check
Identify test classes that are heavily parametrized over input variations on a single utility (e.g. 20+ tests for `parse_float`). These are valuable but inflate the headline number. Report:
- Inflated test classes and their counts
- Adjusted "effective coverage" count (total minus pure-parametrized-utility tests)

### Recommended next tests
List the 2–3 highest-value test gaps to fill, in priority order, with a one-line description of what to test and why.

## Tone

Be direct. A large test count with critical gaps is worse than a smaller count with solid coverage. The goal is an honest signal, not a flattering one.
