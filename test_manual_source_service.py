from urllib.error import HTTPError

import manual_source_service

from manual_source_service import analyse_user_provided_source, validate_safe_url
from source_metadata_service import (
    extract_eurostat_dataset_code,
    normalize_eurostat_dataset_code,
    resolve_eurostat_metadata
)


PUBLIC_TEST_ADDRESS = [
    (
        None,
        None,
        None,
        "",
        (
            "93.184.216.34",
            0
        )
    )
]


class FakeHeaders(dict):

    def get(self, key, default=None):
        return super().get(key, default)


class FakeResponse:

    def __init__(
        self,
        url,
        body,
        content_type="text/csv",
        status=200
    ):
        self._url = url
        self._body = body
        self._status = status
        self.headers = FakeHeaders(
            {
                "Content-Type": content_type,
                "Content-Length": str(len(body))
            }
        )


    def __enter__(self):
        return self


    def __exit__(self, exc_type, exc, tb):
        return False


    def read(self, size=-1):
        if not self._body:
            return b""

        if size < 0:
            body = self._body
            self._body = b""
            return body

        body = self._body[:size]
        self._body = self._body[size:]
        return body


    def geturl(self):
        return self._url


    def getcode(self):
        return self._status


def test_private_url_is_rejected_before_inspection():

    try:
        validate_safe_url("http://127.0.0.1:8000/data.csv")
        assert False
    except ValueError:
        assert True


def test_valid_csv_source_can_be_added():

    def fake_urlopen(request, timeout=10):
        return FakeResponse(
            request.full_url,
            b"age_group,value\n65-74,10\n75-84,8\n",
            "text/csv"
        )


    def fake_analyzer(definition, targets, evidence):
        assert evidence["content_kind"] == "csv"
        assert evidence["headers"] == ["age_group", "value"]

        return {
            "relevant": True,
            "useful_data_source": True,
            "validation_status": "validated",
            "reason": "Contains age-group data.",
            "proposed_data_target": "Age-group values",
            "target_description": "Values by age group.",
            "available_information": ["age_group", "value"],
            "source_title": "Age CSV",
            "publisher": "Example Publisher",
            "geographic_coverage": "unknown",
            "time_coverage": "unknown",
            "source_type": "public_research",
            "data_access_type": "csv"
        }


    original_getaddrinfo = manual_source_service.socket.getaddrinfo

    try:
        manual_source_service.socket.getaddrinfo = lambda *_: PUBLIC_TEST_ADDRESS

        result = analyse_user_provided_source(
            "gerontocracy definition",
            [],
            "https://example.org/data.csv",
            analyzer_func=fake_analyzer,
            urlopen_func=fake_urlopen
        )

    finally:
        manual_source_service.socket.getaddrinfo = original_getaddrinfo

    assert result["accepted"] is True
    assert result["validation_status"] == "validated"
    assert result["source_url"] == "https://example.org/data.csv"


def test_irrelevant_source_is_not_added():

    def fake_urlopen(request, timeout=10):
        return FakeResponse(
            request.full_url,
            b"<html><title>Recipe</title><p>Cookies and sugar.</p></html>",
            "text/html"
        )


    def fake_analyzer(definition, targets, evidence):
        return {
            "relevant": False,
            "useful_data_source": False,
            "validation_status": "invalid",
            "reason": "Recipe page, not a data source.",
            "proposed_data_target": "",
            "target_description": "",
            "available_information": [],
            "source_title": "Recipe",
            "publisher": "unknown",
            "geographic_coverage": "unknown",
            "time_coverage": "unknown",
            "source_type": "unknown",
            "data_access_type": "unknown"
        }


    original_getaddrinfo = manual_source_service.socket.getaddrinfo

    try:
        manual_source_service.socket.getaddrinfo = lambda *_: PUBLIC_TEST_ADDRESS

        result = analyse_user_provided_source(
            "gerontocracy definition",
            [],
            "https://example.org/recipe",
            analyzer_func=fake_analyzer,
            urlopen_func=fake_urlopen
        )

    finally:
        manual_source_service.socket.getaddrinfo = original_getaddrinfo

    assert result["accepted"] is False
    assert result["validation_status"] == "invalid"


