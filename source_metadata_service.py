import json
import re
from html import unescape
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree


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

TITLE_NAMES = {
    "title",
    "preflabel",
    "label",
    "name"
}

DESCRIPTION_NAMES = {
    "description"
}

RDF_SYNTAX_NAMESPACE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"

EXCLUDED_TITLE_NAMES = {
    "identifier",
    "notation"
}

TEMPORAL_NAMES = {
    "temporal"
}

IDENTIFIER_NAMES = {
    "identifier",
    "notation"
}


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


def read_response_url(
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
                "application/json, application/xml, text/xml"
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
        content,
        status_code
    )


def read_json_url(
    url,
    timeout=10,
    urlopen_func=None
):

    content, status_code = read_response_url(
        url,
        timeout=timeout,
        urlopen_func=urlopen_func
    )

    return (
        json.loads(
            content.decode(
                "utf-8-sig"
            )
        ),
        status_code
    )


def clean_metadata_text(value):

    if not value:
        return None

    text = unescape(
        str(
            value
        )
    )

    text = re.sub(
        r"<\s*br\s*/?\s*>",
        " ",
        text,
        flags=re.IGNORECASE
    )
    text = re.sub(
        r"<[^>]+>",
        " ",
        text
    )
    text = " ".join(
        text.split()
    )

    return text or None


def local_name(tag):

    if "}" in tag:
        return tag.rsplit(
            "}",
            1
        )[1].lower()

    if ":" in tag:
        return tag.rsplit(
            ":",
            1
        )[1].lower()

    return tag.lower()


def namespace_uri(tag):

    if tag.startswith(
        "{"
    ) and "}" in tag:

        return tag[1:].split(
            "}",
            1
        )[0]

    return ""


def element_text(element):

    direct_text = clean_metadata_text(
        element.text
    )

    if direct_text:
        return direct_text

    return clean_metadata_text(
        " ".join(
            text
            for text
            in element.itertext()
        )
    )


def find_xml_text(root, accepted_names, excluded_names=None):

    excluded_names = excluded_names or set()
    first_text = None

    for element in root.iter():

        name = local_name(
            element.tag
        )

        if namespace_uri(
            element.tag
        ) == RDF_SYNTAX_NAMESPACE:
            continue

        if name in excluded_names:
            continue

        if name not in accepted_names:
            continue

        text = element_text(
            element
        )

        if text:
            language = (
                element.attrib.get(
                    "{http://www.w3.org/XML/1998/namespace}lang"
                )
                or
                element.attrib.get(
                    "lang"
                )
                or
                ""
            ).lower()

            if language == "en":
                return text

            if first_text is None:
                first_text = text

    return first_text


def find_xml_texts(root, accepted_names):

    values = []

    for element in root.iter():

        if namespace_uri(
            element.tag
        ) == RDF_SYNTAX_NAMESPACE:
            continue

        if local_name(
            element.tag
        ) not in accepted_names:
            continue

        text = element_text(
            element
        )

        if text:
            values.append(
                text
            )

    return values


def is_identifier_like_title(value, dataset_code):

    if not value:
        return True

    cleaned = clean_metadata_text(
        value
    )

    if not cleaned:
        return True

    compact = cleaned.upper().replace(
        " ",
        ""
    )
    code = dataset_code.upper()

    if compact == code:
        return True

    if compact.endswith(
        "/" + code
    ):
        return True

    if compact.startswith(
        "10."
    ):
        return True

    if "<" in cleaned or ">" in cleaned:
        return True

    return False


def extract_doi_from_values(values):

    for value in values:

        cleaned = clean_metadata_text(
            value
        )

        if not cleaned:
            continue

        match = re.search(
            r"10\.\d{4,9}/[^\s<>]+",
            cleaned
        )

        if match:
            return match.group(
                0
            )

    return None


def extract_observation_time_coverage(value):

    if not isinstance(
        value,
        dict
    ):
        return None

    oldest = find_annotation_value(
        value,
        "OBS_PERIOD_OVERALL_OLDEST"
    )
    latest = find_annotation_value(
        value,
        "OBS_PERIOD_OVERALL_LATEST"
    )

    if not oldest:
        oldest = find_text_field(
            value,
            [
                "OBS_PERIOD_OVERALL_OLDEST",
                "obs_period_overall_oldest"
            ]
        )

    if not latest:
        latest = find_text_field(
            value,
            [
                "OBS_PERIOD_OVERALL_LATEST",
                "obs_period_overall_latest"
            ]
        )

    if oldest and latest:
        return oldest + " to " + latest

    if oldest:
        return oldest

    if latest:
        return latest

    return None


def find_annotation_value(value, annotation_type):

    if isinstance(
        value,
        dict
    ):

        if str(
            value.get(
                "type",
                ""
            )
        ).upper() == annotation_type.upper():

            for field_name in (
                "title",
                "text",
                "value",
                "date"
            ):

                field_value = value.get(
                    field_name
                )

                if isinstance(
                    field_value,
                    str
                ) and field_value.strip():

                    return clean_metadata_text(
                        field_value
                    )

        for child_value in value.values():

            result = find_annotation_value(
                child_value,
                annotation_type
            )

            if result:
                return result

    elif isinstance(
        value,
        list
    ):

        for item in value:

            result = find_annotation_value(
                item,
                annotation_type
            )

            if result:
                return result

    return None


