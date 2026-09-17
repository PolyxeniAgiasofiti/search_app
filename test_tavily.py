from tavily import TavilyClient
import os

client = TavilyClient(
    api_key=os.environ["TAVILY_API_KEY"]
)

response = client.search(
    query="official public dataset population by age Europe",
    search_depth="basic",
    max_results=5,
    include_answer=False
)

for result in response.get("results", []):
    print("\nTITLE:")
    print(result.get("title"))

    print("\nURL:")
    print(result.get("url"))

    print("\nCONTENT:")
    print(result.get("content"))

    print("\n" + "-" * 70)