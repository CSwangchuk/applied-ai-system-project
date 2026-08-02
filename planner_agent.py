from typing import Dict, List, Tuple

from pawpal_system import Pet, Task
from retriever import Retriever


class PlannerAgent:
    """Turns retrieved care guidance into concrete, schedulable Tasks.

    The agent is deliberately deterministic: given the same retrieved entries it
    always drafts the same Tasks. Each knowledge-base category maps to a single
    Task template (name, time-of-day, duration, priority, frequency) via
    ``_CATEGORY_RULES``. This makes behavior easy to reason about and to unit
    test, and it keeps the "reasoning" in ``plan_with_trace`` explainable rather
    than opaque.

    Limitation: one entry produces exactly one Task, and the rules are fixed
    heuristics that do not (yet) adapt to the free-text ``content`` or to a
    pet's ``health_issues``. A production planner might parse the content or
    call an LLM to tune cadence and duration per pet.
    """

    # Maps a knowledge-base category to a Task template. Values are chosen with
    # simple, defensible rules:
    #   - feeding is highest priority (a pet must eat) and happens in the
    #     morning, every day.
    #   - exercise is medium priority, scheduled after lunch, every day.
    #   - grooming is low priority and only needed weekly.
    #   - health_checkups is a recurring reminder; "monthly" is a placeholder
    #     cadence since real checkups are usually every 6-12 months, and the
    #     ``Scheduler`` only rolls over "daily" tasks.
    _CATEGORY_RULES = {
        "feeding": {
            "name": "Feeding",
            "time": "08:00",
            "duration": 20,
            "priority": "high",
            "frequency": "daily",
        },
        "exercise": {
            "name": "Walk / playtime",
            "time": "13:00",
            "duration": 45,
            "priority": "medium",
            "frequency": "daily",
        },
        "grooming": {
            "name": "Grooming",
            "time": "17:00",
            "duration": 30,
            "priority": "low",
            "frequency": "weekly",
        },
        "health_checkups": {
            "name": "Vet checkup",
            "time": "10:00",
            "duration": 60,
            "priority": "high",
            "frequency": "monthly",
        },
    }

    # Fallback template for any category we don't have an explicit rule for, so
    # an unexpected knowledge-base entry still yields a usable (if generic) Task
    # rather than being silently dropped.
    _DEFAULT_RULE = {
        "name": "Care task",
        "time": "12:00",
        "duration": 30,
        "priority": "medium",
        "frequency": "daily",
    }

    def _rule_for(self, category: str) -> Dict:
        """Return the Task template for a category, or the default template."""
        return self._CATEGORY_RULES.get(category, self._DEFAULT_RULE)

    def _build_task(self, pet: Pet, entry: dict) -> Task:
        """Draft a single Task from one retrieved knowledge-base entry."""
        category = entry.get("category", "")
        rule = self._rule_for(category)
        # Personalize the task name with the pet's name and category so a plan
        # for multiple pets is readable (e.g. "Feeding - Rex").
        name = f"{rule['name']} - {pet.name}"
        return Task(
            name=name,
            time=rule["time"],
            duration=rule["duration"],
            priority=rule["priority"],
            frequency=rule["frequency"],
        )

    def plan(self, pet: Pet, retriever: Retriever) -> List[Task]:
        """Retrieve care guidance for ``pet`` and draft one Task per entry."""
        entries = retriever.retrieve(pet)
        return [self._build_task(pet, entry) for entry in entries]

    def plan_with_trace(
        self, pet: Pet, retriever: Retriever
    ) -> Tuple[List[Task], List[dict]]:
        """Like ``plan`` but also return a reasoning trace.

        The trace is a list of dicts, one per retrieved entry, recording which
        Task was created and why. This satisfies the ai_interactions.md
        requirement for an inspectable reasoning trace and doubles as a debug
        view into the agent's category-to-Task mapping.
        """
        entries = retriever.retrieve(pet)
        tasks: List[Task] = []
        trace: List[dict] = []

        for entry in entries:
            category = entry.get("category", "")
            task = self._build_task(pet, entry)
            tasks.append(task)

            known = category in self._CATEGORY_RULES
            reasoning = (
                f"Entry category '{category}' mapped to a "
                f"{task.priority}-priority '{task.name}' Task at {task.time} "
                f"for {task.duration} min ({task.frequency})."
            )
            if not known:
                reasoning += (
                    " No explicit rule for this category; used the default "
                    "template."
                )
            # Surface retriever fallbacks in the trace so a reader knows the
            # guidance was less specific than the pet's exact life stage.
            if entry.get("_fallback"):
                reasoning += f" Retriever fallback: {entry.get('_fallback_reason')}"

            trace.append(
                {
                    "entry_id": entry.get("id"),
                    "category": category,
                    "task_created": task.name,
                    "reasoning": reasoning,
                }
            )

        return tasks, trace
