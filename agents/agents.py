"""
Strands Agents
"""

import os
import json
import boto3
from strands import Agent
from strands.models import BedrockModel

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


SUPERVISOR_AGENT_PROMPT = """
You are an expert pattern identifer and recurring theme identifier.


"""