import datetime
import io
import json
import unittest

from ingestion_service import (
    MAX_STORED_ROWS,
    normalise_value,
    parse_csv_bytes,
    parse_json_bytes,
    parse_xlsx_bytes,
    retrieve_dataset
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
