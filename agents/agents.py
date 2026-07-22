"""
Strands Agents
"""
import os
import json
import boto3
from strands import Agent
from strands.models import BedrockModel
from agents.tools_controller import (
    grab_patterns,
    read_entries,
    keyword_search,
    create_pattern,
    read_patterns,
    add_entity_to_pattern,
    add_entry_to_pattern,
    keyword_search_patterns,
    get_entity_stims,
    read_entry_stim_count
)


def get_boto_session() -> boto3.Session:
    """
    Reads AWS_PROFILE from the environment.
    Set it per-project in your .env or shell before running:
        export AWS_PROFILE=my-dev-profile
    Falls back to the default profile if not set.
    """
    profile = os.environ.get("AWS_PROFILE", None)
    region  = os.environ.get("AWS_REGION", "us-east-1")
    return boto3.Session(profile_name=profile, region_name=region)


PATTERN_DETECTION_SYSTEM_PROMPT = """
You are a pattern-detection agent for a personal journaling app. Your job is to find
recurring emotional/behavioral patterns in a user's journal entries, grounded in real
sentiment data, and record them in the pattern graph so the user can see them surface
over time.

You are operating on behalf of user_id=6. Always pass this user_id to every
tool call — never operate on any other user's data.

Follow this workflow every run:

1. IDENTIFY REPEATING ENTITIES
   Call `read_entry_stim_count` scoped to roughly the last 2 weeks (`fromDate`/
   `toDate`), with a `limit` generous enough to see meaningful candidates (e.g. 10-20).
   This directly returns entities ranked by occurrence count — no need to manually
   count anything. Treat entities with only 1-2 occurrences as noise; focus on the
   ones that clearly recur.

2. PULL GROUNDED EMOTIONAL DATA
   For each of the top repeating entities from step 1, call `get_entity_stims` using
   its `id` to fetch the grounded adjective/sentence sentiment data attached to that
   entity. This is your source of truth for what emotions are actually associated
   with the entity — trust this over any impression you form just from reading entry
   text. Discard entities whose stims are overwhelmingly neutral or lack any clear
   emotional valence (e.g. sentiment scores clustered near zero, or adjectives like
   "fine," "okay," "normal" with no strong sentiment attached). You're looking for
   entities with real emotional signal — positive or negative — not background noise.
   Make sure to evaluate the sentence as well before making a decision

3. SEARCH RECENT ENTRIES FOR THESE ENTITIES
   For each entity that survived the neutral-filter in step 2, call `read_entries`
   filtered by that `entity` and the same ~2-week window, to gather the specific
   entries that mention it. You need the actual `entry_id` and creation `date` of
   each relevant entry — you'll need these later to link entries to a pattern.

4. IDENTIFY THE PATTERN
   Look across the entries and their attached sentiment for a recurring theme —
   this could be a recurring emotional reaction to a specific entity, a repeated
   situation, or a behavioral trend that shows up across multiple entries. Only
   proceed if you see genuine repetition (the same entity/emotion pairing showing
   up across multiple distinct entries), not a one-time event. Draft a clear,
   specific `pattern_title` and a `pattern_summary` describing what you observed
   and why it's meaningful, referencing the grounded sentiment data as evidence.

5. CHECK FOR AN EXISTING PATTERN
   Before creating anything, check whether this pattern already exists:
   - Call `keyword_search_patterns` with keywords drawn from your draft title/theme.
   - Call `read_patterns` filtered by `entity` for each entity involved, to see if
     any existing pattern already links to them.
   Compare titles, summaries, and linked entities/entries carefully. A close
   conceptual match (even with different wording) counts as "existing" — don't
   create a near-duplicate pattern just because the title differs.

6. CREATE OR UPDATE
   - If no matching pattern exists: call `create_pattern` with the pattern_title,
     pattern_summary, the list of `entries` (each with entry_id, date, and a
     rationale explaining why that specific entry evidences the pattern), and the
     list of `entities` involved.
   - If a matching pattern already exists: use `add_entry_to_pattern` for each new
     entry (with entry_id, date, and rationale) and `add_entity_to_pattern` for any
     entity not already linked to it. You must pass the existing `pattern_name`
     exactly as stored, and `pattern_summary` on every call to these two tools — if
     you're refining the summary based on new evidence, update it; otherwise pass
     the existing summary through unchanged.

Never fabricate entry_ids, dates, or sentiment data — only use what tools return to
you. If a step's tools return nothing useful (no repeating entities, no non-neutral
stims, no clear pattern), stop and report that no pattern was found this run rather
than forcing one into existence.
"""


def build_pattern_agent(user_id: int) -> Agent:
    session = get_boto_session()
    model = BedrockModel(
        model_id="deepseek.v3.2",
        boto_session=session,
    )
    return Agent(
        model=model,
        system_prompt=PATTERN_DETECTION_SYSTEM_PROMPT.format(user_id=user_id),
        tools=[
            grab_patterns,
            read_entries,
            keyword_search,
            create_pattern,
            read_patterns,
            add_entity_to_pattern,
            add_entry_to_pattern,
            keyword_search_patterns,
            get_entity_stims,
            read_entry_stim_count,
        ],
    )


# ---------------------------------------------------------------------------
# Debug console chat
# ---------------------------------------------------------------------------

class _C:
    """ANSI color codes for pretty console output."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    MAGENTA = "\033[35m"
    YELLOW = "\033[33m"
    GRAY = "\033[90m"


def _print_banner(user_id: int) -> None:
    print(f"{_C.BOLD}{_C.CYAN}{'=' * 60}{_C.RESET}")
    print(f"{_C.BOLD}{_C.CYAN}  Pattern Detection Agent — Debug Console{_C.RESET}")
    print(f"{_C.DIM}  user_id={user_id}{_C.RESET}")
    print(f"{_C.DIM}  Type 'exit' or 'quit' to stop, Ctrl+C also works.{_C.RESET}")
    print(f"{_C.BOLD}{_C.CYAN}{'=' * 60}{_C.RESET}\n")


def _print_user(message: str) -> None:
    print(f"{_C.BOLD}{_C.YELLOW}You:{_C.RESET} {message}\n")


def _print_agent(message: str) -> None:
    print(f"{_C.BOLD}{_C.MAGENTA}Agent:{_C.RESET} {message}\n")


def run_debug_console(user_id: int = 4) -> None:
    """
    Simple REPL loop for manually testing the pattern-detection agent from the
    terminal. Prints a pretty divider between turns so tool-call chatter is
    easy to visually separate from actual agent replies.
    """
    _print_banner(user_id)
    agent = build_pattern_agent(user_id)

    while True:
        try:
            user_input = input(f"{_C.BOLD}{_C.YELLOW}> {_C.RESET}").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{_C.DIM}Session ended.{_C.RESET}")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            print(f"{_C.DIM}Session ended.{_C.RESET}")
            break

        _print_user(user_input)
        print(f"{_C.GRAY}{_C.DIM}--- agent working (tool calls may print below) ---{_C.RESET}")

        try:
            result = agent(user_input)
        except Exception as e:
            print(f"{_C.BOLD}\033[31mError:{_C.RESET} {e}\n")
            continue

        print(f"{_C.GRAY}{_C.DIM}--- done ---{_C.RESET}\n")
        _print_agent(str(result))


if __name__ == "__main__":
    run_debug_console(user_id=4)