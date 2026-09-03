import pytest
from pathlib import Path
from core.resume_parser import ResumeParser

def test_resume_parser_markdown(tmp_path):
    resume_file = tmp_path / "test_resume.md"
    resume_file.write_text("""
    # Candidate Profile
    ## Skills
    - Python, FastAPI, Docker, SQL, LangChain, PyTest, Selenium
    ## Target Roles
    - AI Engineer, Software Engineer
    ## Experience
    - 1 year of exp in backend development
    """, encoding="utf-8")

    parser = ResumeParser(resume_file)
    profile = parser.parse(force_refresh=True)

    assert "Python" in profile.get("skills", [])
    assert "Fastapi" in profile.get("skills", []) or "FASTAPI" in profile.get("skills", [])
    assert len(profile.get("skills", [])) >= 4
    assert profile.get("estimated_experience_years", 0) >= 1.0

def test_resume_parser_nonexistent_file():
    parser = ResumeParser(Path("nonexistent_resume.pdf"))
    with pytest.raises(FileNotFoundError):
        parser.parse()
