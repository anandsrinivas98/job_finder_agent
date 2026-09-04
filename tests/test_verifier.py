import pytest
from core.verifier import JobVerifier
from core.models import VerificationStatus

def test_job_verifier_dimensions():
    verifier = JobVerifier(max_experience_years=3)

    # 1. Valid Fresher Role
    valid_job = {
        "title": "Junior Python Developer",
        "company": "Infosys",
        "location": "Bengaluru, India",
        "job_url": "https://careers.infosys.com/job/123",
        "company_website": "https://www.infosys.com",
        "work_mode": "Hybrid",
        "posted_date": "2026-09-04",
        "description": "Looking for entry level Python developers with FastAPI knowledge."
    }
    res_valid = verifier.verify_job(valid_job)
    assert res_valid["verification_status"] == VerificationStatus.VERIFIED.value
    assert res_valid["experience_verified"] is True
    assert res_valid["india_eligibility_verified"] is True

    # 2. Senior Disqualified Role
    senior_job = {
        "title": "Senior Principal Architect",
        "company": "Tech Corp",
        "location": "Bengaluru, India",
        "job_url": "https://techcorp.com/job/456",
        "description": "Requires 8+ years of distributed systems experience."
    }
    res_senior = verifier.verify_job(senior_job)
    assert res_senior["verification_status"] == VerificationStatus.REJECTED.value
    assert res_senior["experience_verified"] is False
