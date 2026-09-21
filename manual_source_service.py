import csv
import io
import ipaddress
import json
import socket
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import (
    HTTPRedirectHandler,
    Request,
    build_opener
)

from ai_service import analyze_manual_source, analyze_manual_source_url_context
from ingestion_service import detect_format, parse_json_bytes, parse_xlsx_bytes
from search_service import extract_url_content
from source_metadata_service import resolve_source_metadata
from validation import (
    normalise_data_access_type,
    normalise_source_type
)


MAX_INSPECTION_BYTES = 2 * 1024 * 1024
MAX_EVIDENCE_TEXT = 6000
GENERIC_MANUAL_TITLES = {
    "unknown",
    "age statistics",
    "age data",
    "demographic structure",
    "demographic structure data",
    "relevant demographic information",
    "relevant statistical dataset",
    "official dataset",
    "population information",
    "relevant population dataset",
    "population dataset",
    "user-provided data target",
    "user provided data target"
}
GENERIC_DESCRIPTION_MARKERS = {
    "potentially related",
    "contributes structured statistical data",
    "contributes data",
    "relevant information",
    "useful statistics",
    "demographic structure information",
    "generic demographic structure"
}


class UnsafeUrlError(ValueError):
    pass


def validate_safe_url(url):

    parsed = urlparse(
        url
    )

    if parsed.scheme not in {
        "http",
        "https"
    }:

        raise UnsafeUrlError(
            "Only http and https URLs are allowed."
        )


    if parsed.username or parsed.password:

        raise UnsafeUrlError(
            "URLs with embedded credentials are not allowed."
        )


    hostname = parsed.hostname

    if not hostname:

        raise UnsafeUrlError(
            "The URL must include a hostname."
        )


    if hostname.lower() == "localhost":

        raise UnsafeUrlError(
            "Localhost URLs are not allowed."
        )


    try:

        addresses = socket.getaddrinfo(
            hostname,
            None
        )

    except socket.gaierror as error:

        raise UnsafeUrlError(
            "The URL hostname could not be resolved."
        ) from error


    for address in addresses:

        ip_value = address[4][0]

        ip_address = ipaddress.ip_address(
            ip_value
        )

        if (
            ip_address.is_private
            or
            ip_address.is_loopback
            or
            ip_address.is_link_local
            or
            ip_address.is_multicast
            or
            ip_address.is_reserved
        ):

            raise UnsafeUrlError(
                "Private, local, or internal network URLs are not allowed."
            )


def read_limited_response(
    response,
    max_bytes=MAX_INSPECTION_BYTES
):

    content_length = response.headers.get(
        "Content-Length"
    )

    if content_length:

        try:

            if int(
                content_length
            ) > max_bytes:

                raise ValueError(
                    "The source is too large to inspect safely."
                )

        except ValueError:

            raise


    chunks = []
    total = 0

    while True:

        chunk = response.read(
            256 * 1024
        )

        if not chunk:
            break

        total += len(
            chunk
        )

        if total > max_bytes:

            raise ValueError(
                "The source is too large to inspect safely."
            )

        chunks.append(
            chunk
        )

    return b"".join(
        chunks
    )


class SafeRedirectHandler(HTTPRedirectHandler):

    def redirect_request(
        self,
        req,
        fp,
        code,
        msg,
        headers,
        newurl
    ):

        validate_safe_url(
            newurl
        )

        return super().redirect_request(
            req,
            fp,
            code,
            msg,
            headers,
            newurl
        )


