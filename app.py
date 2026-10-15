
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash
)
from database import get_connection, init_db

app = Flask(__name__)
app.secret_key = "skilltrack-local-development-key"

PROJECT_STATUSES = ("Planning", "Active", "Completed")
SKILL_IMPORTANCE = ("Essential", "High", "Preferred")
ASSIGNMENT_STATUSES = ("Proposed", "Active", "Completed")


# ==================================================
# DASHBOARD
# ==================================================

@app.route("/")
def dashboard():
    with get_connection() as db:
        stats = {
            "employees": db.execute(
                "SELECT COUNT(*) FROM employees"
            ).fetchone()[0],
            "projects": db.execute(
                "SELECT COUNT(*) FROM projects WHERE status != 'Completed'"
            ).fetchone()[0],
            "available": db.execute("""
                SELECT COUNT(*) FROM employees
                WHERE availability_pct > 0 AND workload_pct < 80
            """).fetchone()[0],
            "alerts": db.execute(
                "SELECT COUNT(*) FROM employees WHERE workload_pct >= 80"
            ).fetchone()[0],
        }

        projects = db.execute("""
            SELECT p.id, p.name, p.status, p.team_size,
                   COUNT(DISTINCT CASE
                       WHEN a.status = 'Active' THEN a.employee_id
                   END) AS assigned_count
            FROM projects p
            LEFT JOIN assignments a ON a.project_id = p.id
            GROUP BY p.id
            ORDER BY p.id
        """).fetchall()

        employees = db.execute("""
            SELECT e.*,
                   GROUP_CONCAT(es.skill_name, ', ') AS skills
            FROM employees e
            LEFT JOIN employee_skills es ON es.employee_id = e.id
            GROUP BY e.id
            ORDER BY e.workload_pct DESC
            LIMIT 5
        """).fetchall()

    return render_template(
        "dashboard.html",
        stats=stats,
        projects=projects,
        employees=employees
    )


# ==================================================
# EMPLOYEE MANAGEMENT
# ==================================================

@app.route("/employees")
def employees_page():
    with get_connection() as db:
        employees = db.execute("""
            SELECT e.*,
                   GROUP_CONCAT(DISTINCT es.skill_name) AS skills
            FROM employees e
            LEFT JOIN employee_skills es ON es.employee_id = e.id
            GROUP BY e.id
            ORDER BY e.name
        """).fetchall()

        projects = db.execute("""
            SELECT id, name, status, team_size
            FROM projects
            WHERE status != 'Completed'
            ORDER BY name
        """).fetchall()

        assignments = db.execute("""
            SELECT a.id, a.employee_id, a.project_id,
                   a.allocation_pct, a.status,
                   p.name AS project_name
            FROM assignments a
            JOIN projects p ON p.id = a.project_id
            ORDER BY p.name
        """).fetchall()

    assignments_by_employee = {}
    for assignment in assignments:
        assignments_by_employee.setdefault(
            assignment["employee_id"], []
        ).append(assignment)

    return render_template(
        "employees.html",
        employees=employees,
        projects=projects,
        assignments_by_employee=assignments_by_employee,
        assignment_statuses=ASSIGNMENT_STATUSES
    )


@app.route("/employees/new")
def new_employee():
    return render_template(
        "employee_form.html",
        employee=None,
        skills_text=""
    )


@app.route("/employees/<int:employee_id>/edit")
def edit_employee(employee_id):
    with get_connection() as db:
        employee = db.execute(
            "SELECT * FROM employees WHERE id = ?",
            (employee_id,)
        ).fetchone()

        if employee is None:
            flash("Employee not found.", "danger")
            return redirect(url_for("employees_page"))

        skills = db.execute("""
            SELECT skill_name, proficiency
            FROM employee_skills
            WHERE employee_id = ?
            ORDER BY skill_name
        """, (employee_id,)).fetchall()

    skills_text = ", ".join(
        f"{skill['skill_name']}:{skill['proficiency']}"
        for skill in skills
    )

    return render_template(
        "employee_form.html",
        employee=employee,
        skills_text=skills_text
    )


