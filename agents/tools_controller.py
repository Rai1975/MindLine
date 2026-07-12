from agents.config import BACKEND_URL
from flask import jsonify, request
import requests as webRequest

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


def grab_patterns(user_id):
    return call_api(
        method="GET",
        url=f"{BACKEND_URL}/api/patterns/find_patterns",
        params={
            "user_id": user_id
        }
    )

# Definitely need to clean up outputs here
def read_entries(
    user_id='', 
    entry_id='', 
    fromDate='', 
    toDate='', 
    entity='', 
    emotion='', 
    page=1, 
    page_size=10
):
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

def new_entry(
    user_id='',
    raw_entry=''
):
    return call_api(
        method='POST',
        url=f"{BACKEND_URL}/api/entries/create",
        json_body={
            "user_id": user_id,
            "raw_entry": raw_entry
        },
        timeout=999999
    )

def keyword_search(
    user_id='',
    keyword=''
):
    return call_api(
        method='POST',
        url=f'{BACKEND_URL}/api/entries/keywordSearch',
        json_body={
            "user_id": user_id,
            "keyword": keyword
        },
        timeout=999
    )