def test_broken_url_is_not_added():

    def fake_urlopen(request, timeout=10):
        raise HTTPError(
            request.full_url,
            404,
            "Not Found",
            {},
            None
        )


    original_getaddrinfo = manual_source_service.socket.getaddrinfo

    try:
        manual_source_service.socket.getaddrinfo = lambda *_: PUBLIC_TEST_ADDRESS

        result = analyse_user_provided_source(
            "gerontocracy definition",
            [],
            "https://example.org/missing.csv",
            analyzer_func=lambda *_: {},
            urlopen_func=fake_urlopen
        )

    finally:
        manual_source_service.socket.getaddrinfo = original_getaddrinfo

    assert result["accepted"] is False
    assert result["validation_status"] == "invalid"
    assert result["link_status"] == "broken"


def test_eurostat_databrowser_uses_official_metadata_title():

    eurostat_url = (
        "https://ec.europa.eu/eurostat/databrowser/view/"
        "YTH_DEMO_030/default/table?lang=en"
    )

    official_title = (
        "Estimated average age of young persons leaving "
        "the parental household by sex"
    )


    def fake_urlopen(request, timeout=10):

        if "/api/dissemination/" in request.full_url:

            return FakeResponse(
                request.full_url,
                json_bytes(
                    {
                        "dataflows": [
                            {
                                "id": "YTH_DEMO_030",
                                "name": official_title
                            }
                        ]
                    }
                ),
                "application/json"
            )

        return FakeResponse(
            request.full_url,
            b"<html><title>Eurostat Data Browser</title></html>",
            "text/html"
        )


    def fake_analyzer(definition, targets, evidence):
        assert evidence["provider_metadata"]["dataset_code"] == "yth_demo_030"
        assert evidence["provider_metadata"]["source_title"] == official_title

        return {
            "relevant": True,
            "useful_data_source": True,
            "validation_status": "validated",
            "reason": "Official Eurostat table relevant to the topic.",
            "proposed_data_target": "Demographic Structure Data",
            "target_description": "Generic demographic structure data.",
            "available_information": [],
            "source_title": "unknown",
            "publisher": "Eurostat",
            "geographic_coverage": "unknown",
            "time_coverage": "unknown",
            "source_type": "statistical_authority",
            "data_access_type": "table"
        }


    original_getaddrinfo = manual_source_service.socket.getaddrinfo

    try:
        manual_source_service.socket.getaddrinfo = lambda *_: PUBLIC_TEST_ADDRESS

        result = analyse_user_provided_source(
            "gerontocracy definition",
            [],
            eurostat_url,
            analyzer_func=fake_analyzer,
            urlopen_func=fake_urlopen
        )

    finally:
        manual_source_service.socket.getaddrinfo = original_getaddrinfo

    assert extract_eurostat_dataset_code(eurostat_url) == "yth_demo_030"
    assert result["accepted"] is True
    assert result["source_url"] == eurostat_url
    assert result["source_title"] == official_title
    assert result["data_target"] == official_title
    assert result["publisher"] == "Eurostat"
    assert result["source_type"] == "statistical_authority"
    assert result["data_access_type"] == "table"


def test_eurostat_custom_code_normalization():

    assert normalize_eurostat_dataset_code(
        "yth_demo_030__custom_22532746"
    ) == "yth_demo_030"

    assert extract_eurostat_dataset_code(
        "https://ec.europa.eu/eurostat/databrowser/view/"
        "yth_demo_030__custom_22532746/default/table"
    ) == "yth_demo_030"

    assert extract_eurostat_dataset_code(
        "https://ec.europa.eu/eurostat/databrowser/view/"
        "yth_demo_030/default/table"
    ) == "yth_demo_030"

    assert extract_eurostat_dataset_code(
        "https://ec.europa.eu/eurostat/databrowser/view/"
        "lfsa_ergaed__custom_123456/default/table"
    ) == "lfsa_ergaed"


