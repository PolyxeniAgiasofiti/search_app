import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen


EUROSTAT_DATAFLOW_ENDPOINTS = [
    (
        "https://ec.europa.eu/eurostat/api/dissemination/sdmx/3.0/"
        "structure/dataflow/ESTAT/{code}?format=JSON&lang=en&compress=false"
    ),
    (
        "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/"
        "dataflow/ESTAT/{code}?format=JSON&lang=en"
    )
]

EUROSTAT_STATISTICS_DATA_ENDPOINT = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/"
    "data/{code}?lang=en"
)


def normalize_eurostat_dataset_code(raw_code):

    if not raw_code:
        return None

    dataset_code = unquote(
        str(
            raw_code
        )
    ).split(
        "?"
    )[0].split(
        "#"
    )[0].strip()

    if "__custom_" in dataset_code.lower():
        custom_index = dataset_code.lower().index(
            "__custom_"
        )
        dataset_code = dataset_code[
            :custom_index
        ]

    dataset_code = dataset_code.strip()

    if not re.fullmatch(
        r"[A-Za-z0-9_]+",
        dataset_code
    ):
        return None

    return dataset_code.lower()


def extract_eurostat_dataset_code(url):

    parsed = urlparse(
        url
    )

    hostname = (
        parsed.hostname
        or
        ""
    ).lower()

    if hostname != "ec.europa.eu":
        return None

    path_parts = [
        part
        for part
        in parsed.path.split("/")
        if part
    ]

    lowered_parts = [
        part.lower()
        for part
        in path_parts
    ]

    if "databrowser" not in lowered_parts:
        return None

    if "view" not in lowered_parts:
        return None

    view_index = lowered_parts.index(
        "view"
    )

    if view_index + 1 >= len(
        path_parts
    ):
        return None

    return normalize_eurostat_dataset_code(
        path_parts[
            view_index + 1
        ]
    )


def extract_eurostat_raw_dataset_code(url):

    parsed = urlparse(
        url
    )

    hostname = (
        parsed.hostname
        or
        ""
    ).lower()

    if hostname != "ec.europa.eu":
        return None

    path_parts = [
        part
        for part
        in parsed.path.split("/")
        if part
    ]

    lowered_parts = [
        part.lower()
        for part
        in path_parts
    ]

    if "databrowser" not in lowered_parts:
        return None

    if "view" not in lowered_parts:
        return None

    view_index = lowered_parts.index(
        "view"
    )

    if view_index + 1 >= len(
        path_parts
    ):
        return None

    return unquote(
        path_parts[
            view_index + 1
        ]
    )


def read_json_url(
    url,
    timeout=10,
    urlopen_func=None
):

    if urlopen_func is None:
        urlopen_func = urlopen

    request = Request(
        url,
        headers={
            "User-Agent":
                "DataObservatory/1.0",

            "Accept":
                "application/json"
        }
    )

    with urlopen_func(
        request,
        timeout=timeout
    ) as response:

        content = response.read(
            2 * 1024 * 1024
        )

        status_code = (
            response.getcode()
            if hasattr(
                response,
                "getcode"
            )
            else
            None
        )

    return (
        json.loads(
            content.decode(
                "utf-8-sig"
            )
        ),
        status_code
    )


def find_text_field(value, field_names):

    if isinstance(
        value,
        dict
    ):

        for field_name in field_names:

            field_value = value.get(
                field_name
            )

            if isinstance(
                field_value,
                str
            ) and field_value.strip():

                return field_value.strip()

            if isinstance(
                field_value,
                dict
            ):

                for language in (
                    "en",
                    "EN"
                ):

                    text_value = field_value.get(
                        language
                    )

                    if isinstance(
                        text_value,
                        str
                    ) and text_value.strip():

                        return text_value.strip()

        for child_value in value.values():

            result = find_text_field(
                child_value,
                field_names
            )

            if result:
                return result

    elif isinstance(
        value,
        list
    ):

        for item in value:

            result = find_text_field(
                item,
                field_names
            )

            if result:
                return result

    return None


def find_dataset_node(value, dataset_code):

    dataset_code_upper = dataset_code.upper()

    if isinstance(
        value,
        dict
    ):

        identifiers = [
            value.get(
                "id"
            ),
            value.get(
                "ID"
            ),
            value.get(
                "code"
            ),
            value.get(
                "resourceId"
            )
        ]

        if dataset_code_upper in {
            str(identifier).upper()
            for identifier
            in identifiers
            if identifier
        }:

            return value

        for child_value in value.values():

            result = find_dataset_node(
                child_value,
                dataset_code
            )

            if result is not None:
                return result

    elif isinstance(
        value,
        list
    ):

        for item in value:

            result = find_dataset_node(
                item,
                dataset_code
            )

            if result is not None:
                return result

    return None


