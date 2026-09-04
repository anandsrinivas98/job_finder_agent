# 🚀 Automated Daily AI Job Hunting Agent

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tested with Pytest](https://img.shields.io/badge/Tests-100%25%20Passing-brightgreen.svg)](tests/)
[![Security: CWE--1236 Defense](https://img.shields.io/badge/Security-Formula%20Injection%20Safe-success.svg)](core/excel_generator.py)

An autonomous, self-hosted **AI Recruiter and Automated Job Hunter** that scans **30+ job boards, tech startup platforms, and developer hiring feeds** (via **100% Open-Source JobSpy**, public REST APIs, and Reddit communities), matches and ranks openings (**0–100%**) against your **Resume**, builds a professional **6-sheet Excel report** with **1-Click LinkedIn Referral Links**, uploads directly to **Google Drive**, and delivers daily digests to **Email, WhatsApp, Telegram, or Ntfy**.

---

## 🌟 Key Features

* 📄 **Resume as Source of Truth**: Auto-parses `.pdf`, `.docx`, `.txt`, and `.md` resumes to extract technical skills, projects, and target roles.
* 🌐 **30+ Supported Job Boards & Sources (100% Free & Open-Source)**:
  * **Primary Job Boards**: LinkedIn Jobs, Indeed India, Google Jobs, Glassdoor, ZipRecruiter *(Direct live scraping via JobSpy with 98% apply link accuracy)*.
  * **Indian Tech Portals**: Naukri, Internshala, Wellfound, Instahyre, Cutshort, Hirist, Foundit, Shine, TimesJobs, Freshersworld, Fresherslive, Unstop, Apna, WorkIndia.
  * **Tech / Startups / Remote**: YC Jobs (WorkAtAStartup), HackerEarth, HackerRank, Arc.dev, Turing, We Work Remotely, RemoteOK, Remotive, Himalayas, Jobicy, Arbeitnow.
  * **ATS Portals & Communities**: Greenhouse, Lever, Workday, Reddit Developer Hiring (`r/forhire`, `r/jobbit`, `r/remotejobs`).
* 🎯 **Smart Weighted Scoring (0–100%)**: Filters out senior roles (>3 yrs), rewards fresher/entry-level keywords, tech stack overlap, and prioritized locations (Bengaluru & Remote).
* 🤝 **1-Click Referral Search**: Every row in the Excel report includes an **`Ask Referral ↗`** link that opens LinkedIn pre-filtered for software engineers working at that exact hiring company.
* ☁️ **Google Drive Cloud Integration**: Automatically uploads daily Excel reports directly into your designated personal or shared Google Drive folder.
* 💾 **Dual-Engine Database**: Zero-config local **SQLite** (`jobs_history.db`) or Cloud **PostgreSQL / Supabase** (`DATABASE_URL`) with SHA-256 deduplication and status tracking (`🆕 NEW`, `🔄 UPDATED`, `⏳ STILL OPEN`).
* 📊 **6-Sheet Styled Excel Report**: Professional OpenPyXL workbook with frozen headers, formatted match scores, safe clickable apply links, and auto-filters.
* 📡 **Multi-Channel Alerts**:
  * ✉️ **Email (Brevo SMTP / Gmail)**: Daily digest with attached `.xlsx` spreadsheet & live Google Drive link.
  * 🔔 **Ntfy.sh (100% Open Source)**: Instant push notification + file delivered to mobile phone with zero accounts needed.
  * ✈️ **Telegram Bot**: Daily digest + downloadable Excel file sent to phone.
  * 📱 **WhatsApp (Green-API / pywhatkit)**: Direct WhatsApp alerts.
  * 🎮 **Discord Webhook**: Server alerts with attached report.
* 🛡️ **Security Hardened**: Built-in CSV/Excel formula injection defense (CWE-1236), parameterized SQL injection immunity (CWE-89), and strict URL protocol validation.

---

## 📊 Excel Report Structure (`reports/Daily_Job_Hunt_YYYY-MM-DD.xlsx`)

The generated Excel workbook contains 6 specialized sheets with 16 formatted columns:

| Sheet | Focus Area |
|---|---|
| **1. DAILY JOBS** | All 30–50 verified, fresh opportunities with match scores and status badges |
| **2. TOP MATCHES** | The top 10 highest-ranked opportunities for priority application |
| **3. REMOTE** | Remote roles eligible for candidates in India & worldwide |
| **4. AI & GENAI** | Roles specifically targeting AI, ML, GenAI, LangChain, RAG, and NLP |
| **5. INTERNSHIPS** | Graduate Engineer Trainee (GET), ASE, and Internship openings |
| **6. TESTING & ANALYST** | QA Automation, Software Testing, and Data/BI Analyst roles |

---

## ⚡ Quick Start

### 1. Clone & Install Dependencies
```bash
git clone https://github.com/anandsrinivas98/job_finder_agent.git
cd job_finder_agent
pip install -r requirements.txt
```

### 2. Configure Settings
Copy `.env.example` to `.env` and configure your preferences:
```bash
# PowerShell:
Copy-Item .env.example .env

# Linux / MacOS:
cp .env.example .env
```
1. Place your resume in `resume/` (e.g. `resume/Srinivas_A_Resume.pdf`).
2. Configure your **[Brevo Free SMTP](https://www.brevo.com)** credentials for daily email delivery.
3. (Optional) Set `GDRIVE_ENABLED=true` and `GDRIVE_FOLDER_ID` for Google Drive upload.

### 3. Run Pipeline
```bash
# Dry Run (scrapes & generates Excel report without sending alerts):
python main.py --dry-run

# Live Execution (scrapes, builds Excel, uploads to Google Drive, and delivers email/alerts):
python main.py --run-now
```

---

## ⏰ Daily Automation

### Option A: Local Windows Task Scheduler (07:00 AM Daily)
```powershell
powershell -ExecutionPolicy Bypass -File .\setup_windows_task.ps1
```

### Option B: 24/7 Cloud Automation (cron-job.org + GitHub Actions)
The workflow `.github/workflows/daily_job_hunt.yml` is triggered sharply on schedule via **cron-job.org** API (or manual trigger from the Actions tab). This eliminates duplicate executions and preserves your Brevo email quota. Configure your repository secrets under **GitHub Settings > Secrets and variables > Actions**.

---

## 🧪 Running Tests

```bash
python -m pytest -v
```
Verifies database state tracking, candidate scoring, multi-format resume parsing, formula injection sanitization, and secret protection.

---

## 📄 License
Distributed under the MIT License. See `LICENSE` for more information.
