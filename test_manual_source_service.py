from urllib.error import HTTPError

import manual_source_service

from manual_source_service import analyse_user_provided_source, validate_safe_url


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


if __name__ == "__main__":
    test_private_url_is_rejected_before_inspection()
    test_valid_csv_source_can_be_added()
    test_irrelevant_source_is_not_added()
    test_broken_url_is_not_added()
    print("manual source service tests passed")