@app.route("/employees/save", methods=["POST"])
def save_employee():
    name = request.form.get("name", "").strip()
    role = request.form.get("role", "").strip()
    skills_text = request.form.get("skills", "").strip()
    employee_id = request.form.get("employee_id", "").strip()

    try:
        experience = float(request.form.get("experience_years", 0))
        availability = int(request.form.get("availability_pct", 0))
        workload = int(request.form.get("workload_pct", 0))

        if not name or not role:
            raise ValueError("Name and role are required.")
        if experience < 0:
            raise ValueError("Experience cannot be negative.")
        if not 0 <= availability <= 100:
            raise ValueError("Availability must be between 0 and 100.")
        if not 0 <= workload <= 100:
            raise ValueError("Workload must be between 0 and 100.")

        parsed_skills = []
        seen_skills = set()

        for item in skills_text.split(","):
            item = item.strip()
            if not item:
                continue

            if ":" in item:
                skill_name, proficiency_text = item.rsplit(":", 1)
                proficiency = int(proficiency_text.strip())
            else:
                skill_name = item
                proficiency = 3

            skill_name = skill_name.strip()
            if not skill_name:
                continue
            if not 1 <= proficiency <= 5:
                raise ValueError(
                    f"Proficiency for {skill_name} must be between 1 and 5."
                )

            normalized = skill_name.casefold()
            if normalized in seen_skills:
                raise ValueError(f"Duplicate skill: {skill_name}")
            seen_skills.add(normalized)
            parsed_skills.append((skill_name, proficiency))

        with get_connection() as db:
            if employee_id:
                saved_id = int(employee_id)
                existing = db.execute(
                    "SELECT id FROM employees WHERE id = ?",
                    (saved_id,)
                ).fetchone()
                if existing is None:
                    raise ValueError("Employee not found.")

                db.execute("""
                    UPDATE employees
                    SET name = ?, role = ?, experience_years = ?,
                        availability_pct = ?, workload_pct = ?
                    WHERE id = ?
                """, (
                    name, role, experience, availability, workload, saved_id
                ))
            else:
                cursor = db.execute("""
                    INSERT INTO employees
                    (name, role, experience_years,
                     availability_pct, workload_pct)
                    VALUES (?, ?, ?, ?, ?)
                """, (name, role, experience, availability, workload))
                saved_id = cursor.lastrowid

            db.execute(
                "DELETE FROM employee_skills WHERE employee_id = ?",
                (saved_id,)
            )

            for skill_name, proficiency in parsed_skills:
                db.execute("""
                    INSERT INTO employee_skills
                    (employee_id, skill_name, proficiency)
                    VALUES (?, ?, ?)
                """, (saved_id, skill_name, proficiency))

        flash("Employee saved successfully.", "success")
        return redirect(url_for("employees_page"))

    except (ValueError, TypeError) as error:
        flash(str(error), "danger")
        if employee_id.isdigit():
            return redirect(
                url_for("edit_employee", employee_id=int(employee_id))
            )
        return redirect(url_for("new_employee"))

    except Exception:
        app.logger.exception("Failed to save employee")
        flash("Could not save employee. Please check the details.", "danger")
        return redirect(url_for("employees_page"))


@app.route("/employees/<int:employee_id>/delete", methods=["POST"])
def delete_employee(employee_id):
    try:
        with get_connection() as db:
            employee = db.execute(
                "SELECT name FROM employees WHERE id = ?",
                (employee_id,)
            ).fetchone()

            if employee is None:
                flash("Employee not found.", "danger")
                return redirect(url_for("employees_page"))

            db.execute(
                "DELETE FROM employees WHERE id = ?",
                (employee_id,)
            )

        flash(f"Employee '{employee['name']}' deleted successfully.", "success")

    except Exception:
        app.logger.exception("Failed to delete employee")
        flash(
            "Could not delete this employee. Check related database records.",
            "danger"
        )

    return redirect(url_for("employees_page"))


# ==================================================
# PROJECT MANAGEMENT
# ==================================================

def get_project_skills(db, project_id):
    return db.execute("""
        SELECT skill_name, importance
        FROM project_skills
        WHERE project_id = ?
        ORDER BY
            CASE importance
                WHEN 'Essential' THEN 1
                WHEN 'High' THEN 2
                ELSE 3
            END,
            skill_name
    """, (project_id,)).fetchall()


