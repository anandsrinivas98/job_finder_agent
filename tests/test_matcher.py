import pytest
from core.matcher import JobMatcher

def test_matcher_scoring_and_classification():
    profile = {
        "skills": ["Python", "Fastapi", "React", "Postgresql", "Langchain", "Pytest"],
        "target_roles": ["Software Engineer", "AI Engineer"],
        "raw_text": "Built AI assistants using Python, LangChain, and FastAPI."
    }

    matcher = JobMatcher(profile=profile, min_match_score=70.0)

    # High match AI job
    ai_job = {
        "company": "GenAI Labs",
        "title": "Junior AI Engineer",
        "location": "Bengaluru",
        "work_mode": "Hybrid",
        "experience": "0-1 yrs",
        "description": "Looking for Python, LangChain, FastAPI skills for GenAI apps."
    }
    evaluated_ai = matcher.evaluate_job(ai_job)
    assert evaluated_ai["category"] == "AI / ML / GenAI"
    assert evaluated_ai["match_score"] >= 75.0

    # Senior job should be penalized
    senior_job = {
        "company": "BigTech",
        "title": "Principal Architect",
        "location": "Bengaluru",
        "work_mode": "Remote",
        "experience": "10+ yrs",
        "description": "Requires 10 years experience."
    }
    evaluated_senior = matcher.evaluate_job(senior_job)
    assert evaluated_senior["match_score"] <= 40.0
