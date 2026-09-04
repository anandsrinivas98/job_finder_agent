import json, sys
sys.stdout.reconfigure(encoding='utf-8')
with open('scratch/stage2_results.json', encoding='utf-8') as f:
    data = json.load(f)

for idx, j in enumerate(data.get('jobs', []), 1):
    comp = j.get('company')
    title = j.get('title')
    loc = j.get('location')
    cat = j.get('category')
    score = j.get('match_score')
    url = j.get('job_url')
    src = j.get('source')
    sal = j.get('salary', 'Not Disclosed')
    mode = j.get('work_mode', 'On-site / Hybrid')
    posted = j.get('posted_date', 'Recently')
    print(f"{idx} | {comp} | {title} | {loc} | {cat} | {score}% | {mode} | {posted} | {sal} | {src} | {url}")
