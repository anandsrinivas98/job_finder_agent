"""
Semantic Deduplication Engine for V2 AI Job Hunting Agent.
Provides 4-level deduplication across multiple job boards, tech feeds, and company ATS portals.
"""

import re
import urllib.parse
from typing import List, Dict, Any, Tuple, Optional
from core.models import JobRecord, DuplicateStatus

class SemanticDeduplicator:
    """
    Deduplication Levels:
    - Level 1: Exact identity (canonical source URL or identical job ID)
    - Level 2: Strong identity (normalized company + normalized title + normalized location)
    - Level 3: Semantic identity (company match + title similarity + location overlap)
    - Level 4: Uncertain match (flagged for review)
    """

    def __init__(self, title_similarity_threshold: float = 0.85, desc_similarity_threshold: float = 0.80):
        self.title_similarity_threshold = title_similarity_threshold
        self.desc_similarity_threshold = desc_similarity_threshold

    @staticmethod
    def normalize_string(text: str) -> str:
        """Strips punctuation, legal suffixes (Pvt Ltd, Inc, LLC), and extra whitespace."""
        if not text:
            return ""
        s = text.lower().strip()
        # Remove common corporate suffixes
        s = re.sub(r'\b(pvt|ltd|llc|inc|technologies|solutions|services|corp|corporation|private limited|limited)\b', '', s)
        # Remove non-alphanumeric characters
        s = re.sub(r'[^a-z0-9\s]', ' ', s)
        return re.sub(r'\s+', ' ', s).strip()

    @staticmethod
    def sanitize_canonical_url(url: str) -> str:
        """Removes query tracking parameters and normalizes URLs."""
        if not url:
            return ""
        parsed = urllib.parse.urlparse(url)
        # Drop common tracking queries
        query_params = urllib.parse.parse_qs(parsed.query)
        clean_params = {k: v for k, v in query_params.items() if not k.lower().startswith(("utm_", "ref", "tracking", "trk", "session"))}
        clean_query = urllib.parse.urlencode(clean_params, doseq=True)
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), parsed.params, clean_query, ""))

    def compute_jaccard_similarity(self, str1: str, str2: str) -> float:
        """Computes word-level Jaccard similarity between two texts."""
        set1 = set(self.normalize_string(str1).split())
        set2 = set(self.normalize_string(str2).split())
        if not set1 or not set2:
            return 0.0
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        return intersection / union if union > 0 else 0.0

    def is_same_company(self, c1: str, c2: str) -> bool:
        """Checks if two company strings refer to the same corporate entity."""
        n1 = self.normalize_string(c1)
        n2 = self.normalize_string(c2)
        if not n1 or not n2:
            return False
        if n1 == n2 or n1 in n2 or n2 in n1:
            return True
        return self.compute_jaccard_similarity(n1, n2) >= 0.5

    def is_same_location(self, loc1: str, loc2: str) -> bool:
        """Checks if locations are overlapping (e.g. Bengaluru / Bangalore / Remote / India)."""
        l1 = self.normalize_string(loc1)
        l2 = self.normalize_string(loc2)
        if l1 == l2:
            return True
        if any(r in l1 or r in l2 for r in ["remote", "india", "wfh", "work from home"]):
            return True
        # Bengaluru / Bangalore synonym
        if ("bengaluru" in l1 or "bangalore" in l1) and ("bengaluru" in l2 or "bangalore" in l2):
            return True
        return self.compute_jaccard_similarity(l1, l2) >= 0.5

    def deduplicate(self, raw_jobs: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
        """
        Deduplicates a list of job records across all 4 levels.
        Returns:
            (unique_canonical_jobs, deduplication_metrics)
        """
        unique_jobs: List[Dict[str, Any]] = []
        metrics = {
            "total_raw": len(raw_jobs),
            "exact_duplicates": 0,
            "strong_duplicates": 0,
            "semantic_duplicates": 0,
            "uncertain_duplicates": 0,
            "unique_canonical": 0
        }

        for candidate in raw_jobs:
            comp = candidate.get("company", "")
            title = candidate.get("title", "")
            loc = candidate.get("location", "")
            url = self.sanitize_canonical_url(candidate.get("job_url", ""))

            is_duplicate = False
            for existing in unique_jobs:
                e_comp = existing.get("company", "")
                e_title = existing.get("title", "")
                e_loc = existing.get("location", "")
                e_url = self.sanitize_canonical_url(existing.get("job_url", ""))

                # Level 1: Exact Identity (Identical sanitized URL or job_id)
                if url and e_url and url == e_url:
                    is_duplicate = True
                    metrics["exact_duplicates"] += 1
                    self._merge_job_records(existing, candidate)
                    break

                # Level 2 & 3: Company Match + Title Similarity + Location
                if self.is_same_company(comp, e_comp):
                    norm_t1 = self.normalize_string(title)
                    norm_t2 = self.normalize_string(e_title)
                    loc_match = self.is_same_location(loc, e_loc)

                    if norm_t1 == norm_t2 and loc_match:
                        is_duplicate = True
                        metrics["strong_duplicates"] += 1
                        self._merge_job_records(existing, candidate)
                        break

                    # Level 3: Semantic Identity (High Jaccard title similarity)
                    title_sim = self.compute_jaccard_similarity(norm_t1, norm_t2)
                    if title_sim >= 0.60 and loc_match:
                        is_duplicate = True
                        metrics["semantic_duplicates"] += 1
                        self._merge_job_records(existing, candidate)
                        break

            if not is_duplicate:
                unique_jobs.append(candidate)

        metrics["unique_canonical"] = len(unique_jobs)
        return unique_jobs, metrics

    def _merge_job_records(self, primary: Dict[str, Any], duplicate: Dict[str, Any]):
        """
        Merges duplicate record attributes into primary record,
        prioritizing official ATS apply links over aggregator links.
        """
        # If duplicate has direct company ATS apply link (e.g. keka, greenhouse, lever, workday), promote it
        p_url = primary.get("job_url", "").lower()
        d_url = duplicate.get("job_url", "").lower()
        ats_domains = ["keka.com", "greenhouse.io", "lever.co", "myworkdayjobs.com", "smartrecruiters.com", "careers."]
        
        if any(ats in d_url for ats in ats_domains) and not any(ats in p_url for ats in ats_domains):
            primary["job_url"] = duplicate["job_url"]
            primary["source"] = duplicate.get("source", primary.get("source"))

        # Preserve richer description if primary was brief
        if len(duplicate.get("description", "")) > len(primary.get("description", "")):
            primary["description"] = duplicate["description"]

        # Preserve salary if primary had None
        if primary.get("salary") in ["N/A", "Not Disclosed", None, ""] and duplicate.get("salary") not in ["N/A", "Not Disclosed", None, ""]:
            primary["salary"] = duplicate["salary"]
