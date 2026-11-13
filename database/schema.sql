PRAGMA foreign_keys = ON;
CREATE TABLE astronauts (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    mission_name TEXT NOT NULL,
    mission_day INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE indicators (
    id INTEGER PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    unit TEXT NOT NULL,
    instructions TEXT,
    equipment TEXT,
    preparation TEXT,
    frequency TEXT
    );
CREATE TABLE assessment_sessions (
    id INTEGER PRIMARY KEY,
    astronaut_id INTEGER NOT NULL,
    assessment_type TEXT NOT NULL,
    started_at TEXT DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    notes TEXT,
    FOREIGN KEY (astronaut_id) REFERENCES astronauts(id)
);
CREATE TABLE measurements (
    id INTEGER PRIMARY KEY,
    astronaut_id INTEGER NOT NULL,
    indicator_id INTEGER NOT NULL,
    value REAL NOT NULL,
    measured_at TEXT DEFAULT CURRENT_TIMESTAMP,
    session_id INTEGER REFERENCES assessment_sessions(id),
    FOREIGN KEY (astronaut_id) REFERENCES astronauts(id),
    FOREIGN KEY (indicator_id) REFERENCES indicators(id)
);
CREATE TABLE alerts (
    id INTEGER PRIMARY KEY,
    astronaut_id INTEGER NOT NULL,
    severity TEXT NOT NULL CHECK (
        severity IN ('info', 'warning', 'critical')
    ),
    message TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    acknowledged INTEGER NOT NULL DEFAULT 0
    CHECK (acknowledged IN (0, 1)),
    FOREIGN KEY (astronaut_id) REFERENCES astronauts(id)
);
CREATE INDEX idx_measurements_astronaut
ON measurements(astronaut_id);
CREATE INDEX idx_measurements_indicator
ON measurements(indicator_id);
CREATE INDEX idx_measurements_date
ON measurements(measured_at);
CREATE INDEX idx_alerts_astronaut
ON alerts(astronaut_id);
CREATE TABLE symptoms (
    id INTEGER PRIMARY KEY,
    astronaut_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    severity INTEGER NOT NULL CHECK (severity BETWEEN 1 AND 5),
    notes TEXT,
    reported_at TEXT DEFAULT CURRENT_TIMESTAMP,
    session_id INTEGER REFERENCES assessment_sessions(id),
    FOREIGN KEY (astronaut_id) REFERENCES astronauts(id)
);

