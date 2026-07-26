import json
import re
from pydantic import BaseModel, Field
from typing import List, Optional
from agents.agents import get_boto_session
import os
import boto3
from strands import Agent
from strands.models import BedrockModel
from agents.tools_controller import (
    read_reflects,
    write_reflect,
    read_entries
)
from src.backend.db_config import run_neo4j_query, run_psql_query
from src.backend.config import NEO4J_AUTH, NEO4J_PASSWORD, NEO4J_URI
from neo4j import GraphDatabase


# ---------------------------------------------------------------------------
# Shared criteria, kept in one place so generator and validator are judging
# (and writing) against the exact same bar. Do not let these drift apart.
# ---------------------------------------------------------------------------
SHARED_CRITERIA = """
PREFERRED QUESTION CATEGORIES — draw from these, and aim for a mix rather than
repeating one angle across all the questions:
  - EXPECTATIONS — what were you hoping would happen?
  - INTERPRETATIONS — what did that mean to you?
  - ASSUMPTIONS — what made you come to that conclusion?
  - DECISIONS — what led you to do that?
  - UNANSWERED QUESTIONS — what still feels unresolved?
  - EMOTIONALLY SIGNIFICANT MOMENTS — the beat in the entry that seems to carry
    the most emotional weight, even if the entry doesn't dwell on it.

QUALITY CRITERIA — every question must satisfy ALL of these:
  - ONE SENTENCE, NO SETUP. Never restate what happened, never say "you
    mentioned/wrote/said," never summarize the entry before asking. Cut straight
    to the question.
    Good: "What went through your mind when Liam left the room?"
    Bad: "Reflecting on your entry, when Liam left the room, what thoughts or
    feelings came up for you in that moment?"
    Bad: "You wrote that you felt anxious about the meeting — what was behind
    that feeling?"
  - GOES BEYOND THE ENTRY. Never ask something the entry already answers. If the
    entry says "I was frustrated when Liam left," don't ask "how did you feel
    when Liam left" — that's already stated. Ask toward what ISN'T in the entry:
    what came after that feeling, what's underneath it, what they'd want going
    forward. Test: if re-reading the entry alone answers the question, it fails.
  - TAME: open, gentle, no presumed conclusion about the user's feelings,
    motives, or relationships.
    Bad: "Why do you keep letting her treat you this way?"
    Good: "What would you want to say to her, if it couldn't go wrong?"
  - POSITIVELY ORIENTED, never framed around fear, failure, or disappointment.
    Never ask the user to imagine letting someone down, failing, or
    disappointing someone — even gently. Reframe toward the positive mirror of
    the same thought instead. This applies even when the entry itself is about
    worry or self-doubt — the question should still point forward.
    Bad: "What would disappointing the people who believed in you look like?"
    Good: "What would making the people who believe in you proud look like?"
  - SPECIFIC to what's actually in the entry — not a generic prompt that could
    apply to any entry (e.g. "what are you grateful for" unless gratitude is
    actually present).
  - FREE OF DIAGNOSIS. Never assert why the user feels something — invite them
    to name it themselves.
    Bad: "It sounds like you were anxious because..."
    Good: "What was going on for you when..."

HARD CONSTRAINT — every question is shown to the user verbatim. Never include an
entry_id, entity_id, date, a quote/near-quote of the entry's exact wording, or any
system term (entity, stim, sentiment, pattern, entry). A question should make
sense to someone who has never heard of any of this system's internal concepts —
just a person who journaled today.
"""


# ---------------------------------------------------------------------------
# GENERATOR — drafts questions. Never writes to the DB, never self-approves.
# ---------------------------------------------------------------------------
GENERATOR_SYSTEM_PROMPT = f"""
You are the generator half of a two-agent reflection-question system for a personal
journaling app. You draft candidate reflection questions for a single journal entry.
You never decide whether your own questions are good enough — a separate validator
agent does that, and may send your drafts back with specific feedback. Your job is
only to write, and to genuinely revise when told something is wrong.

You are always given an `entry_id` and `user_id`. Pass user_id to every tool call —
never operate on any other user's data.

{SHARED_CRITERIA}

WORKFLOW:

1. Call `read_entries` scoped to `entry_id` + `user_id`. Read the entry text itself
   carefully, not just its entities.

2. If this is a revision round, you will also be given the validator's feedback:
   which of your previous questions were rejected, and why, plus which were
   approved. Keep the approved ones exactly as they were — do not rewrite
   questions that already passed. For each rejected question, write a genuinely
   different replacement that fixes the specific problem named in the feedback.
   Don't make a cosmetic wording change that leaves the same underlying issue —
   actually change the angle or category of the question if that's what's needed.

3. Draft questions per the criteria above until you have 3-5 total (counting any
   already-approved ones from a prior round). Aim for a mix across the preferred
   categories, not 3-5 questions all doing the same thing. If the entry genuinely
   doesn't support 3, fewer (including zero) is correct — say so rather than
   padding with weak questions.

4. Output ONLY valid JSON, nothing else — no prose, no markdown code fences,
   no commentary before or after:

{{"questions": ["question one", "question two", "question three"]}}

Never fabricate entry content. If you cannot ground a question in the entry, don't
write it.
"""


