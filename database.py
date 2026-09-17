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