def test_eurostat_metadata_fallback_succeeds_after_dataflow_failure():

    title = "Fallback official Eurostat title"


    def fake_urlopen(request, timeout=10):

        if "dataflow" in request.full_url:
            raise HTTPError(
                request.full_url,
                404,
                "Not Found",
                {},
                None
            )

        return FakeResponse(
            request.full_url,
            json_bytes(
                {
                    "label": title,
                    "id": ["freq", "geo", "time"]
                }
            ),
            "application/json"
        )


    metadata = resolve_eurostat_metadata(
        "https://ec.europa.eu/eurostat/databrowser/view/"
        "yth_demo_030__custom_22532746/default/table",
        urlopen_func=fake_urlopen
    )

    assert metadata["dataset_code"] == "yth_demo_030"
    assert metadata["raw_dataset_code"] == "yth_demo_030__custom_22532746"
    assert metadata["source_title"] == title
    assert metadata["metadata_method_attempted"] == "statistics_data"
    assert len(metadata["diagnostics"]) >= 2


def test_eurostat_metadata_all_methods_fail_with_diagnostics():

    def fake_urlopen(request, timeout=10):
        raise HTTPError(
            request.full_url,
            404,
            "Not Found",
            {},
            None
        )


    metadata = resolve_eurostat_metadata(
        "https://ec.europa.eu/eurostat/databrowser/view/"
        "yth_demo_030__custom_22532746/default/table",
        urlopen_func=fake_urlopen
    )

    assert "source_title" not in metadata
    assert metadata["dataset_code"] == "yth_demo_030"
    assert metadata["raw_dataset_code"] == "yth_demo_030__custom_22532746"
    assert metadata["metadata_error"] == "Official Eurostat metadata could not be resolved."
    assert metadata["failure_reason"] == "All official Eurostat metadata lookup methods failed."
    assert len(metadata["diagnostics"]) >= 3


def test_eurostat_manual_source_needs_review_when_metadata_fails():

    eurostat_url = (
        "https://ec.europa.eu/eurostat/databrowser/view/"
        "yth_demo_030__custom_22532746/default/table"
    )


    def fake_urlopen(request, timeout=10):

        if "/api/dissemination/" in request.full_url:
            raise HTTPError(
                request.full_url,
                404,
                "Not Found",
                {},
                None
            )

        return FakeResponse(
            request.full_url,
            b"<html><title>Eurostat Data Browser</title></html>",
            "text/html"
        )


    original_getaddrinfo = manual_source_service.socket.getaddrinfo

    try:
        manual_source_service.socket.getaddrinfo = lambda *_: PUBLIC_TEST_ADDRESS

        result = analyse_user_provided_source(
            "gerontocracy definition",
            [],
            eurostat_url,
            analyzer_func=lambda *_: {},
            urlopen_func=fake_urlopen
        )

    finally:
        manual_source_service.socket.getaddrinfo = original_getaddrinfo

    assert result["accepted"] is False
    assert result["validation_status"] == "needs_review"
    assert result["link_status"] == "reachable"
    assert result["publisher"] == "Eurostat"
    assert result["source_type"] == "statistical_authority"


def json_bytes(value):
    import json

    return json.dumps(value).encode("utf-8")


if __name__ == "__main__":
    test_private_url_is_rejected_before_inspection()
    test_valid_csv_source_can_be_added()
    test_irrelevant_source_is_not_added()
    test_broken_url_is_not_added()
    test_eurostat_databrowser_uses_official_metadata_title()
    test_eurostat_custom_code_normalization()
    test_eurostat_metadata_fallback_succeeds_after_dataflow_failure()
    test_eurostat_metadata_all_methods_fail_with_diagnostics()
    test_eurostat_manual_source_needs_review_when_metadata_fails()
    print("manual source service tests passed")
