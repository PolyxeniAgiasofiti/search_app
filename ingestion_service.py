import csv
import datetime
import io
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


MAX_DOWNLOAD_BYTES = 25 * 1024 * 1024
MAX_STORED_ROWS = 5000
SUPPORTED_EXTENSIONS = {
    ".csv",
    ".json",
    ".xlsx",
    ".xls"
}


def normalise_value(value):

    if value == "":

        return None


    if isinstance(
        value,
        (
            datetime.datetime,
            datetime.date
        )
    ):

        return value.isoformat()


    return value


def normalise_row(row):

    return {
        str(key):
            normalise_value(
                value
            )

        for key, value
        in row.items()
    }


def detect_format(
    url,
    content_type=""
):

    path = urlparse(
        url
    ).path.lower()


    if path.endswith(
        ".csv"
    ) or "text/csv" in content_type:

        return "csv"


    if path.endswith(
        ".json"
    ) or "json" in content_type:

        return "json"


    if path.endswith(
        ".xlsx"
    ):

        return "xlsx"


    if path.endswith(
        ".xls"
    ):

        return "xls"


    if "spreadsheetml" in content_type:

        return "xlsx"


    if "excel" in content_type:

        return "xls"


    if "html" in content_type:

        return "html"


    return "unknown"


def read_response_bytes(
    response,
    max_bytes=MAX_DOWNLOAD_BYTES
):

    content_length = response.headers.get(
        "Content-Length"
    )


    if content_length:

        try:

            if int(
                content_length
            ) > max_bytes:

                return (
                    None,
                    True
                )

        except ValueError:

            pass


    chunks = []
    total_bytes = 0


    while True:

        chunk = response.read(
            1024 * 1024
        )

        if not chunk:

            break


        total_bytes += len(
            chunk
        )

        if total_bytes > max_bytes:

            return (
                None,
                True
            )


        chunks.append(
            chunk
        )


    return (
        b"".join(
            chunks
        ),
        False
    )


def fetch_url(
    url,
    timeout=10,
    max_bytes=MAX_DOWNLOAD_BYTES,
    urlopen_func=None
):

    if urlopen_func is None:

        urlopen_func = urlopen


    request = Request(
        url,
        headers={
            "User-Agent":
                "DataObservatory/1.0"
        }
    )


    try:

        with urlopen_func(
            request,
            timeout=timeout
        ) as response:

            data, too_large = read_response_bytes(
                response,
                max_bytes=max_bytes
            )

            return {
                "status":
                    "too_large" if too_large else "ok",

                "content":
                    data,

                "content_type":
                    response.headers.get(
                        "Content-Type",
                        ""
                    ).lower(),

                "final_url":
                    response.geturl()
            }


    except (HTTPError, URLError, TimeoutError, OSError) as error:

        return {
            "status":
                "failed",

            "message":
                str(
                    error
                )
        }


def parse_csv_bytes(content):

    text = content.decode(
        "utf-8-sig"
    )

    sample = text[:4096]

    try:

        dialect = csv.Sniffer().sniff(
            sample,
            delimiters=[
                ",",
                ";",
                "\t",
                "|"
            ]
        )

    except csv.Error:

        dialect = csv.excel


    reader = csv.DictReader(
        io.StringIO(
            text
        ),
        dialect=dialect
    )


    return [
        normalise_row(
            row
        )
        for row
        in reader
    ]


def parse_json_bytes(content):

    parsed = json.loads(
        content.decode(
            "utf-8-sig"
        )
    )


    if isinstance(
        parsed,
        list
    ):

        records = parsed


    elif isinstance(
        parsed,
        dict
    ):

        records = None

        for key in [
            "data",
            "results",
            "items"
        ]:

            if isinstance(
                parsed.get(
                    key
                ),
                list
            ):

                records = parsed[key]
                break


        if records is None:

            return None


    else:

        return None


    if not all(
        isinstance(
            item,
            dict
        )
        for item
        in records
    ):

        return None


    return [
        normalise_row(
            row
        )
        for row
        in records
    ]


def parse_xlsx_bytes(content):

    try:

        from openpyxl import load_workbook

    except ImportError:

        return None


    workbook = load_workbook(
        io.BytesIO(
            content
        ),
        read_only=True,
        data_only=True
    )

    sheet = workbook.active

    rows = sheet.iter_rows(
        values_only=True
    )


    try:

        headers = next(
            rows
        )

    except StopIteration:

        return []


    headers = [
        str(
            header
        )
        if header is not None
        else f"column_{index + 1}"

        for index, header
        in enumerate(
            headers
        )
    ]


    parsed_rows = []

    for values in rows:

        parsed_rows.append(
            normalise_row(
                dict(
                    zip(
                        headers,
                        values
                    )
                )
            )
        )


    return parsed_rows


