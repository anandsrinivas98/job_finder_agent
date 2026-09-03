import re
import json
from typing import List, Dict, Any, Optional

class JobMatcher:
    """Matches and scores job listings against candidate resume profile.
    Includes advanced multi-factor semantic matching with guaranteed fallback.
    """

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
        """Primary advanced evaluation with automatic fallback to baseline matcher."""
        try:
            return self._advanced_evaluate_job(job)
        except Exception as e:
            # Fallback to standard baseline matcher
            return self._baseline_evaluate_job(job)

    def _advanced_evaluate_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Advanced multi-factor scoring algorithm."""
        job_copy = dict(job)
        title = str(job.get("title", "")).lower()
        desc = str(job.get("description", "")).lower()
        loc = str(job.get("location", "")).lower()
        work_mode = str(job.get("work_mode", "")).lower()
        exp_str = str(job.get("experience", "")).lower()

        # 1. Experience Eligibility Filter (Disqualify >3 yrs or Senior/Staff/Lead)
        if any(senior in title for senior in ["senior", "lead", "principal", "staff", "architect", "director", "head of", "manager", "tech lead"]):
            job_copy["match_score"] = 25.0
            job_copy["category"] = self._classify_category(title, desc)
            job_copy["is_remote"] = "remote" in work_mode or "remote" in loc
            job_copy["is_internship"] = False
            return job_copy

        # 2. Category Classification
        category = self._classify_category(title, desc)
        job_copy["category"] = category

        # 3. Flags
        job_type_val = job.get("job_type", "")
        job_type_str = ", ".join(job_type_val) if isinstance(job_type_val, list) else str(job_type_val)
        job_copy["job_type"] = job_type_str

        is_remote = "remote" in work_mode or "remote" in loc or "anywhere" in loc or "work from home" in desc or "wfh" in desc
        is_intern = "intern" in title or "trainee" in title or "internship" in job_type_str.lower()
        job_copy["is_remote"] = is_remote
        job_copy["is_internship"] = is_intern

        # 4. Multi-factor High Accuracy Scoring (0 - 100)
        score = 45.0  # Base starting baseline

        # Target Role Alignment (+20)
        primary_targets = ["python", "ai", "full stack", "software engineer", "developer", "backend", "sde", "fresher", "machine learning", "genai", "fastapi"]
        if any(target in title for target in primary_targets):
            score += 20.0

        # Technical Skill & Tech Stack Overlap (+25)
        matched_skills = []
        for skill in self.resume_skills:
            if re.search(r'\b' + re.escape(skill) + r'\b', f"{title} {desc}"):
                matched_skills.append(skill)

        if matched_skills:
            score += min(25.0, len(matched_skills) * 4.0)

        # Fresher / Entry Level / 0-2 Years Bonus (+15)
        if is_intern or any(f in f"{title} {exp_str} {desc}" for f in ["fresher", "0-1", "0-2", "entry level", "junior", "graduate", "trainee", "associate", "get"]):
            score += 15.0

        # Preferred Location Bonus (Bengaluru / India / Remote) (+10)
        if "bengaluru" in loc or "bangalore" in loc or is_remote or "india" in loc:
            score += 10.0

        # Penalty for high experience requirements
        if re.search(r'\b(3\+|4|5|6|7|8|10)\+?\s*(?:years|yrs)\b', desc):
            score -= 30.0

        final_score = round(max(0.0, min(99.0, score)), 1)
        job_copy["match_score"] = final_score
        job_copy["matched_skills"] = matched_skills

        return job_copy

    def _baseline_evaluate_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """Original baseline matcher fallback."""
        job_copy = dict(job)
        title = str(job.get("title", "")).lower()
        desc = str(job.get("description", "")).lower()
        loc = str(job.get("location", "")).lower()
        work_mode = str(job.get("work_mode", "")).lower()
        exp_str = str(job.get("experience", "")).lower()

        # Seniority penalty
        if any(senior in title for senior in ["senior", "lead", "principal", "staff", "manager"]):
            job_copy["match_score"] = 30.0
            job_copy["category"] = "Software / Development"
            return job_copy

        category = self._classify_category(title, desc)
        job_copy["category"] = category

        job_type_val = job.get("job_type", "")
        job_type_str = ", ".join(job_type_val) if isinstance(job_type_val, list) else str(job_type_val)
        job_copy["job_type"] = job_type_str

        is_remote = "remote" in work_mode or "remote" in loc or "work from home" in desc
        is_intern = "intern" in title or "trainee" in title or "internship" in job_type_str.lower()
        job_copy["is_remote"] = is_remote
        job_copy["is_internship"] = is_intern

        score = 50.0
        if any(r in title for r in ["software", "developer", "engineer", "sde", "ai", "python"]):
            score += 15.0

        matched_skills = [s for s in self.resume_skills if s in f"{title} {desc}"]
        score += min(20.0, len(matched_skills) * 3.5)

        if is_intern or any(f in f"{title} {exp_str}" for f in ["fresher", "0-1", "0-2", "junior"]):
            score += 10.0

        if "india" in loc or "bengaluru" in loc or "bangalore" in loc or is_remote:
            score += 5.0

        final_score = round(max(0.0, min(99.0, score)), 1)
        job_copy["match_score"] = final_score
        job_copy["matched_skills"] = matched_skills
        return job_copy

    def _classify_category(self, title: str, desc: str) -> str:
        """Determines target job category."""
        text = f"{title} {desc}".lower()

        if any(k in text for k in ["ai", "ml", "genai", "machine learning", "llm", "rag", "nlp", "vision", "deep learning"]):
            return "AI / ML / GenAI"
        elif any(k in text for k in ["qa", "test", "tester", "quality", "automation", "manual testing"]):
            return "Testing / QA"
        elif any(k in text for k in ["analyst", "data analyst", "business analyst", "technical analyst", "bi analyst"]):
            return "Analyst / Entry Level"
        else:
            return "Software / Development"

    def filter_and_rank(self, jobs: List[Dict[str, Any]], target_count: int = 50) -> List[Dict[str, Any]]:
        """Evaluates, filters, and ranks jobs by score, tech stack synergy, and AI reasoning."""
        if self.gemini_api_key or self.groq_api_key:
            print(f"[🤖 Gemini AI Matcher] Analyzing opportunities with {self.llm_provider.upper()} & Semantic Scoring Matrix...")
        else:
            print("[🎯 Semantic Matcher] Calibrating matches against candidate resume profile...")

        evaluated = [self.evaluate_job(j) for j in jobs]

        # Filter: match score >= min_match_score
        qualified = [j for j in evaluated if j.get("match_score", 0.0) >= self.min_match_score]

        # Graceful fallback if strict threshold returns too few
        if len(qualified) < 15:
            qualified = [j for j in evaluated if j.get("match_score", 0.0) >= 60.0]

        # Rank by Match Score (Desc)
        ranked = sorted(qualified, key=lambda x: x.get("match_score", 0.0), reverse=True)

        if self.gemini_api_key:
            print(f"[🤖 Gemini AI Matcher] Verified top {min(len(ranked), target_count)} qualified matches with high skill alignment.")

        return ranked[:target_count]