def fetch_source(
    url,
    timeout=10,
    urlopen_func=None
):

    validate_safe_url(
        url
    )

    request = Request(
        url,
        headers={
            "User-Agent":
                "DataObservatory/1.0"
        }
    )

    try:

        if urlopen_func is None:

            opener = build_opener(
                SafeRedirectHandler
            )

            response_context = opener.open(
                request,
                timeout=timeout
            )

        else:

            response_context = urlopen_func(
                request,
                timeout=timeout
            )

        with response_context as response:

            final_url = response.geturl()

            validate_safe_url(
                final_url
            )

            content = read_limited_response(
                response
            )

            return {
                "status":
                    "reachable",

                "original_url":
                    url,

                "final_url":
                    final_url,

                "content_type":
                    response.headers.get(
                        "Content-Type",
                        ""
                    ).lower(),

                "content":
                    content
            }

    except HTTPError as error:

        if error.code in {
            401,
            403,
            429
        }:

            return {
                "status":
                    "restricted",

                "message":
                    str(
                        error
                    ),

                "original_url":
                    url,

                "final_url":
                    error.geturl()
            }

        if error.code in {
            404,
            410
        }:

            return {
                "status":
                    "broken",

                "message":
                    str(
                        error
                    ),

                "original_url":
                    url,

                "final_url":
                    error.geturl()
            }

        return {
            "status":
                "error",

            "message":
                str(
                    error
                ),

            "original_url":
                url
        }

    except (URLError, TimeoutError, OSError, ValueError, UnsafeUrlError) as error:

        return {
            "status":
                "error",

            "message":
                str(
                    error
                ),

            "original_url":
                url
        }


class EvidenceHTMLParser(HTMLParser):

    def __init__(self):

        super().__init__()
        self.title = ""
        self.meta_description = ""
        self.links = []
        self.headings = []
        self.text_parts = []
        self._current_tag = None
        self._skip = False


    def handle_starttag(
        self,
        tag,
        attrs
    ):

        tag = tag.lower()
        self._current_tag = tag

        if tag in {
            "script",
            "style",
            "noscript"
        }:

            self._skip = True


        attrs = dict(
            attrs
        )

        if tag == "meta" and attrs.get(
            "name",
            ""
        ).lower() == "description":

            self.meta_description = attrs.get(
                "content",
                ""
            )


        if tag == "a" and attrs.get(
            "href"
        ):

            self.links.append(
                attrs.get(
                    "href"
                )
            )


    def handle_endtag(
        self,
        tag
    ):

        if tag.lower() in {
            "script",
            "style",
            "noscript"
        }:

            self._skip = False

        self._current_tag = None


    def handle_data(
        self,
        data
    ):

        if self._skip:
            return

        text = " ".join(
            data.split()
        )

        if not text:
            return

        if self._current_tag == "title":

            self.title += text

        elif self._current_tag in {
            "h1",
            "h2",
            "h3"
        }:

            self.headings.append(
                text
            )

        else:

            self.text_parts.append(
                text
            )


def inspect_html(
    content,
    base_url
):

    parser = EvidenceHTMLParser()

    parser.feed(
        content.decode(
            "utf-8",
            errors="ignore"
        )
    )

    data_links = []

    for href in parser.links:

        absolute = urljoin(
            base_url,
            href
        )

        path = urlparse(
            absolute
        ).path.lower()

        if any(
            marker in path
            for marker
            in [
                ".csv",
                ".json",
                ".xlsx",
                ".xls",
                "api",
                "download"
            ]
        ):

            data_links.append(
                absolute
            )

    return {
        "content_kind":
            "html",

        "title":
            parser.title or "unknown",

        "meta_description":
            parser.meta_description or "unknown",

        "headings":
            parser.headings[:20],

        "text":
            " ".join(
                parser.text_parts
            )[:MAX_EVIDENCE_TEXT],

        "data_links":
            data_links[:20]
    }


def inspect_csv(
    content
):

    text = content.decode(
        "utf-8-sig",
        errors="replace"
    )

    reader = csv.DictReader(
        io.StringIO(
            text
        )
    )

    rows = []

    for index, row in enumerate(
        reader
    ):

        if index >= 5:
            break

        rows.append(
            row
        )

    return {
        "content_kind":
            "csv",

        "headers":
            reader.fieldnames or [],

        "sample_rows":
            rows
    }


