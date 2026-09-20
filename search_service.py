import os

from tavily import TavilyClient


# ---------------------------------------------------------
# TAVILY WEB SEARCH
# ---------------------------------------------------------

def search_web(
    query,
    max_results=10
):

    tavily_api_key = os.getenv(
        "TAVILY_API_KEY"
    )


    if not tavily_api_key:

        raise RuntimeError(
            "TAVILY_API_KEY is not configured."
        )


    tavily_client = TavilyClient(
        api_key=tavily_api_key
    )


    tavily_response = tavily_client.search(
        query=query,
        search_depth="basic",
        max_results=max_results,
        include_answer=False
    )


    return tavily_response.get(
        "results",
        []
    )
