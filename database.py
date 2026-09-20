import os

import psycopg

from psycopg.types.json import Jsonb


DATABASE_URL = os.getenv(
    "DATABASE_URL"
)

SCHEMA = "data_observatory"


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
                        CASE
                            WHEN %s IS NOT NULL
                            THEN NOW()
                            ELSE NULL
                        END,
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
                            "link_status"
                        )
                    )
                )


                dataset_id = cur.fetchone()[0]


                saved_dataset = dataset.copy()

                saved_dataset["id"] = dataset_id


                saved_datasets.append(
                    saved_dataset
                )


        conn.commit()


    return saved_datasets


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
                    last_checked_at,
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

            "last_checked_at":
                row[14],

            "review_status":
                row[15]
        }

        for row
        in rows
    ]
