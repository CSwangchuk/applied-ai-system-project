import json
from pathlib import Path
from typing import List

from pawpal_system import Pet

# Path to the committed knowledge base, resolved relative to this file so the
# retriever works regardless of the current working directory.
KNOWLEDGE_BASE_PATH = Path(__file__).parent / "data" / "knowledge_base.json"


class Retriever:
    """Field-matching retriever over the pet-care knowledge base.

    This is a deliberately simple, dependency-free retriever: no embeddings and
    no API calls. It infers a pet's ``pet_type`` and ``life_stage`` from the
    ``Pet`` object, then returns knowledge-base entries whose fields match.
    """

    # Lookup table mapping common breed strings to a species. Keys are stored
    # lowercase and matched case-insensitively.
    # Limitation: this is a small, hand-curated list. Unrecognized breeds fall
    # back to "dog" (see infer_pet_type), which may misclassify cats whose
    # breed we haven't listed.
    _BREED_TO_TYPE = {
        # Dogs
        "labrador": "dog",
        "labrador retriever": "dog",
        "golden retriever": "dog",
        "german shepherd": "dog",
        "shiba inu": "dog",
        "poodle": "dog",
        "bulldog": "dog",
        "beagle": "dog",
        "chihuahua": "dog",
        "dachshund": "dog",
        "husky": "dog",
        "siberian husky": "dog",
        "corgi": "dog",
        "pomeranian": "dog",
        # Cats
        "tabby": "cat",
        "tabby cat": "cat",
        "persian": "cat",
        "siamese": "cat",
        "maine coon": "cat",
        "bengal": "cat",
        "ragdoll": "cat",
        "sphynx": "cat",
        "british shorthair": "cat",
        "scottish fold": "cat",
        "domestic shorthair": "cat",
    }

    def __init__(self, knowledge_base_path: Path = KNOWLEDGE_BASE_PATH):
        self.knowledge_base_path = Path(knowledge_base_path)

    def infer_pet_type(self, breed: str) -> str:
        """Map a breed string to "dog" or "cat" via a lookup table.

        Matching is case-insensitive and whitespace-trimmed. Unrecognized
        breeds default to "dog".

        Limitation: the lookup table is small and hand-curated, and the "dog"
        default means any breed we haven't listed (including cats) is treated
        as a dog. A production system would use a fuzzy match or a full breed
        registry rather than an exact-key lookup.
        """
        key = (breed or "").strip().lower()
        return self._BREED_TO_TYPE.get(key, "dog")

    def infer_life_stage(self, age: int, pet_type: str) -> str:
        """Map an age (in years) to a life stage.

        Thresholds:
            under 1 year  -> "puppy" (dog) / "kitten" (cat)
            1 to 6 years  -> "adult"
            7 years and up -> "senior"

        Reasoning: these are common, widely cited veterinary rules of thumb.
        Both dogs and cats are generally considered adults around 1 year, and
        the ~7-year mark is a frequently used starting point for "senior" care
        (more frequent checkups, diet adjustments), though the exact age varies
        by breed and size. We keep a single simple threshold here for clarity;
        this matches the life_stage values used in data/knowledge_base.json.
        """
        if age < 1:
            return "kitten" if pet_type == "cat" else "puppy"
        if age <= 6:
            return "adult"
        return "senior"

    def _load_knowledge_base(self) -> List[dict]:
        """Load and return the knowledge-base entries from disk."""
        with open(self.knowledge_base_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def retrieve(self, pet: Pet) -> List[dict]:
        """Return knowledge-base entries relevant to the given pet.

        Inference: pet_type is inferred from ``pet.breed`` and life_stage from
        ``pet.age``. Matching is a two-step field match:
            1. Exact match on both pet_type AND life_stage.
            2. If nothing matches exactly, fall back to pet_type only.

        When a fallback happens, each returned entry is tagged with
        ``_fallback=True`` and ``_fallback_reason`` so callers (and the UI) can
        surface that the results are less specific than requested.
        """
        pet_type = self.infer_pet_type(pet.breed)
        life_stage = self.infer_life_stage(pet.age, pet_type)

        entries = self._load_knowledge_base()

        exact = [
            entry
            for entry in entries
            if entry.get("pet_type") == pet_type
            and entry.get("life_stage") == life_stage
        ]
        if exact:
            return exact

        # Fallback: no entry matched both fields, so broaden to pet_type only.
        fallback = [
            {
                **entry,
                "_fallback": True,
                "_fallback_reason": (
                    f"No entries matched pet_type='{pet_type}' and "
                    f"life_stage='{life_stage}'; broadened to pet_type only."
                ),
            }
            for entry in entries
            if entry.get("pet_type") == pet_type
        ]
        return fallback
