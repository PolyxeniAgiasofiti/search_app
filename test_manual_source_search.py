import data_service


def test_user_provided_url_is_kept_and_deduplicates_discovered_source():

    def fake_fetch_source(url):
        return {
            "status": "reachable",
            "final_url": url
        }


    def fake_build_search_query(topic, target):
        return "query"


    def fake_search_web(query, max_results=10):
        return [
            {
                "url": "https://example.org/manual.csv",
                "title": "Duplicate"
            }
        ]


    def fake_evaluate_search_results(topic, data_target, search_results):
        return {
            "datasets": [
                {
                    "data_target": "Age data",
                    "title": "Duplicate discovered source",
                    "publisher": "Example",
                    "source_url": "https://example.org/manual.csv",
                    "description": "Duplicate of the manual URL.",
                    "geographic_coverage": "unknown",
                    "time_coverage": "unknown",
                    "format": "csv",
                    "official_source": True,
                    "actual_data_access": True,
                    "source_type": "public_research",
                    "data_access_type": "csv"
                }
            ]
        }


    original_fetch_source = data_service.fetch_source
    original_build_search_query = data_service.build_search_query
    original_search_web = data_service.search_web
    original_evaluate_search_results = data_service.evaluate_search_results

    try:
        data_service.fetch_source = fake_fetch_source
        data_service.build_search_query = fake_build_search_query
        data_service.search_web = fake_search_web
        data_service.evaluate_search_results = fake_evaluate_search_results

        result = data_service.search_public_datasets(
            topic="gerontocracy",
            data_targets=[
                {
                    "name": "Age data",
                    "reason": "Need age-group data.",
                    "origin": "user_provided",
                    "provided_source_url": "https://example.org/manual.csv",
                    "source_title": "Manual CSV",
                    "publisher": "Example",
                    "validation_status": "validated",
                    "source_type": "public_research",
                    "data_access_type": "csv"
                }
            ]
        )

    finally:
        data_service.fetch_source = original_fetch_source
        data_service.build_search_query = original_build_search_query
        data_service.search_web = original_search_web
        data_service.evaluate_search_results = original_evaluate_search_results

    datasets = result["datasets"]

    assert len(datasets) == 1
    assert datasets[0]["source_url"] == "https://example.org/manual.csv"
    assert datasets[0]["source_origin"] == "user_provided"


if __name__ == "__main__":
    test_user_provided_url_is_kept_and_deduplicates_discovered_source()
    print("manual source search tests passed")
