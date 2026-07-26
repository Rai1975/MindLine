from agents.config import BACKEND_URL
from flask import jsonify, request
import requests as webRequest
from strands import tool
from typing import Optional


def call_api(url, method="GET", params=None, headers=None, json_body=None, timeout=10):
    """
    Perform a standard API call.

    Args:
        url (str): The endpoint URL.
        method (str): HTTP method - GET, POST, PUT, PATCH, DELETE. Defaults to GET.
        params (dict): Query string parameters (for GET, etc).
        headers (dict): Request headers, e.g. {"Authorization": "Bearer ..."}.
        json_body (dict): JSON payload for POST/PUT/PATCH requests.
        timeout (int): Request timeout in seconds.

    Returns:
        dict: {"status_code": int, "data": <parsed JSON or raw text>, "error": str|None}
    """
    try:
        response = webRequest.request(
            method=method.upper(),
            url=url,
            params=params,
            headers=headers,
            json=json_body,
            timeout=timeout
        )
        response.raise_for_status()

        try:
            data = response.json()
        except ValueError:
            data = response.text

        return {"status_code": response.status_code, "data": data, "error": None}

    except webRequest.exceptions.HTTPError as e:
        return {"status_code": response.status_code, "data": None, "error": f"HTTP error: {e}"}
    except webRequest.exceptions.ConnectionError as e:
        return {"status_code": None, "data": None, "error": f"Connection error: {e}"}
    except webRequest.exceptions.Timeout as e:
        return {"status_code": None, "data": None, "error": f"Timeout: {e}"}
    except webRequest.exceptions.RequestException as e:
        return {"status_code": None, "data": None, "error": f"Request failed: {e}"}


@tool
def grab_patterns(
    user_id: int,
    pattern_name: str = '',
    entry_id: Optional[int] = None,
    entity: str = '',
    page: int = 1,
    page_size: int = 20
) -> dict:
    """
    Fetch patterns belonging to a user, optionally filtered by pattern name,
    a linked entry id, or a linked entity, with pagination support.

    Args:
        user_id (int): The unique identifier of the user whose patterns should be retrieved.
        pattern_name (str, optional): Filter to a specific pattern by title.
        entry_id (int, optional): Filter to patterns linked to this entry id.
        entity (str, optional): Filter to patterns linked to this entity name.
        page (int): Page number for pagination. Defaults to 1.
        page_size (int): Number of patterns per page. Defaults to 20.

    Returns:
        dict: API response containing the user's patterns, or an error message.
    """
    try:
        user_id = int(user_id)
        pattern_name = str(pattern_name)
        entry_id = int(entry_id) if entry_id is not None else ''
        entity = str(entity)
        page = int(page)
        page_size = int(page_size)
    except (ValueError, TypeError):
        return {"error": "user_id, entry_id, page, and page_size must be integers"}

    return call_api(
        method="GET",
        url=f"{BACKEND_URL}/api/patterns/find_patterns",
        params={
            "user_id": user_id,
            "pattern_name": pattern_name,
            "entry_id": entry_id,
            "entity": entity,
            "page": page,
            "page_size": page_size
        }
    )

# Entry-level tools

# Definitely need to clean up outputs here
@tool
def read_entries(
    user_id: int,
    entry_id: Optional[int] = None,
    fromDate: str = '',
    toDate: str = '',
    entity: str = '',
    emotion: str = '',
    page: int = 1,
    page_size: int = 10
) -> dict:
    """
    Read journal entries for a user, optionally filtered by entry id, date range,
    entity, or emotion, with pagination support.

    Args:
        user_id (int): The unique identifier of the user whose entries should be read.
        entry_id (int, optional): A specific entry id to fetch. Omit to fetch multiple entries.
        fromDate (str, optional): Start of the date range filter, e.g. "2026-07-01".
        toDate (str, optional): End of the date range filter, e.g. "2026-07-21".
        entity (str, optional): Filter entries mentioning this entity name.
        emotion (str, optional): Filter entries tagged with this emotion.
        page (int): Page number for pagination. Defaults to 1.
        page_size (int): Number of entries per page. Defaults to 10.

    Returns:
        dict: API response containing matching entries, or an error message.
    """
    try:
        user_id = int(user_id)
        entry_id = int(entry_id) if entry_id is not None else ''
        fromDate = str(fromDate)
        toDate = str(toDate)
        entity = str(entity)
        emotion = str(emotion)
        page = int(page)
        page_size = int(page_size)
    except (ValueError, TypeError):
        return {"error": "user_id, entry_id, page, and page_size must be integers"}

    return call_api(
        method="GET",
        url=f"{BACKEND_URL}/api/entries/read",
        params={
            "user_id": user_id,
            "entry_id": entry_id,
            "from_date": fromDate,
            "to_date": toDate,
            "entity": entity,
            "emotion": emotion,
            "page": page,
            "page_size": page_size

        }
    )


