import os
import re
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import pypdf
import docx

class ResumeParser:
    """Extracts structured skills, tech stack, and profile from PDF, DOCX, TXT, or MD resumes."""

    def __init__(self, resume_path: Path):
        self.resume_path = Path(resume_path)
        self.cache_path = self.resume_path.parent / f".{self.resume_path.stem}_parsed.json"

    def read_raw_text(self) -> str:
        """Reads raw text from resume depending on extension."""
        if not self.resume_path.exists():
            raise FileNotFoundError(f"Resume file not found at: {self.resume_path}")

        ext = self.resume_path.suffix.lower()
        if ext in [".txt", ".md"]:
            with open(self.resume_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()

        elif ext == ".pdf":
            reader = pypdf.PdfReader(str(self.resume_path))
            text = "\n".join([page.extract_text() or "" for page in reader.pages])
            return text

        elif ext in [".docx", ".doc"]:
            doc = docx.Document(str(self.resume_path))
            text = "\n".join([p.text for p in doc.paragraphs])
            return text

        else:
            with open(self.resume_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()

    def parse(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Parses the resume and returns a structured dictionary."""
        # Use cached parsed profile if available and not modified
        if not force_refresh and self.cache_path.exists():
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)
                    if cached_data.get("mtime") == self.resume_path.stat().st_mtime:
                        return cached_data.get("profile", {})
            except Exception:
                pass

        raw_text = self.read_raw_text()
        profile = self._extract_profile_data(raw_text)

        # Cache result
        try:
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump({
                    "mtime": self.resume_path.stat().st_mtime,
                    "profile": profile
                }, f, indent=2)
        except Exception:
            pass

        return profile

    def _extract_profile_data(self, text: str) -> Dict[str, Any]:
        """Extracts structured fields using robust heuristics and keyword analysis."""
        lower_text = text.lower()

        # Common Tech Keywords to look for
        skill_catalog = [
            "python", "javascript", "typescript", "java", "c++", "c#", "golang", "rust", "php", "ruby", "sql", "html", "css",
            "react", "react.js", "next.js", "vue", "angular", "node.js", "express", "fastapi", "flask", "django", "spring boot",
            "rest", "restful api", "graphql", "grpc", "microservices", "docker", "kubernetes", "aws", "gcp", "azure", "linux", "git",
            "postgresql", "mysql", "mongodb", "redis", "sqlite", "pinecone", "chromadb", "weaviate", "qdrant",
            "openai", "langchain", "llamaindex", "rag", "llm", "large language models", "prompt engineering", "genai", "generative ai",
            "machine learning", "deep learning", "pytorch", "tensorflow", "scikit-learn", "pandas", "numpy", "hugging face", "transformers", "nlp", "computer vision",
            "pytest", "selenium", "postman", "jest", "cypress", "playwright", "manual testing", "automation testing", "qa",
            "data analysis", "tableau", "power bi", "excel", "spark", "hadoop", "airflow"
        ]

        found_skills = []
        for skill in skill_catalog:
            pattern = r'\b' + re.escape(skill) + r'\b'
            if re.search(pattern, lower_text):
                found_skills.append(skill.title() if len(skill) > 3 else skill.upper())

        # Experience estimate (years)
        exp_years = 0.0
        exp_matches = re.findall(r'(\d+(?:\.\d+)?)\s*(?:\+|-)?\s*(?:years|yrs|year|yr)\s*(?:of)?\s*exp', lower_text)
        if exp_matches:
            try:
                exp_years = max([float(x) for x in exp_matches])
            except ValueError:
                exp_years = 0.0

        # Target roles inferred or mentioned
        roles = []
        possible_roles = [
            "Software Engineer", "Software Developer", "SDE", "Full Stack Developer", "Backend Developer", "Frontend Developer",
            "Python Developer", "React Developer", "AI Engineer", "AI/ML Engineer", "Machine Learning Engineer", "GenAI Engineer",
            "LLM Engineer", "QA Engineer", "Software Test Engineer", "Automation Tester", "Data Analyst", "Business Analyst"
        ]
        for role in possible_roles:
            if re.search(r'\b' + re.escape(role.lower()) + r'\b', lower_text):
                roles.append(role)

        if not roles:
            roles = ["Software Engineer", "AI/ML Engineer", "Python Developer", "Data Analyst"]

        return {
            "raw_text": text,
            "skills": list(set(found_skills)),
            "target_roles": roles,
            "estimated_experience_years": exp_years,
            "key_highlights": [
                line.strip("- *# \t") for line in text.splitlines()
                if len(line.strip()) > 30 and any(kw in line.lower() for kw in ["built", "developed", "designed", "created", "implemented", "engineered"])
            ][:10]
        }
