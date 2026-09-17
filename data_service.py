import json

from google import genai


client = genai.Client()


def clean_json_response(response_text):

    response_text = response_text.strip()

    if response_text.startswith("```json"):
        response_text = response_text[7:]

    elif response_text.startswith("```"):
        response_text = response_text[3:]

    if response_text.endswith("```"):
        response_text = response_text[:-3]

    return response_text.strip()


def search_public_datasets(topic, data_targets):

    targets_text = "\n".join(
        f"- {item['name']}: {item['reason']}"
        for item in data_targets
    )

    prompt = f"""
You are helping a data research application find REAL,
publicly available datasets.

Research topic:

"{topic}"

The approved data targets are:

{targets_text}


SEARCH REQUIREMENTS:

Use Google Search to find publicly available datasets
that could satisfy these data targets.

Strongly prefer authoritative sources such as:

- Eurostat
- European Commission
- OECD
- World Bank
- United Nations
- national statistical authorities
- government open-data portals
- official public institutions

For each dataset:

- identify which approved data target it supports
- provide the dataset title
- provide the publisher
- provide the public source URL
- briefly explain why it is relevant
- identify the apparent format if possible
- identify geographic coverage if possible
- identify time coverage if possible

IMPORTANT:

Only include datasets that appear to actually exist.

Do NOT invent dataset names.

Do NOT invent URLs.

Do NOT invent data values.

Do NOT create synthetic data.

This stage is dataset DISCOVERY only.

Return ONLY valid JSON:

{{
    "datasets": [
        {{
            "data_target": "Approved data target",
            "title": "Dataset title",
            "publisher": "Publisher",
            "source_url": "https://...",
            "description": "Why this dataset is relevant",
            "geographic_coverage": "Coverage if known",
            "time_coverage": "Coverage if known",
            "format": "CSV, JSON, API, XLSX, unknown"
        }}
    ]
}}
"""

    interaction = client.interactions.create(
        model="gemini-3.5-flash-lite",
        input=prompt,
        tools=[
            {
                "type": "google_search"
            }
        ]
    )

    response_text = clean_json_response(
        interaction.output_text
    )

    return json.loads(response_text)