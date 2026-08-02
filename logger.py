import json
import os
from datetime import datetime
from typing import Dict, List

# Default location for the append-only interaction log. JSON Lines (one JSON
# object per line) is used so runs can be appended cheaply and read back one
# entry at a time without loading/rewriting a single large JSON array.
_DEFAULT_LOG_PATH = "logs/ai_interactions_log.jsonl"


class Logger:
    """Appends and reads back PawPal+ AI interaction records.

    Each ``log_run`` call captures one end-to-end run: the planner's reasoning
    trace plus the validator's repair summary, stamped with a timestamp. The log
    is an audit trail of what the agent decided and why, satisfying the
    ai_interactions.md logging requirement.
    """

    def log_run(
        self,
        pet_name: str,
        trace: List[dict],
        validator_summary: Dict,
        log_path: str = _DEFAULT_LOG_PATH,
    ) -> None:
        """Append one run as a JSON line to ``log_path``.

        The entry records a timestamp, the pet, the planner's ``trace``, and the
        validator's ``attempts``/``passed``/``history``. The ``logs/`` directory
        and file are created on first use if they don't already exist.
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "pet_name": pet_name,
            "trace": trace,
            "validator_summary": {
                "attempts": validator_summary.get("attempts"),
                "passed": validator_summary.get("passed"),
                "history": validator_summary.get("history"),
            },
        }

        # Create the parent directory (e.g. "logs/") if the path has one and it
        # doesn't exist yet, so the first run doesn't fail on a missing folder.
        parent = os.path.dirname(log_path)
        if parent:
            os.makedirs(parent, exist_ok=True)

        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")

    def read_all(self, log_path: str = _DEFAULT_LOG_PATH) -> List[dict]:
        """Return every logged entry from ``log_path``.

        Returns an empty list if the file doesn't exist yet, so callers can read
        before anything has been logged. Blank lines are skipped defensively.
        """
        if not os.path.exists(log_path):
            return []

        entries: List[dict] = []
        with open(log_path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries
