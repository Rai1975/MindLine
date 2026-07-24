import json

from pydantic import BaseModel, Field
from typing import List

from agents.agents import get_boto_session

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
    read_entry_stim_count,
    search_patterns_by_entity
)

from src.backend.db_config import run_neo4j_query, run_psql_query
from src.backend.config import NEO4J_AUTH, NEO4J_PASSWORD, NEO4J_URI
from neo4j import GraphDatabase


class EntityPatternInsights(BaseModel):
    entity_name: str = Field(description="The entity being analyzed")
    bullets: List[str] = Field(
        description=(
            "Exactly 3 very concise (10-15 words) bullet points summarizing the pattern(s) this "
            "entity is linked to and how the entity specifically shows up "
            "across them, grounded in the entry rationales provided. If "
            "fewer than 3 patterns/entries exist, use remaining bullets to "
            "note that explicitly rather than padding with filler."
        ),
        min_length=3,
        max_length=3,
    )


ENTITY_INSIGHT_SYSTEM_PROMPT = """
You help people understand themselves better by reflecting back the patterns
you notice in their journal. You'll be given, in the user message, everything
already gathered about one person or thing (an "entity") they've written
about — including which patterns it's connected to and specific notes on why
each journal entry was tied to that pattern.

You are working on behalf of user_id={user_id}.

The data you receive is a list of records, one per pattern this entity shows
up in, shaped like:
{{
    "entity_id": ...,
    "entity_name": ...,
    "pattern_title": ...,
    "pattern_summary": ...,
    "entries": [
        {{ "entry_id": ..., "date": ..., "rationale": ... }},
        ...
    ]
}}

Your job is to write exactly 3 short bullets (10-15 words each) that help the
person see, at a glance, what's going on with this entity in their life. Write
directly to them, like a thoughtful friend pointing something out — plain
language, no clinical or technical terms, nothing that sounds like a report.

If there's no data, or the list is empty, just say so gently — something like
"nothing recurring here yet" — rather than inventing a pattern.

If there is data, use the "rationale" notes on each entry as your main source
— that's where the real detail lives about how this entity actually shows up
day to day, not just the general pattern description. Look for what keeps
repeating across entries rather than restating any single note.

Your 3 bullets should cover:
1. The big picture — what pattern (or patterns) this entity is part of, in
   plain, everyday words.
2. The specific way this entity tends to show up — what actually keeps
   happening, based on the entry notes, told like an observation rather than
   a diagnosis.
3. A small, honest takeaway — something worth noticing or sitting with, not
   advice or a fix.

If there's only one pattern, don't force three separate patterns into the
bullets — instead, give one bullet to the theme, one to how this entity
specifically plays into it, and one to what stands out about it.

Never make up entries, dates, notes, or feelings that aren't in the data you
were given. Stick to what's actually there.
"""


def build_entity_insight_agent(user_id: int) -> Agent:
    session = get_boto_session()
    model = BedrockModel(
        model_id="deepseek.v3.2",
        boto_session=session,
    )
    return Agent(
        model=model,
        system_prompt=ENTITY_INSIGHT_SYSTEM_PROMPT.format(user_id=user_id),
        tools=[],
    )


def get_entity_pattern_insights(user_id: int, entity_name: str) -> EntityPatternInsights:
    """
    Fetch pattern data for an entity, then run the insight agent over the
    full payload (including entry rationales) to produce 3 structured bullets.
    """
    response = search_patterns_by_entity(user_id=user_id, entity_name=entity_name)

    if response.get("error"):
        # Still produce a valid, on-schema response rather than raising —
        # downstream callers expect an EntityPatternInsights either way.
        return EntityPatternInsights(
            entity_name=entity_name,
            bullets=[
                f"No pattern data could be retrieved for '{entity_name}'.",
                f"Reason: {response['error']}",
                "No insights available until this entity has recorded patterns.",
            ],
        )

    records = (response.get("data") or {}).get("records", [])
    payload = json.dumps(records)

    agent = build_entity_insight_agent(user_id)
    return agent.structured_output(
        EntityPatternInsights,
        f"entity_name: {entity_name}\n\ndata: {payload}"
    )

def write_entity_insights(user_id: int, entity_name: str, bullets: list) -> dict:
    """
    Directly writes up to 3 insight bullets onto an Entity node as
    insight_1/insight_2/insight_3 properties. Plain helper function (not a
    Flask route, not a @tool) — call this straight from other backend/agent
    code when you already have the bullets in hand and don't need to go
    through an HTTP round trip.

    Returns {"success": bool, "record": dict|None, "message": str}
    """
    if not entity_name or not bullets:
        return {"success": False, "record": None, "message": "Missing entity_name or bullets"}

    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        return {"success": False, "record": None, "message": "user_id must be an integer"}

    if not isinstance(bullets, list) or not all(isinstance(b, str) for b in bullets):
        return {"success": False, "record": None, "message": "bullets must be a list of strings"}

    # Cap at 3, but don't fail on fewer — every slot is still explicitly set
    # (with None where unused) so a stale insight_3 from a previous run
    # doesn't linger if this run only produced 2 bullets.
    bullets = bullets[:3]

    set_clauses = []
    params = {"user_id": user_id, "entity_name": entity_name}
    for idx in range(1, 4):
        key = f"insight_{idx}"
        set_clauses.append(f"e.{key} = ${key}")
        params[key] = bullets[idx - 1] if idx <= len(bullets) else None

    query = f'''
    MATCH (e:Entity {{user_id: $user_id, entity_name: $entity_name}})
    SET {", ".join(set_clauses)}
    RETURN {{
        entity_id: e.entity_id,
        entity_name: e.entity_name,
        insight_1: e.insight_1,
        insight_2: e.insight_2,
        insight_3: e.insight_3
    }} AS result
    '''

    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_AUTH, NEO4J_PASSWORD)) as driver:
        try:
            driver.verify_connectivity()
        except Exception as e:
            return {"success": False, "record": None, "message": f"Error: {e}"}
        try:
            records = driver.execute_query(query, **params)
            data = [record for record in records.records]
            if not data:
                return {
                    "success": False,
                    "record": None,
                    "message": f"No entity found for user_id={user_id} with entity_name='{entity_name}'"
                }
            return {"success": True, "record": data[0], "message": "Success"}
        except Exception as e:
            return {"success": False, "record": None, "message": f"Database transaction error: {e}"}

if __name__ == "__main__": 
    entity_name = "Dad"
    x = get_entity_pattern_insights(user_id=6, entity_name=entity_name)
    print(x)
    print(type(x.bullets))
    print(write_entity_insights(user_id=6, entity_name=entity_name, bullets=x.bullets))