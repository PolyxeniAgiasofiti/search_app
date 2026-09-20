import unittest
from urllib.error import HTTPError

from database import update_dataset_review_status
from validation import (
    check_source_link,
    validate_dataset_candidate
)


class FakeResponse:

    def __init__(
        self,
        status_code,
        final_url="https://example.gov/data"
    ):

        self.status_code = status_code
        self.final_url = final_url


    def __enter__(self):

        return self


    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback
    ):

        return False


    def getcode(self):

        return self.status_code


    def geturl(self):

        return self.final_url


def make_candidate(
    url="https://example.gov/data",
    official_source=True,
    actual_data_access=True,
    geographic_match=True,
    data_access_type="dataset"
):

    return {
        "data_target":
            "Population age structure",

        "title":
            "Example dataset",

        "publisher":
            "Example statistical authority",

        "source_url":
            url,

        "description":
            "Example description",

        "geographic_coverage":
            "Example geography",

        "time_coverage":
            "Example time coverage",

        "format":
            "table",

        "source_type":
            "statistical_authority",

        "data_access_type":
            data_access_type,

        "official_source":
            official_source,

        "actual_data_access":
            actual_data_access,

        "geographic_match":
            geographic_match
    }


class ValidationTest(unittest.TestCase):

    def test_official_direct_dataset_can_pass(self):

        candidate = make_candidate(
            data_access_type="dataset"
        )

        result = validate_dataset_candidate(
            candidate,
            real_urls={
                candidate["source_url"]
            },
            seen_urls=set(),
            check_link=False
        )

        self.assertTrue(
            result["accepted"]
        )

        self.assertEqual(
            result["dataset"]["data_access_type"],
            "dataset"
        )


    def test_blocked_domain_is_invalid(self):

        candidate = make_candidate(
            url="https://worldometers.info/population"
        )

        result = validate_dataset_candidate(
            candidate,
            real_urls={
                "https://worldometers.info/population"
            },
            seen_urls=set(),
            check_link=False
        )

        self.assertFalse(
            result["accepted"]
        )

        self.assertEqual(
            result["validation_status"],
            "invalid"
        )


    def test_url_must_come_from_tavily_results(self):

        result = validate_dataset_candidate(
            make_candidate(),
            real_urls={
                "https://example.gov/other"
            },
            seen_urls=set(),
            check_link=False
        )

        self.assertFalse(
            result["accepted"]
        )


    def test_semantic_flags_are_required(self):

        for flag in [
            "official_source",
            "actual_data_access",
            "geographic_match"
        ]:

            candidate = make_candidate()
            candidate[flag] = False

            result = validate_dataset_candidate(
                candidate,
                real_urls={
                    candidate["source_url"]
                },
                seen_urls=set(),
                check_link=False
            )

            self.assertFalse(
                result["accepted"]
            )

            self.assertEqual(
                result["validation_status"],
                "invalid"
            )


    def test_informational_article_without_data_access_is_rejected(self):

        candidate = make_candidate(
            actual_data_access=False,
            data_access_type="unknown"
        )

        result = validate_dataset_candidate(
            candidate,
            real_urls={
                candidate["source_url"]
            },
            seen_urls=set(),
            check_link=False
        )

        self.assertFalse(
            result["accepted"]
        )


    def test_unknown_data_access_type_is_rejected(self):

        candidate = make_candidate(
            actual_data_access=True,
            data_access_type="unknown"
        )

        result = validate_dataset_candidate(
            candidate,
            real_urls={
                candidate["source_url"]
            },
            seen_urls=set(),
            check_link=False
        )

        self.assertFalse(
            result["accepted"]
        )


    def test_duplicate_url_is_rejected(self):

        candidate = make_candidate()

        result = validate_dataset_candidate(
            candidate,
            real_urls={
                candidate["source_url"]
            },
            seen_urls={
                candidate["source_url"]
            },
            check_link=False
        )

        self.assertFalse(
            result["accepted"]
        )


    def test_link_status_mapping(self):

        def ok_urlopen(
            request,
            timeout
        ):

            return FakeResponse(
                200
            )


        def forbidden_urlopen(
            request,
            timeout
        ):

            raise HTTPError(
                request.full_url,
                403,
                "Forbidden",
                hdrs=None,
                fp=None
            )


        def missing_urlopen(
            request,
            timeout
        ):

            raise HTTPError(
                request.full_url,
                404,
                "Not Found",
                hdrs=None,
                fp=None
            )


        def timeout_urlopen(
            request,
            timeout
        ):

            raise TimeoutError(
                "timed out"
            )


        self.assertEqual(
            check_source_link(
                "https://example.gov/data",
                urlopen_func=ok_urlopen
            )["link_status"],
            "reachable"
        )

        self.assertEqual(
            check_source_link(
                "https://example.gov/data",
                urlopen_func=forbidden_urlopen
            )["link_status"],
            "restricted"
        )

        self.assertEqual(
            check_source_link(
                "https://example.gov/data",
                urlopen_func=missing_urlopen
            )["link_status"],
            "broken"
        )

        self.assertEqual(
            check_source_link(
                "https://example.gov/data",
                urlopen_func=timeout_urlopen
            )["link_status"],
            "error"
        )


    def test_broken_link_makes_candidate_invalid(self):

        def missing_urlopen(
            request,
            timeout
        ):

            raise HTTPError(
                request.full_url,
                404,
                "Not Found",
                hdrs=None,
                fp=None
            )


        candidate = make_candidate()

        result = validate_dataset_candidate(
            candidate,
            real_urls={
                candidate["source_url"]
            },
            seen_urls=set(),
            urlopen_func=missing_urlopen
        )

        self.assertFalse(
            result["accepted"]
        )

        self.assertEqual(
            result["validation_status"],
            "invalid"
        )


    def test_restricted_link_needs_review(self):

        def forbidden_urlopen(
            request,
            timeout
        ):

            raise HTTPError(
                request.full_url,
                403,
                "Forbidden",
                hdrs=None,
                fp=None
            )


        candidate = make_candidate()

        result = validate_dataset_candidate(
            candidate,
            real_urls={
                candidate["source_url"]
            },
            seen_urls=set(),
            urlopen_func=forbidden_urlopen
        )

        self.assertTrue(
            result["accepted"]
        )

        self.assertEqual(
            result["validation_status"],
            "needs_review"
        )


    def test_invalid_review_status_is_rejected(self):

        with self.assertRaises(
            ValueError
        ):

            update_dataset_review_status(
                dataset_id=1,
                review_status="not_a_real_status"
            )


if __name__ == "__main__":
    unittest.main()