def inspect_json(
    content
):

    parsed_rows = parse_json_bytes(
        content
    )

    if parsed_rows is None:

        parsed = json.loads(
            content.decode(
                "utf-8-sig"
            )
        )

        return {
            "content_kind":
                "json",

            "structure":
                type(
                    parsed
                ).__name__,

            "keys":
                list(
                    parsed.keys()
                )[:20]
                if isinstance(
                    parsed,
                    dict
                )
                else
                []
        }

    return {
        "content_kind":
            "json",

        "headers":
            list(
                parsed_rows[0].keys()
            )
            if parsed_rows
            else
            [],

        "sample_rows":
            parsed_rows[:5]
    }


def inspect_xlsx(
    content
):

    rows = parse_xlsx_bytes(
        content
    )

    return {
        "content_kind":
            "xlsx",

        "headers":
            list(
                rows[0].keys()
            )
            if rows
            else
            [],

        "sample_rows":
            rows[:5]
    }


def build_source_evidence(
    fetch_result
):

    content = fetch_result.get(
        "content",
        b""
    )

    final_url = fetch_result.get(
        "final_url",
        fetch_result.get(
            "original_url"
        )
    )

    data_format = detect_format(
        final_url,
        fetch_result.get(
            "content_type",
            ""
        )
    )

    if data_format == "csv":

        inspected = inspect_csv(
            content
        )

    elif data_format == "json":

        inspected = inspect_json(
            content
        )

    elif data_format == "xlsx":

        inspected = inspect_xlsx(
            content
        )

    else:

        inspected = inspect_html(
            content,
            final_url
        )

    inspected["original_url"] = fetch_result.get(
        "original_url"
    )
    inspected["final_url"] = final_url
    inspected["content_type"] = fetch_result.get(
        "content_type",
        ""
    )

    return inspected


def build_tavily_source_evidence(
    extraction_result,
    fetch_result
):

    content = extraction_result.get(
        "content",
        ""
    )

    return {
        "content_kind":
            "tavily_extract",

        "original_url":
            fetch_result.get(
                "original_url"
            ),

        "final_url":
            extraction_result.get(
                "final_url"
            )
            or
            fetch_result.get(
                "final_url"
            ),

        "content_type":
            fetch_result.get(
                "content_type",
                ""
            ),

        "extract_depth":
            extraction_result.get(
                "extract_depth"
            ),

        "extracted_text":
            content[:MAX_EVIDENCE_TEXT],

        "text":
            content[:MAX_EVIDENCE_TEXT],

        "extraction_attempts":
            extraction_result.get(
                "attempts",
                []
            )
    }


def merge_provider_metadata(
    evidence,
    metadata
):

    if not metadata:
        return evidence

    enriched = evidence.copy()
    enriched["provider_metadata"] = metadata

    if metadata.get(
        "source_title"
    ):

        enriched["title"] = metadata.get(
            "source_title"
        )

    if metadata.get(
        "description"
    ):

        enriched["official_description"] = metadata.get(
            "description"
        )

    if metadata.get(
        "available_information"
    ):

        enriched["available_information"] = metadata.get(
            "available_information"
        )

    return enriched


def is_generic_manual_title(value):

    if not value:
        return True

    cleaned = " ".join(
        str(
            value
        ).strip().lower().split()
    )

    return cleaned in GENERIC_MANUAL_TITLES


def is_generic_description(value):

    if not value:
        return True

    cleaned = " ".join(
        str(
            value
        ).strip().lower().split()
    )

    return any(
        marker in cleaned
        for marker
        in GENERIC_DESCRIPTION_MARKERS
    )


def is_bad_display_value(value):

    if not value:
        return True

    cleaned = str(
        value
    ).strip()

    if cleaned.lower() == "unknown":
        return True

    if len(
        cleaned
    ) > 500:
        return True

    if "<" in cleaned or ">" in cleaned:
        return True

    if cleaned.upper().startswith(
        "10."
    ):
        return True

    return False


