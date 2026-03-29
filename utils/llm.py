"""
Centralized LLM configuration.

All agents import get_llm() from here instead of creating their own LLM.
To switch models, change this ONE file — every agent updates automatically.

Setup:
1. Place your service account JSON in the project and set GOOGLE_APPLICATION_CREDENTIALS in .env
2. Set GOOGLE_CLOUD_PROJECT in .env
"""

import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

# Point to your service account credentials
credentials_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
if credentials_path and os.path.exists(credentials_path):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.abspath(credentials_path)

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "")


def get_llm(temperature: float = 0):
    """
    Returns a Gemini 2.5 Pro instance via Google GenAI.
    """
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-pro",
        project=PROJECT_ID,
        temperature=temperature,
        max_output_tokens=8192,
    )