@tool
def keyword_search(
    user_id: int,
    keyword: str
) -> dict:
    """
    Search a user's journal entries for a specific keyword.

    Args:
        user_id (int): The unique identifier of the user whose entries should be searched.
        keyword (str): The keyword or phrase to search for within entries.

    Returns:
        dict: API response containing matching entries, or an error message.
    """
    try:
        user_id = int(user_id)
        keyword = str(keyword)
    except (ValueError, TypeError):
        return {"error": "user_id must be an integer and keyword must be a string"}

    return call_api(
        method='POST',
        url=f'{BACKEND_URL}/api/entries/keywordSearch',
        json_body={
            "user_id": user_id,
            "keyword": keyword
        },
        timeout=999
    )


# Pattern level calls
@tool
def create_pattern(
    user_id: int,
    pattern_title: str,
    pattern_summary: str,
    entries: list,
    entities: list
) -> dict:
    """
    Create a new pattern, or update an existing one with the same title, linking it
    to the journal entries that evidence it and the entities involved in it.

    Args:
        user_id (int): The unique identifier of the user who owns this pattern.
        pattern_title (str): The title of the pattern. Used as the unique key alongside
            user_id — calling this again with the same title updates the existing pattern
            rather than creating a duplicate.
        pattern_summary (str): A description of the pattern, overwritten on every call.
        entries (list): A list of entries evidencing this pattern. Each entry must be a
            dict with the shape:
            {
                "entry_id": int,       # the id of the journal entry
                "date": str,           # the creation date of the entry, e.g. "2026-07-20"
                "rationale": str       # why this specific entry relates to the pattern
            }
        entities (list): A list of entities (people/things) involved in this pattern.
            Each entity must be a dict with the shape:
            {
                "entity_id": str,      # the unique identifier of the entity
                "entity_name": str     # the display name of the entity
            }
            Entities are connected directly to the pattern (not to individual entries),
            since an entity's relationship to a pattern is a recurring, overall
            association rather than tied to a single entry.

    Returns:
        dict: API response containing the created/updated pattern, or an error message.
    """
    try:
        user_id = int(user_id)
        pattern_title = str(pattern_title)
        pattern_summary = str(pattern_summary)

        cast_entries = []
        for entry in entries:
            cast_entries.append({
                "entry_id": int(entry["entry_id"]),
                "date": str(entry["date"]),
                "rationale": str(entry["rationale"])
            })

        cast_entities = []
        for entity in entities:
            cast_entities.append({
                "entity_id": str(entity["entity_id"]),
                "entity_name": str(entity["entity_name"])
            })
    except (ValueError, TypeError, KeyError) as e:
        return {"error": f"Invalid entries/entities format: {e}"}

    return call_api(
        method='POST',
        url=f'{BACKEND_URL}/api/patterns/create_pattern',
        json_body={
            "user_id": user_id,
            "pattern_title": pattern_title,
            "pattern_summary": pattern_summary,
            "entries": cast_entries,
            "entities": cast_entities
        },
        timeout=30
    )


