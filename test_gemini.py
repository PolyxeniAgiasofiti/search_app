import json

from google import genai
from prompts import build_topic_analysis_prompt


client = genai.Client()

topic = "Gerontocracy"

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


result = json.loads(response_text)


print("\nDEFINITION\n")
print(result["definition"])

print("\nDATA NEEDED FOR THE STUDY\n")

for item in result["data_needed"]:
    print(f"- {item['name']}")
    print(f"  {item['reason']}\n")