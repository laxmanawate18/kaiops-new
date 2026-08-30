"""
Metadata Agent

Domain expert for application metadata and context management.
Provides authoritative source of truth for application configurations.
"""

from agents.metadata_agent.tools import (
    search_application_by_name,
    list_all_applications,
    query_mongodb
)

from agents.metadata_agent.prompt import metadata_expertise

# Metadata agent exports tools and prompt for root agent composition
metadata_tools = [
    search_application_by_name,
    list_all_applications,
    query_mongodb
]

metadata_prompt = metadata_expertise

__all__ = [
    "metadata_tools",
    "metadata_prompt",
    "search_application_by_name",
    "list_all_applications",
    "query_mongodb"
]
