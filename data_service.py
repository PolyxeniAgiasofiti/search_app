import json

from google import genai

from search_service import search_web
from manual_source_service import fetch_source
from validation import validate_dataset_candidate


def normalise_url_for_dedup(url):

    if not url:
        return ""

    return url.strip().rstrip("/")


def build_user_provided_dataset_candidate(target):

    source_url = target.get(
        "provided_source_url"
    )

    if not source_url:
        return None

    fetch_result = fetch_source(
        source_url
    )

    link_status = fetch_result.get(
        "status",
        "error"
    )

    validation_status = target.get(
        "validation_status",
        "needs_review"
    )

    if link_status == "restricted":
        validation_status = "needs_review"

    elif link_status in {
        "broken",
        "error"
    }:
        validation_status = "invalid"

    return {
        "data_target":
            target.get(
                "name",
                "User-provided data target"
            ),

        "title":
            target.get(
                "source_title"
            )
            or
            target.get(
                "name",
                "User-provided source"
            ),

        "publisher":
            target.get(
                "publisher",
                "unknown"
            ),

        "source_url":
            source_url,

        "description":
            target.get(
                "source_description"
            )
            or
            target.get(
                "description"
            )
            or
            target.get(
                "reason",
                ""
            ),

        "geographic_coverage":
            target.get(
                "geographic_coverage",
                "unknown"
            ),

        "time_coverage":
            target.get(
                "time_coverage",
                "unknown"
            ),

        "format":
            target.get(
                "format"
            )
            or
            target.get(
                "data_access_type"
            ),

        "source_type":
            target.get(
                "source_type",
                "unknown"
            ),

        "validation_status":
            validation_status,

        "link_status":
            link_status,

        "http_status":
            None,

        "final_url":
            fetch_result.get(
                "final_url"
            )
            or
            target.get(
                "final_url"
            ),

        "source_origin":
            "user_provided",

        "dataset_code":
            target.get(
                "dataset_code"
            ),

        "doi":
            target.get(
                "doi"
            ),

        "available_information":
            target.get(
                "available_information",
                []
            ),

        "validation_reason":
            target.get(
                "validation_reason",
                ""
            ),

        "source_metadata":
            target.get(
                "source_metadata"
            ),

        "official_source":
            validation_status == "validated",

        "actual_data_access":
            validation_status == "validated"
    }


# ---------------------------------------------------------
# GEMINI
# ---------------------------------------------------------

gemini_client = genai.Client()


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

   A trusted publisher alone is not enough.

   actual_data_access must be true ONLY when the Tavily
   title/content reasonably indicates access to structured
   data or a direct official dataset resource.

   Mark actual_data_access false for:

   - informational or explanatory articles
   - general topic pages
   - methodology-only pages
   - news releases
   - publication pages without accessible underlying data
   - organisation homepages

   For example, an official "Statistics Explained" article
   should not be accepted unless the supplied result clearly
   provides or directly links to a dataset, table, data browser,
   API, catalogue entry, or download.

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

For actual_data_access, be strict:

- true means the result provides or directly leads to
  structured data.
- false means the result mainly discusses statistics
  without clear data access.

Also classify source_type using exactly one of:

government
statistical_authority
intergovernmental
parliamentary
central_bank
open_data_portal
public_research
independent_research
secondary_portal
unknown

source_type describes the organisation or source,
not the file format.

Also classify data_access_type using exactly one of:

dataset
table
api
csv
xlsx
json
database
catalogue
unknown

data_access_type describes how the data can be accessed.
Use unknown only when the Tavily evidence does not clearly
show a structured data access path.


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
            "source_type": "statistical_authority",
            "data_access_type": "table",
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

    all_datasets = []

    seen_urls = set()


    for target in data_targets:

        if target.get(
            "origin"
        ) == "user_provided":

            manual_dataset = build_user_provided_dataset_candidate(
                target
            )

            if manual_dataset:

                manual_url_key = normalise_url_for_dedup(
                    manual_dataset.get(
                        "final_url"
                    )
                    or
                    manual_dataset.get(
                        "source_url"
                    )
                )

                if manual_url_key:
                    seen_urls.add(
                        manual_url_key
                    )

                seen_urls.add(
                    manual_dataset.get(
                        "source_url"
                    )
                )

                all_datasets.append(
                    manual_dataset
                )

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

        search_results = search_web(
            query=query,
            max_results=10
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

            validation_result = validate_dataset_candidate(
                dataset=dataset,
                real_urls=real_urls,
                seen_urls=seen_urls
            )


            message = validation_result.get(
                "message"
            )

            detail = validation_result.get(
                "detail"
            )


            if not validation_result.get(
                "accepted"
            ):

                if detail is None:

                    print(
                        message
                    )

                else:

                    print(
                        message,
                        detail
                    )

                continue


            accepted_dataset = validation_result.get(
                "dataset",
                dataset
            )

            url = accepted_dataset.get(
                "source_url"
            )

            url_key = normalise_url_for_dedup(
                accepted_dataset.get(
                    "final_url"
                )
                or
                url
            )

            if url_key in seen_urls:

                print(
                    "REJECTED DUPLICATE URL:",
                    url
                )

                continue

            seen_urls.add(
                url_key
            )


            all_datasets.append(
                accepted_dataset
            )


            print(
                message,
                detail
            )


    return {
        "datasets":
            all_datasets
    }
