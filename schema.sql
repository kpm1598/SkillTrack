
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    experience_years REAL NOT NULL DEFAULT 0,
    availability_pct INTEGER NOT NULL DEFAULT 100
        CHECK (availability_pct BETWEEN 0 AND 100),
    workload_pct INTEGER NOT NULL DEFAULT 0
        CHECK (workload_pct BETWEEN 0 AND 100),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS employee_skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    skill_name TEXT NOT NULL COLLATE NOCASE,
    proficiency INTEGER NOT NULL DEFAULT 3
        CHECK (proficiency BETWEEN 1 AND 5),
    FOREIGN KEY (employee_id)
        REFERENCES employees(id) ON DELETE CASCADE,
    UNIQUE (employee_id, skill_name)
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    duration_weeks INTEGER NOT NULL DEFAULT 4,
    team_size INTEGER NOT NULL DEFAULT 3,
    min_experience REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'Planning'
        CHECK (status IN ('Planning', 'Active', 'Completed')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS project_skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,
    skill_name TEXT NOT NULL COLLATE NOCASE,
    importance TEXT NOT NULL DEFAULT 'High'
        CHECK (importance IN ('Essential', 'High', 'Preferred')),
    FOREIGN KEY (project_id)
        REFERENCES projects(id) ON DELETE CASCADE,
    UNIQUE (project_id, skill_name)
);

CREATE TABLE IF NOT EXISTS assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    project_id INTEGER NOT NULL,
    allocation_pct INTEGER NOT NULL
        CHECK (allocation_pct BETWEEN 1 AND 100),
    status TEXT NOT NULL DEFAULT 'Active'
        CHECK (status IN ('Proposed', 'Active', 'Completed')),
    FOREIGN KEY (employee_id)
        REFERENCES employees(id) ON DELETE CASCADE,
    FOREIGN KEY (project_id)
        REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS training (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_name TEXT NOT NULL COLLATE NOCASE,
    course_title TEXT NOT NULL,
    resource_url TEXT NOT NULL DEFAULT ''
);