@app.route("/projects")
def projects_page():
    with get_connection() as db:
        projects = db.execute("""
            SELECT p.*,
                   COUNT(DISTINCT CASE
                       WHEN a.status = 'Active' THEN a.employee_id
                   END) AS assigned_count
            FROM projects p
            LEFT JOIN assignments a ON a.project_id = p.id
            GROUP BY p.id
            ORDER BY p.id DESC
        """).fetchall()

        project_skills = {
            project["id"]: get_project_skills(db, project["id"])
            for project in projects
        }

    return render_template(
        "projects.html",
        projects=projects,
        project_skills=project_skills
    )


@app.route("/projects/new")
def new_project():
    return render_template(
        "project_form.html",
        project=None,
        skills=[],
        statuses=PROJECT_STATUSES,
        importance_options=SKILL_IMPORTANCE
    )


@app.route("/projects/<int:project_id>/edit")
def edit_project(project_id):
    with get_connection() as db:
        project = db.execute(
            "SELECT * FROM projects WHERE id = ?",
            (project_id,)
        ).fetchone()

        if project is None:
            flash("Project not found.", "danger")
            return redirect(url_for("projects_page"))

        skills = get_project_skills(db, project_id)

    return render_template(
        "project_form.html",
        project=project,
        skills=skills,
        statuses=PROJECT_STATUSES,
        importance_options=SKILL_IMPORTANCE
    )