@tool
def read_patterns(
    user_id: int,
    pattern_name: str = '',
    entry_id: Optional[int] = None,
    entity: str = '',
    page: int = 1,
    page_size: int = 20
) -> dict:
    """
    Read a user's patterns, optionally filtered by pattern name, a linked entry id,
    or a linked entity, with pagination support.

    Args:
        user_id (int): The unique identifier of the user whose patterns should be read.
        pattern_name (str, optional): Filter to a specific pattern by title.
        entry_id (int, optional): Filter to patterns linked to this entry id.
        entity (str, optional): Filter to patterns linked to this entity name.
        page (int): Page number for pagination. Defaults to 1.
        page_size (int): Number of patterns per page. Defaults to 20.

    Returns:
        dict: API response containing matching patterns, or an error message.
    """
    try:
        user_id = int(user_id)
        pattern_name = str(pattern_name)
        entry_id = int(entry_id) if entry_id is not None else ''
        entity = str(entity)
        page = int(page)
        page_size = int(page_size)
    except (ValueError, TypeError):
        return {"error": "user_id, entry_id, page, and page_size must be integers"}

    return call_api(
        method='GET',
        url=f'{BACKEND_URL}/api/patterns/find_patterns',
        params={
            "user_id": user_id,
            "pattern_name": pattern_name,
            "entry_id": entry_id,
            "entity": entity,
            "page": page,
            "page_size": page_size
        }
    )


@tool
def add_entity_to_pattern(
    user_id: int,
    pattern_name: str,
    pattern_summary: str,
    entity_id: str,
    entity_name: str
) -> dict:
    """
    Link an entity (person/thing) to an existing pattern, creating the entity if it
    doesn't already exist. Entities are connected directly to the pattern to capture
    the organic, recurring association between the entity and the pattern.

    Args:
        user_id (int): The unique identifier of the user who owns this pattern.
        pattern_name (str): The title of the pattern to link the entity to.
        pattern_summary (str): Updated summary text for the pattern.
        entity_id (str): The unique identifier of the entity.
        entity_name (str): The display name of the entity.

    Returns:
        dict: API response confirming the link, or an error message.
    """
    try:
        user_id = int(user_id)
        pattern_name = str(pattern_name)
        pattern_summary = str(pattern_summary)
        entity_id = str(entity_id)
        entity_name = str(entity_name)
    except (ValueError, TypeError):
        return {"error": "user_id must be an integer"}

    return call_api(
        method='POST',
        url=f'{BACKEND_URL}/api/patterns/add_entity',
        json_body={
            "user_id": user_id,
            "pattern_name": pattern_name,
            "pattern_summary": pattern_summary,
            "entity_id": entity_id,
            "entity_name": entity_name
        },
        timeout=30
    )


@tool
def add_entry_to_pattern(
    user_id: int,
    pattern_name: str,
    pattern_summary: str,
    entry_id: int,
    date: str,
    rationale: str
) -> dict:
    """
    Link a journal entry to an existing pattern, creating the entry if it doesn't
    already exist. Captures why this specific entry relates to the pattern.

    Args:
        user_id (int): The unique identifier of the user who owns this pattern.
        pattern_name (str): The title of the pattern to link the entry to.
        pattern_summary (str): Updated summary text for the pattern.
        entry_id (int): The unique identifier of the journal entry.
        date (str): The creation date of the entry, e.g. "2026-07-20".
        rationale (str): Why this entry relates to the pattern. Calling this again
            with the same entry_id updates the rationale rather than duplicating the link.

    Returns:
        dict: API response confirming the link, or an error message.
    """
    try:
        user_id = int(user_id)
        pattern_name = str(pattern_name)
        pattern_summary = str(pattern_summary)
        entry_id = int(entry_id)
        date = str(date)
        rationale = str(rationale)
    except (ValueError, TypeError):
        return {"error": "user_id and entry_id must be integers"}

    return call_api(
        method='POST',
        url=f'{BACKEND_URL}/api/patterns/add_entry',
        json_body={
            "user_id": user_id,
            "pattern_name": pattern_name,
            "pattern_summary": pattern_summary,
            "entry_id": entry_id,
            "date": date,
            "rationale": rationale
        },
        timeout=30
    )


