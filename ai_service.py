import json

from google import genai
from prompts import build_topic_analysis_prompt


client = genai.Client()


def analyze_topic(topic):

    prompt = build_topic_analysis_prompt(topic)

    interaction = client.interactions.create(
        model="gemini-3.5-flash-lite",
        input=prompt
    )

    response_text = interaction.output_text.strip()

    # Remove Markdown code fences if Gemini adds them
    if response_text.startswith("```json"):
        response_text = response_text[7:]

    if response_text.startswith("```"):
        response_text = response_text[3:]

    if response_text.endswith("```"):
        response_text = response_text[:-3]

    response_text = response_text.strip()

    return json.loads(response_text)