import re
import json
import requests
from typing import List, Dict, Any, Optional

class JobMatcher:
    """Matches and scores job listings against candidate resume profile with optional Free LLM enhancements."""

    def __init__(self, profile: Dict[str, Any], min_match_score: float = 70.0,
                 gemini_api_key: str = "", groq_api_key: str = "", llm_provider: str = "gemini"):
        self.profile = profile
        self.min_match_score = min_match_score
        self.gemini_api_key = gemini_api_key.strip()
        self.groq_api_key = groq_api_key.strip()
        self.llm_provider = llm_provider.lower().strip()
        self.resume_skills = [s.lower() for s in profile.get("skills", [])]
        self.resume_roles = [r.lower() for r in profile.get("target_roles", [])]
        self.resume_text = profile.get("raw_text", "").lower()

    def evaluate_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Calculates 0-100% score, assigns category, and tags."""
        job_copy = dict(job)
        title = job.get("title", "").lower()
        desc = job.get("description", "").lower()
        loc = job.get("location", "").lower()
        work_mode = job.get("work_mode", "").lower()
        exp_str = job.get("experience", "").lower()

        # 1. Experience Eligibility Filter (Skip > 3 yrs)
        if any(senior in title for senior in ["senior", "lead", "principal", "staff", "architect", "director", "head of", "manager"]):
            job_copy["match_score"] = 30.0
            return job_copy

        # 2. Category Classification
        category = self._classify_category(title, desc)
        job_copy["category"] = category

        # 3. Flags
        is_remote = "remote" in work_mode or "remote" in loc or "anywhere" in loc or "work from home" in desc or "wfh" in desc
        is_intern = "intern" in title or "trainee" in title or "internship" in job.get("job_type", "").lower()
        job_copy["is_remote"] = is_remote
        job_copy["is_internship"] = is_intern

        # 4. Multi-factor Scoring (0 - 100)
        score = 50.0  # Base starting score

        # Role & Title Alignment (+15)
        if any(r in title for r in ["software", "developer", "engineer", "sde", "ai", "ml", "qa", "analyst", "python"]):
            score += 15.0

        # Skill & Tech Stack Overlap (+20)
        matched_skills = []
        for skill in self.resume_skills:
            if re.search(r'\b' + re.escape(skill) + r'\b', f"{title} {desc}"):
                matched_skills.append(skill)

        if matched_skills:
            score += min(20.0, len(matched_skills) * 3.5)

        # Fresher / Entry Level bonus (+10)
        if is_intern or any(f in f"{title} {exp_str} {desc}" for f in ["fresher", "0-1", "0-2", "entry level", "junior", "graduate", "trainee", "associate"]):
            score += 10.0

        # Location Bonus (+5)
        if "india" in loc or any(city in loc for city in ["bengaluru", "bangalore", "hyderabad", "pune", "chennai", "delhi", "gurgaon", "noida", "mumbai", "remote"]):
            score += 5.0

        # Penalize if explicit high experience is mentioned
        if re.search(r'\b(4|5|6|7|8|10)\+?\s*(?:years|yrs)\b', desc):
            score -= 25.0

        final_score = round(max(0.0, min(99.0, score)), 1)
        job_copy["match_score"] = final_score
        job_copy["matched_skills"] = matched_skills

        return job_copy

    def _classify_category(self, title: str, desc: str) -> str:
        """Determines target job category."""
        text = f"{title} {desc}"

        if any(k in title for k in ["ai", "ml", "genai", "machine learning", "llm", "rag", "nlp", "vision", "deep learning", "prompt"]):
            return "AI / ML / GenAI"
        elif any(k in title for k in ["qa", "test", "tester", "quality", "automation", "manual testing"]):
            return "Testing / QA"
        elif any(k in title for k in ["analyst", "data analyst", "business analyst", "technical analyst", "bi analyst"]):
            return "Analyst / Entry Level"
        elif any(k in title for k in ["sde", "developer", "software", "backend", "full stack", "frontend", "python", "react", "api"]):
            return "Software / Development"
        else:
            return "Software / Development"

    def filter_and_rank(self, jobs: List[Dict[str, Any]], target_count: int = 25) -> List[Dict[str, Any]]:
        """Evaluates, filters, and ranks jobs by score and freshness."""
        evaluated = [self.evaluate_job(j) for j in jobs]

        # Filter: match score >= min_match_score
        qualified = [j for j in evaluated if j.get("match_score", 0.0) >= self.min_match_score]

        # If too few meet strict min score, gracefully take the best available above 60%
        if len(qualified) < 10:
            qualified = [j for j in evaluated if j.get("match_score", 0.0) >= 60.0]

        # Rank by Match Score (Desc)
        ranked = sorted(qualified, key=lambda x: x.get("match_score", 0.0), reverse=True)

        return ranked[:target_count]