@app.route("/projects/save", methods=["POST"])
def save_project():
    project_id = request.form.get("project_id", "").strip()
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    status = request.form.get("status", "Planning").strip()

    try:
        duration = int(request.form.get("duration_weeks", 4))
        team_size = int(request.form.get("team_size", 3))
        min_experience = float(request.form.get("min_experience", 0))

        if not name:
            raise ValueError("Project name is required.")
        if duration < 1:
            raise ValueError("Duration must be at least 1 week.")
        if team_size < 1:
            raise ValueError("Team size must be at least 1.")
        if min_experience < 0:
            raise ValueError("Minimum experience cannot be negative.")
        if status not in PROJECT_STATUSES:
            raise ValueError("Choose a valid project status.")

        skill_names = request.form.getlist("skill_name[]")
        importances = request.form.getlist("importance[]")
        if len(skill_names) != len(importances):
            raise ValueError("Each skill must have an importance level.")

        parsed_skills = []
        seen_skills = set()

        for skill_name, importance in zip(skill_names, importances):
            skill_name = skill_name.strip()
            importance = importance.strip()
            if not skill_name:
                continue
            if importance not in SKILL_IMPORTANCE:
                raise ValueError(f"Invalid importance for {skill_name}.")
            normalized = skill_name.casefold()
            if normalized in seen_skills:
                raise ValueError(f"Duplicate required skill: {skill_name}")
            seen_skills.add(normalized)
            parsed_skills.append((skill_name, importance))

        with get_connection() as db:
            if project_id:
                saved_id = int(project_id)
                existing = db.execute(
                    "SELECT id FROM projects WHERE id = ?",
                    (saved_id,)
                ).fetchone()
                if existing is None:
                    raise ValueError("Project not found.")

                db.execute("""
                    UPDATE projects
                    SET name = ?, description = ?, duration_weeks = ?,
                        team_size = ?, min_experience = ?, status = ?
                    WHERE id = ?
                """, (
                    name, description, duration, team_size,
                    min_experience, status, saved_id
                ))
            else:
                cursor = db.execute("""
                    INSERT INTO projects
                    (name, description, duration_weeks,
                     team_size, min_experience, status)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    name, description, duration, team_size,
                    min_experience, status
                ))
                saved_id = cursor.lastrowid

            db.execute(
                "DELETE FROM project_skills WHERE project_id = ?",
                (saved_id,)
            )

            for skill_name, importance in parsed_skills:
                db.execute("""
                    INSERT INTO project_skills
                    (project_id, skill_name, importance)
                    VALUES (?, ?, ?)
                """, (saved_id, skill_name, importance))

        flash("Project saved successfully.", "success")
        return redirect(url_for("projects_page"))

    except (ValueError, TypeError) as error:
        flash(str(error), "danger")
        if project_id.isdigit():
            return redirect(
                url_for("edit_project", project_id=int(project_id))
            )
        return redirect(url_for("new_project"))

    except Exception:
        app.logger.exception("Failed to save project")
        flash("Could not save the project. Check the details.", "danger")
        return redirect(url_for("projects_page"))


@app.route("/projects/<int:project_id>/delete", methods=["POST"])
def delete_project(project_id):
    try:
        with get_connection() as db:
            project = db.execute(
                "SELECT name FROM projects WHERE id = ?",
                (project_id,)
            ).fetchone()

            if project is None:
                flash("Project not found.", "danger")
                return redirect(url_for("projects_page"))

            # The schema cascades deletion to project skills and assignments.
            db.execute("DELETE FROM projects WHERE id = ?", (project_id,))

        flash(f"Project '{project['name']}' deleted successfully.", "success")

    except Exception:
        app.logger.exception("Failed to delete project")
        flash("Could not delete this project. Check the server terminal.", "danger")

    return redirect(url_for("projects_page"))


# ==================================================
# EMPLOYEE-PROJECT ASSIGNMENTS
# ==================================================

@app.route("/assignments/create", methods=["POST"])
def create_assignment():
    try:
        employee_id = int(request.form.get("employee_id", "0"))
        project_id = int(request.form.get("project_id", "0"))
        allocation_pct = int(request.form.get("allocation_pct", "100"))
        status = request.form.get("status", "Active").strip()

        if not 1 <= allocation_pct <= 100:
            raise ValueError("Allocation must be between 1% and 100%.")

        if status not in ASSIGNMENT_STATUSES:
            raise ValueError("Choose a valid assignment status.")

        with get_connection() as db:
            employee = db.execute(
                "SELECT name FROM employees WHERE id = ?",
                (employee_id,)
            ).fetchone()

            project = db.execute(
                "SELECT name, status FROM projects WHERE id = ?",
                (project_id,)
            ).fetchone()

            if employee is None:
                raise ValueError("Select a valid employee.")
            if project is None:
                raise ValueError("Select a valid project.")
            if project["status"] == "Completed":
                raise ValueError("Completed projects cannot receive assignments.")

            existing = db.execute("""
                SELECT id FROM assignments
                WHERE employee_id = ? AND project_id = ?
                  AND status != 'Completed'
                ORDER BY id DESC LIMIT 1
            """, (employee_id, project_id)).fetchone()

            if existing:
                db.execute("""
                    UPDATE assignments
                    SET allocation_pct = ?, status = ?
                    WHERE id = ?
                """, (allocation_pct, status, existing["id"]))
                message = (
                    f"Updated {employee['name']}'s assignment to "
                    f"{project['name']}."
                )
            else:
                db.execute("""
                    INSERT INTO assignments
                    (employee_id, project_id, allocation_pct, status)
                    VALUES (?, ?, ?, ?)
                """, (employee_id, project_id, allocation_pct, status))
                message = (
                    f"Assigned {employee['name']} to {project['name']}."
                )

        flash(message, "success")

    except (ValueError, TypeError) as error:
        flash(str(error), "danger")

    except Exception:
        app.logger.exception("Failed to create assignment")
        flash("Could not save the assignment. Check the server terminal.", "danger")

    return redirect(url_for("employees_page"))


@app.route("/assignments/<int:assignment_id>/delete", methods=["POST"])
def delete_assignment(assignment_id):
    try:
        with get_connection() as db:
            assignment = db.execute("""
                SELECT e.name AS employee_name, p.name AS project_name
                FROM assignments a
                JOIN employees e ON e.id = a.employee_id
                JOIN projects p ON p.id = a.project_id
                WHERE a.id = ?
            """, (assignment_id,)).fetchone()

            if assignment is None:
                flash("Assignment not found.", "danger")
            else:
                db.execute(
                    "DELETE FROM assignments WHERE id = ?",
                    (assignment_id,)
                )
                flash(
                    f"Removed {assignment['employee_name']} from "
                    f"{assignment['project_name']}.",
                    "success"
                )

    except Exception:
        app.logger.exception("Failed to delete assignment")
        flash("Could not remove the assignment.", "danger")

    return redirect(url_for("employees_page"))



# ==================================================
# SMART TEAM RECOMMENDATIONS
# ==================================================

def _recommendation_skill_score(employee_skills, required_skills):
    """Return a 0-100 skill score, weighted by project skill importance."""
    if not required_skills:
        return 100.0, []

    importance_weights = {"Essential": 3.0, "High": 2.0, "Preferred": 1.0}
    total_weight = sum(importance_weights.get(s["importance"], 1.0) for s in required_skills)
    earned = 0.0
    explanations = []

    for required in required_skills:
        key = required["skill_name"].strip().casefold()
        skill = employee_skills.get(key)
        weight = importance_weights.get(required["importance"], 1.0)
        if skill:
            # Proficiency 1–5 maps to 20–100% credit for this skill.
            earned += weight * (skill / 5.0)
            explanations.append(
                f"{required['skill_name']}: proficiency {skill}/5"
            )
        else:
            explanations.append(f"Missing {required['skill_name']}")

    return round(100 * earned / total_weight, 1), explanations


@app.route("/recommendations")
def team_recommendations():
    selected_project_id = request.args.get("project_id", type=int)

    with get_connection() as db:
        projects = db.execute("""
            SELECT id, name, description, team_size, min_experience, status
            FROM projects
            WHERE status != 'Completed'
            ORDER BY name
        """).fetchall()

        if not projects:
            return render_template(
                "recommendations.html",
                projects=[],
                selected_project=None,
                candidates=[],
                recommended_team=[],
                required_skills=[],
                skill_gaps=[],
                team_coverage=[],
                message="Create a project before generating team recommendations."
            )

        project_ids = {project["id"] for project in projects}
        if selected_project_id not in project_ids:
            selected_project_id = projects[0]["id"]

        selected_project = next(
            project for project in projects
            if project["id"] == selected_project_id
        )

        required_skills = db.execute("""
            SELECT skill_name, importance
            FROM project_skills
            WHERE project_id = ?
            ORDER BY CASE importance
                WHEN 'Essential' THEN 1
                WHEN 'High' THEN 2
                ELSE 3
            END, skill_name
        """, (selected_project_id,)).fetchall()

        employees = db.execute("""
            SELECT id, name, role, experience_years,
                   availability_pct, workload_pct
            FROM employees
            ORDER BY name
        """).fetchall()

        skill_rows = db.execute("""
            SELECT employee_id, skill_name, proficiency
            FROM employee_skills
        """).fetchall()

        active_allocations = db.execute("""
            SELECT employee_id, COALESCE(SUM(allocation_pct), 0) AS allocated_pct
            FROM assignments
            WHERE status = 'Active'
            GROUP BY employee_id
        """).fetchall()

    skills_by_employee = {}
    for row in skill_rows:
        skills_by_employee.setdefault(row["employee_id"], {})[
            row["skill_name"].strip().casefold()
        ] = row["proficiency"]

    allocations_by_employee = {
        row["employee_id"]: row["allocated_pct"]
        for row in active_allocations
    }

    candidates = []
    for employee in employees:
        skill_map = skills_by_employee.get(employee["id"], {})
        skill_score, skill_explanations = _recommendation_skill_score(
            skill_map, required_skills
        )

        minimum_experience = float(selected_project["min_experience"] or 0)
        if minimum_experience <= 0:
            experience_score = 100.0
        else:
            experience_score = min(
                100.0,
                100.0 * float(employee["experience_years"]) / minimum_experience
            )

        # workload_pct and active assignment allocations can describe overlapping
        # commitments; use the higher value to avoid double-counting them.
        recorded_workload = int(employee["workload_pct"] or 0)
        active_allocated = int(allocations_by_employee.get(employee["id"], 0) or 0)
        committed_pct = min(100, max(recorded_workload, active_allocated))
        remaining_capacity = max(0, 100 - committed_pct)
        capacity_score = float(remaining_capacity)

        availability_score = float(employee["availability_pct"])
        overall_score = round(
            skill_score * 0.50
            + experience_score * 0.20
            + capacity_score * 0.20
            + availability_score * 0.10,
            1
        )

        meets_experience = (
            float(employee["experience_years"]) >= minimum_experience
        )
        eligible = (
            selected_project["status"] != "Completed"
            and meets_experience
            and availability_score > 0
            and remaining_capacity > 0
        )

        reasons = []
        if skill_score >= 80:
            reasons.append("Strong match for required skills")
        elif skill_score >= 50:
            reasons.append("Partial match for required skills")
        else:
            reasons.append("Several required skills need coverage")
        if not meets_experience:
            reasons.append(
                f"Below minimum experience ({minimum_experience:g} years)"
            )
        if remaining_capacity <= 0:
            reasons.append("No remaining capacity")
        if availability_score <= 0:
            reasons.append("No recorded availability")

        candidates.append({
            "id": employee["id"],
            "name": employee["name"],
            "role": employee["role"],
            "experience_years": employee["experience_years"],
            "availability_pct": employee["availability_pct"],
            "workload_pct": employee["workload_pct"],
            "remaining_capacity": remaining_capacity,
            "skill_score": skill_score,
            "experience_score": round(experience_score, 1),
            "capacity_score": round(capacity_score, 1),
            "availability_score": round(availability_score, 1),
            "overall_score": overall_score,
            "skill_explanations": skill_explanations,
            "reasons": reasons,
            "eligible": eligible,
            "skill_map": skill_map
        })

    candidates.sort(
        key=lambda c: (c["eligible"], c["overall_score"], c["remaining_capacity"]),
        reverse=True
    )

    # Greedy team selection: prefer candidates who add coverage for important
    # project skills, then use their individual score as a tie-breaker.
    eligible_candidates = [c for c in candidates if c["eligible"]]
    selected = []
    remaining = eligible_candidates[:]
    covered_skill_names = set()
    target_size = int(selected_project["team_size"])

    while remaining and len(selected) < target_size:
        def marginal_value(candidate):
            added = 0.0
            for requirement in required_skills:
                key = requirement["skill_name"].strip().casefold()
                if key not in covered_skill_names and key in candidate["skill_map"]:
                    importance = {"Essential": 3.0, "High": 2.0, "Preferred": 1.0}
                    added += importance.get(requirement["importance"], 1.0) * (
                        candidate["skill_map"][key] / 5.0
                    )
            return added

        best = max(
            remaining,
            key=lambda c: (
                marginal_value(c),
                c["overall_score"],
                c["remaining_capacity"]
            )
        )
        selected.append(best)
        remaining.remove(best)
        for requirement in required_skills:
            key = requirement["skill_name"].strip().casefold()
            if key in best["skill_map"]:
                covered_skill_names.add(key)

    team_coverage = []
    skill_gaps = []
    for requirement in required_skills:
        key = requirement["skill_name"].strip().casefold()
        contributors = [
            member for member in selected
            if key in member["skill_map"]
        ]
        strongest = max(
            (member["skill_map"][key] for member in contributors),
            default=0
        )
        covered = bool(contributors)
        coverage_item = {
            "skill_name": requirement["skill_name"],
            "importance": requirement["importance"],
            "covered": covered,
            "strongest_proficiency": strongest,
            "contributors": [member["name"] for member in contributors]
        }
        team_coverage.append(coverage_item)
        if not covered:
            skill_gaps.append(requirement["skill_name"])

    return render_template(
        "recommendations.html",
        projects=projects,
        selected_project=selected_project,
        candidates=candidates,
        recommended_team=selected,
        required_skills=required_skills,
        skill_gaps=skill_gaps,
        team_coverage=team_coverage,
        message=None
    )



# ==================================================
# SKILL GAPS & TRAINING
# ==================================================

@app.route("/skill-gaps")
def skill_gaps_training():
    selected_project_id = request.args.get("project_id", type=int)

    with get_connection() as db:
        projects = db.execute("""
            SELECT id, name, team_size, min_experience, status
            FROM projects
            WHERE status != 'Completed'
            ORDER BY name
        """).fetchall()

        if not projects:
            return render_template(
                "skill_gaps.html",
                projects=[],
                selected_project=None,
                assigned_members=[],
                skill_analysis=[],
                gap_count=0,
                covered_count=0,
                message="Create a project and add its required skills to review skill gaps."
            )

        valid_project_ids = {project["id"] for project in projects}
        if selected_project_id not in valid_project_ids:
            selected_project_id = projects[0]["id"]

        selected_project = next(
            project for project in projects
            if project["id"] == selected_project_id
        )

        required_skills = db.execute("""
            SELECT skill_name, importance
            FROM project_skills
            WHERE project_id = ?
            ORDER BY CASE importance
                WHEN 'Essential' THEN 1
                WHEN 'High' THEN 2
                ELSE 3
            END, skill_name
        """, (selected_project_id,)).fetchall()

        assigned_members = db.execute("""
            SELECT e.id, e.name, e.role, a.allocation_pct, a.status
            FROM assignments a
            JOIN employees e ON e.id = a.employee_id
            WHERE a.project_id = ? AND a.status = 'Active'
            ORDER BY e.name
        """, (selected_project_id,)).fetchall()

        skill_rows = db.execute("""
            SELECT es.employee_id, es.skill_name, es.proficiency
            FROM employee_skills es
            JOIN assignments a ON a.employee_id = es.employee_id
            WHERE a.project_id = ? AND a.status = 'Active'
        """, (selected_project_id,)).fetchall()

        training_rows = db.execute("""
            SELECT skill_name, course_title, resource_url
            FROM training
            ORDER BY skill_name, course_title
        """).fetchall()

    skills_by_employee = {}
    for row in skill_rows:
        skills_by_employee.setdefault(row["employee_id"], {})[
            row["skill_name"].strip().casefold()
        ] = int(row["proficiency"])

    training_by_skill = {}
    for row in training_rows:
        training_by_skill.setdefault(
            row["skill_name"].strip().casefold(), []
        ).append({
            "course_title": row["course_title"],
            "resource_url": row["resource_url"]
        })

    skill_analysis = []
    for requirement in required_skills:
        skill_key = requirement["skill_name"].strip().casefold()
        holders = []
        for member in assigned_members:
            proficiency = skills_by_employee.get(member["id"], {}).get(skill_key)
            if proficiency is not None:
                holders.append({
                    "name": member["name"],
                    "proficiency": proficiency
                })

        best_proficiency = max(
            (holder["proficiency"] for holder in holders),
            default=0
        )

        # A required skill is considered a gap if no active team member has it
        # or if the strongest available proficiency is below 3/5.
        if not holders:
            status = "Missing"
            status_detail = "No assigned team member has this skill."
        elif best_proficiency < 3:
            status = "Needs improvement"
            status_detail = "The strongest assigned proficiency is below 3/5."
        else:
            status = "Covered"
            status_detail = "At least one assigned member has proficiency 3/5 or higher."

        skill_analysis.append({
            "skill_name": requirement["skill_name"],
            "importance": requirement["importance"],
            "holders": holders,
            "best_proficiency": best_proficiency,
            "status": status,
            "status_detail": status_detail,
            "resources": training_by_skill.get(skill_key, [])
        })

    return render_template(
        "skill_gaps.html",
        projects=projects,
        selected_project=selected_project,
        assigned_members=assigned_members,
        skill_analysis=skill_analysis,
        gap_count=sum(1 for item in skill_analysis if item["status"] != "Covered"),
        covered_count=sum(1 for item in skill_analysis if item["status"] == "Covered"),
        message=None
    )



# ==================================================
# WORKLOAD & CAPACITY
# ==================================================

@app.route("/workload")
def workload_capacity():
    with get_connection() as db:
        employees = db.execute("""
            SELECT e.id, e.name, e.role, e.availability_pct, e.workload_pct,
                   COALESCE(a.allocated_pct, 0) AS allocated_pct,
                   COALESCE(a.project_count, 0) AS project_count
            FROM employees e
            LEFT JOIN (
                SELECT employee_id,
                       SUM(allocation_pct) AS allocated_pct,
                       COUNT(DISTINCT project_id) AS project_count
                FROM assignments
                WHERE status = 'Active'
                GROUP BY employee_id
            ) a ON a.employee_id = e.id
            ORDER BY e.name
        """).fetchall()

        projects = db.execute("""
            SELECT p.id, p.name, p.team_size,
                   COUNT(DISTINCT CASE WHEN a.status = 'Active' THEN a.employee_id END) AS assigned_count
            FROM projects p
            LEFT JOIN assignments a ON a.project_id = p.id
            WHERE p.status != 'Completed'
            GROUP BY p.id
            ORDER BY p.name
        """).fetchall()

    workload_rows = []
    for employee in employees:
        recorded = int(employee["workload_pct"] or 0)
        allocated = int(employee["allocated_pct"] or 0)
        committed = min(100, max(recorded, allocated))
        remaining = max(0, 100 - committed)
        # Capacity is constrained by both remaining workload capacity and recorded availability.
        usable_capacity = min(remaining, int(employee["availability_pct"] or 0))
        if committed >= 90:
            status = "Overloaded"
        elif usable_capacity <= 20:
            status = "Limited capacity"
        else:
            status = "Available"
        workload_rows.append({
            "id": employee["id"],
            "name": employee["name"],
            "role": employee["role"],
            "availability_pct": employee["availability_pct"],
            "workload_pct": recorded,
            "allocated_pct": allocated,
            "committed_pct": committed,
            "remaining_capacity": remaining,
            "usable_capacity": usable_capacity,
            "project_count": employee["project_count"],
            "status": status
        })

    workload_rows.sort(key=lambda row: (row["usable_capacity"], row["name"]))
    return render_template(
        "workload.html",
        employees=workload_rows,
        projects=projects,
        overloaded_count=sum(1 for row in workload_rows if row["status"] == "Overloaded"),
        available_count=sum(1 for row in workload_rows if row["status"] == "Available"),
        total_usable_capacity=sum(row["usable_capacity"] for row in workload_rows)
    )


# ==================================================
# WORKFORCE ANALYTICS
# ==================================================

@app.route("/analytics")
def workforce_analytics():
    with get_connection() as db:
        employee_count = db.execute(
            "SELECT COUNT(*) FROM employees"
        ).fetchone()[0]
        project_count = db.execute(
            "SELECT COUNT(*) FROM projects WHERE status != 'Completed'"
        ).fetchone()[0]

        workload_data = db.execute("""
            SELECT id, name, workload_pct, availability_pct
            FROM employees
            ORDER BY name
        """).fetchall()

        skill_distribution = db.execute("""
            SELECT skill_name, COUNT(DISTINCT employee_id) AS employee_count
            FROM employee_skills
            GROUP BY skill_name COLLATE NOCASE
            ORDER BY employee_count DESC, skill_name
            LIMIT 10
        """).fetchall()

        project_staffing = db.execute("""
            SELECT p.name, p.team_size,
                   COUNT(DISTINCT CASE WHEN a.status = 'Active' THEN a.employee_id END) AS assigned_count
            FROM projects p
            LEFT JOIN assignments a ON a.project_id = p.id
            WHERE p.status != 'Completed'
            GROUP BY p.id
            ORDER BY p.name
        """).fetchall()

        assignment_count = db.execute("""
            SELECT COUNT(*) FROM assignments WHERE status = 'Active'
        """).fetchone()[0]

    # Supply plain arrays for Chart.js. All values come from SQLite.
    workload_chart = [{
        "name": row["name"],
        "workload": int(row["workload_pct"] or 0),
        "availability": int(row["availability_pct"] or 0)
    } for row in workload_data]

    skills_chart = [{
        "skill": row["skill_name"],
        "count": int(row["employee_count"])
    } for row in skill_distribution]

    staffing_chart = [{
        "project": row["name"],
        "assigned": int(row["assigned_count"]),
        "target": int(row["team_size"])
    } for row in project_staffing]

    return render_template(
        "analytics.html",
        employee_count=employee_count,
        project_count=project_count,
        assignment_count=assignment_count,
        workload_chart=workload_chart,
        skills_chart=skills_chart,
        staffing_chart=staffing_chart
    )


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