# ---------------------------------------------------------------------------
# VALIDATOR — judges drafts against the same criteria, checks for conflicts
# with existing saved reflections, and is the only one who writes to the DB.
# ---------------------------------------------------------------------------
VALIDATOR_SYSTEM_PROMPT = f"""
You are the validator half of a two-agent reflection-question system for a personal
journaling app. A generator agent has drafted candidate reflection questions for a
single journal entry. Your job is ONLY to judge each one against a strict bar and
reject anything that doesn't clear it with a specific reason. You do not save
anything — a separate deterministic process handles persistence based on your
verdict. You have no write access in this run.

You are always given an `entry_id`, `user_id`, and the generator's draft questions.
Pass user_id to every tool call — never operate on any other user's data.

{SHARED_CRITERIA}

WORKFLOW:

1. Call `read_entries` scoped to `entry_id` + `user_id` to read the actual entry
   text. You need this to judge whether each question genuinely goes beyond the
   entry, is specific to it, and doesn't quote it — you cannot judge this from the
   questions alone.

2. Call `read_reflects` for this `entry_id` + `user_id` to see existing saved
   reflection questions. Any draft that duplicates or closely overlaps an existing
   question in meaning is a REJECT for that reason, regardless of how well it
   otherwise meets the criteria.

3. Evaluate every draft question individually against every criterion above (the
   preferred categories, the quality criteria, and the hard constraint). Be a
   genuinely hard grader — the generator's job is to write, yours is to catch
   what it missed. Common failure modes to check specifically for:
     - a lead-in clause restating the entry ("you wrote...", "reflecting on...")
     - a question the entry itself already answers
     - negative framing around failure, fear, or disappointing someone
     - a quote, near-quote, date, entry_id, or system term
     - vague/generic phrasing not grounded in this specific entry
   Also judge the SET as a whole: if all surviving questions cluster in one
   category (e.g. every one is "unanswered questions"), flag that the generator
   should diversify, even if no single question is individually broken.

4. For every REJECTED question, write a specific, actionable reason (name the
   exact criterion violated, not "this needs work"). For every APPROVED question,
   leave it untouched — do not rewrite the generator's wording yourself.

5. Output ONLY valid JSON, nothing else — no prose, no markdown code fences, no
   commentary before or after it:

{{"status": "approved" | "needs_revision",
  "approved_questions": ["question", ...],
  "rejected": [{{"question": "...", "reason": "..."}}],
  "diversity_note": "optional note if the surviving set is too one-note, else null"}}

   Use "approved" if every draft passes (or the only issues are rejections you've
   listed and the approved set is still enough — you decide "enough" using the
   same judgment as the generator: 0-5 grounded, non-redundant questions is fine).
   Use "needs_revision" if you want the generator to take another pass at the
   rejected ones.

   You do NOT save anything yourself — you only judge and report. A separate,
   deterministic process outside this conversation handles persistence based on
   your `approved_questions` list. Do not attempt to call any write/save tool;
   your only output is the JSON above.

Never fabricate entry content, existing reflections, or a reason you didn't actually
find. If you reject something, the reason must be real and specific.
"""


def _extract_text(result) -> str:
    """
    Strands agent call results can vary in shape depending on version/config.
    Try the common attribute shapes, fall back to str().
    """
    for attr in ("message", "content", "text", "output"):
        if hasattr(result, attr):
            val = getattr(result, attr)
            if isinstance(val, str):
                return val
    return str(result)


def _parse_json_block(raw: str) -> dict:
    """
    Agents are told to output pure JSON, but thinking-style models (e.g. Kimi K2
    Thinking) can leak reasoning-trace text around the actual answer, such as
    "...ready to output the JSON. </think> {...}". Handle that defensively:
    strip any <think>...</think> content (even if the opening tag got cut off
    by the caller), strip markdown fences, then fall back to extracting the
    outermost {...} block from wherever it sits in the string.
    """
    cleaned = raw.strip()

    # Drop everything up to and including a stray closing </think> tag, in case
    # the opening <think> wasn't captured (as seen with Kimi K2 Thinking output).
    if "</think>" in cleaned:
        cleaned = cleaned.split("</think>")[-1].strip()

    # Also handle well-formed <think>...</think> blocks anywhere in the string.
    cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL).strip()

    # Strip markdown code fences if the model wrapped the JSON despite instructions.
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Last resort: pull out the outermost {...} block from wherever it is,
    # in case there's still leading/trailing prose around the JSON.
    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    if not match:
        raise ValueError(
            f"Could not find a JSON object in model output:\n{raw!r}"
        )
    return json.loads(match.group(0))


class RejectedQuestion(BaseModel):
    question: str
    reason: str


