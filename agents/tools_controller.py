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