def extract_eurostat_metadata_from_payload(
    payload,
    dataset_code
):

    dataset_node = find_dataset_node(
        payload,
        dataset_code
    )

    search_root = (
        dataset_node
        if dataset_node is not None
        else
        payload
    )

    title = find_text_field(
        search_root,
        [
            "label",
            "name",
            "Name",
            "title",
            "Title"
        ]
    )

    description = find_text_field(
        search_root,
        [
            "description",
            "Description",
            "desc",
            "annotationTitle"
        ]
    )

    if not title:
        return None

    return {
        "provider":
            "eurostat",

        "dataset_code":
            dataset_code.lower(),

        "source_title":
            title,

        "publisher":
            "Eurostat",

        "description":
            description
            or
            title,

        "source_type":
            "statistical_authority",

        "data_access_type":
            "table",

        "format":
            "table",

        "available_information":
            [
                "Eurostat dataset code: "
                + dataset_code.lower(),
                "Official Eurostat dataset title: "
                + title
            ]
    }


def resolve_eurostat_dataflow_metadata(
    dataset_code,
    urlopen_func=None
):

    attempts = []

    for endpoint_template in EUROSTAT_DATAFLOW_ENDPOINTS:

        metadata_url = endpoint_template.format(
            code=dataset_code.upper()
        )

        attempt = {
            "method":
                "sdmx_dataflow",

            "url":
                metadata_url
        }

        try:

            payload, status_code = read_json_url(
                metadata_url,
                urlopen_func=urlopen_func
            )

            attempt["http_status"] = status_code

        except HTTPError as error:

            attempt["http_status"] = error.code
            attempt["failure_reason"] = str(
                error
            )
            attempts.append(
                attempt
            )
            continue

        except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as error:

            attempt["failure_reason"] = str(
                error
            )
            attempts.append(
                attempt
            )
            continue

        metadata = extract_eurostat_metadata_from_payload(
            payload,
            dataset_code
        )

        if metadata:

            metadata["metadata_url"] = metadata_url
            metadata["metadata_method_attempted"] = "sdmx_dataflow"
            metadata["metadata_http_status"] = status_code
            metadata["diagnostics"] = attempts + [
                attempt
            ]
            return metadata, metadata["diagnostics"]

        attempt["failure_reason"] = "No dataset title found in dataflow payload."
        attempts.append(
            attempt
        )

    return None, attempts


def resolve_eurostat_statistics_data_metadata(
    dataset_code,
    urlopen_func=None
):

    metadata_url = EUROSTAT_STATISTICS_DATA_ENDPOINT.format(
        code=dataset_code.upper()
    )

    attempt = {
        "method":
            "statistics_data",

        "url":
            metadata_url
    }

    try:

        payload, status_code = read_json_url(
            metadata_url,
            urlopen_func=urlopen_func
        )

        attempt["http_status"] = status_code

    except HTTPError as error:

        attempt["http_status"] = error.code
        attempt["failure_reason"] = str(
            error
        )
        return None, [
            attempt
        ]

    except (URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as error:

        attempt["failure_reason"] = str(
            error
        )
        return None, [
            attempt
        ]

    metadata = extract_eurostat_metadata_from_payload(
        payload,
        dataset_code
    )

    if metadata:

        metadata["metadata_url"] = metadata_url
        metadata["metadata_method_attempted"] = "statistics_data"
        metadata["metadata_http_status"] = status_code
        metadata["diagnostics"] = [
            attempt
        ]
        return metadata, [
            attempt
        ]

    attempt["failure_reason"] = "No dataset title found in statistics data payload."
    return None, [
        attempt
    ]


def resolve_eurostat_metadata(
    url,
    urlopen_func=None
):

    raw_dataset_code = extract_eurostat_raw_dataset_code(
        url
    )

    dataset_code = normalize_eurostat_dataset_code(
        raw_dataset_code
    )

    if dataset_code is None:
        return None

    if raw_dataset_code is None:
        raw_dataset_code = dataset_code

    metadata, attempts = resolve_eurostat_dataflow_metadata(
        dataset_code,
        urlopen_func=urlopen_func
    )

    if metadata:
        metadata["raw_dataset_code"] = raw_dataset_code
        metadata["normalized_dataset_code"] = dataset_code
        return metadata

    fallback_metadata, fallback_attempts = resolve_eurostat_statistics_data_metadata(
        dataset_code,
        urlopen_func=urlopen_func
    )
    attempts.extend(
        fallback_attempts
    )

    if fallback_metadata:
        fallback_metadata["raw_dataset_code"] = raw_dataset_code
        fallback_metadata["normalized_dataset_code"] = dataset_code
        fallback_metadata["diagnostics"] = attempts
        return fallback_metadata

    return {
        "provider":
            "eurostat",

        "dataset_code":
            dataset_code,

        "raw_dataset_code":
            raw_dataset_code,

        "normalized_dataset_code":
            dataset_code,

        "metadata_method_attempted":
            "sdmx_dataflow, statistics_data",

        "metadata_error":
            "Official Eurostat metadata could not be resolved.",

        "failure_reason":
            "All official Eurostat metadata lookup methods failed.",

        "diagnostics":
            attempts
    }


def resolve_source_metadata(
    url,
    urlopen_func=None
):

    eurostat_metadata = resolve_eurostat_metadata(
        url,
        urlopen_func=urlopen_func
    )

    if eurostat_metadata:
        return eurostat_metadata

    return None
