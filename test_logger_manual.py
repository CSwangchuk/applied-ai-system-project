"""Manual verification script for the Logger class.

Runs the full pipeline (Retriever -> PlannerAgent -> Validator) on the same
conflicting-task scenario as test_validator_manual.py, logs the planner trace
and validator summary via Logger.log_run, then reads everything back with
Logger.read_all to confirm the log round-trips correctly.
"""

from pawpal_system import Owner, Pet, Task
from retriever import Retriever
from planner_agent import PlannerAgent
from validator import Validator
from logger import Logger


def main():
    # Same setup as test_validator_manual.py: an existing 13:00 appointment
    # collides with the exercise Task the planner drafts at 13:00.
    existing = Task("Existing appointment", "13:00", 45, "high", "daily")
    pet = Pet("Rex", "Labrador", 4, "none", tasks=[existing])
    owner = Owner("Alex", pets=[pet], available_time="07:00-18:00")

    # Capture the planner trace and the validator summary separately: the
    # validator runs its own plan internally, but we also need the trace to log.
    _tasks, trace = PlannerAgent().plan_with_trace(pet, Retriever())
    _final_tasks, summary = Validator().validate_with_replan(
        pet, owner, Retriever(), PlannerAgent()
    )

    logger = Logger()
    logger.log_run(pet.name, trace, summary)

    entries = logger.read_all()
    print(f"=== read_all() returned {len(entries)} entr(y/ies) ===")
    for i, entry in enumerate(entries, start=1):
        print(f"\n--- Entry {i} ---")
        print(f"  timestamp: {entry['timestamp']}")
        print(f"  pet_name:  {entry['pet_name']}")
        print(f"  trace steps: {len(entry['trace'])}")
        for step in entry["trace"]:
            print(f"    - {step['task_created']}: {step['reasoning']}")
        vs = entry["validator_summary"]
        print(f"  validator attempts: {vs['attempts']}")
        print(f"  validator passed:   {vs['passed']}")
        print(f"  validator history entries: {len(vs['history'])}")


if __name__ == "__main__":
    main()
