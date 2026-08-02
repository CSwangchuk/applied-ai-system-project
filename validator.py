import copy
from typing import Dict, List, Tuple

from pawpal_system import Owner, Pet, Scheduler, Task, _to_minutes
from planner_agent import PlannerAgent
from retriever import Retriever

# Fixed increment (in minutes) used by the deterministic repair step. Chosen to
# be large enough to clear a typical task's duration in a single shift while
# staying small relative to the owner's available window.
_SHIFT_MINUTES = 30

# Minutes in a day, used to wrap times so a repair never produces an invalid
# "HH:MM" (e.g. shifting 23:50 forward rolls it to 00:20 rather than 24:20).
_DAY_MINUTES = 24 * 60


def _to_time_str(minutes: int) -> str:
    """Convert minutes-since-midnight back into a wrapped 'HH:MM' string."""
    minutes %= _DAY_MINUTES
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _parse_window(available_time: str) -> Tuple[int, int]:
    """Parse an 'HH:MM-HH:MM' window into (start, end) minutes since midnight.

    Raises ValueError if the string is empty or malformed so callers get a
    clear signal rather than a silently-passing validation.
    """
    if not available_time or "-" not in available_time:
        raise ValueError(f"Invalid available_time window: {available_time!r}")
    start_str, end_str = available_time.split("-", 1)
    return _to_minutes(start_str.strip()), _to_minutes(end_str.strip())


class Validator:
    """Checks proposed Tasks against an owner's schedule and availability.

    The validator never mutates the real ``Owner``/``Pet`` objects: it works on
    a deep copy so a rejected plan leaves the live schedule untouched. It reuses
    the existing ``Scheduler.detect_conflicts()`` for overlap detection rather
    than reimplementing it, and adds an availability-window check on top.
    """

    def validate(self, owner: Owner, proposed_tasks: List[Task]) -> Dict:
        """Validate ``proposed_tasks`` against ``owner``'s schedule and window.

        Runs two independent checks on a safe copy of the owner:
            1. Time overlaps among all tasks (existing + proposed) via
               ``Scheduler.detect_conflicts()``.
            2. Each proposed task falling inside ``owner.available_time``.

        Returns a summary dict::

            {
                "passed": bool,
                "conflicts": [(name_a, name_b), ...],
                "out_of_window": [task_name, ...],
                "reasons": [human-readable strings],
            }
        """
        reasons: List[str] = []

        # Work on a deep copy so nothing we do here touches the live objects.
        owner_copy = copy.deepcopy(owner)
        proposed_copy = copy.deepcopy(proposed_tasks)

        # Attach the proposed tasks to a pet on the copy so detect_conflicts()
        # considers them alongside the existing schedule. Any pet works since
        # detect_conflicts aggregates across all of the owner's pets; if the
        # owner has no pets we create a throwaway carrier pet on the copy.
        if owner_copy.pets:
            owner_copy.pets[0].tasks.extend(proposed_copy)
        else:
            owner_copy.pets.append(Pet(name="__proposed__", breed="", age=0,
                                       health_issues="", tasks=proposed_copy))

        # --- Check 1: time overlaps among all tasks -------------------------
        conflict_pairs = Scheduler(owner_copy).detect_conflicts()
        conflicts = [(first.name, second.name) for first, second in conflict_pairs]
        for first_name, second_name in conflicts:
            reasons.append(f"'{first_name}' overlaps with '{second_name}'.")

        # --- Check 2: proposed tasks inside the availability window ----------
        out_of_window: List[str] = []
        try:
            window_start, window_end = _parse_window(owner.available_time)
        except ValueError as exc:
            # A missing/malformed window can't be checked, so fail loudly
            # rather than pretending every task is in range.
            reasons.append(str(exc))
            window_start = window_end = None

        if window_start is not None:
            for task in proposed_tasks:
                task_start = _to_minutes(task.time)
                task_end = task_start + task.duration
                if task_start < window_start or task_end > window_end:
                    out_of_window.append(task.name)
                    reasons.append(
                        f"'{task.name}' ({task.time}, {task.duration} min) falls "
                        f"outside available window {owner.available_time}."
                    )

        passed = not conflicts and not out_of_window and window_start is not None
        return {
            "passed": passed,
            "conflicts": conflicts,
            "out_of_window": out_of_window,
            "reasons": reasons,
        }

    def validate_with_replan(
        self,
        pet: Pet,
        owner: Owner,
        retriever: Retriever,
        planner: PlannerAgent,
        max_attempts: int = 3,
    ) -> Tuple[List[Task], Dict]:
        """Plan tasks for ``pet``, validate, and deterministically repair.

        Drafts tasks via ``planner.plan_with_trace``, validates them, and on
        failure applies a simple fixed-increment time shift to each offending
        task before re-validating. Repeats up to ``max_attempts`` times.

        The repair is intentionally naive and deterministic (no search, no
        LLM): every out-of-window or conflicting task is pushed forward by
        ``_SHIFT_MINUTES``. This may not resolve every schedule, but it is
        predictable and easy to reason about.

        Returns ``(final_tasks, summary)`` where ``summary`` includes::

            {
                "attempts": int,          # how many validate() passes ran
                "passed": bool,           # final result
                "final_result": {...},    # the last validate() dict
                "history": [validate dicts, one per attempt],
            }
        """
        tasks, _trace = planner.plan_with_trace(pet, retriever)

        history: List[Dict] = []
        result: Dict = {}
        attempts = 0

        for attempt in range(1, max_attempts + 1):
            attempts = attempt
            result = self.validate(owner, tasks)
            history.append(result)

            if result["passed"]:
                break

            # Deterministic repair: shift every flagged task forward by a fixed
            # increment, then re-validate on the next loop iteration.
            flagged = set(result["out_of_window"])
            for name_a, name_b in result["conflicts"]:
                # Shift the later task in each overlapping pair.
                flagged.add(name_b)

            if not flagged:
                # Nothing actionable to shift (e.g. a malformed window); further
                # attempts would be identical, so stop early.
                break

            for task in tasks:
                if task.name in flagged:
                    task.time = _to_time_str(_to_minutes(task.time) + _SHIFT_MINUTES)

        return tasks, {
            "attempts": attempts,
            "passed": result.get("passed", False),
            "final_result": result,
            "history": history,
        }
