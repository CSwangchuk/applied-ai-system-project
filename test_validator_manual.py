"""Manual verification script for the Validator class.

Sets up an owner whose existing 13:00 appointment collides with the exercise
Task that PlannerAgent schedules at 13:00, then runs validate_with_replan and
prints the repair history so the deterministic shift can be inspected by hand.
"""

from pawpal_system import Owner, Pet, Task
from retriever import Retriever
from planner_agent import PlannerAgent
from validator import Validator


def main():
    # Existing task at 13:00 will overlap the exercise Task the planner drafts
    # at 13:00, forcing the validator into its repair loop.
    existing = Task("Existing appointment", "13:00", 45, "high", "daily")
    pet = Pet("Rex", "Labrador", 4, "none", tasks=[existing])
    owner = Owner("Alex", pets=[pet], available_time="07:00-18:00")

    tasks, summary = Validator().validate_with_replan(
        pet, owner, Retriever(), PlannerAgent()
    )

    print("=== Final tasks ===")
    for task in tasks:
        print(
            f"  {task.name} | {task.time} | {task.duration} min | "
            f"{task.priority} | {task.frequency}"
        )

    print("\n=== Summary ===")
    print(f"  attempts: {summary['attempts']}")
    print(f"  passed:   {summary['passed']}")

    print("\n=== History (per attempt) ===")
    for i, result in enumerate(summary["history"], start=1):
        print(f"  Attempt {i}:")
        print(f"    passed:        {result['passed']}")
        print(f"    conflicts:     {result['conflicts']}")
        print(f"    out_of_window: {result['out_of_window']}")


if __name__ == "__main__":
    main()
