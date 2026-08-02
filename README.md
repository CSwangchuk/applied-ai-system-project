# PawPal+ Applied AI System (CodePath AI110 Project 4)

## Base Project

This project extends **PawPal+**, originally built for CodePath AI110 Module 2. The original PawPal+ was a Streamlit app that let a pet owner track pets and care tasks (walks, feeding, meds, grooming) and generate a time-ordered daily schedule, including conflict detection between overlapping tasks. The core classes — `Task`, `Pet`, `Owner`, `Scheduler` — are unchanged in this extension; all new AI functionality is built as additional components on top of them.

## Title and Summary

**PawPal+ Applied AI System** turns PawPal+ from a manual task tracker into a system that *plans* pet care automatically. Given a pet's profile, it retrieves relevant care guidance, drafts a schedule, checks that schedule for conflicts, and self-corrects if problems are found — all before handing the result to the existing `Scheduler`.

This matters because it moves PawPal+ from "the owner has to think of every task" to "the system proposes a reasonable starting schedule and defends it," which is a meaningfully different (and more useful) product.

## Architecture Overview

See `diagrams/architecture.mmd` for the full Mermaid source. In summary:

Owner/Pet Profile → Retriever (matches pet_type + life_stage against knowledge_base.json)
→ PlannerAgent (drafts Tasks from retrieved guidance)
→ Validator (checks conflicts via existing Scheduler.detect_conflicts()
+ checks owner.available_time window)
├── fail → deterministic repair (shift task time) → re-validate
└── pass → Logger records the full run (trace + validator history)


- **CareKnowledgeBase** (`data/knowledge_base.json`): 8 hand-written, vet-source-verified pet care guidelines covering dog/cat × puppy-kitten/adult/senior × exercise/feeding/grooming/health_checkups (not fully crossed — see Limitations).
- **Retriever** (`retriever.py`): deterministic field-matching (no embeddings, no API calls) — infers `pet_type` from breed and `life_stage` from age, then matches against the knowledge base, falling back to pet_type-only matches when no exact life_stage match exists.
- **PlannerAgent** (`planner_agent.py`): maps each retrieved entry's `category` to a `Task` via fixed, documented rules (e.g. feeding → high priority, morning; grooming → low priority, weekly). Produces a reasoning trace alongside the tasks.
- **Validator** (`validator.py`): reuses the *existing* `Scheduler.detect_conflicts()` rather than reimplementing overlap detection, adds an `owner.available_time` window check, and drives a deterministic replan loop (shift conflicting/out-of-window tasks by a fixed +30 min increment, up to 3 attempts).
- **Logger** (`logger.py`): appends every run (trace + validator history) as a JSON line to `logs/ai_interactions_log.jsonl`, and can read all past runs back.

## Setup Instructions

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

No API keys are required — the Retriever and PlannerAgent are fully deterministic and rule-based, with no external calls.

## Sample Interactions

### 1. Simple case — Retriever + PlannerAgent, no conflicts

$ python3 test_planner_manual.py
=== Generated tasks ===
13:00 | Walk / playtime - Rex | 45 min | medium priority | daily

=== Reasoning trace ===
{'entry_id': 'dog_adult_exercise', 'category': 'exercise', 'task_created': 'Walk / playtime - Rex', 'reasoning': "Entry category 'exercise' mapped to a medium-priority 'Walk / playtime - Rex' Task at 13:00 for 45 min (daily)."}

=== Scheduler plan ===
13:00 - Walk / playtime - Rex (45 min, medium priority)


Rex (a Labrador, age 4) was correctly inferred as `dog`/`adult`, matched to the single relevant knowledge base entry available for that combination, and the resulting Task passed cleanly into the existing `Scheduler`.

### 2. Conflict detected and self-repaired — Validator's replan loop

$ python3 test_validator_manual.py
=== Final tasks ===
Walk / playtime - Rex | 14:00 | 45 min | medium | daily

=== Summary ===
attempts: 3
passed: True

=== History (per attempt) ===
Attempt 1:
passed: False
conflicts: [('Existing appointment', 'Walk / playtime - Rex')]
out_of_window: []
Attempt 2:
passed: False
conflicts: [('Existing appointment', 'Walk / playtime - Rex')]
out_of_window: []
Attempt 3:
passed: True
conflicts: []
out_of_window: []


Rex had an existing appointment at 13:00-13:45. PlannerAgent proposed a walk at the same time. The Validator detected the overlap using the *existing* `Scheduler.detect_conflicts()`, shifted the proposed task by 30 minutes twice, and passed on the third attempt — a working plan → check → replan agentic loop.

### 3. Logged and retrieved run history

$ python3 test_logger_manual.py
=== read_all() returned 2 entr(y/ies) ===

--- Entry 1 ---
timestamp: 2026-08-02T18:16:29.219799
pet_name: Rex
trace steps: 1
- Walk / playtime - Rex: Entry category 'exercise' mapped to a medium-priority 'Walk / playtime - Rex' Task at 13:00 for 45 min (daily).
validator attempts: 3
validator passed: True
validator history entries: 3


Every run — including the reasoning trace and full validator history — is persisted to `logs/ai_interactions_log.jsonl` and can be read back for auditing.

## Design Decisions

- **Field-matching over embeddings for the Retriever.** With only 8 knowledge base entries, semantic embeddings would add API dependency, cost, and non-determinism for no real accuracy gain. Deterministic field-matching is fully testable (exact input → exact expected output) and fits the reliability focus of this module. Embeddings remain a natural stretch-feature extension.
- **Reusing `Scheduler.detect_conflicts()` in the Validator** rather than reimplementing conflict detection. This avoids duplicating logic that's already tested and working, and keeps the new AI components thin wrappers around proven code.
- **Deterministic, rule-based repair** (fixed +30 min shift) instead of an LLM-based repair. This keeps the replan loop's behavior fully predictable and unit-testable, at the cost of being a naive repair strategy that only shifts the later of two conflicting tasks.
- **JSON Lines for the log format** — allows appending new runs cheaply without rewriting the whole file, and each line is independently parseable.

## Testing Summary

Manual verification scripts (`test_planner_manual.py`, `test_validator_manual.py`, `test_logger_manual.py`) confirmed:
- Retriever correctly infers pet_type/life_stage and falls back gracefully when no exact match exists (verified with a dog, a cat, and an unrecognized breed — see `retriever.py` limitations).
- PlannerAgent produces valid `Task` objects that the *existing, unmodified* `Scheduler` can schedule without error.
- Validator correctly detects an intentionally-triggered conflict and resolves it within 3 replan attempts.
- Logger correctly round-trips run data (write then read back matched exactly).

All manual tests passed on first working implementation after one round of review per component. See `model_card.md` for AI collaboration details and honest limitations.

## Reflection

See `model_card.md` for the full responsible-AI reflection (limitations, misuse considerations, testing surprises, and AI collaboration — one helpful and one flawed suggestion).

## Presentation / Portfolio
https://github.com/CSwangchuk/applied-ai-system-project
This project pushed me to think about AI systems as pipelines with checkpoints, not single black-box calls. Building the Validator's replan loop — watching it actually detect a conflict and fix its own output over three attempts — was the first time an "agentic" system felt real to me rather than just a buzzword. I also learned that reusing existing, tested code (like `Scheduler.detect_conflicts()`) instead of rebuilding it is often the better engineering choice, even when building something new.