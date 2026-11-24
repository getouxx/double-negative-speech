# double-negative-speech

Rule-based generator/decoder for Chinese **double negation and hedging** ("绕弯说话术"). It treats negation as an operator: parity folding × scope × quantifier range × conditional nesting — not as a rhetoric trick.

**Why it exists:** negation and double negation are among the weakest spots for LLMs and statistical models, so a small, explainable rule layer is a useful complement rather than a duplicate.

## What it does

- **Decode**: take a twisty Chinese sentence, return a fixed-shape JSON verdict (`status`, `certainty`, `polarity`, `confidence`, `rules`, `scope`).
- **Generate**: turn a plain sentence into light / medium / heavy wrapping while keeping a unique reading, verified by round-trip folding.
- **Explain**: every ambiguity carries a rule id (`R-SPECIAL`, `R-LEXICAL`, `R-QUANT`, `R-SCOPE`, `R-DEPTH`, `R-CONFLICT`), and `check` reports `matched_rules` plus `conflicts`.

## Install

```bash
pip install -e .            # provides `wanhua` and `negation-count` (Python >= 3.8, stdlib only)
uv tool install .
```

As an Agent Skill, run `./install.sh` from a clone (it only installs into existing skill directories).

## Quick use

```bash
wanhua solve "差点没赶上"          # status: ambiguous, certainty: uncertain, exit 3
wanhua solve "难道这不叫负责吗？"    # status: out_of_scope, polarity: null — no guessing
wanhua check "不是不该改"           # matched_rules / conflicts / pass
wanhua compare "不是不该改" "该改"   # same_polarity: true
```

## Honesty notes

- **Three-tier certainty**: `certain` (usable), `uncertain` (polarity is a hint only), `out_of_scope` (rules cannot decide — human review required).
- **No guessing**: rhetorical/sarcastic sentences return `out_of_scope` with `polarity: null` instead of a low-confidence verdict.
- **Measured, not asserted**: 33 regression cases (84.38% polarity) plus a 60-sentence hold-out set written independently of the rule table (88.33% polarity, 92.31% recall on negatives). Misses stay in the report; labels are never bent to fit rules.
- **Not a corpus benchmark**: CCL and similar licensed corpora are not wired in, so the hold-out set is an authored complement, not a substitute for corpus evaluation.
- **Scope**: logical wrapping only. Word-sense weirdness, homophone typos and dialect variance are out of scope by design.

## Contract

See [`references/contract.md`](references/contract.md) for fields, status semantics, exit codes and rule ids; [`CHANGELOG.md`](CHANGELOG.md) tracks rule drift.

License: GPL-3.0.
