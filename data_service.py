import os
import json
from urllib.parse import urlparse

from google import genai
from tavily import TavilyClient


gemini_client = genai.Client()

tavily_client = TavilyClient(
    api_key=os.environ["TAVILY_API_KEY"]
)


# Obvious non-official / aggregator sources
BLOCKED_DOMAINS = {
    "worldometers.info",
    "statista.com",
    "wikipedia.org",
    "sciencedirect.com",
    "researchgate.net",
    "kaggle.com",
    "medium.com",
}


def clean_json_response(response_text):

    response_text = response_text.strip()

    if response_text.startswith("```json"):
        response_text = response_text[7:]

    elif response_text.startswith("```"):
        response_text = response_text[3:]

    if response_text.endswith("```"):
        response_text = response_text[:-3]

    return response_text.strip()


def get_domain(url):

    try:
        domain = urlparse(url).netloc.lower()

        if domain.startswith("www."):
            domain = domain[4:]

        return domain

    except Exception:
        return ""


def is_blocked_domain(url):

    domain = get_domain(url)

    return any(
        domain == blocked or domain.endswith("." + blocked)
        for blocked in BLOCKED_DOMAINS
    )


def build_search_query(topic, data_target):

    prompt = f"""
You are creating a search query for a public-data discovery system.

Research topic:

"{topic}"

Approved data target:

"{data_target['name']}"

Reason this data is needed:

"{data_target['reason']}"


Create ONE concise natural-language search query.

The goal is to find a REAL dataset or statistical table
from an authoritative public institution.

Possible sources include:

- national statistical authorities
- government departments
- government open-data portals
- international organisations
- central banks
- parliaments
- official research institutions
- official statistical agencies

The source may come from ANY country.

Strongly favour words such as:

official statistics
dataset
open data
API
statistical database
downloadable data
government statistics

IMPORTANT:

Do NOT use search-engine operators such as:

site:
filetype:
OR
AND

Use normal natural-language search terms only.

Do not search for articles, commentary or news.

Return ONLY the search query.
"""

    interaction = gemini_client.interactions.create(
        model="gemini-3.5-flash-lite",
        input=prompt
    )

    return interaction.output_text.strip()


def evaluate_search_results(
    topic,
    data_target,
    search_results
):

    simplified_results = []

    for result in search_results:

        simplified_results.append({
            "title": result.get("title"),
            "url": result.get("url"),
            "content": result.get("content", "")
        })


    prompt = f"""
You are evaluating REAL web-search results for a public-data application.

Research topic:

"{topic}"

Approved data target:

"{data_target['name']}"

Reason:

"{data_target['reason']}"


REAL Tavily results:

{json.dumps(
    simplified_results,
    ensure_ascii=False,
    indent=2
)}


Your task is to identify results that are genuine,
authoritative public-data sources.


A result should normally satisfy ALL of these conditions:

1. It comes from an official or authoritative public institution.

2. It provides direct access to data, a statistical table,
   dataset catalogue entry, downloadable dataset, API,
   official database, or similar data resource.

3. It is genuinely relevant to the approved data target.

4. Its geographic coverage is appropriate for the research topic,
   OR it is a global dataset that includes the required geography.

5. It is not merely a general homepage or informational article.


EXCLUDE:

- commercial data aggregators
- news articles
- journal articles
- blogs
- Wikipedia
- Worldometer
- Statista
- generic topic pages
- search-result pages
- pages that discuss data without giving meaningful access to it


IMPORTANT:

Do NOT invent URLs.

The source_url MUST be copied exactly from one of the supplied
Tavily results.

Do NOT invent data values.

Do NOT create synthetic data.


For each accepted result also classify:

- official_source
- actual_data_access
- geographic_match

Only return results where ALL THREE are true.


Return ONLY valid JSON:

{{
    "datasets": [
        {{
            "data_target": "{data_target['name']}",
            "title": "Dataset/data resource title",
            "publisher": "Publisher",
            "source_url": "Exact Tavily URL",
            "description": "Why it matches the approved target",
            "geographic_coverage": "Coverage or Unknown",
            "time_coverage": "Coverage or Unknown",
            "format": "CSV, JSON, API, XLSX, table, catalogue, or unknown",
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

    return json.loads(response_text)


def search_public_datasets(topic, data_targets):

    all_datasets = []
    seen_urls = set()

    for target in data_targets:

        # -----------------------------------
        # 1. GEMINI CREATES SEARCH QUERY
        # -----------------------------------

        query = build_search_query(
            topic,
            target
        )

        print(
            f"\nSEARCH QUERY FOR {target['name']}:\n{query}\n"
        )


        # -----------------------------------
        # 2. TAVILY SEARCHES THE REAL WEB
        # -----------------------------------

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


        # Build a set of REAL URLs returned by Tavily
        real_urls = {
            item.get("url")
            for item in search_results
            if item.get("url")
        }


        # -----------------------------------
        # 3. GEMINI EVALUATES RESULTS
        # -----------------------------------

        evaluated = evaluate_search_results(
            topic=topic,
            data_target=target,
            search_results=search_results
        )


        # -----------------------------------
        # 4. PYTHON VERIFIES GEMINI'S CHOICES
        # -----------------------------------

        for dataset in evaluated.get(
            "datasets",
            []
        ):

            url = dataset.get("source_url")

            if not url:
                continue

            # Gemini may ONLY use a URL Tavily actually found
            if url not in real_urls:
                continue

            # Reject known non-authoritative sources
            if is_blocked_domain(url):
                continue

            # All verification flags must be true
            if dataset.get("official_source") is not True:
                continue

            if dataset.get("actual_data_access") is not True:
                continue

            if dataset.get("geographic_match") is not True:
                continue

            # Prevent duplicate sources
            if url in seen_urls:
                continue

            seen_urls.add(url)

            all_datasets.append(dataset)


    return {
        "datasets": all_datasets
    }