def url_context_retrieval_succeeded(
    metadata,
    provided_url
):

    if not metadata:
        return False

    provided_host = urlparse(
        provided_url
    ).hostname

    for item in metadata:

        status = str(
            item.get(
                "url_retrieval_status",
                ""
            )
        ).upper()

        retrieved_url = item.get(
            "retrieved_url"
        )

        if not retrieved_url:
            continue

        try:
            validate_safe_url(
                retrieved_url
            )
        except UnsafeUrlError:
            continue

        retrieved_host = urlparse(
            retrieved_url
        ).hostname

        if provided_host and retrieved_host and provided_host != retrieved_host:
            continue

        if (
            "SUCCESS" in status
            or
            status in {
                "",
                "URL_RETRIEVAL_STATUS_SUCCESS"
            }
        ):
            return True

    return False


def normalise_url_context_analysis(
    url_context_result
):

    if not isinstance(
        url_context_result,
        dict
    ):
        return None

    analysis = url_context_result.get(
        "analysis"
    )

    if not isinstance(
        analysis,
        dict
    ):
        return None

    if "description" in analysis and "target_description" not in analysis:
        analysis["target_description"] = analysis.get(
            "description"
        )

    if "format" in analysis and "data_access_type" not in analysis:
        analysis["data_access_type"] = analysis.get(
            "format"
        )

    return analysis