@tool
def keyword_search_patterns(
    user_id: int,
    keyword: str,
    page: int = 1,
    page_size: int = 10
) -> dict:
    """
    Search a user's patterns for a specific keyword.

    Args:
        user_id (int): The unique identifier of the user whose patterns should be searched.
        keyword (str): The keyword or phrase to search for within pattern titles/summaries.
        page (int): Page number for pagination. Defaults to 1.
        page_size (int): Number of patterns per page. Defaults to 10.

    Returns:
        dict: API response containing matching patterns, or an error message.
    """
    try:
        user_id = int(user_id)
        keyword = str(keyword)
        page = int(page)
        page_size = int(page_size)
    except (ValueError, TypeError):
        return {"error": "user_id, page, and page_size must be integers"}

    return call_api(
        method='GET',
        url=f'{BACKEND_URL}/api/patterns/keyword_search',
        params={
            "user_id": user_id,
            "keyword": keyword,
            "page": page,
            "page_size": page_size
        }
    )

@tool
def get_entity_stims(
    entity_id: int,
    user_id: int,
    page: int = 1,
    pageSize: int = 10
) -> dict:
    """
    Fetch emotional stimuli data attached to a specific entity. Stimuli are grounded,
    directly-sourced records of adjectives and sentences associated with an entity and
    their sentiment scores — independent of any pattern or entry inference. Use this to
    verify or cross-check emotional associations with an entity against grounded truth,
    rather than relying solely on entries/patterns' inferred emotional framing.

    Args:
        entity_id (int): The unique identifier of the entity (stimulus) to fetch data for.
        user_id (int): The unique identifier of the user who owns this data.
        page (int): Page number for pagination. Defaults to 1.
        pageSize (int): Number of records per page. Defaults to 10.

    Returns:
        dict: {
            "page": int,
            "pageSize": int,
            "data": [
                {
                    "entity": str,                    # the entity's name
                    "adjective": str,                 # adjective associated with the entity
                    "sentence": str,                  # source sentence the adjective was drawn from
                    "sentence_sentiment": float|str,  # sentiment score/label for the sentence
                    "adjective_sentiment": float|str, # sentiment score/label for the adjective itself
                    "e1": ...,                        # additional emotion-related field
                    "e2": ...,                         # additional emotion-related field
                    "e3": ...                          # additional emotion-related field
                },
                ...
            ]
        }
        Returns an empty "data" list if no stimuli are found, or an error message if the
        request fails.
    """
    try:
        entity_id = int(entity_id)
        user_id = int(user_id)
        page = int(page)
        pageSize = int(pageSize)
    except (ValueError, TypeError):
        return {"error": "entity_id, user_id, page, and pageSize must be integers"}

    return call_api(
        method="GET",
        url=f"{BACKEND_URL}/api/stims/getEntityStims",
        params={
            "entity_id": entity_id,
            "user_id": user_id,
            "page": page,
            "pageSize": pageSize
        }
    )

@tool
def read_entry_stim_count(
    user_id: int,
    fromDate: str = '',
    toDate: str = '',
    limit: int = 10
) -> dict:
    """
    Get the top recurring entities (stimuli) mentioned across a user's journal entries,
    ranked by occurrence count, optionally scoped to a date range. This is the
    starting point for pattern detection — use it to identify which entities show
    up repeatedly before digging into their emotional data or entry content.

    Args:
        user_id (int): The unique identifier of the user whose entries should be counted.
        fromDate (str, optional): Start of the date range filter, e.g. "2026-07-01".
            Omit to count from the beginning of the user's history.
        toDate (str, optional): End of the date range filter, e.g. "2026-07-21".
            Omit to count through the most recent entries.
        limit (int): Max number of top entities to return, ranked by occurrence count
            descending. Capped at 100 server-side. Defaults to 10.

    Returns:
        dict: {
            "top_stims": [
                {
                    "id": int,                  # entity_id, for use with get_entity_stims etc.
                    "entity": str,              # entity name
                    "occurrence_count": int     # number of times this entity appeared
                },
                ...
            ],
            "count": int   # number of entities returned
        }
        or an error message if the request fails.
    """
    try:
        user_id = int(user_id)
        fromDate = str(fromDate)
        toDate = str(toDate)
        limit = int(limit)
    except (ValueError, TypeError):
        return {"error": "user_id and limit must be integers"}

    return call_api(
        method="GET",
        url=f"{BACKEND_URL}/api/entries/readCount",
        params={
            "user_id": user_id,
            "fromDate": fromDate,
            "toDate": toDate,
            "limit": limit
        }
    )

