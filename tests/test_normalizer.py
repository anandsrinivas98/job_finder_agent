import pytest
from datetime import datetime, timedelta
from core.normalizer import JobNormalizer
from core.models import FreshnessState, PostedDateStatus

def test_company_normalization():
    normalizer = JobNormalizer()
    assert normalizer.clean_company_name("Google India Pvt Ltd") == "Google India"
    assert normalizer.clean_company_name("Infosys Technologies Limited") == "Infosys"
    assert normalizer.normalize_text("Microsoft Corporation") == "microsoft"

def test_title_cleaning():
    normalizer = JobNormalizer()
    assert normalizer.clean_title("[HIRING] Python Developer (Urgent)") == "Python Developer"
    assert normalizer.clean_title("AI Engineer - Full Time - Fresher") == "AI Engineer"

def test_location_and_work_mode():
    normalizer = JobNormalizer()
    loc, mode, is_remote = normalizer.normalize_location("Bangalore", "Python developer needed")
    assert loc == "Bengaluru, Karnataka, India"
    assert mode == "On-site"
    assert is_remote is False

    loc_rem, mode_rem, is_rem = normalizer.normalize_location("Remote", "100% remote position")
    assert "Remote" in loc_rem
    assert mode_rem == "Remote"
    assert is_rem is True

def test_freshness_states():
    normalizer = JobNormalizer()
    now = datetime.now()

    # Under 24h
    iso_24 = (now - timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M:%S")
    _, status_24, state_24, age_24 = normalizer.compute_freshness(iso_24)
    assert status_24 == PostedDateStatus.VERIFIED.value
    assert state_24 == FreshnessState.FRESH_24H.value
    assert age_24 < 24.0

    # 48h -> FRESH_72H
    iso_72 = (now - timedelta(hours=48)).strftime("%Y-%m-%d %H:%M:%S")
    _, status_72, state_72, age_72 = normalizer.compute_freshness(iso_72)
    assert state_72 == FreshnessState.FRESH_72H.value

    # 5 days -> FRESH_7D
    iso_7d = (now - timedelta(days=5)).strftime("%Y-%m-%d")
    _, _, state_7d, _ = normalizer.compute_freshness(iso_7d)
    assert state_7d == FreshnessState.FRESH_7D.value

    # Unknown date
    _, status_unk, state_unk, age_unk = normalizer.compute_freshness(None)
    assert status_unk == PostedDateStatus.NOT_VERIFIED.value
    assert state_unk == FreshnessState.DATE_UNKNOWN.value
    assert age_unk is None

def test_full_job_normalization():
    normalizer = JobNormalizer()
    raw = {
        "company": "Amazon Development Centre India Pvt Ltd",
        "title": "Software Development Engineer - Fresher",
        "location": "Bangalore",
        "job_url": "https://amazon.jobs/en/jobs/12345?utm_source=linkedin&ref=share",
        "description": "Looking for Python, FastAPI, and Docker skills to build scalable microservices.",
        "posted_date": datetime.now().strftime("%Y-%m-%d")
    }
    norm = normalizer.normalize(raw)
    assert norm["company"] == "Amazon Development Centre India"
    assert norm["title"] == "Software Development Engineer"
    assert "utm_source" not in norm["job_url"]
    assert "Python" in norm["skills"]
    assert "FastAPI" in norm["skills"]
    assert norm["freshness_state"] == FreshnessState.FRESH_24H.value
