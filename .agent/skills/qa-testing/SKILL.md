---
name: qa-testing
description: Comprehensive QA testing strategy, automated test plan, security penetration verification, and regression test harness for the AI Job Hunting Agent.
---

# QA Testing Strategy & Test Execution Skill

This skill provides step-by-step procedures for running automated unit, integration, security, and end-to-end regression tests across all modules of the **Daily AI Job Hunting Agent**.

## Quick Test Commands

### 1. Full PyTest Test Suite
```powershell
python -m pytest -v
```

### 2. Fast Dry-Run Smoke Test
```powershell
python main.py --dry-run
```

### 3. Live End-to-End Pipeline Verification
```powershell
python main.py --run-now
```

## Test Coverage Modules

1. **Resume Parser (`tests/test_resume_parser.py`)**: Tests `.pdf`, `.md`, and invalid path handling.
2. **Matcher & Scoring (`tests/test_matcher.py`)**: Tests senior title disqualification, fresher weighting, and 0–100% scoring.
3. **Database Engine (`tests/test_db.py`)**: Tests SQLite/PostgreSQL upserts, SHA-256 deduplication, and status badging (`🆕 NEW`, `🔄 UPDATED`, `⏳ STILL OPEN`).
4. **Security & Injection (`tests/test_security.py`)**: Tests CWE-1236 spreadsheet formula injection defense and `.gitignore` secret isolation.
5. **Google Drive & Notifications**: Tests OAuth2/Desktop sync and Brevo SMTP email delivery.

For full test matrix and details, see [`testing_strategy.md`](../testing_strategy.md).
