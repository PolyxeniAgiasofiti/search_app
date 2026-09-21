from urllib.error import HTTPError

import ai_service
import manual_source_service

from manual_source_service import analyse_user_provided_source, validate_safe_url
from search_service import extract_url_content
from source_metadata_service import (
    detect_eurostat_custom_view,
    extract_eurostat_metadata_from_xml,
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

EUROSTAT_BOOKMARK_URL = (
    "https://ec.europa.eu/eurostat/databrowser/view/"
    "yth_demo_030__custom_22711535/bookmark/table?lang=en"
    "&bookmarkId=4e866041-fb81-4144-be5d-0f064c5edb21"
    "&c=1788854031000"
)


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


class FakeTavilyClient:

    def __init__(self):
        self.calls = []


    def extract(self, **kwargs):
        self.calls.append(
            kwargs
        )

        if kwargs.get(
            "extract_depth"
        ) == "basic":

            return {
                "results": [
                    {
                        "url": kwargs["urls"][0],
                        "raw_content": ""
                    }
                ]
            }

        return {
            "results": [
                {
                    "url": kwargs["urls"][0],
                    "raw_content": (
                        "Estimated average age of young people leaving the "
                        "parental household by sex. Official statistical "
                        "table with dimensions for sex, country, and year."
                    )
                }
            ]
        }


def test_private_url_is_rejected_before_inspection():

    try:
        validate_safe_url("http://127.0.0.1:8000/data.csv")
        assert False
    except ValueError:
        assert True


def test_extract_url_content_retries_advanced_after_empty_basic():

    client = FakeTavilyClient()

    result = extract_url_content(
        "https://example.org/data",
        definition="gerontocracy definition",
        tavily_client=client
    )

    assert result["status"] == "success"
    assert result["extract_depth"] == "advanced"
    assert client.calls[0]["urls"] == ["https://example.org/data"]
    assert client.calls[0]["extract_depth"] == "basic"
    assert client.calls[1]["urls"] == ["https://example.org/data"]
    assert client.calls[1]["extract_depth"] == "advanced"
    assert "Current approved definition" in client.calls[0]["query"]


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


def test_manual_url_uses_exact_tavily_extract_content():

    calls = []


    def fake_urlopen(request, timeout=10):
        return FakeResponse(
            request.full_url,
            b"<html><title>Dataset page</title></html>",
            "text/html"
        )


    def fake_extractor(url, definition=None):
        calls.append(
            {
                "url": url,
                "definition": definition
            }
        )
        return {
            "status": "success",
            "extract_depth": "basic",
            "provided_url": url,
            "final_url": url,
            "content": (
                "Dataset title: Estimated average age of young people "
                "leaving the parental household by sex. Publisher: Eurostat. "
                "This page provides an official statistical table with years, "
                "countries, and sex dimensions."
            ),
            "attempts": [
                {
                    "extract_depth": "basic",
                    "status": "success"
                }
            ]
        }


    def fake_analyzer(definition, targets, evidence):
        assert evidence["content_kind"] == "tavily_extract"
        assert evidence["extract_depth"] == "basic"
        assert "Estimated average age" in evidence["extracted_text"]

        return {
            "relevant": True,
            "useful_data_source": True,
            "validation_status": "validated",
            "reason": "Official table.",
            "proposed_data_target": "Estimated average age of young people leaving the parental household",
            "target_description": "Official statistical table about leaving the parental household.",
            "available_information": ["years", "countries", "sex"],
            "source_title": "Estimated average age of young people leaving the parental household by sex",
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
            "https://example.org/exact-url",
            analyzer_func=fake_analyzer,
            urlopen_func=fake_urlopen,
            extractor_func=fake_extractor
        )

    finally:
        manual_source_service.socket.getaddrinfo = original_getaddrinfo

    assert calls == [
        {
            "url": "https://example.org/exact-url",
            "definition": "gerontocracy definition"
        }
    ]
    assert result["accepted"] is True
    assert result["source_url"] == "https://example.org/exact-url"
    assert result["source_title"] == "Estimated average age of young people leaving the parental household by sex"


def test_tavily_extract_cookie_recipe_is_rejected():

    def fake_urlopen(request, timeout=10):
        return FakeResponse(
            request.full_url,
            b"<html><title>Cookies</title></html>",
            "text/html"
        )


    def fake_extractor(url, definition=None):
        return {
            "status": "success",
            "extract_depth": "basic",
            "content": (
                "Soft chocolate chip cookies. Ingredients include flour, "
                "sugar, butter, eggs, and chocolate. Bake for 12 minutes."
            )
        }


    def fake_analyzer(definition, targets, evidence):
        return {
            "relevant": False,
            "useful_data_source": False,
            "validation_status": "invalid",
            "reason": "Recipe content, not a data source.",
            "proposed_data_target": "",
            "target_description": "",
            "available_information": [],
            "source_title": "Soft chocolate chip cookies",
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
            "https://example.org/cookies",
            analyzer_func=fake_analyzer,
            urlopen_func=fake_urlopen,
            extractor_func=fake_extractor
        )

    finally:
        manual_source_service.socket.getaddrinfo = original_getaddrinfo

    assert result["accepted"] is False
    assert result["validation_status"] == "invalid"


def test_relevant_article_without_data_is_not_validated():

    def fake_urlopen(request, timeout=10):
        return FakeResponse(
            request.full_url,
            b"<html><title>Ageing article</title></html>",
            "text/html"
        )


    def fake_extractor(url, definition=None):
        return {
            "status": "success",
            "extract_depth": "advanced",
            "content": (
                "This article discusses population ageing and political power "
                "among older generations, but does not provide a table, API, "
                "download, database, or structured dataset."
            )
        }


    def fake_analyzer(definition, targets, evidence):
        return {
            "relevant": True,
            "useful_data_source": False,
            "validation_status": "needs_review",
            "reason": "Relevant article, but no structured data access.",
            "proposed_data_target": "Population ageing discussion",
            "target_description": "Article discussion without data access.",
            "available_information": [],
            "source_title": "Population ageing article",
            "publisher": "Example News",
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
            "https://example.org/article",
            analyzer_func=fake_analyzer,
            urlopen_func=fake_urlopen,
            extractor_func=fake_extractor
        )

    finally:
        manual_source_service.socket.getaddrinfo = original_getaddrinfo

    assert result["accepted"] is False
    assert result["validation_status"] == "needs_review"


def test_tavily_extract_failure_returns_needs_review_without_invented_title():

    def fake_urlopen(request, timeout=10):
        return FakeResponse(
            request.full_url,
            b"<html><title>JavaScript app</title><script></script></html>",
            "text/html"
        )


    def fake_extractor(url, definition=None):
        return {
            "status": "empty",
            "content": "",
            "attempts": [
                {
                    "extract_depth": "basic",
                    "status": "empty"
                },
                {
                    "extract_depth": "advanced",
                    "status": "empty"
                }
            ]
        }


    def fake_analyzer(definition, targets, evidence):
        return {
            "relevant": True,
            "useful_data_source": True,
            "validation_status": "validated",
            "reason": "Bad invented fallback.",
            "proposed_data_target": "Demographic Structure",
            "target_description": "Generic demographic structure.",
            "available_information": [],
            "source_title": "unknown",
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
            "https://example.org/js-app",
            analyzer_func=fake_analyzer,
            urlopen_func=fake_urlopen,
            extractor_func=fake_extractor
        )

    finally:
        manual_source_service.socket.getaddrinfo = original_getaddrinfo

    assert result["accepted"] is False
    assert result["validation_status"] == "needs_review"


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

    custom_view = detect_eurostat_custom_view(
        EUROSTAT_BOOKMARK_URL
    )

    assert extract_eurostat_dataset_code(
        EUROSTAT_BOOKMARK_URL
    ) == "yth_demo_030"
    assert custom_view["is_custom_view"] is True
    assert custom_view["raw_dataset_code"] == "yth_demo_030__custom_22711535"
    assert custom_view["bookmark_id"] == "4e866041-fb81-4144-be5d-0f064c5edb21"


def test_eurostat_bookmark_url_preserves_custom_state():

    official_title = (
        "Estimated average age of young persons leaving "
        "the parental household"
    )


    def fake_urlopen(request, timeout=10):

        if "/api/dissemination/" in request.full_url:

            return FakeResponse(
                request.full_url,
                json_bytes(
                    {
                        "version": "2.0",
                        "class": "dataset",
                        "label": official_title,
                        "extension": {
                            "id": "YTH_DEMO_030",
                            "description": "Official Eurostat indicator.",
                            "annotation": [
                                {
                                    "type": "OBS_PERIOD_OVERALL_OLDEST",
                                    "title": "2000"
                                },
                                {
                                    "type": "OBS_PERIOD_OVERALL_LATEST",
                                    "title": "2025"
                                }
                            ]
                        }
                    }
                ),
                "application/json"
            )

        return FakeResponse(
            request.full_url,
            b"<html><title>Eurostat Data Browser</title></html>",
            "text/html"
        )


    def fake_extractor(url, definition=None):
        assert url == EUROSTAT_BOOKMARK_URL
        return {
            "status": "success",
            "extract_depth": "advanced",
            "provided_url": url,
            "final_url": url,
            "content": (
                "Estimated average age of young persons leaving the parental "
                "household. Eurostat Data Browser table."
            )
        }


    def fake_analyzer(definition, targets, evidence):
        return {
            "relevant": True,
            "useful_data_source": True,
            "validation_status": "validated",
            "reason": "Official Eurostat table.",
            "proposed_data_target": "Estimated average age of young persons leaving the parental household",
            "target_description": "Official Eurostat indicator.",
            "available_information": ["Eurostat Data Browser table"],
            "source_title": official_title,
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
            EUROSTAT_BOOKMARK_URL,
            analyzer_func=fake_analyzer,
            urlopen_func=fake_urlopen,
            extractor_func=fake_extractor
        )

    finally:
        manual_source_service.socket.getaddrinfo = original_getaddrinfo

    assert result["accepted"] is True
    assert result["source_url"] == EUROSTAT_BOOKMARK_URL
    assert result["dataset_code"] == "yth_demo_030"
    assert result["source_title"] == official_title
    assert result["data_target"] == "Estimated average age of young persons leaving the parental household"
    assert result["is_custom_view"] is True
    assert result["bookmark_id"] == "4e866041-fb81-4144-be5d-0f064c5edb21"
    assert result["custom_selection_status"] == "unresolved"
    assert result["selected_dimensions"] == {}
    assert result["data_access_url"] is None


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


def test_eurostat_rdf_xml_metadata_uses_semantic_title_and_description():

    xml_payload = b"""
    <rdf:RDF
        xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
        xmlns:dct="http://purl.org/dc/terms/"
        xmlns:adms="http://www.w3.org/ns/adms#"
        xmlns:skos="http://www.w3.org/2004/02/skos/core#">
      <rdf:Description>
        <adms:identifier>
          <skos:notation>10.2908/YTH_DEMO_030</skos:notation>
        </adms:identifier>
        <dct:title>
          Estimated average age of young people leaving the parental household by sex
        </dct:title>
        <dct:description>
          &lt;p&gt;The indicator represents the age at which 50 % of the population
          no longer live in a household with their parent(s) (Source: EU-LFS).&lt;/p&gt;
        </dct:description>
        <dct:issued>2023-01-19</dct:issued>
      </rdf:Description>
    </rdf:RDF>
    """

    metadata = extract_eurostat_metadata_from_xml(
        xml_payload,
        "yth_demo_030"
    )

    assert metadata["source_title"] == (
        "Estimated average age of young people leaving "
        "the parental household by sex"
    )
    assert metadata["source_title"] != "10.2908/YTH_DEMO_030"
    assert metadata["description"] == (
        "The indicator represents the age at which 50 % of the population "
        "no longer live in a household with their parent(s) (Source: EU-LFS)."
    )
    assert metadata["time_coverage"] == "unknown"
    assert metadata["geographic_coverage"] == "unknown"


def test_eurostat_manual_source_ignores_metadata_issued_as_time_coverage():

    eurostat_url = (
        "https://ec.europa.eu/eurostat/databrowser/view/"
        "yth_demo_030__custom_22532746/default/table"
    )

    xml_payload = b"""
    <rdf:RDF
        xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
        xmlns:dct="http://purl.org/dc/terms/"
        xmlns:adms="http://www.w3.org/ns/adms#">
      <rdf:Description>
        <adms:identifier>10.2908/YTH_DEMO_030</adms:identifier>
        <dct:title>Estimated average age of young people leaving the parental household by sex</dct:title>
        <dct:description>&lt;p&gt;The indicator represents the age at which 50 % of the population no longer live in a household with their parent(s).&lt;/p&gt;</dct:description>
        <dct:issued>2023-01-19</dct:issued>
      </rdf:Description>
    </rdf:RDF>
    """


    def fake_urlopen(request, timeout=10):

        if "/api/dissemination/" in request.full_url:
            return FakeResponse(
                request.full_url,
                xml_payload,
                "application/rdf+xml"
            )

        return FakeResponse(
            request.full_url,
            b"<html><title>Eurostat Data Browser</title></html>",
            "text/html"
        )


    def fake_analyzer(definition, targets, evidence):
        return {
            "relevant": True,
            "useful_data_source": True,
            "validation_status": "validated",
            "reason": "Relevant official Eurostat data.",
            "proposed_data_target": "Demographic Structure",
            "target_description": "Generic demographic structure.",
            "available_information": [],
            "source_title": "unknown",
            "publisher": "Eurostat",
            "geographic_coverage": "Europe",
            "time_coverage": "2023-01-19",
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

    assert result["accepted"] is True
    assert result["source_title"] == (
        "Estimated average age of young people leaving "
        "the parental household by sex"
    )
    assert result["target_description"] == (
        "The indicator represents the age at which 50 % of the population "
        "no longer live in a household with their parent(s)."
    )
    assert result["time_coverage"] == "unknown"
    assert result["geographic_coverage"] == "unknown"


def test_json_observation_period_maps_to_time_coverage():

    metadata = resolve_eurostat_metadata(
        "https://ec.europa.eu/eurostat/databrowser/view/"
        "yth_demo_030/default/table",
        urlopen_func=lambda request, timeout=10: FakeResponse(
            request.full_url,
            json_bytes(
                {
                    "dataflows": [
                        {
                            "id": "YTH_DEMO_030",
                            "name": "Estimated average age of young people leaving the parental household by sex",
                            "OBS_PERIOD_OVERALL_OLDEST": "2000",
                            "OBS_PERIOD_OVERALL_LATEST": "2023"
                        }
                    ]
                }
            ),
            "application/json"
        )
    )

    assert metadata["time_coverage"] == "2000 to 2023"


def test_bad_ai_source_title_forces_needs_review():

    def fake_urlopen(request, timeout=10):
        return FakeResponse(
            request.full_url,
            b"metric,value\nage,42\n",
            "text/csv"
        )


    def fake_analyzer(definition, targets, evidence):
        return {
            "relevant": True,
            "useful_data_source": True,
            "validation_status": "validated",
            "reason": "Structured CSV.",
            "proposed_data_target": "Age metric",
            "target_description": "Age metric data.",
            "available_information": ["metric", "value"],
            "source_title": "<adms:identifier>10.2908/BAD</adms:identifier>",
            "publisher": "Example",
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

    assert result["accepted"] is False
    assert result["validation_status"] == "needs_review"


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


def test_manual_url_context_preserves_eurostat_bookmark_selection():

    calls = {
        "url_context": [],
        "extractor": []
    }


    def fake_urlopen(request, timeout=10):
        if "api.db.nomics.world" in request.full_url:
            return FakeResponse(
                request.full_url,
                json_bytes(
                    {
                        "datasets": {
                            "docs": [
                                {
                                    "code": "yth_demo_030",
                                    "name": (
                                        "Estimated average age of young persons "
                                        "leaving the parental household"
                                    ),
                                    "description": "Eurostat mirrored dataset."
                                }
                            ]
                        }
                    }
                ),
                "application/json"
            )

        return FakeResponse(
            request.full_url,
            b"<html><title>Eurostat Data Browser</title></html>",
            "text/html"
        )


    def fake_url_context(definition, targets, url):
        calls["url_context"].append(
            url
        )
        return {
            "analysis": {
                "relevant": True,
                "useful_data_source": True,
                "validation_status": "validated",
                "source_title": (
                    "Estimated average age of young persons leaving the "
                    "parental household"
                ),
                "publisher": "Eurostat",
                "proposed_data_target": (
                    "Estimated average age of young persons leaving the "
                    "parental household"
                ),
                "description": "Official Eurostat Data Browser table.",
                "dataset_code": "yth_demo_030",
                "available_information": [
                    "2025 values by reporting country"
                ],
                "geographic_coverage": "34/36 reporting entities displayed",
                "time_coverage": "2025",
                "selected_dimensions": {
                    "time": ["2025"],
                    "sex": ["Total"],
                    "unit": ["Average"],
                    "freq": ["Annual"],
                    "geo": ["34/36 values displayed"]
                },
                "custom_selection_status": "resolved",
                "format": "table",
                "source_type": "statistical_authority",
                "bookmark_id": "4e866041-fb81-4144-be5d-0f064c5edb21",
                "is_custom_view": True,
                "reason": "The URL Context result retrieved the exact Eurostat table."
            },
            "url_context_metadata": [
                {
                    "retrieved_url": EUROSTAT_BOOKMARK_URL,
                    "url_retrieval_status": "URL_RETRIEVAL_STATUS_SUCCESS"
                }
            ]
        }


    def fake_extractor(url, definition=None):
        calls["extractor"].append(
            url
        )
        return {
            "status": "error"
        }


    original_getaddrinfo = manual_source_service.socket.getaddrinfo

    try:
        manual_source_service.socket.getaddrinfo = lambda *_: PUBLIC_TEST_ADDRESS

        result = analyse_user_provided_source(
            "gerontocracy definition",
            [],
            EUROSTAT_BOOKMARK_URL,
            urlopen_func=fake_urlopen,
            extractor_func=fake_extractor,
            url_context_func=fake_url_context
        )

    finally:
        manual_source_service.socket.getaddrinfo = original_getaddrinfo

    assert calls["url_context"] == [EUROSTAT_BOOKMARK_URL]
    assert calls["extractor"] == []
    assert result["accepted"] is True
    assert result["source_url"] == EUROSTAT_BOOKMARK_URL
    assert result["publisher"] == "Eurostat"
    assert result["dataset_code"] == "yth_demo_030"
    assert result["bookmark_id"] == "4e866041-fb81-4144-be5d-0f064c5edb21"
    assert result["custom_selection_status"] == "resolved"
    assert result["retrieval_scope"] == "bookmark_selection"
    assert result["selected_dimensions"]["time"] == ["2025"]
    assert result["selected_dimensions"]["sex"] == ["Total"]
    assert result["selected_dimensions"]["unit"] == ["Average"]
    assert result["selected_dimensions"]["freq"] == ["Annual"]
    assert result["source_title"] == (
        "Estimated average age of young persons leaving the parental household"
    )


def test_unresolved_eurostat_bookmark_uses_dbnomics_only_for_data_access():

    def fake_urlopen(request, timeout=10):
        if "api.db.nomics.world" in request.full_url:
            return FakeResponse(
                request.full_url,
                json_bytes(
                    {
                        "datasets": {
                            "docs": [
                                {
                                    "code": "yth_demo_030",
                                    "name": (
                                        "Estimated average age of young persons "
                                        "leaving the parental household"
                                    ),
                                    "description": "Eurostat mirrored dataset."
                                }
                            ]
                        }
                    }
                ),
                "application/json"
            )

        return FakeResponse(
            request.full_url,
            b"<html><title>Server temporarily unavailable</title></html>",
            "text/html"
        )


    def fake_url_context(definition, targets, url):
        return {
            "analysis": {
                "relevant": True,
                "useful_data_source": True,
                "validation_status": "needs_review",
                "source_title": None,
                "publisher": "Eurostat",
                "proposed_data_target": (
                    "Estimated average age of young persons leaving the "
                    "parental household"
                ),
                "description": None,
                "dataset_code": "yth_demo_030",
                "available_information": [],
                "geographic_coverage": None,
                "time_coverage": None,
                "selected_dimensions": {},
                "custom_selection_status": "unresolved",
                "format": "table",
                "source_type": "statistical_authority",
                "bookmark_id": "4e866041-fb81-4144-be5d-0f064c5edb21",
                "is_custom_view": True,
                "reason": "The custom table filters could not be extracted."
            },
            "url_context_metadata": [
                {
                    "retrieved_url": EUROSTAT_BOOKMARK_URL,
                    "url_retrieval_status": "success"
                }
            ]
        }


    original_getaddrinfo = manual_source_service.socket.getaddrinfo

    try:
        manual_source_service.socket.getaddrinfo = lambda *_: PUBLIC_TEST_ADDRESS

        result = analyse_user_provided_source(
            "gerontocracy definition",
            [],
            EUROSTAT_BOOKMARK_URL,
            urlopen_func=fake_urlopen,
            url_context_func=fake_url_context
        )

    finally:
        manual_source_service.socket.getaddrinfo = original_getaddrinfo

    assert result["accepted"] is True
    assert result["validation_status"] == "validated"
    assert result["source_url"] == EUROSTAT_BOOKMARK_URL
    assert result["publisher"] == "Eurostat"
    assert result["source_title"] == (
        "Estimated average age of young persons leaving the parental household"
    )
    assert result["data_access_url"] == (
        "https://api.db.nomics.world/v22/series/Eurostat/yth_demo_030/"
        "A.AVG.T?observations=1"
    )
    assert result["data_access_provider"] == "DB.nomics"
    assert result["data_access_role"] == "mirror"
    assert result["retrieval_scope"] == "dataset"
    assert result["custom_selection_status"] == "unresolved"
    assert result["selected_dimensions"] == {}


def test_manual_url_context_failure_falls_back_to_extract():

    calls = {
        "extractor": []
    }


    def fake_urlopen(request, timeout=10):
        return FakeResponse(
            request.full_url,
            b"id,value\nage,1\n",
            "text/csv"
        )


    def fake_url_context(definition, targets, url):
        return {
            "analysis": {
                "relevant": True,
                "useful_data_source": True,
                "validation_status": "validated",
                "source_title": "Unverified title"
            },
            "url_context_metadata": [
                {
                    "retrieved_url": url,
                    "url_retrieval_status": "URL_RETRIEVAL_STATUS_ERROR"
                }
            ]
        }


    def fake_extractor(url, definition=None):
        calls["extractor"].append(
            url
        )
        return {
            "status": "success",
            "provided_url": url,
            "final_url": url,
            "content": "Age CSV with useful structured data."
        }


    def fake_analyzer(definition, targets, evidence):
        return {
            "relevant": True,
            "useful_data_source": True,
            "validation_status": "validated",
            "reason": "Fallback extract contains data.",
            "proposed_data_target": "Age data",
            "target_description": "CSV age data.",
            "available_information": ["age", "value"],
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
            urlopen_func=fake_urlopen,
            extractor_func=fake_extractor,
            url_context_func=fake_url_context
        )

    finally:
        manual_source_service.socket.getaddrinfo = original_getaddrinfo

    assert calls["extractor"] == ["https://example.org/data.csv"]
    assert result["accepted"] is True
    assert result["source_title"] == "Age CSV"


def test_url_context_ai_call_uses_url_context_without_google_search():

    captured = {}


    class FakeInteraction:

        output_text = (
            '{"relevant": false, "useful_data_source": false, '
            '"validation_status": "invalid"}'
        )

        def model_dump(self, mode="json", exclude_none=True):
            return {
                "candidates": [
                    {
                        "urlContextMetadata": {
                            "urlMetadata": [
                                {
                                    "retrievedUrl": EUROSTAT_BOOKMARK_URL,
                                    "urlRetrievalStatus": (
                                        "URL_RETRIEVAL_STATUS_SUCCESS"
                                    )
                                }
                            ]
                        }
                    }
                ]
            }


    class FakeInteractions:

        def create(self, **kwargs):
            captured.update(
                kwargs
            )
            return FakeInteraction()


    class FakeClient:

        interactions = FakeInteractions()


    original_client = ai_service.client

    try:
        ai_service.client = FakeClient()

        result = ai_service.analyze_manual_source_url_context(
            "gerontocracy definition",
            [],
            EUROSTAT_BOOKMARK_URL
        )

    finally:
        ai_service.client = original_client

    assert captured["tools"] == [
        {
            "type": "url_context"
        }
    ]
    assert "google_search" not in str(
        captured["tools"]
    )
    assert result["url_context_metadata"] == [
        {
            "retrieved_url": EUROSTAT_BOOKMARK_URL,
            "url_retrieval_status": "URL_RETRIEVAL_STATUS_SUCCESS"
        }
    ]


def json_bytes(value):
    import json

    return json.dumps(value).encode("utf-8")


if __name__ == "__main__":
    test_private_url_is_rejected_before_inspection()
    test_extract_url_content_retries_advanced_after_empty_basic()
    test_valid_csv_source_can_be_added()
    test_manual_url_uses_exact_tavily_extract_content()
    test_tavily_extract_cookie_recipe_is_rejected()
    test_relevant_article_without_data_is_not_validated()
    test_tavily_extract_failure_returns_needs_review_without_invented_title()
    test_irrelevant_source_is_not_added()
    test_broken_url_is_not_added()
    test_eurostat_databrowser_uses_official_metadata_title()
    test_eurostat_custom_code_normalization()
    test_eurostat_bookmark_url_preserves_custom_state()
    test_eurostat_metadata_fallback_succeeds_after_dataflow_failure()
    test_eurostat_metadata_all_methods_fail_with_diagnostics()
    test_eurostat_rdf_xml_metadata_uses_semantic_title_and_description()
    test_eurostat_manual_source_ignores_metadata_issued_as_time_coverage()
    test_json_observation_period_maps_to_time_coverage()
    test_bad_ai_source_title_forces_needs_review()
    test_eurostat_manual_source_needs_review_when_metadata_fails()
    test_manual_url_context_preserves_eurostat_bookmark_selection()
    test_unresolved_eurostat_bookmark_uses_dbnomics_only_for_data_access()
    test_manual_url_context_failure_falls_back_to_extract()
    test_url_context_ai_call_uses_url_context_without_google_search()
    print("manual source service tests passed")