def analyse_user_provided_source(
    definition,
    existing_data_targets,
    url,
    analyzer_func=None,
    urlopen_func=None,
    extractor_func=None,
    url_context_func=None
):

    fetch_result = fetch_source(
        url,
        urlopen_func=urlopen_func
    )

    if fetch_result.get(
        "status"
    ) != "reachable":

        link_status = fetch_result.get(
            "status",
            "error"
        )

        return {
            "accepted":
                False,

            "validation_status":
                "needs_review"
                if link_status == "restricted"
                else
                "invalid",

            "link_status":
                link_status,

            "source_url":
                url,

            "final_url":
                fetch_result.get(
                    "final_url"
                ),

            "message":
                fetch_result.get(
                    "message",
                    "The URL could not be inspected."
                )
        }

    if url_context_func is None and analyzer_func is None:
        url_context_func = analyze_manual_source_url_context

    url_context_result = None
    url_context_success = False

    if url_context_func is not None:
        try:
            url_context_result = url_context_func(
                definition,
                existing_data_targets,
                url
            )
            url_context_success = url_context_retrieval_succeeded(
                url_context_result.get(
                    "url_context_metadata",
                    []
                ),
                url
            )
        except Exception:
            url_context_result = None

    extraction_result = None
    extraction_succeeded = False

    metadata = None

    if url_context_success:

        analysis = normalise_url_context_analysis(
            url_context_result
        )

        if analysis is None:
            analysis = {}

        evidence = {
            "content_kind":
                "gemini_url_context",

            "original_url":
                url,

            "final_url":
                fetch_result.get(
                    "final_url"
                ),

            "url_context_metadata":
                url_context_result.get(
                    "url_context_metadata",
                    []
                )
        }

        try:
            metadata = resolve_source_metadata(
                url,
                urlopen_func=urlopen_func
            )
        except Exception:
            metadata = None

    else:

        if extractor_func is None:
            extractor_func = extract_url_content

        try:
            extraction_result = extractor_func(
                url,
                definition=definition
            )
        except Exception as error:
            extraction_result = {
                "status":
                    "error",

                "message":
                    str(
                        error
                    ),

                "attempts":
                    [
                        {
                            "status":
                                "error",

                            "message":
                                str(
                                    error
                                )
                        }
                    ]
            }

        extraction_succeeded = (
            isinstance(
                extraction_result,
                dict
            )
            and
            extraction_result.get(
                "status"
            ) == "success"
            and
            extraction_result.get(
                "content"
            )
        )

    if (not url_context_success) and extraction_succeeded:

        evidence = build_tavily_source_evidence(
            extraction_result,
            fetch_result
        )

        try:
            metadata = resolve_source_metadata(
                url,
                urlopen_func=urlopen_func
            )
        except Exception:
            metadata = None

    elif not url_context_success:

        evidence = build_source_evidence(
            fetch_result
        )

        metadata = resolve_source_metadata(
            url,
            urlopen_func=urlopen_func
        )

        if (
            metadata
            and
            metadata.get(
                "provider"
            ) == "eurostat"
            and
            not metadata.get(
                "source_title"
            )
        ):

            return {
                "accepted":
                    False,

                "validation_status":
                    "needs_review",

                "link_status":
                    "reachable",

                "source_url":
                    url,

                "final_url":
                    fetch_result.get(
                        "final_url"
                    ),

                "publisher":
                    "Eurostat",

                "source_type":
                    "statistical_authority",

                "data_access_type":
                    "table",

                "message":
                    metadata.get(
                        "metadata_error",
                        "Tavily Extract did not return enough content, and official metadata could not be resolved."
                    )
            }

        analysis = None

    evidence = merge_provider_metadata(
        evidence,
        metadata
    )

    if not url_context_success:

        if analyzer_func is None:

            analyzer_func = analyze_manual_source

        analysis = analyzer_func(
            definition,
            existing_data_targets,
            evidence
        )

    validation_status = analysis.get(
        "validation_status",
        "invalid"
    )

    accepted = (
        analysis.get(
            "relevant"
        ) is True
        and
        analysis.get(
            "useful_data_source"
        ) is True
        and
        validation_status == "validated"
    )

    source_type = normalise_source_type(
        analysis.get(
            "source_type"
        )
    )

    data_access_type = normalise_data_access_type(
        analysis.get(
            "data_access_type"
        )
    )

    source_title = analysis.get(
        "source_title",
        evidence.get(
            "title",
            "unknown"
        )
    )

    publisher = analysis.get(
        "publisher",
        "unknown"
    )

    target_description = analysis.get(
        "target_description",
        ""
    )

    available_information = analysis.get(
        "available_information",
        []
    )
    geographic_coverage = analysis.get(
        "geographic_coverage",
        "unknown"
    )
    time_coverage = analysis.get(
        "time_coverage",
        "unknown"
    )

    should_apply_metadata_display = (
        metadata
        and
        metadata.get(
            "source_title"
        )
        and
        (
            (
                not url_context_success
                and
                not extraction_succeeded
            )
            or
            is_bad_display_value(
                source_title
            )
            or
            is_generic_manual_title(
                source_title
            )
        )
    )

    if should_apply_metadata_display:

        source_title = metadata.get(
            "source_title"
        )
        publisher = metadata.get(
            "publisher",
            publisher
        )
        target_description = metadata.get(
            "description",
            target_description
        )
        if is_generic_description(
            target_description
        ):
            target_description = metadata.get(
                "description",
                target_description
            )
        available_information = metadata.get(
            "available_information",
            available_information
        )
        geographic_coverage = metadata.get(
            "geographic_coverage",
            "unknown"
        )
        time_coverage = metadata.get(
            "time_coverage",
            "unknown"
        )
        source_type = normalise_source_type(
            metadata.get(
                "source_type"
            )
        )
        data_access_type = normalise_data_access_type(
            metadata.get(
                "data_access_type"
            )
        )

    data_target = analysis.get(
        "proposed_data_target",
        ""
    )

    if metadata and metadata.get(
        "source_title"
    ) and is_generic_manual_title(
        data_target
    ):

        data_target = metadata.get(
            "source_title"
        )

    dataset_code = analysis.get(
        "dataset_code"
    )
    doi = analysis.get(
        "doi"
    )
    is_custom_view = bool(
        analysis.get(
            "is_custom_view"
        )
    )
    bookmark_id = analysis.get(
        "bookmark_id"
    )
    custom_selection_status = analysis.get(
        "custom_selection_status"
    )
    selected_dimensions = analysis.get(
        "selected_dimensions"
    )
    data_access_url = analysis.get(
        "data_access_url"
    )
    data_access_provider = analysis.get(
        "data_access_provider"
    )
    data_access_role = analysis.get(
        "data_access_role"
    )
    retrieval_scope = analysis.get(
        "retrieval_scope"
    )

    if not isinstance(
        selected_dimensions,
        dict
    ):
        selected_dimensions = {}

    if metadata:
        dataset_code = dataset_code or metadata.get(
            "dataset_code"
        )
        doi = doi or metadata.get(
            "doi"
        )
        is_custom_view = is_custom_view or bool(
            metadata.get(
                "is_custom_view"
            )
        )
        bookmark_id = bookmark_id or metadata.get(
            "bookmark_id"
        )
        custom_selection_status = custom_selection_status or metadata.get(
            "custom_selection_status"
        )
        if not selected_dimensions:
            selected_dimensions = metadata.get(
                "selected_dimensions",
                {}
            )
        data_access_url = data_access_url or metadata.get(
            "data_access_url"
        )
        data_access_provider = data_access_provider or metadata.get(
            "data_access_provider"
        )
        data_access_role = data_access_role or metadata.get(
            "data_access_role"
        )
        retrieval_scope = retrieval_scope or metadata.get(
            "retrieval_scope"
        )

    if is_custom_view and not custom_selection_status:
        custom_selection_status = "unresolved"
    elif not custom_selection_status:
        custom_selection_status = "not_applicable"

    if custom_selection_status == "resolved":
        retrieval_scope = "bookmark_selection"
    elif custom_selection_status in {
        "unresolved",
        "partially_resolved"
    }:
        retrieval_scope = "dataset"
    elif not retrieval_scope:
        retrieval_scope = (
            "bookmark_selection"
            if custom_selection_status == "resolved"
            else
            "dataset"
        )

    if (
        not accepted
        and
        analysis.get(
            "relevant"
        ) is True
        and
        analysis.get(
            "useful_data_source"
        ) is True
        and
        validation_status == "needs_review"
        and
        metadata
        and
        metadata.get(
            "provider"
        ) == "eurostat"
        and
        metadata.get(
            "source_title"
        )
        and
        data_access_url
    ):
        validation_status = "validated"
        accepted = True

    if accepted and is_bad_display_value(
        source_title
    ):

        accepted = False
        validation_status = "needs_review"

    return {
        "accepted":
            accepted,

        "validation_status":
            validation_status
            if validation_status in {
                "validated",
                "needs_review",
                "invalid"
            }
            else
            "invalid",

        "link_status":
            "reachable",

        "source_url":
            url,

        "final_url":
            fetch_result.get(
                "final_url"
            ),

        "reason":
            analysis.get(
                "reason",
                ""
            ),

        "validation_reason":
            analysis.get(
                "reason",
                ""
            ),

        "data_target":
            data_target,

        "target_description":
            target_description,

        "available_information":
            available_information,

        "source_title":
            source_title,

        "publisher":
            publisher,

        "geographic_coverage":
            geographic_coverage,

        "time_coverage":
            time_coverage,

        "source_type":
            source_type,

        "data_access_type":
            data_access_type,

        "evidence":
            evidence,

        "source_metadata":
            metadata,

        "dataset_code":
            dataset_code,

        "doi":
            doi,

        "is_custom_view":
            is_custom_view,

        "bookmark_id":
            bookmark_id,

        "custom_selection_status":
            custom_selection_status,

        "selected_dimensions":
            selected_dimensions,

        "data_access_url":
            data_access_url,

        "data_access_provider":
            data_access_provider,

        "data_access_role":
            data_access_role,

        "retrieval_scope":
            retrieval_scope,

        "message":
            analysis.get(
                "reason",
                ""
            )
    }
