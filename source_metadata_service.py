import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
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

    dataset_code = path_parts[
        view_index + 1
    ].upper()

    if not re.fullmatch(
        r"[A-Z0-9_]+",
        dataset_code
    ):
        return None

    return dataset_code


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

    return json.loads(
        content.decode(
            "utf-8-sig"
        )
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

        if dataset_code in {
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
            dataset_code,

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
                + dataset_code,
                "Official Eurostat dataset title: "
                + title
            ]
    }


def resolve_eurostat_metadata(
    url,
    urlopen_func=None
):

    dataset_code = extract_eurostat_dataset_code(
        url
    )

    if not dataset_code:
        return None

    for endpoint_template in EUROSTAT_DATAFLOW_ENDPOINTS:

        metadata_url = endpoint_template.format(
            code=dataset_code
        )

        try:

            payload = read_json_url(
                metadata_url,
                urlopen_func=urlopen_func
            )

        except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
            continue

        metadata = extract_eurostat_metadata_from_payload(
            payload,
            dataset_code
        )

        if metadata:

            metadata["metadata_url"] = metadata_url
            return metadata

    return {
        "provider":
            "eurostat",

        "dataset_code":
            dataset_code,

        "metadata_error":
            "Official Eurostat metadata could not be resolved."
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

