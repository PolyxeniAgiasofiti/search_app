import datetime
import io
import json
import unittest

from ingestion_service import (
    MAX_STORED_ROWS,
    build_eurostat_api_url,
    discover_data_resources,
    normalise_value,
    parse_csv_bytes,
    parse_html_table_bytes,
    parse_json_bytes,
    parse_xlsx_bytes,
    retrieve_dataset
)
from source_metadata_service import (
    detect_eurostat_custom_view,
    extract_eurostat_dataset_code
)


EUROSTAT_BOOKMARK_URL = (
    "https://ec.europa.eu/eurostat/databrowser/view/"
    "yth_demo_030__custom_22711535/bookmark/table?lang=en"
    "&bookmarkId=4e866041-fb81-4144-be5d-0f064c5edb21"
    "&c=1788854031000"
)


class FakeHeaders:

    def __init__(
        self,
        values
    ):

        self.values = values


    def get(
        self,
        key,
        default=None
    ):

        return self.values.get(
            key,
            default
        )


class FakeResponse:

    def __init__(
        self,
        content,
        url="https://example.gov/data.csv",
        content_type="text/csv",
        content_length=None
    ):

        self.content = io.BytesIO(
            content
        )
        self.url = url
        self.headers = FakeHeaders(
            {
                "Content-Type":
                    content_type,

                "Content-Length":
                    str(
                        content_length
                    )
                    if content_length is not None
                    else
                    str(
                        len(
                            content
                        )
                    )
            }
        )


    def __enter__(self):

        return self


    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback
    ):

        return False


    def read(
        self,
        size=-1
    ):

        return self.content.read(
            size
        )


    def geturl(self):

        return self.url


