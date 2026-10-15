# SkillTrack — Workforce Intelligence

Flask + SQLite workforce planning MVP with employee and project management, assignments,
rule-based team recommendations, skill gaps and training, workload/capacity, and analytics.

## Requirements
- Python 3.10+
- Internet connection for Bootstrap and Chart.js CDN assets

## Windows setup (PowerShell)
```powershell
cd "path\to\SkillTrack"
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python app.py
```
Open the local URL printed by Flask.

## Notes
- SQLite database is stored at `instance/skilltrack.db`.
- Back up `instance/skilltrack.db` before making schema or data changes.
- Team recommendations are proposals and do not automatically create assignments.
- Workload/capacity values are estimates based on recorded workload, active assignments, and availability.
- Chart.js is loaded from a CDN; analytics charts require an internet connection.
- This is a local demo MVP; set a secure secret key and use production-grade server configuration before deployment.
