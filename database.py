import os

import psycopg

from psycopg.types.json import Jsonb


DATABASE_URL = os.getenv(
    "DATABASE_URL"
)

SCHEMA = "data_observatory"

VALID_REVIEW_STATUSES = {
    "pending_review",
    "approved",
    "rejected"
}


# ---------------------------------------------------------
# CONNECTION
# ---------------------------------------------------------

def get_connection():

    if not DATABASE_URL:

        raise RuntimeError(
            "DATABASE_URL is not configured."
        )


    return psycopg.connect(
        DATABASE_URL
    )


# ---------------------------------------------------------
# INITIALISE DATABASE
# ---------------------------------------------------------

def init_database():

    with get_connection() as conn:

        with conn.cursor() as cur:

            # ---------------------------------------------
            # SCHEMA
            # ---------------------------------------------

            cur.execute(
                f"""
                CREATE SCHEMA IF NOT EXISTS {SCHEMA};
                """
            )


            # ---------------------------------------------
            # RESEARCH RUNS
            # ---------------------------------------------

            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA}.research_runs (

                    id BIGSERIAL PRIMARY KEY,

                    topic TEXT NOT NULL,

                    definition TEXT,

                    data_targets JSONB,

                    created_at TIMESTAMPTZ
                        DEFAULT NOW()
                );
                """
            )


            # ---------------------------------------------
            # DATASET CANDIDATES
            # ---------------------------------------------

            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA}.datasets (

                    id BIGSERIAL PRIMARY KEY,

                    research_run_id BIGINT
                        REFERENCES {SCHEMA}.research_runs(id)
                        ON DELETE CASCADE,

                    data_target TEXT,

                    title TEXT NOT NULL,

                    publisher TEXT,

                    source_url TEXT,

                    description TEXT,

                    geographic_coverage TEXT,

                    time_coverage TEXT,

                    format TEXT,

                    row_count BIGINT,

                    review_status TEXT
                        DEFAULT 'pending_review',

                    created_at TIMESTAMPTZ
                        DEFAULT NOW()
                );
                """
            )

            cur.execute(
                f"""
                ALTER TABLE {SCHEMA}.datasets
                ADD COLUMN IF NOT EXISTS source_type TEXT;
                """
            )

            cur.execute(
                f"""
                ALTER TABLE {SCHEMA}.datasets
                ADD COLUMN IF NOT EXISTS validation_status TEXT;
                """
            )

            cur.execute(
                f"""
                ALTER TABLE {SCHEMA}.datasets
                ADD COLUMN IF NOT EXISTS link_status TEXT;
                """
            )

            cur.execute(
                f"""
                ALTER TABLE {SCHEMA}.datasets
                ADD COLUMN IF NOT EXISTS http_status INTEGER;
                """
            )

            cur.execute(
                f"""
                ALTER TABLE {SCHEMA}.datasets
                ADD COLUMN IF NOT EXISTS final_url TEXT;
                """
            )

            cur.execute(
                f"""
                ALTER TABLE {SCHEMA}.datasets
                ADD COLUMN IF NOT EXISTS last_checked_at TIMESTAMPTZ;
                """
            )

            cur.execute(
                f"""
                ALTER TABLE {SCHEMA}.datasets
                ADD COLUMN IF NOT EXISTS source_origin TEXT DEFAULT 'discovered';
                """
            )

            cur.execute(
                f"""
                ALTER TABLE {SCHEMA}.datasets
                ADD COLUMN IF NOT EXISTS dataset_code TEXT;
                """
            )

            cur.execute(
                f"""
                ALTER TABLE {SCHEMA}.datasets
                ADD COLUMN IF NOT EXISTS doi TEXT;
                """
            )

            cur.execute(
                f"""
                ALTER TABLE {SCHEMA}.datasets
                ADD COLUMN IF NOT EXISTS validation_reason TEXT;
                """
            )

            cur.execute(
                f"""
                ALTER TABLE {SCHEMA}.datasets
                ADD COLUMN IF NOT EXISTS is_custom_view BOOLEAN DEFAULT FALSE;
                """
            )

            cur.execute(
                f"""
                ALTER TABLE {SCHEMA}.datasets
                ADD COLUMN IF NOT EXISTS bookmark_id TEXT;
                """
            )

            cur.execute(
                f"""
                ALTER TABLE {SCHEMA}.datasets
                ADD COLUMN IF NOT EXISTS custom_selection_status TEXT;
                """
            )

            cur.execute(
                f"""
                ALTER TABLE {SCHEMA}.datasets
                ADD COLUMN IF NOT EXISTS selected_dimensions JSONB;
                """
            )

            cur.execute(
                f"""
                ALTER TABLE {SCHEMA}.datasets
                ADD COLUMN IF NOT EXISTS retrieval_status TEXT;
                """
            )

            cur.execute(
                f"""
                ALTER TABLE {SCHEMA}.datasets
                ADD COLUMN IF NOT EXISTS data_access_url TEXT;
                """
            )

            cur.execute(
                f"""
                ALTER TABLE {SCHEMA}.datasets
                ADD COLUMN IF NOT EXISTS data_access_provider TEXT;
                """
            )

            cur.execute(
                f"""
                ALTER TABLE {SCHEMA}.datasets
                ADD COLUMN IF NOT EXISTS data_access_role TEXT;
                """
            )

            cur.execute(
                f"""
                ALTER TABLE {SCHEMA}.datasets
                ADD COLUMN IF NOT EXISTS retrieval_scope TEXT;
                """
            )

            cur.execute(
                f"""
                ALTER TABLE {SCHEMA}.datasets
                ADD COLUMN IF NOT EXISTS retrieval_method TEXT;
                """
            )

            cur.execute(
                f"""
                ALTER TABLE {SCHEMA}.datasets
                ADD COLUMN IF NOT EXISTS retrieval_message TEXT;
                """
            )

            cur.execute(
                f"""
                ALTER TABLE {SCHEMA}.datasets
                ADD COLUMN IF NOT EXISTS retrieved_row_count BIGINT;
                """
            )

            cur.execute(
                f"""
                ALTER TABLE {SCHEMA}.datasets
                ADD COLUMN IF NOT EXISTS stored_row_count BIGINT;
                """
            )

            cur.execute(
                f"""
                ALTER TABLE {SCHEMA}.datasets
                ADD COLUMN IF NOT EXISTS retrieved_at TIMESTAMPTZ;
                """
            )


            # ---------------------------------------------
            # ACTUAL DATA ROWS
            # ---------------------------------------------

            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA}.dataset_rows (

                    id BIGSERIAL PRIMARY KEY,

                    dataset_id BIGINT NOT NULL
                        REFERENCES {SCHEMA}.datasets(id)
                        ON DELETE CASCADE,

                    row_data JSONB NOT NULL,

                    created_at TIMESTAMPTZ
                        DEFAULT NOW()
                );
                """
            )


        conn.commit()


# ---------------------------------------------------------
# SAVE APPROVED RESEARCH RUN
# ---------------------------------------------------------

def save_research_run(
    topic,
    definition,
    data_targets
):

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                f"""
                INSERT INTO {SCHEMA}.research_runs
                (
                    topic,
                    definition,
                    data_targets
                )

                VALUES
                (
                    %s,
                    %s,
                    %s
                )

                RETURNING id;
                """,

                (
                    topic,
                    definition,
                    Jsonb(
                        data_targets
                    )
                )
            )


            research_run_id = cur.fetchone()[0]


        conn.commit()


    return research_run_id


# ---------------------------------------------------------
# SAVE DATASET CANDIDATES
# ---------------------------------------------------------

def save_dataset_candidates(
    research_run_id,
    datasets
):

    saved_datasets = []


    with get_connection() as conn:

        with conn.cursor() as cur:

            for dataset in datasets:

                title = (
                    dataset.get(
                        "title"
                    )
                    or
                    "Untitled dataset"
                )


                cur.execute(
                    f"""
                    INSERT INTO {SCHEMA}.datasets
                    (
                        research_run_id,
                        data_target,
                        title,
                        publisher,
                        source_url,
                        description,
                        geographic_coverage,
                        time_coverage,
                        format,
                        source_type,
                        validation_status,
                        link_status,
                        http_status,
                        final_url,
                        source_origin,
                        dataset_code,
                        doi,
                        validation_reason,
                        is_custom_view,
                        bookmark_id,
                        custom_selection_status,
                        selected_dimensions,
                        data_access_url,
                        data_access_provider,
                        data_access_role,
                        retrieval_scope,
                        retrieval_status,
                        last_checked_at,
                        review_status
                    )

                    VALUES
                    (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        'not_started',
                        NOW(),
                        'pending_review'
                    )

                    RETURNING id;
                    """,

                    (
                        research_run_id,

                        dataset.get(
                            "data_target"
                        ),

                        title,

                        dataset.get(
                            "publisher"
                        ),

                        dataset.get(
                            "source_url"
                        ),

                        dataset.get(
                            "description"
                        ),

                        dataset.get(
                            "geographic_coverage"
                        ),

                        dataset.get(
                            "time_coverage"
                        ),

                        dataset.get(
                            "format"
                        ),

                        dataset.get(
                            "source_type"
                        ),

                        dataset.get(
                            "validation_status"
                        ),

                        dataset.get(
                            "link_status"
                        ),

                        dataset.get(
                            "http_status"
                        ),

                        dataset.get(
                            "final_url"
                        ),

                        dataset.get(
                            "source_origin",
                            "discovered"
                        ),

                        dataset.get(
                            "dataset_code"
                        ),

                        dataset.get(
                            "doi"
                        ),

                        dataset.get(
                            "validation_reason"
                        ),

                        dataset.get(
                            "is_custom_view",
                            False
                        ),

                        dataset.get(
                            "bookmark_id"
                        ),

                        dataset.get(
                            "custom_selection_status"
                        ),

                        Jsonb(
                            dataset.get(
                                "selected_dimensions",
                                {}
                            )
                        ),

                        dataset.get(
                            "data_access_url"
                        ),

                        dataset.get(
                            "data_access_provider"
                        ),

                        dataset.get(
                            "data_access_role"
                        ),

                        dataset.get(
                            "retrieval_scope"
                        )
                    )
                )


                dataset_id = cur.fetchone()[0]


                saved_dataset = dataset.copy()

                saved_dataset["id"] = dataset_id

                saved_dataset["review_status"] = "pending_review"

                saved_dataset["retrieval_status"] = "not_started"


                saved_datasets.append(
                    saved_dataset
                )


        conn.commit()


    return saved_datasets


# ---------------------------------------------------------
# UPDATE DATASET REVIEW STATUS
# ---------------------------------------------------------

def update_dataset_review_status(
    dataset_id,
    review_status
):

    if review_status not in VALID_REVIEW_STATUSES:

        raise ValueError(
            "review_status must be pending_review, approved, or rejected"
        )


    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                f"""
                UPDATE {SCHEMA}.datasets

                SET review_status = %s

                WHERE id = %s

                RETURNING id;
                """,

                (
                    review_status,
                    dataset_id
                )
            )


            updated = cur.fetchone()


        conn.commit()


    if updated is None:

        raise ValueError(
            "No dataset was found for the supplied dataset_id."
        )


    return {
        "id":
            dataset_id,

        "review_status":
            review_status
    }


# ---------------------------------------------------------
# UPDATE DATASET RETRIEVAL METADATA
# ---------------------------------------------------------

def update_dataset_retrieval(
    dataset_id,
    retrieval_status,
    data_access_url=None,
    data_access_provider=None,
    data_access_role=None,
    retrieval_scope=None,
    retrieval_method=None,
    retrieval_message=None,
    retrieved_row_count=None,
    stored_row_count=None
):

    valid_statuses = {
        "not_started",
        "retrieved",
        "retrieved_with_warnings",
        "unsupported",
        "failed",
        "too_large"
    }


    if retrieval_status not in valid_statuses:

        raise ValueError(
            "Invalid retrieval_status."
        )


    with get_connection() as conn:

        with conn.cursor() as cur:

            if retrieval_status in {
                "retrieved",
                "retrieved_with_warnings"
            }:

                retrieved_at_sql = "NOW()"

            else:

                retrieved_at_sql = "retrieved_at"


            cur.execute(
                f"""
                UPDATE {SCHEMA}.datasets

                SET
                    retrieval_status = %s,
                    data_access_url = %s,
                    data_access_provider = COALESCE(%s, data_access_provider),
                    data_access_role = COALESCE(%s, data_access_role),
                    retrieval_scope = COALESCE(%s, retrieval_scope),
                    retrieval_method = COALESCE(%s, retrieval_method),
                    retrieval_message = %s,
                    retrieved_row_count = %s,
                    stored_row_count = %s,
                    retrieved_at = {retrieved_at_sql}

                WHERE id = %s

                RETURNING id;
                """,

                (
                    retrieval_status,
                    data_access_url,
                    data_access_provider,
                    data_access_role,
                    retrieval_scope,
                    retrieval_method,
                    retrieval_message,
                    retrieved_row_count,
                    stored_row_count,
                    dataset_id
                )
            )

            updated = cur.fetchone()


        conn.commit()


    if updated is None:

        raise ValueError(
            "No dataset was found for the supplied dataset_id."
        )


def clear_dataset_rows(
    dataset_id
):

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                f"""
                DELETE FROM {SCHEMA}.dataset_rows

                WHERE dataset_id = %s;
                """,

                (
                    dataset_id,
                )
            )


        conn.commit()


def save_dataset_rows(
    dataset_id,
    rows
):

    with get_connection() as conn:

        with conn.cursor() as cur:

            if rows:

                cur.executemany(
                    f"""
                    INSERT INTO {SCHEMA}.dataset_rows
                    (
                        dataset_id,
                        row_data
                    )

                    VALUES
                    (
                        %s,
                        %s
                    );
                    """,

                    [
                        (
                            dataset_id,
                            Jsonb(
                                row
                            )
                        )
                        for row
                        in rows
                    ]
                )


        conn.commit()


    return len(
        rows
    )


def replace_dataset_rows(
    dataset_id,
    rows
):

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                f"""
                DELETE FROM {SCHEMA}.dataset_rows

                WHERE dataset_id = %s;
                """,

                (
                    dataset_id,
                )
            )

            if rows:

                cur.executemany(
                    f"""
                    INSERT INTO {SCHEMA}.dataset_rows
                    (
                        dataset_id,
                        row_data
                    )

                    VALUES
                    (
                        %s,
                        %s
                    );
                    """,

                    [
                        (
                            dataset_id,
                            Jsonb(
                                row
                            )
                        )
                        for row
                        in rows
                    ]
                )


        conn.commit()


    return len(
        rows
    )


def get_dataset_rows(
    dataset_id,
    limit=20
):

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                f"""
                SELECT row_data

                FROM {SCHEMA}.dataset_rows

                WHERE dataset_id = %s

                ORDER BY id

                LIMIT %s;
                """,

                (
                    dataset_id,
                    limit
                )
            )

            rows = cur.fetchall()


    return [
        row[0]
        for row
        in rows
    ]


# ---------------------------------------------------------
# READ DATASET CANDIDATES
# ---------------------------------------------------------

def get_datasets_for_run(
    research_run_id
):

    with get_connection() as conn:

        with conn.cursor() as cur:

            cur.execute(
                f"""
                SELECT
                    id,
                    data_target,
                    title,
                    publisher,
                    source_url,
                    description,
                    geographic_coverage,
                    time_coverage,
                    format,
                    source_type,
                    validation_status,
                    link_status,
                    http_status,
                    final_url,
                    source_origin,
                    dataset_code,
                    doi,
                    validation_reason,
                    is_custom_view,
                    bookmark_id,
                    custom_selection_status,
                    selected_dimensions,
                    last_checked_at,
                    retrieval_status,
                    data_access_url,
                    data_access_provider,
                    data_access_role,
                    retrieval_scope,
                    retrieval_method,
                    retrieval_message,
                    retrieved_row_count,
                    stored_row_count,
                    retrieved_at,
                    review_status

                FROM {SCHEMA}.datasets

                WHERE research_run_id = %s

                ORDER BY id;
                """,

                (
                    research_run_id,
                )
            )


            rows = cur.fetchall()


    return [

        {
            "id":
                row[0],

            "data_target":
                row[1],

            "title":
                row[2],

            "publisher":
                row[3],

            "source_url":
                row[4],

            "description":
                row[5],

            "geographic_coverage":
                row[6],

            "time_coverage":
                row[7],

            "format":
                row[8],

            "source_type":
                row[9],

            "validation_status":
                row[10],

            "link_status":
                row[11],

            "http_status":
                row[12],

            "final_url":
                row[13],

            "source_origin":
                row[14],

            "dataset_code":
                row[15],

            "doi":
                row[16],

            "validation_reason":
                row[17],

            "is_custom_view":
                row[18],

            "bookmark_id":
                row[19],

            "custom_selection_status":
                row[20],

            "selected_dimensions":
                row[21],

            "last_checked_at":
                row[22],

            "retrieval_status":
                row[23],

            "data_access_url":
                row[24],

            "data_access_provider":
                row[25],

            "data_access_role":
                row[26],

            "retrieval_scope":
                row[27],

            "retrieval_method":
                row[28],

            "retrieval_message":
                row[29],

            "retrieved_row_count":
                row[30],

            "stored_row_count":
                row[31],

            "retrieved_at":
                row[32],

            "review_status":
                row[33]
        }

        for row
        in rows
    ]
