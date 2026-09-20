from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


# ---------------------------------------------------------
# DOMAINS WE DO NOT WANT TO ACCEPT
# ---------------------------------------------------------

BLOCKED_DOMAINS = {
    "worldometers.info",
    "statista.com",
    "wikipedia.org",
    "sciencedirect.com",
    "researchgate.net",
    "kaggle.com",
    "medium.com"
}


SOURCE_TYPES = {
    "government",
    "statistical_authority",
    "intergovernmental",
    "parliamentary",
    "central_bank",
    "open_data_portal",
    "public_research",
    "independent_research",
    "secondary_portal",
    "unknown"
}


DATA_ACCESS_TYPES = {
    "dataset",
    "table",
    "api",
    "csv",
    "xlsx",
    "json",
    "database",
    "catalogue",
    "unknown"
}


# ---------------------------------------------------------
# DOMAIN UTILITIES
# ---------------------------------------------------------

def get_domain(url):

    try:

        domain = urlparse(
            url
        ).netloc.lower()


        if domain.startswith("www."):
            domain = domain[4:]


        return domain


    except Exception:

        return ""


def is_blocked_domain(url):

    domain = get_domain(
        url
    )


    return any(

        domain == blocked
        or
        domain.endswith(
            "." + blocked
        )

        for blocked
        in BLOCKED_DOMAINS
    )


def is_usable_url(url):

    try:

        parsed = urlparse(
            url
        )


        return (
            parsed.scheme in {
                "http",
                "https"
            }
            and bool(
                parsed.netloc
            )
        )


    except Exception:

        return False


# ---------------------------------------------------------
# SOURCE TYPE
# ---------------------------------------------------------

def normalise_source_type(source_type):

    if not source_type:

        return "unknown"


    source_type = str(
        source_type
    ).strip().lower().replace(
        " ",
        "_"
    ).replace(
        "-",
        "_"
    )


    if source_type in SOURCE_TYPES:

        return source_type


    return "unknown"


def normalise_data_access_type(data_access_type):

    if not data_access_type:

        return "unknown"


    data_access_type = str(
        data_access_type
    ).strip().lower().replace(
        " ",
        "_"
    ).replace(
        "-",
        "_"
    )


    if data_access_type in DATA_ACCESS_TYPES:

        return data_access_type


    return "unknown"


# ---------------------------------------------------------
# LINK CHECKING
# ---------------------------------------------------------

def classify_http_status(status_code):

    if status_code is None:

        return "error"


    if 200 <= status_code < 300:

        return "reachable"


    if status_code in {
        401,
        403,
        429
    }:

        return "restricted"


    if status_code in {
        404,
        410
    }:

        return "broken"


    if 300 <= status_code < 400:

        return "reachable"


    return "error"


def check_source_link(
    url,
    timeout=10,
    urlopen_func=None
):

    if not is_usable_url(
        url
    ):

        return {
            "link_status":
                "broken",

            "http_status":
                None,

            "final_url":
                url
        }


    if urlopen_func is None:

        urlopen_func = urlopen


    request = Request(
        url,
        headers={
            "User-Agent":
                "DataObservatory/1.0"
        }
    )


    try:

        with urlopen_func(
            request,
            timeout=timeout
        ) as response:

            status_code = response.getcode()

            final_url = response.geturl()


        return {
            "link_status":
                classify_http_status(
                    status_code
                ),

            "http_status":
                status_code,

            "final_url":
                final_url
        }


    except HTTPError as error:

        return {
            "link_status":
                classify_http_status(
                    error.code
                ),

            "http_status":
                error.code,

            "final_url":
                error.geturl()
        }


    except (TimeoutError, URLError, OSError):

        return {
            "link_status":
                "error",

            "http_status":
                None,

            "final_url":
                url
        }


# ---------------------------------------------------------
# DATASET CANDIDATE VALIDATION
# ---------------------------------------------------------

def validate_dataset_candidate(
    dataset,
    real_urls,
    seen_urls,
    check_link=True,
    urlopen_func=None
):

    url = dataset.get(
        "source_url"
    )


    if not url:

        return {
            "accepted":
                False,

            "message":
                "REJECTED: missing URL",

            "detail":
                None,

            "validation_status":
                "invalid"
        }


    # Gemini is only allowed to choose
    # URLs Tavily actually returned.
    if url not in real_urls:

        return {
            "accepted":
                False,

            "message":
                "REJECTED URL NOT FROM TAVILY:",

            "detail":
                url,

            "validation_status":
                "invalid"
        }


    # Reject known unwanted domains.
    if is_blocked_domain(
        url
    ):

        return {
            "accepted":
                False,

            "message":
                "REJECTED BLOCKED DOMAIN:",

            "detail":
                url,

            "validation_status":
                "invalid"
        }


    # Gemini must explicitly verify
    # all three semantic conditions.
    if dataset.get(
        "official_source"
    ) is not True:

        return {
            "accepted":
                False,

            "message":
                "REJECTED NOT OFFICIAL:",

            "detail":
                url,

            "validation_status":
                "invalid"
        }


    if dataset.get(
        "actual_data_access"
    ) is not True:

        return {
            "accepted":
                False,

            "message":
                "REJECTED NO DATA ACCESS:",

            "detail":
                url,

            "validation_status":
                "invalid"
        }


    data_access_type = normalise_data_access_type(
        dataset.get(
            "data_access_type"
        )
    )


    if data_access_type == "unknown":

        return {
            "accepted":
                False,

            "message":
                "REJECTED UNKNOWN DATA ACCESS:",

            "detail":
                url,

            "validation_status":
                "invalid"
        }


    if dataset.get(
        "geographic_match"
    ) is not True:

        return {
            "accepted":
                False,

            "message":
                "REJECTED GEOGRAPHY:",

            "detail":
                url,

            "validation_status":
                "invalid"
        }


    # Avoid duplicate URLs.
    if url in seen_urls:

        return {
            "accepted":
                False,

            "message":
                "REJECTED DUPLICATE:",

            "detail":
                url,

            "validation_status":
                "invalid"
        }


    link_result = {
        "link_status":
            "reachable",

        "http_status":
            None,

        "final_url":
            url
    }


    if check_link:

        link_result = check_source_link(
            url,
            urlopen_func=urlopen_func
        )


    link_status = link_result.get(
        "link_status",
        "error"
    )


    if link_status == "reachable":

        validation_status = "validated"


    elif link_status in {
        "restricted",
        "error"
    }:

        validation_status = "needs_review"


    else:

        validation_status = "invalid"


    enriched_dataset = dataset.copy()

    enriched_dataset["source_type"] = normalise_source_type(
        enriched_dataset.get(
            "source_type"
        )
    )

    enriched_dataset["data_access_type"] = data_access_type

    enriched_dataset["validation_status"] = validation_status

    enriched_dataset["link_status"] = link_status

    enriched_dataset["http_status"] = link_result.get(
        "http_status"
    )

    enriched_dataset["final_url"] = link_result.get(
        "final_url"
    )


    if validation_status == "invalid":

        return {
            "accepted":
                False,

            "message":
                "REJECTED LINK:",

            "detail":
                url,

            "validation_status":
                "invalid",

            "dataset":
                enriched_dataset
        }


    return {
        "accepted":
            True,

        "message":
            "ACCEPTED:",

        "detail":
            enriched_dataset.get(
                "title"
            ),

        "validation_status":
            validation_status,

        "dataset":
            enriched_dataset
    }
