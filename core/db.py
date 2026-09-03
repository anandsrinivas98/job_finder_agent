import os
import sqlite3
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

class JobHistoryDB:
    """Hybrid Database for job deduplication and state tracking.
    Supports both Local SQLite (default) and Cloud PostgreSQL / Supabase (via DATABASE_URL).
    """

    def __init__(self, db_path: Path, database_url: str = ""):
        self.db_path = Path(db_path)
        self.database_url = (database_url or os.getenv("DATABASE_URL", "")).strip()
        self.is_postgres = self.database_url.startswith(("postgresql://", "postgres://"))
        self._init_db()

    def _get_connection(self):
        """Returns connection object for SQLite or PostgreSQL."""
        if self.is_postgres:
            try:
                import psycopg2
                import psycopg2.extras
                conn = psycopg2.connect(self.database_url, cursor_factory=psycopg2.extras.RealDictCursor)
                return conn
            except ImportError:
                print("[⚠️ DB Warning] psycopg2 not installed. Falling back to local SQLite. (Run: pip install psycopg2-binary)")
                self.is_postgres = False

        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initializes the database schema."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if self.is_postgres:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS jobs (
                        id SERIAL PRIMARY KEY,
                        job_hash VARCHAR(64) UNIQUE NOT NULL,
                        company TEXT NOT NULL,
                        title TEXT NOT NULL,
                        location TEXT,
                        work_mode TEXT,
                        posted_date TEXT,
                        salary TEXT,
                        experience TEXT,
                        job_type TEXT,
                        job_url TEXT,
                        source TEXT,
                        recruiter_name TEXT,
                        recruiter_linkedin TEXT,
                        company_website TEXT,
                        match_score REAL,
                        category TEXT,
                        status VARCHAR(32) DEFAULT 'NEW',
                        first_seen TEXT NOT NULL,
                        last_seen TEXT NOT NULL,
                        run_count INTEGER DEFAULT 1
                    );
                    CREATE INDEX IF NOT EXISTS idx_job_hash ON jobs(job_hash);
                    CREATE INDEX IF NOT EXISTS idx_status ON jobs(status);
                """)
            else:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS jobs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        job_hash TEXT UNIQUE NOT NULL,
                        company TEXT NOT NULL,
                        title TEXT NOT NULL,
                        location TEXT,
                        work_mode TEXT,
                        posted_date TEXT,
                        salary TEXT,
                        experience TEXT,
                        job_type TEXT,
                        job_url TEXT,
                        source TEXT,
                        recruiter_name TEXT,
                        recruiter_linkedin TEXT,
                        company_website TEXT,
                        match_score REAL,
                        category TEXT,
                        status TEXT DEFAULT 'NEW',
                        first_seen TEXT NOT NULL,
                        last_seen TEXT NOT NULL,
                        run_count INTEGER DEFAULT 1
                    );
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_hash ON jobs(job_hash);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON jobs(status);")

            conn.commit()
        finally:
            conn.close()

    def compute_job_hash(self, company: str, title: str, job_url: str) -> str:
        """Generates a stable signature for job deduplication."""
        clean_comp = company.strip().lower()
        clean_title = title.strip().lower()
        clean_url = job_url.split("?")[0].strip().lower() if job_url else ""
        raw = f"{clean_comp}|{clean_title}|{clean_url}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def upsert_and_classify_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """
        Inserts or updates a job and assigns its status:
        - 🆕 NEW
        - 🔄 UPDATED
        - ⏳ STILL OPEN
        """
        job_hash = self.compute_job_hash(
            company=job.get("company", ""),
            title=job.get("title", ""),
            job_url=job.get("job_url", "")
        )
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            ph = "%s" if self.is_postgres else "?"

            cursor.execute(f"SELECT * FROM jobs WHERE job_hash = {ph}", (job_hash,))
            existing = cursor.fetchone()

            if not existing:
                # 🆕 Brand new job
                status = "NEW"
                insert_sql = f"""
                    INSERT INTO jobs (
                        job_hash, company, title, location, work_mode, posted_date,
                        salary, experience, job_type, job_url, source, recruiter_name,
                        recruiter_linkedin, company_website, match_score, category,
                        status, first_seen, last_seen, run_count
                    ) VALUES ({', '.join([ph]*20)})
                """
                cursor.execute(insert_sql, (
                    job_hash,
                    job.get("company", "N/A"),
                    job.get("title", "N/A"),
                    job.get("location", "India"),
                    job.get("work_mode", "N/A"),
                    job.get("posted_date", "Date not verified"),
                    job.get("salary", "N/A"),
                    job.get("experience", "Fresher / 0-2 yrs"),
                    job.get("job_type", "Full-time"),
                    job.get("job_url", ""),
                    job.get("source", "N/A"),
                    job.get("recruiter_name", "N/A"),
                    job.get("recruiter_linkedin", "N/A"),
                    job.get("company_website", "N/A"),
                    float(job.get("match_score", 0.0)),
                    job.get("category", "Software / Development"),
                    status,
                    now_str,
                    now_str,
                    1
                ))
            else:
                # Existing job: check if updated or still open
                prev_score = existing["match_score"]
                new_score = float(job.get("match_score", 0.0))
                run_count = existing["run_count"] + 1

                if abs(new_score - prev_score) > 5.0 or (job.get("salary") != "N/A" and existing["salary"] == "N/A"):
                    status = "UPDATED"
                else:
                    status = "STILL OPEN"

                update_sql = f"""
                    UPDATE jobs SET
                        last_seen = {ph},
                        run_count = {ph},
                        status = {ph},
                        match_score = {ph},
                        salary = CASE WHEN {ph} != 'N/A' THEN {ph} ELSE salary END,
                        job_url = CASE WHEN {ph} != '' THEN {ph} ELSE job_url END
                    WHERE job_hash = {ph}
                """
                cursor.execute(update_sql, (
                    now_str,
                    run_count,
                    status,
                    new_score,
                    job.get("salary", "N/A"),
                    job.get("salary", "N/A"),
                    job.get("job_url", ""),
                    job.get("job_url", ""),
                    job_hash
                ))

            conn.commit()
        finally:
            conn.close()

        # Return job with assigned DB status
        job_copy = dict(job)
        job_copy["status"] = status
        job_copy["job_hash"] = job_hash
        return job_copy

    def get_all_jobs_history(self) -> List[Dict[str, Any]]:
        """Returns all recorded jobs."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs ORDER BY last_seen DESC")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()
