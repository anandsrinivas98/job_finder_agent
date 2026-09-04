"""
V2 Match Scoring Engine for AI Job Hunting Agent.
Implements the 7-Factor Qualification Matrix (100% total) with detailed match breakdowns:
1. Technical Skills Alignment (35%)
2. Responsibilities Alignment (25%)
3. Project Relevance (15%)
4. Experience Eligibility (10%)
5. Education / Qualification (5%)
6. Location / Work Mode (5%)
7. Other Requirements / Eligibility (5%)
"""

import re
import json
from typing import List, Dict, Any, Optional
from core.models import MatchBreakdown

class JobMatcher:
    """Matches and scores job listings against candidate resume profile."""

    def __init__(self, profile: Dict[str, Any], min_match_score: float = 70.0,
                 gemini_api_key: str = "", groq_api_key: str = "", llm_provider: str = "gemini"):
        self.profile = profile
        self.min_match_score = min_match_score
        self.gemini_api_key = gemini_api_key.strip()
        self.groq_api_key = groq_api_key.strip()
        self.llm_provider = llm_provider.lower().strip()

        # Extract normalized candidate profile elements
        self.resume_skills = [s.lower() for s in profile.get("skills", [])]
        self.resume_roles = [r.lower() for r in profile.get("target_roles", [])]
        self.resume_text = profile.get("raw_text", "").lower()

        # Core candidate stack definition
        self.core_python_stack = ["python", "fastapi", "flask", "django", "sql", "postgresql", "mysql", "sqlalchemy"]
        self.core_ai_stack = ["langchain", "rag", "huggingface", "tensorflow", "scikit-learn", "nlp", "spacy", "nltk", "llm"]
        self.core_web_stack = ["react", "next.js", "javascript", "typescript", "node.js", "tailwind", "html", "css"]

    def evaluate_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluates a job record using the V2 7-Factor Qualification Matrix."""
        job_copy = dict(job)
        title = str(job.get("title", "")).lower()
        desc = str(job.get("description", "")).lower()
        loc = str(job.get("location", "")).lower()
        work_mode = str(job.get("work_mode", "")).lower()
        exp_str = str(job.get("experience", "")).lower()
        combined_text = f"{title} {desc} {exp_str}"

        # 1. Hard Seniority / Excessive Experience Filter
        senior_keywords = ["senior", "lead", "principal", "staff", "architect", "director", "head of", "manager", "tech lead"]
        if any(re.search(r'\b' + re.escape(sk) + r'\b', title) for sk in senior_keywords):
            breakdown = MatchBreakdown(skills=10.0, responsibilities=5.0, projects=5.0, experience=0.0, education=5.0, location=5.0, other=0.0)
            job_copy["match_score"] = breakdown.total()
            job_copy["match_breakdown"] = breakdown
            job_copy["category"] = self._classify_category(title, desc)
            job_copy["is_remote"] = "remote" in work_mode or "remote" in loc
            job_copy["is_internship"] = False
            return job_copy

        # 2. Factor 1: Technical Skills Alignment (Max 35 pts)
        matched_skills = []
        for skill in self.resume_skills:
            if re.search(r'\b' + re.escape(skill) + r'\b', combined_text):
                matched_skills.append(skill)

        # Calculate skill score (base 15 for primary language match + 3 per additional skill)
        skill_score = 0.0
        if any(ps in combined_text for ps in ["python", "javascript", "typescript", "sql"]):
            skill_score += 15.0
        skill_score += min(20.0, len(matched_skills) * 3.0)
        skill_score = min(35.0, skill_score)

        # 3. Factor 2: Responsibilities Alignment (Max 25 pts)
        resp_score = 0.0
        role_targets = ["software engineer", "developer", "sde", "backend", "full stack", "ai engineer", "ml engineer", "genai", "intern", "trainee", "associate", "qa", "analyst"]
        for target in role_targets:
            if target in title:
                resp_score = max(resp_score, 20.0)
                break

        if any(kw in desc for kw in ["develop", "build", "api", "design", "model", "pipeline", "test"]):
            resp_score = min(25.0, resp_score + 5.0)

        # 4. Factor 3: Project Relevance (Max 15 pts)
        proj_score = 0.0
        if any(kw in combined_text for kw in ["rag", "langchain", "microservices", "fastapi", "next.js", "huggingface", "docker", "spacy"]):
            proj_score = 15.0
        elif any(kw in combined_text for kw in ["react", "node", "tensorflow", "scikit-learn", "postgres", "rest api"]):
            proj_score = 11.0
        elif any(kw in combined_text for kw in ["python", "sql", "full stack", "frontend", "backend"]):
            proj_score = 8.0

        # 5. Factor 4: Experience Eligibility (Max 10 pts)
        exp_score = 0.0
        if any(kw in combined_text for kw in ["fresher", "0-1", "0-2", "entry level", "graduate trainee", "intern", "internship", "junior"]):
            exp_score = 10.0
        elif not re.search(r'\b([3-9]|1[0-9])\+?\s*(?:years|yrs)\b', desc):
            exp_score = 8.0
        else:
            exp_score = 0.0

        # 6. Factor 5: Education / Qualification (Max 5 pts)
        edu_score = 5.0  # B.E. in Information Science satisfies degree requirements

        # 7. Factor 6: Location / Work Mode (Max 5 pts)
        loc_score = 0.0
        if any(kw in loc for kw in ["bengaluru", "bangalore"]) or "remote" in work_mode or "remote" in loc:
            loc_score = 5.0
        elif any(kw in loc for kw in ["chennai", "hyderabad", "pune", "mumbai", "delhi", "noida", "gurgaon", "gurugram", "india"]):
            loc_score = 4.0
        else:
            loc_score = 3.0

        # 8. Factor 7: Other Requirements / Eligibility (Max 5 pts)
        other_score = 5.0

        # Calculate Breakdown & Total
        breakdown = MatchBreakdown(
            skills=round(skill_score, 1),
            responsibilities=round(resp_score, 1),
            projects=round(proj_score, 1),
            experience=round(exp_score, 1),
            education=round(edu_score, 1),
            location=round(loc_score, 1),
            other=round(other_score, 1)
        )

        final_score = breakdown.total()

        # Hard penalty for experience disqualifiers
        if re.search(r'\b(4|5|6|7|8|10)\+?\s*(?:years|yrs)\b', desc[:1500]):
            final_score = max(0.0, final_score - 40.0)

        job_copy["match_score"] = round(min(100.0, final_score), 1)
        job_copy["match_breakdown"] = breakdown
        job_copy["matched_skills"] = matched_skills
        job_copy["category"] = self._classify_category(title, desc)
        job_copy["is_remote"] = "remote" in work_mode or "remote" in loc
        job_copy["is_internship"] = "intern" in title or "trainee" in title or "internship" in str(job.get("job_type", "")).lower()

        return job_copy

    def _classify_category(self, title: str, desc: str) -> str:
        """Classifies opportunity into one of the 5 canonical categories."""
        combined = f"{title} {desc}".lower()

        if any(k in title for k in ["ai", "ml", "machine learning", "genai", "generative ai", "llm", "rag", "nlp", "computer vision", "deep learning"]):
            return "AI / ML / GenAI"
        elif any(k in title for k in ["qa", "tester", "testing", "sdet", "quality analyst", "automation tester"]):
            return "Testing / QA"
        elif any(k in title for k in ["data analyst", "business analyst", "bi analyst", "product analyst", "technology analyst", "operations analyst"]):
            return "Analyst / Entry Level"
        elif any(k in title for k in ["intern", "internship", "trainee", "graduate trainee", "get", "apprentice"]):
            return "Internships"
        else:
            return "Software / Development"

    def filter_and_rank(self, jobs: List[Dict[str, Any]], target_count: int = 50) -> List[Dict[str, Any]]:
        """Evaluates all candidate jobs, applies match threshold, and ranks by relevance."""
        scored_jobs = [self.evaluate_job(j) for j in jobs]
        qualified = [j for j in scored_jobs if j.get("match_score", 0) >= self.min_match_score]
        # Rank by match score (highest first)
        ranked = sorted(qualified, key=lambda x: x.get("match_score", 0), reverse=True)
        return ranked[:target_count]
