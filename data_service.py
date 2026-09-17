import os
import json

from urllib.parse import urlparse

from google import genai
from tavily import TavilyClient


# ---------------------------------------------------------
# GEMINI
# ---------------------------------------------------------

gemini_client = genai.Client()


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
# JSON CLEANER
# ---------------------------------------------------------

def clean_json_response(response_text):

    response_text = response_text.strip()


    if response_text.startswith("```json"):
        response_text = response_text[7:]


    elif response_text.startswith("```"):
        response_text = response_text[3:]


    if response_text.endswith("```"):
        response_text = response_text[:-3]


    return response_text.strip()


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
# GEMINI CREATES THE SEARCH QUERY
# ---------------------------------------------------------

def build_search_query(
    topic,
    data_target
):

    prompt = f"""
You are creating a web search query for a
public-data discovery application.

Research topic:

"{topic}"

Approved data target:

"{data_target['name']}"

Reason this data is needed:

"{data_target['reason']}"


Create ONE concise natural-language search query.

The goal is to discover a REAL dataset,
statistical table, database, API,
open-data catalogue entry or downloadable
data resource from an authoritative
public institution.

Possible authoritative publishers include:

- national statistical authorities
- government departments
- government open-data portals
- international organisations
- central banks
- parliaments
- official statistical agencies
- public research institutions

IMPORTANT:

The source may come from ANY country.

Do NOT assume that only well-known sources
such as Eurostat, OECD or World Bank exist.

An appropriate official American,
Canadian, Australian, Asian, African,
European or other national source is valid.

Strongly favour search concepts such as:

official statistics
dataset
open data
statistical database
API
downloadable data
government statistics
data catalogue

Do NOT use search-engine operators such as:

site:
filetype:
OR
AND

Use natural-language search terms only.

Do not search for:

news
opinion articles
blogs
commercial reports
general informational webpages

Return ONLY the search query.
"""


    interaction = gemini_client.interactions.create(
        model="gemini-3.5-flash-lite",
        input=prompt
    )


    return interaction.output_text.strip()


# ---------------------------------------------------------
# GEMINI EVALUATES REAL TAVILY RESULTS
# ---------------------------------------------------------

def evaluate_search_results(
    topic,
    data_target,
    search_results
):

    simplified_results = []


    for result in search_results:

        simplified_results.append(
            {
                "title":
                    result.get(
                        "title"
                    ),

                "url":
                    result.get(
                        "url"
                    ),

                "content":
                    result.get(
                        "content",
                        ""
                    )
            }
        )


    prompt = f"""
You are evaluating REAL web-search results
for a public-data discovery application.

Research topic:

"{topic}"

Approved data target:

"{data_target['name']}"

Why this data is needed:

"{data_target['reason']}"


Below are REAL results returned by Tavily:

{json.dumps(
    simplified_results,
    ensure_ascii=False,
    indent=2
)}


Your job is to retain only genuine,
authoritative public-data sources.


A result should normally satisfy ALL
of the following:

1. It comes from an authoritative public,
   governmental, statistical,
   intergovernmental, parliamentary,
   central-bank or public-research institution.

2. It provides meaningful access to actual data,
   such as:

   - a statistical table
   - dataset
   - database
   - data catalogue entry
   - downloadable CSV/XLSX/JSON
   - API
   - official data browser

3. It is genuinely relevant to the
   approved data target.

4. Its geographic coverage is appropriate
   to the research topic OR it is a wider
   dataset that contains the required geography.

5. It is not simply a general homepage,
   article or descriptive webpage.


EXCLUDE:

- Worldometer
- Statista
- Wikipedia
- commercial aggregators
- newspapers
- news articles
- blogs
- journal articles
- ScienceDirect
- ResearchGate
- Kaggle
- Medium
- consulting-company articles
- generic company websites
- opinion pieces
- general topic pages
- pages discussing statistics without
  giving meaningful data access


IMPORTANT:

An official source may come from ANY country.

Do not reject a legitimate official source
just because the organisation is unfamiliar.

Do NOT invent URLs.

source_url MUST be copied exactly from
one of the supplied Tavily results.

Do NOT invent dataset titles.

Do NOT invent statistics.

Do NOT invent publishers.

For each accepted result,
classify these three verification fields:

official_source
actual_data_access
geographic_match

Only return a candidate when ALL THREE are true.


Return ONLY valid JSON in this exact form:

{{
    "datasets": [
        {{
            "data_target": "{data_target['name']}",
            "title": "Dataset or data-resource title",
            "publisher": "Publisher",
            "source_url": "Exact Tavily URL",
            "description": "Why this source matches the approved target",
            "geographic_coverage": "Coverage or Unknown",
            "time_coverage": "Coverage or Unknown",
            "format": "CSV, JSON, API, XLSX, table, catalogue, database, or unknown",
            "official_source": true,
            "actual_data_access": true,
            "geographic_match": true
        }}
    ]
}}
"""


    interaction = gemini_client.interactions.create(
        model="gemini-3.5-flash-lite",
        input=prompt
    )


    response_text = clean_json_response(
        interaction.output_text
    )


    return json.loads(
        response_text
    )


