# Model Card — PawPal+ Applied AI System

## Limitations and Biases

- **Retriever defaults unknown breeds to "dog."** `infer_pet_type()` uses a small hand-curated lookup table; any breed not in that table — including cats with an unlisted breed name — is classified as a dog. This was confirmed directly during testing (a pet named "Ghost" with breed "Unknown Mix" was retrieved as a dog). This is a real bias in the system, not a hypothetical one.
- **Knowledge base coverage is incomplete.** The 8 entries in `knowledge_base.json` don't cover every pet_type × life_stage × category combination (e.g. there is no `dog_puppy_health_checkups` or `cat_senior_feeding`). In practice this means some pets receive only a partial plan — for example, a 4-year-old Labrador (Rex) received only one Task (exercise) because no feeding, grooming, or health_checkup entry exists for dog/adult.
- **PlannerAgent ignores `Pet.health_issues`.** The planner drafts Tasks purely from the retrieved category, with no adjustment for a pet's specific health conditions (e.g. a "sensitive stomach" note has no effect on the feeding Task it would generate). This is a meaningful gap for a real pet-care tool.
- **Validator's repair strategy is naive.** When two tasks conflict, only the later-starting task is shifted forward by a fixed 30 minutes; the earlier task is never moved. This resolved our test case but is not guaranteed to resolve every possible conflict within `max_attempts`.

## Potential Misuse and Mitigations

This system gives care *scheduling* advice, not medical advice, but a user could mistake the retrieved knowledge-base content for authoritative veterinary guidance. The `content` field is deliberately general and was manually spot-checked against real veterinary sources (e.g. AAHA guidance on senior dog checkup frequency) before being committed, rather than trusting AI-generated text as fact. If this were extended into a real product, it would need an explicit disclaimer that it does not replace professional veterinary advice, especially since the Retriever can silently misclassify a pet's species and therefore surface guidance for the wrong animal.

## What Surprised Me During Testing

I expected the Validator's replan loop to resolve a conflict in a single attempt. Instead, testing showed it took three attempts: the first shift (+30 min) moved the new task from 13:00 to 13:30, which still overlapped the existing 13:00-13:45 appointment; only the second shift, to 14:00, actually cleared it. This was a useful reminder that a "simple" fixed-increment repair doesn't always converge quickly, and it's the kind of behavior you only catch by actually running the system rather than assuming the logic is right.

## AI Collaboration

**Helpful suggestion:** When building the Validator, Claude Code's design reused the existing, already-tested `Scheduler.detect_conflicts()` method rather than reimplementing overlap detection from scratch. This kept the new code smaller, avoided duplicating logic, and meant the Validator was trustworthy immediately since it was built on a method that already had passing tests.

**Flawed suggestion:** Early in planning the `CareKnowledgeBase`, Claude (chat) initially recommended plain markdown/text files for the knowledge base, reasoning it would be more consistent with prior RAG work. I pushed back and pointed out that JSON with structured fields (`pet_type`, `life_stage`, `category`) would let the Retriever filter by metadata before doing any matching, which was a better fit for this system's actual retrieval need. Claude agreed the JSON approach was better on reflection. This was a case where the AI's first suggestion optimized for "consistency with what you did before" rather than "what actually fits this specific problem," and catching that required me to think about what the Retriever would actually need to do, not just accept the suggestion.