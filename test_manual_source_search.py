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


def test_user_provided_metadata_survives_public_data_search():

    official_title = (
        "Estimated average age of young people leaving "
        "the parental household by sex"
    )
    bookmark_url = (
        "https://ec.europa.eu/eurostat/databrowser/view/"
        "yth_demo_030__custom_22711535/bookmark/table?lang=en"
        "&bookmarkId=4e866041-fb81-4144-be5d-0f064c5edb21"
        "&c=1788854031000"
    )


    def fake_fetch_source(url):
        return {
            "status": "reachable",
            "final_url": url
        }


    def fake_build_search_query(topic, target):
        return "query"


    def fake_search_web(query, max_results=10):
        return []


    def fake_evaluate_search_results(topic, data_target, search_results):
        return {
            "datasets": []
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
                    "name": "Estimated average age of young people leaving the parental household",
                    "reason": official_title,
                    "origin": "user_provided",
                    "provided_source_url": bookmark_url,
                    "source_title": official_title,
                    "publisher": "Eurostat",
                    "source_description": official_title,
                    "geographic_coverage": "unknown",
                    "time_coverage": "unknown",
                    "format": "table",
                    "dataset_code": "yth_demo_030",
                    "doi": "10.2908/YTH_DEMO_030",
                    "validation_reason": "Official Eurostat metadata resolved.",
                    "validation_status": "validated",
                    "source_type": "statistical_authority",
                    "data_access_type": "table",
                    "is_custom_view": True,
                    "bookmark_id": "4e866041-fb81-4144-be5d-0f064c5edb21",
                    "custom_selection_status": "unresolved",
                    "selected_dimensions": {}
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
    assert datasets[0]["title"] == official_title
    assert datasets[0]["title"] != "unknown"
    assert datasets[0]["publisher"] == "Eurostat"
    assert datasets[0]["format"] == "table"
    assert datasets[0]["dataset_code"] == "yth_demo_030"
    assert datasets[0]["doi"] == "10.2908/YTH_DEMO_030"
    assert datasets[0]["validation_reason"] == "Official Eurostat metadata resolved."
    assert datasets[0]["source_origin"] == "user_provided"
    assert datasets[0]["source_url"] == bookmark_url
    assert datasets[0]["is_custom_view"] is True
    assert datasets[0]["bookmark_id"] == "4e866041-fb81-4144-be5d-0f064c5edb21"
    assert datasets[0]["custom_selection_status"] == "unresolved"
    assert datasets[0]["selected_dimensions"] == {}


if __name__ == "__main__":
    test_user_provided_url_is_kept_and_deduplicates_discovered_source()
    test_user_provided_metadata_survives_public_data_search()
    print("manual source search tests passed")