# ---------------------------------------------------------
# MAIN PUBLIC DATA SEARCH
# ---------------------------------------------------------

def search_public_datasets(
    topic,
    data_targets
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


    all_datasets = []

    seen_urls = set()


    for target in data_targets:

        print(
            "\n------------------------------------"
        )

        print(
            "DATA TARGET:",
            target.get(
                "name"
            )
        )


        # ---------------------------------------------
        # 1. GEMINI BUILDS QUERY
        # ---------------------------------------------

        query = build_search_query(
            topic,
            target
        )


        print(
            "\nSEARCH QUERY:"
        )

        print(
            query
        )


        # ---------------------------------------------
        # 2. TAVILY SEARCHES REAL WEB
        # ---------------------------------------------

        tavily_response = tavily_client.search(
            query=query,
            search_depth="basic",
            max_results=10,
            include_answer=False
        )


        search_results = tavily_response.get(
            "results",
            []
        )


        print(
            "RAW TAVILY RESULTS:",
            len(
                search_results
            )
        )


        # ---------------------------------------------
        # REAL URL ALLOWLIST
        # ---------------------------------------------

        real_urls = {

            item.get(
                "url"
            )

            for item
            in search_results

            if item.get(
                "url"
            )
        }


        # ---------------------------------------------
        # 3. GEMINI EVALUATES RESULTS
        # ---------------------------------------------

        evaluated = evaluate_search_results(
            topic=topic,
            data_target=target,
            search_results=search_results
        )


        # ---------------------------------------------
        # 4. PYTHON VERIFICATION
        # ---------------------------------------------

        for dataset in evaluated.get(
            "datasets",
            []
        ):

            url = dataset.get(
                "source_url"
            )


            if not url:

                print(
                    "REJECTED: missing URL"
                )

                continue


            # Gemini is only allowed to choose
            # URLs Tavily actually returned.
            if url not in real_urls:

                print(
                    "REJECTED URL NOT FROM TAVILY:",
                    url
                )

                continue


            # Reject known unwanted domains.
            if is_blocked_domain(
                url
            ):

                print(
                    "REJECTED BLOCKED DOMAIN:",
                    url
                )

                continue


            # Gemini must explicitly verify
            # all three conditions.
            if dataset.get(
                "official_source"
            ) is not True:

                print(
                    "REJECTED NOT OFFICIAL:",
                    url
                )

                continue


            if dataset.get(
                "actual_data_access"
            ) is not True:

                print(
                    "REJECTED NO DATA ACCESS:",
                    url
                )

                continue


            if dataset.get(
                "geographic_match"
            ) is not True:

                print(
                    "REJECTED GEOGRAPHY:",
                    url
                )

                continue


            # Avoid duplicate URLs.
            if url in seen_urls:

                print(
                    "REJECTED DUPLICATE:",
                    url
                )

                continue


            seen_urls.add(
                url
            )


            all_datasets.append(
                dataset
            )


            print(
                "ACCEPTED:",
                dataset.get(
                    "title"
                )
            )


    return {
        "datasets":
            all_datasets
    }