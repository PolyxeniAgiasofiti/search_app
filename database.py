import os
import psycopg


DATABASE_URL = os.getenv("DATABASE_URL")

SCHEMA = "data_observatory"


def get_connection():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured.")

    return psycopg.connect(DATABASE_URL)


def init_database():

    with get_connection() as conn:
        with conn.cursor() as cur:

            # Separate schema for this app
            cur.execute(
                f"""
                CREATE SCHEMA IF NOT EXISTS {SCHEMA};
                """
            )

            # Research sessions / runs
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA}.research_runs (
                    id BIGSERIAL PRIMARY KEY,
                    topic TEXT NOT NULL,
                    definition TEXT,
                    data_targets JSONB,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                """
            )

            # Public datasets discovered for a research run
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

                    review_status TEXT DEFAULT 'pending_review',

                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                """
            )

            # Actual rows downloaded from public datasets
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {SCHEMA}.dataset_rows (
                    id BIGSERIAL PRIMARY KEY,

                    dataset_id BIGINT NOT NULL
                        REFERENCES {SCHEMA}.datasets(id)
                        ON DELETE CASCADE,

                    row_data JSONB NOT NULL,

                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                """
            )

        conn.commit()

def save_research_run(topic, definition, data_targets):

    with get_connection() as conn:
        with conn.cursor() as cur:

            cur.execute(
                f"""
                INSERT INTO {SCHEMA}.research_runs
                (topic, definition, data_targets)
                VALUES (%s, %s, %s)
                RETURNING id;
                """,
                (
                    topic,
                    definition,
                    psycopg.types.json.Jsonb(data_targets)
                )
            )

            research_run_id = cur.fetchone()[0]

        conn.commit()

    return research_run_id

def save_dataset_candidates(research_run_id, datasets):

    saved_datasets = []

    with get_connection() as conn:
        with conn.cursor() as cur:

            for dataset in datasets:

                cur.execute(
                    f"""
                    INSERT INTO {SCHEMA}.datasets (
                        research_run_id,
                        data_target,
                        title,
                        publisher,
                        source_url,
                        description,
                        geographic_coverage,
                        time_coverage,
                        format,
                        review_status
                    )
                    VALUES (
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        'pending_review'
                    )
                    RETURNING id;
                    """,
                    (
                        research_run_id,
                        dataset.get("data_target"),
                        dataset.get("title"),
                        dataset.get("publisher"),
                        dataset.get("source_url"),
                        dataset.get("description"),
                        dataset.get("geographic_coverage"),
                        dataset.get("time_coverage"),
                        dataset.get("format")
                    )
                )

                dataset_id = cur.fetchone()[0]

                saved_dataset = dataset.copy()
                saved_dataset["id"] = dataset_id

                saved_datasets.append(saved_dataset)

        conn.commit()

    return saved_datasets

def get_datasets_for_run(research_run_id):

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
                    review_status
                FROM {SCHEMA}.datasets
                WHERE research_run_id = %s
                ORDER BY id;
                """,
                (research_run_id,)
            )

            rows = cur.fetchall()

    return [
        {
            "id": row[0],
            "data_target": row[1],
            "title": row[2],
            "publisher": row[3],
            "source_url": row[4],
            "description": row[5],
            "geographic_coverage": row[6],
            "time_coverage": row[7],
            "format": row[8],
            "review_status": row[9]
        }
        for row in rows
    ]