def find_doi_in_payload(value):

    doi_xml = find_annotation_value(
        value,
        "DISSEMINATION_DOI_XML"
    )

    if doi_xml:
        return extract_doi_from_values(
            [
                doi_xml
            ]
        )

    return None


def find_geographic_dimension_label(value):

    if not isinstance(
        value,
        dict
    ):
        return None

    dimension = value.get(
        "dimension"
    )

    if not isinstance(
        dimension,
        dict
    ):
        return None

    geo = dimension.get(
        "geo"
    )

    if not isinstance(
        geo,
        dict
    ):
        return None

    return clean_metadata_text(
        geo.get(
            "label"
        )
    )


def _unused_old_extract_observation_time_coverage(value):

    oldest = find_text_field(
        value,
        [
            "OBS_PERIOD_OVERALL_OLDEST",
            "obs_period_overall_oldest"
        ]
    )
    latest = find_text_field(
        value,
        [
            "OBS_PERIOD_OVERALL_LATEST",
            "obs_period_overall_latest"
        ]
    )

    if oldest and latest:
        return oldest + " to " + latest

    if oldest:
        return oldest

    if latest:
        return latest

    return None


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

    title_fields = [
        "label",
        "name",
        "Name",
        "title",
        "Title"
    ]

    title = find_text_field(
        search_root,
        title_fields
    )

    if is_identifier_like_title(
        title,
        dataset_code
    ):

        title = find_text_field(
            payload,
            title_fields
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

    title = clean_metadata_text(
        title
    )
    description = clean_metadata_text(
        description
    )
    time_coverage = extract_observation_time_coverage(
        payload
    )
    geographic_coverage = find_geographic_dimension_label(
        payload
    )
    doi = find_doi_in_payload(
        payload
    )

    if is_identifier_like_title(
        title,
        dataset_code
    ):
        return None

    metadata = {
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

        "time_coverage":
            time_coverage
            or
            "unknown",

        "geographic_coverage":
            geographic_coverage
            or
            "unknown",

        "available_information":
            [
                "Eurostat dataset code: "
                + dataset_code.lower(),
                "Official Eurostat dataset title: "
                + title
            ]
    }

    if doi:
        metadata["doi"] = doi
        metadata["available_information"].append(
            "DOI: "
            + doi
        )

    return metadata


def extract_eurostat_metadata_from_xml(
    content,
    dataset_code
):

    try:
        root = ElementTree.fromstring(
            content
        )
    except ElementTree.ParseError:
        return None

    title = find_xml_text(
        root,
        {
            "title"
        },
        EXCLUDED_TITLE_NAMES
    )

    if not title:
        title = find_xml_text(
            root,
            {
                "preflabel"
            },
            EXCLUDED_TITLE_NAMES
        )

    if not title:
        title = find_xml_text(
            root,
            {
                "label"
            },
            EXCLUDED_TITLE_NAMES
        )

    if is_identifier_like_title(
        title,
        dataset_code
    ):
        return None

    description = find_xml_text(
        root,
        DESCRIPTION_NAMES
    )
    temporal = find_xml_text(
        root,
        TEMPORAL_NAMES
    )
    identifiers = find_xml_texts(
        root,
        IDENTIFIER_NAMES
    )
    doi = extract_doi_from_values(
        identifiers
    )

    metadata = {
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

        "time_coverage":
            temporal
            or
            "unknown",

        "geographic_coverage":
            "unknown",

        "available_information":
            [
                "Eurostat dataset code: "
                + dataset_code.lower(),
                "Official Eurostat dataset title: "
                + title
            ]
    }

    if doi:
        metadata["doi"] = doi
        metadata["available_information"].append(
            "DOI: "
            + doi
        )

    return metadata


def extract_eurostat_metadata_from_content(
    content,
    dataset_code
):

    try:
        payload = json.loads(
            content.decode(
                "utf-8-sig"
            )
        )
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = None

    if payload is not None:
        return extract_eurostat_metadata_from_payload(
            payload,
            dataset_code
        )

    return extract_eurostat_metadata_from_xml(
        content,
        dataset_code
    )


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

            content, status_code = read_response_url(
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

        except (URLError, TimeoutError, OSError, ValueError) as error:

            attempt["failure_reason"] = str(
                error
            )
            attempts.append(
                attempt
            )
            continue

        metadata = extract_eurostat_metadata_from_content(
            content,
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

        content, status_code = read_response_url(
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

    except (URLError, TimeoutError, OSError, ValueError) as error:

        attempt["failure_reason"] = str(
            error
        )
        return None, [
            attempt
        ]

    metadata = extract_eurostat_metadata_from_content(
        content,
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