def parse_rows(
    content,
    data_format
):

    if data_format == "csv":

        return parse_csv_bytes(
            content
        )


    if data_format == "json":

        return parse_json_bytes(
            content
        )


    if data_format == "xlsx":

        return parse_xlsx_bytes(
            content
        )


    return None


def find_data_links(
    html_content,
    base_url
):

    from html.parser import HTMLParser

    class LinkParser(HTMLParser):

        def __init__(self):

            super().__init__()
            self.links = []


        def handle_starttag(
            self,
            tag,
            attrs
        ):

            if tag.lower() != "a":

                return


            attrs = dict(
                attrs
            )

            href = attrs.get(
                "href"
            )

            if href:

                self.links.append(
                    href
                )


    parser = LinkParser()

    parser.feed(
        html_content.decode(
            "utf-8",
            errors="ignore"
        )
    )


    candidate_links = []

    for href in parser.links:

        absolute_url = urljoin(
            base_url,
            href
        )

        path = urlparse(
            absolute_url
        ).path.lower()

        if any(
            path.endswith(
                extension
            )
            for extension
            in SUPPORTED_EXTENSIONS
        ):

            candidate_links.append(
                absolute_url
            )


    return candidate_links


def build_result(
    retrieval_status,
    message=None,
    data_access_url=None,
    data_format=None,
    rows=None
):

    rows = rows or []

    stored_rows = rows[:MAX_STORED_ROWS]


    result = {
        "retrieval_status":
            retrieval_status,

        "message":
            message or "",

        "data_access_url":
            data_access_url,

        "format":
            data_format,

        "retrieved_row_count":
            len(
                rows
            )
            if rows is not None
            else None,

        "stored_row_count":
            len(
                stored_rows
            ),

        "rows":
            stored_rows
    }


    if rows and len(
        rows
    ) > MAX_STORED_ROWS:

        result["message"] = (
            f"Retrieved {len(rows)} rows. "
            f"Stored the first {MAX_STORED_ROWS} rows."
        )


    return result


def retrieve_dataset(
    source_url,
    urlopen_func=None,
    max_bytes=MAX_DOWNLOAD_BYTES
):

    first_fetch = fetch_url(
        source_url,
        max_bytes=max_bytes,
        urlopen_func=urlopen_func
    )


    if first_fetch["status"] == "too_large":

        return build_result(
            "too_large",
            message="The source is larger than the allowed download size.",
            data_access_url=source_url
        )


    if first_fetch["status"] == "failed":

        return build_result(
            "failed",
            message=first_fetch.get(
                "message",
                "The source could not be retrieved."
            ),
            data_access_url=source_url
        )


    final_url = first_fetch.get(
        "final_url",
        source_url
    )

    data_format = detect_format(
        final_url,
        first_fetch.get(
            "content_type",
            ""
        )
    )


    if data_format == "html":

        links = find_data_links(
            first_fetch["content"],
            final_url
        )

        for link in links:

            link_fetch = fetch_url(
                link,
                max_bytes=max_bytes,
                urlopen_func=urlopen_func
            )

            if link_fetch["status"] != "ok":

                continue


            link_format = detect_format(
                link_fetch.get(
                    "final_url",
                    link
                ),
                link_fetch.get(
                    "content_type",
                    ""
                )
            )

            rows = parse_rows(
                link_fetch["content"],
                link_format
            )

            if rows is not None:

                return build_result(
                    "retrieved",
                    data_access_url=link_fetch.get(
                        "final_url",
                        link
                    ),
                    data_format=link_format,
                    rows=rows
                )


        return build_result(
            "unsupported",
            message="No supported downloadable data resource was found.",
            data_access_url=source_url
        )


    if data_format == "xls":

        return build_result(
            "unsupported",
            message="Legacy .xls files are not supported in this MVP.",
            data_access_url=final_url,
            data_format=data_format
        )


    rows = parse_rows(
        first_fetch["content"],
        data_format
    )

    if rows is None:

        return build_result(
            "unsupported",
            message="The source format could not be interpreted as tabular records.",
            data_access_url=final_url,
            data_format=data_format
        )


    return build_result(
        "retrieved",
        data_access_url=final_url,
        data_format=data_format,
        rows=rows
    )
