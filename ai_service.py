import json

from google import genai
from prompts import (
    build_topic_analysis_prompt,
    build_revision_prompt
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
    # ENFORCE SEPARATION IN PYTHON
    # -----------------------------------

    if target == "definition":

        # Gemini may revise ONLY the definition.
        # Data targets are preserved exactly.
        result["data_needed"] = current_analysis["data_needed"]


    elif target == "data":

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