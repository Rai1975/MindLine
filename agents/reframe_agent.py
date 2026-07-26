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
    search_patterns_by_entity,
    get_related_patterns,
    connect_patterns,
    get_connected_patterns
)
from src.backend.db_config import run_neo4j_query, run_psql_query
from src.backend.config import NEO4J_AUTH, NEO4J_PASSWORD, NEO4J_URI
from neo4j import GraphDatabase