@tool
def search_patterns_by_entity(
    user_id: int,
    entity_name: str,
    page: int = 1,
    page_size: int = 20
) -> dict:
    """
    Find all patterns linked to a given entity, returning that entity's id along
    with each linked pattern's title, summary, and the entries (with rationale)
    attached to that pattern. Use this when you already know which entity you care
    about and want to see the patterns/entries built around it, rather than
    filtering patterns generically (use read_patterns for that).

    Args:
        user_id (int): The unique identifier of the user who owns this data.
        entity_name (str): The display name of the entity to search by.
        page (int): Page number for pagination. Defaults to 1.
        page_size (int): Number of pattern results per page. Defaults to 20.

    Returns:
        dict: API response where each record contains:
            {
                "entity_id": str,
                "entity_name": str,
                "pattern_title": str,
                "pattern_summary": str,
                "entries": [
                    {
                        "entry_id": int,
                        "date": str,
                        "rationale": str
                    },
                    ...
                ]
            }
        One record per pattern the entity is connected to. Returns an error message
        if the entity isn't found or the request fails.
    """
    try:
        user_id = int(user_id)
        entity_name = str(entity_name)
        page = int(page)
        page_size = int(page_size)
    except (ValueError, TypeError):
        return {"error": "user_id, page, and page_size must be integers"}

    return call_api(
        method='GET',
        url=f'{BACKEND_URL}/api/patterns/search_by_entity',
        params={
            "user_id": user_id,
            "entity_name": entity_name,
            "page": page,
            "page_size": page_size
        }
    )

@tool
def get_related_patterns(
    user_id: int,
    pattern_name: str
) -> dict:
    """
    Find other patterns related to a given pattern, inferred through shared
    entities (patterns connected to the same entity) and shared entries
    (patterns linked to the same journal entry). Use this to explore how
    patterns interconnect — e.g. whether two seemingly separate patterns are
    actually tied together through a common person or a common entry.

    Args:
        user_id (int): The unique identifier of the user who owns this pattern.
        pattern_name (str): The title of the pattern to find related patterns for.

    Returns:
        dict: API response where each record contains:
            {
                "pattern_title": str,
                "pattern_summary": str,
                "shared_entities": [str, ...],   # entity names connecting the two patterns
                "shared_entries": [int, ...]     # entry ids connecting the two patterns
            }
        Returns an error message if the pattern isn't found or has no related patterns.
    """
    try:
        user_id = int(user_id)
        pattern_name = str(pattern_name)
    except (ValueError, TypeError):
        return {"error": "user_id must be an integer"}

    return call_api(
        method="GET",
        url=f"{BACKEND_URL}/api/patterns/related_patterns",
        params={
            "user_id": user_id,
            "pattern_name": pattern_name
        }
    )

@tool
def connect_patterns(
    user_id: int,
    pattern_name_1: str,
    pattern_name_2: str,
    rationale: str
) -> dict:
    """
    Create a "related_to" connection between two patterns, with a rationale
    explaining why they're connected. Use this when you've identified that
    two patterns are meaningfully linked (e.g. they share an underlying
    cause, one seems to trigger the other, they reflect the same theme from
    different angles) and want to record that relationship for the user.
    Calling this again for the same pair of patterns will update the
    rationale rather than create a duplicate connection.
    Args:
        user_id (int): The unique identifier of the user who owns these patterns.
        pattern_name_1 (str): The title of the first pattern.
        pattern_name_2 (str): The title of the second pattern. Must be different from pattern_name_1.
        rationale (str): Explanation of why these two patterns are related.
    Returns:
        dict: API response where the record contains:
            {
                "pattern_1": str,
                "pattern_2": str,
                "rationale": str
            }
        Returns an error message if either pattern isn't found, if the two
        pattern names are the same, or if required params are missing.
    """
    try:
        user_id = int(user_id)
        pattern_name_1 = str(pattern_name_1)
        pattern_name_2 = str(pattern_name_2)
        rationale = str(rationale)
    except (ValueError, TypeError):
        return {"error": "user_id must be an integer"}
    return call_api(
        method="POST",
        url=f"{BACKEND_URL}/api/patterns/connect_patterns",
        params={
            "user_id": user_id,
            "pattern_name_1": pattern_name_1,
            "pattern_name_2": pattern_name_2,
            "rationale": rationale
        }
    )

