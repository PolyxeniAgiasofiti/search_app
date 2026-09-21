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


def extract_url_content(
    url,
    definition=None,
    timeout=30,
    tavily_client=None
):

    tavily_api_key = os.getenv(
        "TAVILY_API_KEY"
    )

    if tavily_client is None:

        if not tavily_api_key:

            raise RuntimeError(
                "TAVILY_API_KEY is not configured."
            )

        tavily_client = TavilyClient(
            api_key=tavily_api_key
        )

    query = None

    if definition:
        query = (
            "Extract the dataset title, indicator definition, publisher, "
            "dimensions, geographic coverage, time coverage, format, "
            "data access information, and available information from this "
            "exact page. Current approved definition: "
            + definition
        )

    attempts = []

    for depth in (
        "basic",
        "advanced"
    ):

        try:

            response = tavily_client.extract(
                urls=[
                    url
                ],
                extract_depth=depth,
                format="markdown",
                timeout=timeout,
                query=query
            )

        except Exception as error:

            attempts.append(
                {
                    "extract_depth":
                        depth,

                    "status":
                        "error",

                    "message":
                        str(
                            error
                        )
                }
            )
            continue

        result = first_extract_result(
            response
        )

        content = extract_result_content(
            result
        )

        attempts.append(
            {
                "extract_depth":
                    depth,

                "status":
                    "success"
                    if content
                    else
                    "empty",

                "content_length":
                    len(
                        content
                    )
            }
        )

        if is_extracted_content_sufficient(
            content
        ):

            return {
                "status":
                    "success",

                "extract_depth":
                    depth,

                "provided_url":
                    url,

                "final_url":
                    result.get(
                        "url"
                    )
                    if isinstance(
                        result,
                        dict
                    )
                    else
                    None,

                "content":
                    content,

                "attempts":
                    attempts,

                "raw_result":
                    result
            }

    return {
        "status":
            "empty",

        "provided_url":
            url,

        "content":
            "",

        "attempts":
            attempts
    }


def first_extract_result(response):

    if not isinstance(
        response,
        dict
    ):
        return {}

    results = response.get(
        "results"
    )

    if isinstance(
        results,
        list
    ) and results:
        return results[0]

    if isinstance(
        results,
        dict
    ):
        return results

    return response


def extract_result_content(result):

    if not isinstance(
        result,
        dict
    ):
        return ""

    for field_name in (
        "raw_content",
        "content",
        "markdown",
        "text"
    ):

        value = result.get(
            field_name
        )

        if isinstance(
            value,
            str
        ) and value.strip():

            return value.strip()

    return ""


def is_extracted_content_sufficient(content):

    if not content:
        return False

    normalized = " ".join(
        content.split()
    )

    return len(
        normalized
    ) >= 120
