"""Manual verification for PlannerAgent.

Not a pytest suite — run directly with ``python3 test_planner_manual.py`` to
eyeball the generated tasks, the reasoning trace, and that the tasks slot into
the existing Scheduler without errors.
"""

from pawpal_system import Owner, Pet, Scheduler
from planner_agent import PlannerAgent
from retriever import Retriever


def main() -> None:
    pet = Pet("Rex", "Labrador", 4, "none")

    retriever = Retriever()
    planner = PlannerAgent()
    tasks, trace = planner.plan_with_trace(pet, retriever)

    print("=== Generated tasks ===")
    for task in tasks:
        print(
            f"{task.time} | {task.name} | {task.duration} min | "
            f"{task.priority} priority | {task.frequency}"
        )

    print("\n=== Reasoning trace ===")
    for entry in trace:
        print(entry)

    # Attach the generated tasks to the pet, wrap in an Owner, and confirm the
    # existing Scheduler can build a plan from them without errors.
    for task in tasks:
        pet.add_task(task)
    owner = Owner("Alex", pets=[pet])
    scheduler = Scheduler(owner)

    print("\n=== Scheduler plan ===")
    for line in scheduler.generate_plan():
        print(line)


if __name__ == "__main__":
    main()