class IngestionServiceTest(unittest.TestCase):

    def test_csv_parsing(self):

        rows = parse_csv_bytes(
            b"name,age\nAlice,30\nBob,\n"
        )

        self.assertEqual(
            rows,
            [
                {
                    "name":
                        "Alice",
                    "age":
                        "30"
                },
                {
                    "name":
                        "Bob",
                    "age":
                        None
                }
            ]
        )


    def test_json_list_parsing(self):

        rows = parse_json_bytes(
            json.dumps(
                [
                    {
                        "a":
                            1
                    }
                ]
            ).encode(
                "utf-8"
            )
        )

        self.assertEqual(
            rows,
            [
                {
                    "a":
                        1
                }
            ]
        )


    def test_json_data_object_parsing(self):

        rows = parse_json_bytes(
            json.dumps(
                {
                    "data":
                        [
                            {
                                "a":
                                    1
                            }
                        ]
                }
            ).encode(
                "utf-8"
            )
        )

        self.assertEqual(
            rows,
            [
                {
                    "a":
                        1
                }
            ]
        )


    def test_json_stat_parsing(self):

        rows = parse_json_bytes(
            json.dumps(
                {
                    "id": [
                        "time",
                        "geo"
                    ],
                    "size": [
                        1,
                        2
                    ],
                    "dimension": {
                        "time": {
                            "category": {
                                "index": {
                                    "2025": 0
                                },
                                "label": {
                                    "2025": "2025"
                                }
                            }
                        },
                        "geo": {
                            "category": {
                                "index": {
                                    "EL": 0,
                                    "IT": 1
                                },
                                "label": {
                                    "EL": "Greece",
                                    "IT": "Italy"
                                }
                            }
                        }
                    },
                    "value": [
                        30.9,
                        30.2
                    ]
                }
            ).encode(
                "utf-8"
            )
        )

        self.assertEqual(
            rows,
            [
                {
                    "time": "2025",
                    "time_label": "2025",
                    "geo": "EL",
                    "geo_label": "Greece",
                    "value": 30.9
                },
                {
                    "time": "2025",
                    "time_label": "2025",
                    "geo": "IT",
                    "geo_label": "Italy",
                    "value": 30.2
                }
            ]
        )


    def test_dbnomics_series_json_parsing(self):

        rows = parse_json_bytes(
            json.dumps(
                {
                    "series": {
                        "docs": [
                            {
                                "dataset_code": "yth_demo_030",
                                "dataset_name": (
                                    "Estimated average age of young persons "
                                    "leaving the parental household"
                                ),
                                "series_code": "A.AVG.T.EL",
                                "series_name": "Annual - Average - Total - Greece",
                                "dimensions": {
                                    "freq": "A",
                                    "unit": "AVG",
                                    "sex": "T",
                                    "geo": "EL"
                                },
                                "period": [
                                    "2024",
                                    "2025"
                                ],
                                "value": [
                                    30.7,
                                    30.9
                                ]
                            }
                        ]
                    }
                }
            ).encode(
                "utf-8"
            )
        )

        self.assertEqual(
            rows,
            [
                {
                    "dataset_code": "yth_demo_030",
                    "dataset_name": (
                        "Estimated average age of young persons leaving "
                        "the parental household"
                    ),
                    "series_code": "A.AVG.T.EL",
                    "series_name": "Annual - Average - Total - Greece",
                    "time": "2024",
                    "value": 30.7,
                    "freq": "A",
                    "unit": "AVG",
                    "sex": "T",
                    "geo": "EL"
                },
                {
                    "dataset_code": "yth_demo_030",
                    "dataset_name": (
                        "Estimated average age of young persons leaving "
                        "the parental household"
                    ),
                    "series_code": "A.AVG.T.EL",
                    "series_name": "Annual - Average - Total - Greece",
                    "time": "2025",
                    "value": 30.9,
                    "freq": "A",
                    "unit": "AVG",
                    "sex": "T",
                    "geo": "EL"
                }
            ]
        )


    def test_unsupported_json_structure(self):

        rows = parse_json_bytes(
            json.dumps(
                {
                    "metadata":
                        {
                            "a":
                                1
                        }
                }
            ).encode(
                "utf-8"
            )
        )

        self.assertIsNone(
            rows
        )


    def test_xlsx_parsing(self):

        try:

            from openpyxl import Workbook

        except ImportError:

            self.skipTest(
                "openpyxl is not installed"
            )


        workbook = Workbook()
        sheet = workbook.active
        sheet.append(
            [
                "name",
                "created"
            ]
        )
        sheet.append(
            [
                "Alice",
                datetime.date(
                    2024,
                    1,
                    1
                )
            ]
        )

        buffer = io.BytesIO()
        workbook.save(
            buffer
        )

        rows = parse_xlsx_bytes(
            buffer.getvalue()
        )

        self.assertEqual(
            rows[0]["name"],
            "Alice"
        )

        self.assertEqual(
            rows[0]["created"],
            "2024-01-01T00:00:00"
        )


    def test_html_table_parsing(self):

        rows = parse_html_table_bytes(
            b"""
            <table>
              <tr><th>Age group</th><th>Turnout</th></tr>
              <tr><td>18 to 24</td><td>46.9</td></tr>
            </table>
            """
        )

        self.assertEqual(
            rows,
            [
                {
                    "Age group": "18 to 24",
                    "Turnout": "46.9"
                }
            ]
        )


    def test_eurostat_code_extraction_and_api_url(self):

        self.assertEqual(
            extract_eurostat_dataset_code(
                EUROSTAT_BOOKMARK_URL
            ),
            "yth_demo_030"
        )
        self.assertEqual(
            detect_eurostat_custom_view(
                EUROSTAT_BOOKMARK_URL
            )["bookmark_id"],
            "4e866041-fb81-4144-be5d-0f064c5edb21"
        )
        self.assertEqual(
            build_eurostat_api_url(
                "yth_demo_030__custom_22711535"
            ),
            (
                "https://ec.europa.eu/eurostat/api/dissemination/"
                "statistics/1.0/data/YTH_DEMO_030?format=JSON&lang=en"
            )
        )


    def test_eurostat_official_api_retrieval_preserves_source_url(self):

        def fake_urlopen(
            request,
            timeout
        ):
            self.assertIn(
                "statistics/1.0/data/YTH_DEMO_030",
                request.full_url
            )
            return FakeResponse(
                json.dumps(
                    {
                        "id": [
                            "time",
                            "geo"
                        ],
                        "size": [
                            1,
                            1
                        ],
                        "dimension": {
                            "time": {
                                "category": {
                                    "index": {
                                        "2025": 0
                                    },
                                    "label": {
                                        "2025": "2025"
                                    }
                                }
                            },
                            "geo": {
                                "category": {
                                    "index": {
                                        "EL": 0
                                    },
                                    "label": {
                                        "EL": "Greece"
                                    }
                                }
                            }
                        },
                        "value": [
                            30.9
                        ]
                    }
                ).encode(
                    "utf-8"
                ),
                url=request.full_url,
                content_type="application/json"
            )


        result = retrieve_dataset(
            EUROSTAT_BOOKMARK_URL,
            data_target="Estimated average age of young persons leaving the parental household",
            publisher="Eurostat",
            urlopen_func=fake_urlopen
        )

        self.assertEqual(
            result["retrieval_status"],
            "retrieved"
        )
        self.assertEqual(
            result["retrieval_method"],
            "official_api"
        )
        self.assertEqual(
            result["retrieved_scope"],
            "dataset"
        )
        self.assertEqual(
            result["metadata"]["source_url"],
            EUROSTAT_BOOKMARK_URL
        )
        self.assertEqual(
            result["rows"][0]["geo_label"],
            "Greece"
        )


    def test_landing_page_candidate_discovery_ranks_relevant_download(self):

        html = b"""
        <html>
          <a href="/about">About</a>
          <a href="/downloads/voter_turnout_by_age.xlsx">Download voter turnout by age Excel data</a>
          <a href="https://other.example/file.csv">Other CSV</a>
        </html>
        """

        candidates = discover_data_resources(
            html,
            "https://www.census.gov/topics/public-sector/voting.html",
            data_target="Voter Turnout by Age Group",
            publisher="U.S. Census Bureau"
        )

        self.assertEqual(
            candidates[0]["url"],
            "https://www.census.gov/downloads/voter_turnout_by_age.xlsx"
        )


    def test_landing_page_retrieves_ranked_resource(self):

        html = b"""
        <html>
          <a href="/downloads/voter_turnout_by_age.csv">Download voter turnout by age CSV</a>
        </html>
        """

        def fake_urlopen(
            request,
            timeout
        ):
            if request.full_url.endswith(
                "voter_turnout_by_age.csv"
            ):
                return FakeResponse(
                    b"age_group,turnout\n18-24,46.9\n",
                    url=request.full_url,
                    content_type="text/csv"
                )

            return FakeResponse(
                html,
                url="https://www.census.gov/topics/public-sector/voting.html",
                content_type="text/html"
            )


        result = retrieve_dataset(
            "https://www.census.gov/topics/public-sector/voting.html",
            data_target="Voter Turnout by Age Group",
            publisher="U.S. Census Bureau",
            urlopen_func=fake_urlopen
        )

        self.assertEqual(
            result["retrieval_status"],
            "retrieved"
        )
        self.assertEqual(
            result["retrieval_method"],
            "resource_discovery"
        )
        self.assertEqual(
            result["data_access_url"],
            "https://www.census.gov/downloads/voter_turnout_by_age.csv"
        )
        self.assertEqual(
            result["metadata"]["source_url"],
            "https://www.census.gov/topics/public-sector/voting.html"
        )


    def test_empty_retrieval_is_rejected(self):

        def fake_urlopen(
            request,
            timeout
        ):
            return FakeResponse(
                b"not,a,table\n",
                url="https://example.gov/empty.csv",
                content_type="text/csv"
            )


        result = retrieve_dataset(
            "https://example.gov/empty.csv",
            data_target="Voter Turnout by Age Group",
            urlopen_func=fake_urlopen
        )

        self.assertEqual(
            result["retrieval_status"],
            "unsupported"
        )
        self.assertEqual(
            result["validation_status"],
            "invalid"
        )


    def test_row_cap(self):

        csv_rows = "a\n" + "\n".join(
            str(
                index
            )
            for index
            in range(
                MAX_STORED_ROWS + 1
            )
        )

        def fake_urlopen(
            request,
            timeout
        ):

            return FakeResponse(
                csv_rows.encode(
                    "utf-8"
                ),
                url="https://example.gov/data.csv",
                content_type="text/csv"
            )


        result = retrieve_dataset(
            "https://example.gov/data.csv",
            urlopen_func=fake_urlopen
        )

        self.assertEqual(
            result["retrieval_status"],
            "retrieved"
        )

        self.assertEqual(
            result["retrieved_row_count"],
            MAX_STORED_ROWS + 1
        )

        self.assertEqual(
            result["stored_row_count"],
            MAX_STORED_ROWS
        )


    def test_size_limit(self):

        def fake_urlopen(
            request,
            timeout
        ):

            return FakeResponse(
                b"",
                content_length=26 * 1024 * 1024
            )


        result = retrieve_dataset(
            "https://example.gov/data.csv",
            urlopen_func=fake_urlopen
        )

        self.assertEqual(
            result["retrieval_status"],
            "too_large"
        )


    def test_html_with_download_link(self):

        html = b'<html><a href="/files/data.json">Download</a></html>'

        def fake_urlopen(
            request,
            timeout
        ):

            if request.full_url.endswith(
                "/files/data.json"
            ):

                return FakeResponse(
                    b'[{"a": 1}]',
                    url="https://example.gov/files/data.json",
                    content_type="application/json"
                )


            return FakeResponse(
                html,
                url="https://example.gov/page",
                content_type="text/html"
            )


        result = retrieve_dataset(
            "https://example.gov/page",
            urlopen_func=fake_urlopen
        )

        self.assertEqual(
            result["retrieval_status"],
            "retrieved"
        )

        self.assertEqual(
            result["data_access_url"],
            "https://example.gov/files/data.json"
        )


    def test_date_serialisation(self):

        self.assertEqual(
            normalise_value(
                datetime.date(
                    2024,
                    1,
                    2
                )
            ),
            "2024-01-02"
        )


if __name__ == "__main__":
    unittest.main()
