import json

from google import genai
from prompts import (
    build_topic_analysis_prompt,
    build_revision_prompt,
    build_manual_source_analysis_prompt,
    build_manual_source_url_context_prompt
)


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


def analyze_topic(topic):

    prompt = build_topic_analysis_prompt(topic)

    interaction = client.interactions.create(
        model="gemini-3.5-flash-lite",
        input=prompt
    )

    response_text = clean_json_response(
        interaction.output_text
    )

    result = json.loads(response_text)

    return result


def revise_topic_analysis(
    topic,
    current_analysis,
    user_feedback,
    target
):

    if target not in ["definition", "data"]:
        raise ValueError(
            "target must be 'definition' or 'data'"
        )

    prompt = build_revision_prompt(
        topic,
        current_analysis,
        user_feedback,
        target
    )

    interaction = client.interactions.create(
        model="gemini-3.5-flash-lite",
        input=prompt
    )

    response_text = clean_json_response(
        interaction.output_text
    )

    result = json.loads(response_text)


    # -----------------------------------
    # ENFORCE REVIEW BOUNDARIES IN PYTHON
    # -----------------------------------

    if target == "data":

        # Gemini may revise ONLY the data targets.
        # Definition is preserved exactly.
        result["definition"] = current_analysis["definition"]


    # Preserve scope information
    result["in_scope"] = current_analysis.get(
        "in_scope",
        True
    )

    result["scope_message"] = current_analysis.get(
        "scope_message",
        ""
    )


    return result


def analyze_manual_source(
    definition,
    existing_data_targets,
    source_evidence
):

    prompt = build_manual_source_analysis_prompt(
        definition,
        existing_data_targets,
        source_evidence
    )

    interaction = client.interactions.create(
        model="gemini-3.5-flash-lite",
        input=prompt
    )

    response_text = clean_json_response(
        interaction.output_text
    )

    return json.loads(
        response_text
    )


def analyze_manual_source_url_context(
    definition,
    existing_data_targets,
    provided_url
):

    prompt = build_manual_source_url_context_prompt(
        definition,
        existing_data_targets,
        provided_url
    )

    interaction = client.interactions.create(
        model="gemini-3.5-flash-lite",
        input=prompt,
        tools=[
            {
                "type":
                    "url_context"
            }
        ]
    )

    response_text = clean_json_response(
        interaction.output_text
    )

    return {
        "analysis":
            json.loads(
                response_text
            ),

        "url_context_metadata":
            extract_url_context_metadata(
                interaction
            )
    }


def extract_url_context_metadata(value):

    if value is None:
        return []

    if hasattr(
        value,
        "model_dump"
    ):

        value = value.model_dump(
            mode="json",
            exclude_none=True
        )

    elif hasattr(
        value,
        "__dict__"
    ):

        value = vars(
            value
        )

    if isinstance(
        value,
        dict
    ):

        if value.get(
            "type"
        ) == "url_context_result":
            return normalise_url_context_metadata(
                value.get(
                    "result",
                    []
                )
            )

        for key in (
            "url_context_metadata",
            "urlContextMetadata"
        ):

            metadata = value.get(
                key
            )

            if metadata:

                return normalise_url_context_metadata(
                    metadata
                )

        for child in value.values():

            metadata = extract_url_context_metadata(
                child
            )

            if metadata:
                return metadata

    elif isinstance(
        value,
        list
    ):

        for item in value:

            metadata = extract_url_context_metadata(
                item
            )

            if metadata:
                return metadata

    return []


def normalise_url_context_metadata(metadata):

    if hasattr(
        metadata,
        "model_dump"
    ):

        metadata = metadata.model_dump(
            mode="json",
            exclude_none=True
        )

    if isinstance(
        metadata,
        dict
    ):

        url_metadata = (
            metadata.get(
                "url_metadata"
            )
            or
            metadata.get(
                "urlMetadata"
            )
            or
            []
        )

    else:

        url_metadata = metadata

    if not isinstance(
        url_metadata,
        list
    ):
        url_metadata = [
            url_metadata
        ]

    normalised = []

    for item in url_metadata:

        if hasattr(
            item,
            "model_dump"
        ):
            item = item.model_dump(
                mode="json",
                exclude_none=True
            )

        if not isinstance(
            item,
            dict
        ):
            continue

        normalised.append(
            {
                "retrieved_url":
                    item.get(
                        "retrieved_url"
                    )
                    or
                    item.get(
                        "retrievedUrl"
                    )
                    or
                    item.get(
                        "url"
                    ),

                "url_retrieval_status":
                    item.get(
                        "url_retrieval_status"
                    )
                    or
                    item.get(
                        "urlRetrievalStatus"
                    )
                    or
                    item.get(
                        "status"
                    )
            }
        )

    return normalised