class ValidationResult(BaseModel):
    status: str
    approved_questions: List[str] = Field(default_factory=list)
    rejected: List[RejectedQuestion] = Field(default_factory=list)
    diversity_note: Optional[str] = None


def build_generator_agent() -> Agent:
    session = get_boto_session()
    model = BedrockModel(
        model_id="moonshot.kimi-k2-thinking",
        boto_session=session,
    )
    return Agent(
        model=model,
        system_prompt=GENERATOR_SYSTEM_PROMPT,
        tools=[read_entries],
    )


def build_validator_agent() -> Agent:
    session = get_boto_session()
    model = BedrockModel(
        model_id="moonshot.kimi-k2-thinking",
        boto_session=session,
    )
    return Agent(
        model=model,
        system_prompt=VALIDATOR_SYSTEM_PROMPT,
        tools=[read_entries, read_reflects],  # no write_reflect — judge only
    )


def _ensure_written(entry_id, user_id, approved_questions: List[str]) -> List[str]:
    """
    The sole writer for this pipeline. The validator agent has no write_reflect
    tool access at all — it only judges and reports approved_questions. This
    function is the only thing that ever calls write_reflect, deterministically,
    based on the validator's verdict. This avoids any possibility of a double
    write (agent writes + this also writes) — there is exactly one writer.

    Also dedupes against already-existing saved reflections for this entry
    before writing, in case this pipeline is re-run over the same entry.

    NOTE: adjust the keyword args below if your actual read_reflects/
    write_reflect signatures differ from (entry_id, user_id, question).
    """
    if not approved_questions:
        return []

    try:
        existing = read_reflects(entry_id=entry_id, user_id=user_id)
    except Exception:
        existing = []

    existing_texts = set()
    if isinstance(existing, list):
        for item in existing:
            if isinstance(item, dict):
                existing_texts.add(item.get("question", "").strip())
            elif isinstance(item, str):
                existing_texts.add(item.strip())

    confirmed = []
    for question in approved_questions:
        if question.strip() in existing_texts:
            confirmed.append(question)
            continue
        try:
            write_reflect(entry_id=entry_id, user_id=user_id, question=question)
            confirmed.append(question)
        except Exception as e:
            print(f"WARNING: failed to write_reflect for question {question!r}: {e}")

    return confirmed


def run_reflection_pipeline(entry_id: str, user_id: int, max_rounds: int = 3):
    """
    Runs the generator -> validator loop for a single entry. The validator is
    the only agent with write access; nothing is saved until a round is fully
    approved, or max_rounds is hit (at which point we take whatever the last
    round approved, if anything, and ask the validator to persist just that).
    """
    generator = build_generator_agent()
    validator = build_validator_agent()

    feedback_context = ""
    last_validation: Optional[ValidationResult] = None

    for round_num in range(1, max_rounds + 1):
        gen_prompt = (
            f"entry_id: {entry_id}\n"
            f"user_id: {user_id}\n"
            f"{feedback_context}\n"
            "Draft your reflection questions per your workflow. Output only JSON."
        )
        gen_raw = _extract_text(generator(gen_prompt))
        draft = _parse_json_block(gen_raw)
        draft_questions = draft.get("questions", [])

        if not draft_questions:
            return {"status": "no_questions", "rounds": round_num, "written": []}

        val_prompt = (
            f"entry_id: {entry_id}\n"
            f"user_id: {user_id}\n"
            f"draft_questions: {json.dumps(draft_questions)}\n\n"
            "Validate these per your workflow. If approved, write them. "
            "Output only JSON."
        )
        val_raw = _extract_text(validator(val_prompt))
        val_json = _parse_json_block(val_raw)
        last_validation = ValidationResult(**val_json)

        if last_validation.status == "approved":
            written = _ensure_written(
                entry_id, user_id, last_validation.approved_questions
            )
            return {
                "status": "approved",
                "rounds": round_num,
                "written": written,
            }

        # needs_revision: hand rejected feedback + already-approved questions
        # back to the generator for another pass.
        feedback_context = (
            "\nPREVIOUS ROUND FEEDBACK:\n"
            f"Already approved (keep these unchanged): "
            f"{json.dumps(last_validation.approved_questions)}\n"
            f"Rejected (fix these specifically): "
            f"{json.dumps([r.model_dump() for r in last_validation.rejected])}\n"
        )

    # Max rounds hit without full approval — persist whatever the last round
    # approved (could be zero), rather than saving nothing or looping forever.
    if last_validation and last_validation.approved_questions:
        written = _ensure_written(
            entry_id, user_id, last_validation.approved_questions
        )
        return {
            "status": "approved_after_max_rounds",
            "rounds": max_rounds,
            "written": written,
        }

    return {"status": "no_questions", "rounds": max_rounds, "written": []}


if __name__ == "__main__":
    entry_id = 53
    user_id = 6

    if not entry_id or not user_id:
        raise ValueError("Set ENTRY_ID and USER_ID to run this pipeline.")

    result = run_reflection_pipeline(entry_id, int(user_id))
    print(json.dumps(result, indent=2))