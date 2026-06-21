"""
Strands Agent — Emotion Pair Filter
Sits between spaCy extraction and the sentiment/emotion models.
Receives raw (noun, adjective) pairs and returns only significant ones.
"""

import os
import json
import boto3
from typing import Optional
from pydantic import BaseModel, Field
from strands import Agent
from strands.models import BedrockModel
from src.backend.classes.stimulus import Stimulus


# ---------------------------------------------------------------------------
# 1. AWS session — profile driven by env var, never system-wide
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 2. Pydantic models — structured output contract
# ---------------------------------------------------------------------------
class EmotionPair(BaseModel):
    entity: str         = Field(..., description="The significant person or activity")
    adjective: str      = Field(..., description="The adjective describing it")
    sentence: str       = Field("", description="The original full sentence")
    sentence_sentiment: str    = Field("", description="Sentence sentiment")
    adjective_sentiment: str    = Field("", description="Adjective Sentiment")
    emotion1: str        = Field("", description="Top 3 emotions sensed")
    emotion2: str        = Field("", description="Top 3 emotions sensed")
    emotion3: str        = Field("", description="Top 3 emotions sensed")


class FilterResult(BaseModel):
    significant_pairs: list[EmotionPair] = Field(
        default_factory=list,
        description="Only the emotionally meaningful entity-adjective pairs"
    )
    dropped: list[str] = Field(
        default_factory=list,
        description="Pairs that were removed and a short reason why"
    )

def normalize_self_references(result: FilterResult) -> FilterResult:
    SELF_REFS = {"i", "me", "myself", "my", "mine"}

    normalized = [
        EmotionPair(
            entity="self" if pair.entity.lower() in SELF_REFS else pair.entity,
            adjective=pair.adjective,
            sentence=pair.sentence,
            sentence_sentiment=pair.sentence_sentiment,
            adjective_sentiment=pair.adjective_sentiment,
            emotion1=pair.emotion1,
            emotion2=pair.emotion2,
            emotion3=pair.emotion3
        )
        for pair in result.significant_pairs
    ]

    return FilterResult(significant_pairs=normalized, dropped=result.dropped)

# ---------------------------------------------------------------------------
# 3. Build the agent
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """
You are a linguistic filter for an emotion analysis pipeline.

You will receive a list of (entity, adjective) pairs extracted by a spaCy parser.
Your job is to remove noise and keep only pairs that are emotionally meaningful.

Rules:
- KEEP pairs where the entity is a named person, a specific place, or a concrete activity
- KEEP pairs where the adjective meaningfully describes emotional tone (e.g. energetic, chaotic, warm)
- KEEP pairs that describe a dimensionality of time. Like "Today" or "Tomorrow"
- KEEP pairs that refer to self. "I" or  "me" included.
- DROP pairs where the entity is a generic/filler noun: thing, way, fact, time, friend, coworker, etc.
- DROP generic nouns like "student" or "teacher" that isn't referring to a specific person.
- DROP pairs that are redundant duplicates of a kept pair
- DROP pairs where the adjective is trivial or non-emotional (e.g. "new", "little", "same")

Always respond with valid JSON matching this schema exactly:
{
  "significant_pairs": [
    {"entity": "<name or activity>", "adjective": "<adjective>"}
  ],
  "dropped": ["<entity>:<adjective> — <reason>", ...]
}
No prose. No markdown. JSON only.
"""


def build_agent() -> Agent:
    session = get_boto_session()

    model = BedrockModel(
        model_id="qwen.qwen3-32b-v1:0",   # swap to claude-3-haiku etc. if preferred
        boto_session=session,
        temperature=0.0,                        # deterministic for a filter task
    )

    return Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
    )


# ---------------------------------------------------------------------------
# 4. Public interface — call this from your main pipeline
# ---------------------------------------------------------------------------

def filter_pairs(
    raw_pairs: list[Stimulus],
    agent: Optional[Agent] = None,
) -> FilterResult:
    if not raw_pairs:
        return FilterResult()

    if agent is None:
        agent = build_agent()

    # Build a lookup so we can re-attach full stimulus data after LLM filtering
    stimulus_lookup: dict[tuple[str, str], Stimulus] = {
        (s.noun.token.lower(), s.adjective.lower()): s
        for s in raw_pairs
    }

    payload = json.dumps([{"entity": s.noun.getToken(), "adjective": s.adjective} for s in raw_pairs])
    prompt  = f"Filter these pairs:\n{payload}"

    response = agent(prompt)

    raw_text = str(response).strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.split("```")[1]
        if raw_text.startswith("json"):
            raw_text = raw_text[4:]

    parsed = json.loads(raw_text)

    # Re-hydrate each kept pair with full stimulus data
    enriched_pairs = []
    for pair in parsed.get("significant_pairs", []):
        key = (pair["entity"].lower(), pair["adjective"].lower())
        stimulus = stimulus_lookup.get(key)

        enriched_pairs.append(EmotionPair(
            entity=pair["entity"],
            adjective=pair["adjective"],
            sentence=stimulus.sentence if stimulus else "",
            sentence_sentiment=stimulus.sentiment[0][0] if stimulus else "",
            adjective_sentiment=stimulus.sentiment[1][0] if stimulus else "",
            emotion1=stimulus.emotion[0][0] if stimulus else "",
            emotion2=stimulus.emotion[1][0] if stimulus else "",
            emotion3=stimulus.emotion[2][0] if stimulus else "",
        ))

    result = FilterResult(significant_pairs=enriched_pairs, dropped=parsed.get("dropped", []))
    return normalize_self_references(result)