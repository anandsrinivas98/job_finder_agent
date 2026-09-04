import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

with open('scratch/stage2_results.json', encoding='utf-8') as f:
    data = json.load(f)

jobs = data.get('jobs', [])
print(f"TOTAL VERIFIED QUALIFIED JOBS: {len(jobs)}")

def print_table(job_sublist, header):
    print(f"\n### {header} ({len(job_sublist)} Opportunities)")
    print("| # | Company | Role | Location | Work Mode | Posted | Match | Salary | Apply |")
    print("|---|---|---|---|---|---|---|---|---|")
    for idx, j in enumerate(job_sublist, 1):
        url = j.get('job_url', '')
        link = f"[Apply ↗]({url})" if url else "N/A"
        comp = j.get('company', 'N/A')
        role = j.get('title', 'N/A')
        loc = j.get('location', 'India')
        mode = j.get('work_mode', 'N/A')
        posted = j.get('posted_date', 'Recently')
        score = f"{j.get('match_score', 0)}%"
        sal = j.get('salary', 'Not Disclosed')
        print(f"| {idx} | **{comp}** | {role} | {loc} | {mode} | {posted} | **{score}** | {sal} | {link} |")

# 1. Top 10
print_table(jobs[:10], "TOP OPPORTUNITIES")

# 2. Categories
ai_jobs = [j for j in jobs if j.get('category') == 'AI / ML / GenAI']
swe_jobs = [j for j in jobs if j.get('category') == 'Software / Development']
qa_jobs = [j for j in jobs if j.get('category') == 'Testing / QA']
analyst_jobs = [j for j in jobs if j.get('category') == 'Analyst / Entry Level']
intern_jobs = [j for j in jobs if j.get('is_internship') or 'intern' in j.get('title','').lower() or 'intern' in j.get('job_type','').lower()]
fresher_jobs = [j for j in jobs if 'fresher' in j.get('title','').lower() or 'junior' in j.get('title','').lower() or 'trainee' in j.get('title','').lower() or 'graduate' in j.get('title','').lower()]

print_table(ai_jobs[:8], "AI / ML / GENAI")
print_table(swe_jobs[:8], "SOFTWARE DEVELOPMENT")
print_table(qa_jobs[:5], "TESTING / QA / SDET")
print_table(analyst_jobs[:5], "DATA / ANALYST")
print_table(fresher_jobs[:6], "FRESHER / GRADUATE")
print_table(intern_jobs[:6], "INTERNSHIPS")

# Metrics
print("\n--- METRICS ---")
print(f"Discovered: {data.get('total_raw')}")
print(f"Scored >= 70%: {data.get('total_scored')}")
scores = [j.get('match_score', 0) for j in jobs]
print(f"Avg Score: {sum(scores)/len(scores):.1f}%" if scores else "N/A")
print(f"Max Score: {max(scores)}%" if scores else "N/A")
