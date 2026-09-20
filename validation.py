from urllib.parse import urlparse


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


# ---------------------------------------------------------
# DATASET CANDIDATE VALIDATION
# ---------------------------------------------------------

def validate_dataset_candidate(
    dataset,
    real_urls,
    seen_urls
):

    url = dataset.get(
        "source_url"
    )


    if not url:

        return (
            False,
            "REJECTED: missing URL",
            None
        )


    # Gemini is only allowed to choose
    # URLs Tavily actually returned.
    if url not in real_urls:

        return (
            False,
            "REJECTED URL NOT FROM TAVILY:",
            url
        )


    # Reject known unwanted domains.
    if is_blocked_domain(
        url
    ):

        return (
            False,
            "REJECTED BLOCKED DOMAIN:",
            url
        )


    # Gemini must explicitly verify
    # all three conditions.
    if dataset.get(
        "official_source"
    ) is not True:

        return (
            False,
            "REJECTED NOT OFFICIAL:",
            url
        )


    if dataset.get(
        "actual_data_access"
    ) is not True:

        return (
            False,
            "REJECTED NO DATA ACCESS:",
            url
        )


    if dataset.get(
        "geographic_match"
    ) is not True:

        return (
            False,
            "REJECTED GEOGRAPHY:",
            url
        )


    # Avoid duplicate URLs.
    if url in seen_urls:

        return (
            False,
            "REJECTED DUPLICATE:",
            url
        )


    return (
        True,
        "ACCEPTED:",
        dataset.get(
            "title"
        )
    )