@tool
def get_connected_patterns(
    user_id: int,
    pattern_name: str
) -> dict:
    """
    Find other patterns explicitly connected to a given pattern via a
    "related_to" relationship (created by connect_patterns), along with the
    rationale explaining why each connection was made. Unlike
    get_related_patterns, which infers relationships through shared entities
    or entries, this returns only patterns that have been directly and
    intentionally linked, with a human/model-authored explanation for the
    link. The relationship is treated as symmetric — connections are
    returned regardless of which pattern was originally the source.
    Args:
        user_id (int): The unique identifier of the user who owns this pattern.
        pattern_name (str): The title of the pattern to find connected patterns for.
    Returns:
        dict: API response where each record contains:
            {
                "pattern_title": str,
                "pattern_summary": str,
                "rationale": str   # why this pattern was connected to the queried one
            }
        Returns an error message if the pattern isn't found or has no connected patterns.
    """
    try:
        user_id = int(user_id)
        pattern_name = str(pattern_name)
    except (ValueError, TypeError):
        return {"error": "user_id must be an integer"}
    return call_api(
        method="GET",
        url=f"{BACKEND_URL}/api/patterns/connected_patterns",
        params={
            "user_id": user_id,
            "pattern_name": pattern_name
        }
    )

@tool
def read_reflects(
    user_id: int,
    entry_id: int
) -> dict:
    """
    Retrieve all reflection questions written for a specific journal entry.
    Use this to see what reflective questions have already been posed to the
    user for a given entry, e.g. before deciding whether to write a new one
    or to reference a prior question in conversation.
    Args:
        user_id (int): The unique identifier of the user who owns the entry.
        entry_id (int): The unique identifier of the journal entry.
    Returns:
        dict: API response containing:
            {
                "message": str,
                "data": [
                    {
                        "entry_id": int,
                        "user_id": int,
                        "question": str
                    },
                    ...
                ]
            }
        Returns an error message if user_id or entry_id is missing, or if a
        database error occurs.
    """
    try:
        user_id = int(user_id)
        entry_id = int(entry_id)
    except (ValueError, TypeError):
        return {"error": "user_id and entry_id must be integers"}
    return call_api(
        method="GET",
        url=f"{BACKEND_URL}/api/reflect/read",
        params={
            "user_id": user_id,
            "entry_id": entry_id
        }
    )


@tool
def write_reflect(
    user_id: int,
    entry_id: int,
    question: str
) -> dict:
    """
    Write a new reflective question tied to a specific journal entry. Use
    this to prompt the user with a question meant to deepen their reflection
    on something they wrote about in a given entry.
    Args:
        user_id (int): The unique identifier of the user who owns the entry.
        entry_id (int): The unique identifier of the journal entry this question relates to.
        question (str): The reflective question to store.
    Returns:
        dict: API response containing:
            {
                "message": str,
                "data": [{"id": int}]   # the id of the newly created reflect row
            }
        Returns an error message if any required field is missing, or if a
        database error occurs.
    """
    try:
        user_id = int(user_id)
        entry_id = int(entry_id)
        question = str(question)
    except (ValueError, TypeError):
        return {"error": "user_id and entry_id must be integers"}
    return call_api(
        method="POST",
        url=f"{BACKEND_URL}/api/reflect/write",
        json_body={
            "user_id": user_id,
            "entry_id": entry_id,
            "question": question
        }
    )