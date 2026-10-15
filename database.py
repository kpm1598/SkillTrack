
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "instance" / "skilltrack.db"
SCHEMA_PATH = BASE_DIR / "schema.sql"


def get_connection():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    with get_connection() as db:
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        db.executescript(schema)

        # Insert sample data only into an empty employee database.
        count = db.execute(
            "SELECT COUNT(*) FROM employees"
        ).fetchone()[0]

        if count > 0:
            return

        employees = [
            ("Aarav Sharma", "Python Developer", 3, 100, 40),
            ("Priya Nair", "Cloud Engineer", 5, 60, 85),
            ("Rahul Verma", "Data Analyst", 2, 100, 25),
            ("Meera Iyer", "DevOps Engineer", 4, 80, 60),
            ("Dev Patel", "Software Engineer", 3, 100, 35),
            ("Ananya Rao", "Data Scientist", 4, 70, 75),
            ("Vikram Singh", "Backend Developer", 6, 50, 90),
            ("Sara Khan", "Cloud Developer", 2, 100, 20),
        ]

        db.executemany(
            """
            INSERT INTO employees
                (name, role, experience_years,
                 availability_pct, workload_pct)
            VALUES (?, ?, ?, ?, ?)
            """,
            employees,
        )

        skills = {
            "Aarav Sharma": [
                ("Python", 5), ("Flask", 5), ("SQL", 4),
                ("Data Analytics", 3),
            ],
            "Priya Nair": [
                ("Cloud Computing", 5), ("AWS", 5),
                ("Docker", 4), ("Linux", 4),
            ],
            "Rahul Verma": [
                ("Python", 4), ("SQL", 5),
                ("Data Analytics", 5), ("Excel", 4),
            ],
            "Meera Iyer": [
                ("Cloud Computing", 4), ("AWS", 4),
                ("Docker", 5), ("Linux", 5),
            ],
            "Dev Patel": [
                ("Python", 4), ("JavaScript", 4),
                ("SQL", 3), ("Flask", 3),
            ],
            "Ananya Rao": [
                ("Python", 5), ("Machine Learning", 5),
                ("Data Analytics", 5), ("SQL", 4),
            ],
            "Vikram Singh": [
                ("Python", 4), ("Flask", 4),
                ("SQL", 5), ("Cloud Computing", 3),
            ],
            "Sara Khan": [
                ("Cloud Computing", 4), ("AWS", 3),
                ("Python", 3), ("Docker", 3),
            ],
        }

        employee_ids = {
            row["name"]: row["id"]
            for row in db.execute(
                "SELECT id, name FROM employees"
            )
        }

        for name, employee_skills in skills.items():
            db.executemany(
                """
                INSERT INTO employee_skills
                    (employee_id, skill_name, proficiency)
                VALUES (?, ?, ?)
                """,
                [
                    (employee_ids[name], skill, level)
                    for skill, level in employee_skills
                ],
            )

        projects = [
            (
                "Cloud Analytics Platform",
                "Build a cloud-based analytics platform.",
                12, 4, 2, "Active",
            ),
            (
                "Customer Data Migration",
                "Migrate and validate customer records.",
                8, 3, 2, "Planning",
            ),
            (
                "Internal Reporting Tool",
                "Create an internal reporting application.",
                6, 3, 1, "Active",
            ),
        ]

        db.executemany(
            """
            INSERT INTO projects
                (name, description, duration_weeks,
                 team_size, min_experience, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            projects,
        )

        project_ids = {
            row["name"]: row["id"]
            for row in db.execute(
                "SELECT id, name FROM projects"
            )
        }

        project_skills = {
            "Cloud Analytics Platform": [
                ("Python", "Essential"),
                ("Cloud Computing", "Essential"),
                ("Data Analytics", "Essential"),
            ],
            "Customer Data Migration": [
                ("SQL", "Essential"),
                ("Python", "High"),
                ("Cloud Computing", "High"),
            ],
            "Internal Reporting Tool": [
                ("SQL", "Essential"),
                ("Data Analytics", "High"),
            ],
        }

        for name, required_skills in project_skills.items():
            db.executemany(
                """
                INSERT INTO project_skills
                    (project_id, skill_name, importance)
                VALUES (?, ?, ?)
                """,
                [
                    (project_ids[name], skill, importance)
                    for skill, importance in required_skills
                ],
            )

        training_resources = [
            (
                "Cloud Computing",
                "AWS Cloud Practitioner Essentials",
                "https://skillbuilder.aws/",
            ),
            (
                "Python",
                "Python Tutorial",
                "https://docs.python.org/3/tutorial/",
            ),
            (
                "Data Analytics",
                "Power BI Learning Resources",
                "https://learn.microsoft.com/training/powerplatform/power-bi/",
            ),
            (
                "SQL",
                "SQLBolt Interactive Lessons",
                "https://sqlbolt.com/",
            ),
            (
                "Docker",
                "Docker Get Started",
                "https://docs.docker.com/get-started/",
            ),
        ]

        db.executemany(
            """
            INSERT INTO training
                (skill_name, course_title, resource_url)
            VALUES (?, ?, ?)
            """,
            training_resources,
        )


if __name__ == "__main__":
    init_db()
    print(f"Database initialized at: {DATABASE_PATH}")

    with get_connection() as db:
        print("Employees:", db.execute(
            "SELECT COUNT(*) FROM employees"
        ).fetchone()[0])

        print("Projects:", db.execute(
            "SELECT COUNT(*) FROM projects"
        ).fetchone()[0])

        print("Employee skills:", db.execute(
            "SELECT COUNT(*) FROM employee_skills"
        ).fetchone()[0])
