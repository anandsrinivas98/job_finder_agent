import pytest
from pathlib import Path
from core.db import JobHistoryDB

def test_db_upsert_and_status_tracking(tmp_path):
    db_file = tmp_path / "test_history.db"
    db = JobHistoryDB(db_file)

    sample_job = {
        "company": "Acme Corp",
        "title": "Junior Python Developer",
        "location": "Bengaluru",
        "work_mode": "Hybrid",
        "posted_date": "2026-09-03",
        "salary": "N/A",
        "experience": "0-1 yrs",
        "job_type": "Full-time",
        "job_url": "https://example.com/jobs/1",
        "source": "LinkedIn",
        "match_score": 85.0,
        "category": "Software / Development"
    }

    # 1. First time -> 🆕 NEW
    res1 = db.upsert_and_classify_job(sample_job)
    assert res1["status"] == "NEW"

    # 2. Second time without score change -> ⏳ STILL OPEN
    res2 = db.upsert_and_classify_job(sample_job)
    assert res2["status"] == "STILL OPEN"

    # 3. Third time with significant score or salary change -> 🔄 UPDATED
    sample_job_updated = dict(sample_job)
    sample_job_updated["salary"] = "₹8 - ₹12 LPA"
    res3 = db.upsert_and_classify_job(sample_job_updated)
    assert res3["status"] == "UPDATED"

    # Verify count in DB
    history = db.get_all_jobs_history()
    assert len(history) == 1
    assert history[0]["company"] == "Acme Corp"
