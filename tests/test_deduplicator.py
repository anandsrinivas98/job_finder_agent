import pytest
from core.deduplicator import SemanticDeduplicator

def test_semantic_deduplication_exact_and_fuzzy():
    dedup = SemanticDeduplicator()

    raw_jobs = [
        {
            "company": "Google India Pvt Ltd",
            "title": "Software Engineer, Python",
            "location": "Bengaluru, Karnataka",
            "job_url": "https://www.linkedin.com/jobs/view/12345?utm_source=feed"
        },
        {
            "company": "Google",
            "title": "Software Engineer - Python",
            "location": "Bangalore",
            "job_url": "https://careers.google.com/jobs/results/12345"
        },
        {
            "company": "Microsoft",
            "title": "AI Engineer Fresher",
            "location": "Hyderabad",
            "job_url": "https://careers.microsoft.com/us/en/job/67890"
        }
    ]

    unique_jobs, metrics = dedup.deduplicate(raw_jobs)
    assert len(unique_jobs) == 2
    assert metrics["unique_canonical"] == 2
    assert metrics["semantic_duplicates"] == 1 or metrics["strong_duplicates"] == 1
