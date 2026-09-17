def build_topic_analysis_prompt(topic):

    return f"""
You are assisting with a data research application.

The user wants to study the following topic:

"{topic}"

Your task is to provide two things:

1. SIMPLE DEFINITION
Provide a short, clear, neutral definition of the topic.
Use plain language.
Keep it to approximately 2-4 sentences.

2. DATA NEEDED FOR THE STUDY
Identify the main categories of data that would be necessary
to properly study and analyse this topic.

For every data category:
- provide a short and clear category name
- briefly explain why this data is relevant

Do NOT search for specific datasets.
Do NOT search for repositories.
Do NOT provide URLs or sources.
We are only identifying what kinds of data would be needed.

Return ONLY valid JSON in exactly this structure:

{{
    "definition": "Simple definition here",
    "data_needed": [
        {{
            "name": "Data category",
            "reason": "Why this data is needed"
        }},
        {{
            "name": "Another data category",
            "reason": "Why this data is needed"
        }}
    ]
}}
"""