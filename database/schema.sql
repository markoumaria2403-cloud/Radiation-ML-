PRAGMA foreign_keys = ON;
CREATE TABLE dataset_info (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE astronauts (
    id                 INTEGER PRIMARY KEY,
    name               TEXT NOT NULL,
    mission_name       TEXT NOT NULL,
    mission_start_date TEXT NOT NULL,          
    baseline_start     TEXT,
    baseline_end       TEXT,
    created_at         TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE indicators (
    id                 INTEGER PRIMARY KEY,
    slug               TEXT NOT NULL UNIQUE,
    name               TEXT NOT NULL,
    category           TEXT NOT NULL,
    unit               TEXT NOT NULL,
    instructions       TEXT,
    equipment          TEXT,
    preparation        TEXT,
    frequency          TEXT,
    radiation_relevant INTEGER NOT NULL DEFAULT 0 CHECK (radiation_relevant IN (0, 1))
);
CREATE TABLE symptom_types (
    id                 INTEGER PRIMARY KEY,
    name               TEXT NOT NULL UNIQUE,
    category           TEXT NOT NULL,
    radiation_relevant INTEGER NOT NULL DEFAULT 0 CHECK (radiation_relevant IN (0, 1))
);
CREATE TABLE radiation_events (
    id            INTEGER PRIMARY KEY,
    started_at    TEXT NOT NULL,
    ended_at      TEXT,
    peak_at       TEXT,
    peak_flux_pfu REAL,
    noaa_scale    TEXT CHECK (noaa_scale IN ('S1','S2','S3','S4','S5')),
    notes         TEXT,
    CHECK (ended_at IS NULL OR ended_at > started_at)
);
CREATE TABLE radiation_readings (
    id              INTEGER PRIMARY KEY,
    astronaut_id    INTEGER REFERENCES astronauts(id),
    source          TEXT NOT NULL CHECK (source IN ('dosimeter','goes','simulated')),
    interval_start  TEXT NOT NULL,
    interval_end    TEXT NOT NULL,
    dose_rate_usv_h REAL CHECK (dose_rate_usv_h IS NULL OR dose_rate_usv_h >= 0),
    proton_flux_pfu REAL CHECK (proton_flux_pfu IS NULL OR proton_flux_pfu >= 0),
    noaa_scale      TEXT CHECK (noaa_scale IN ('S0','S1','S2','S3','S4','S5')),
    CHECK (interval_end > interval_start),
    CHECK (dose_rate_usv_h IS NOT NULL OR proton_flux_pfu IS NOT NULL),
    UNIQUE (source, astronaut_id, interval_start)
);
CREATE INDEX idx_rad_time       ON radiation_readings(source, interval_start);
CREATE INDEX idx_rad_astronaut  ON radiation_readings(astronaut_id, interval_start);
CREATE TABLE assessment_sessions (
    id               INTEGER PRIMARY KEY,
    astronaut_id     INTEGER NOT NULL REFERENCES astronauts(id),
    assessment_type  TEXT NOT NULL CHECK (assessment_type IN
                         ('daily_checkin','event_triggered','lab_panel','ad_hoc')),
    started_at       TEXT NOT NULL,
    completed_at     TEXT,
    trigger_event_id INTEGER REFERENCES radiation_events(id),
    notes            TEXT,
    CHECK (completed_at IS NULL OR completed_at >= started_at)
);
CREATE INDEX idx_sessions_astronaut ON assessment_sessions(astronaut_id, started_at);

CREATE TABLE measurements (
    id           INTEGER PRIMARY KEY,
    astronaut_id INTEGER NOT NULL REFERENCES astronauts(id),
    indicator_id INTEGER NOT NULL REFERENCES indicators(id),
    value        REAL NOT NULL,
    measured_at  TEXT NOT NULL,
    session_id   INTEGER NOT NULL REFERENCES assessment_sessions(id),
    UNIQUE (session_id, indicator_id)     
);
CREATE INDEX idx_meas_session   ON measurements(session_id);
CREATE INDEX idx_meas_astr_ind  ON measurements(astronaut_id, indicator_id, measured_at);
CREATE TABLE symptoms (
    id              INTEGER PRIMARY KEY,
    astronaut_id    INTEGER NOT NULL REFERENCES astronauts(id),
    symptom_type_id INTEGER NOT NULL REFERENCES symptom_types(id),
    severity        INTEGER NOT NULL CHECK (severity BETWEEN 1 AND 5),
    notes           TEXT,
    reported_at     TEXT NOT NULL,
    session_id      INTEGER NOT NULL REFERENCES assessment_sessions(id),
    UNIQUE (session_id, symptom_type_id)
);
CREATE INDEX idx_symptoms_session ON symptoms(session_id);
CREATE INDEX idx_symptoms_astr    ON symptoms(astronaut_id, reported_at);
CREATE TABLE baselines (
    astronaut_id INTEGER NOT NULL REFERENCES astronauts(id),
    indicator_id INTEGER NOT NULL REFERENCES indicators(id),
    mean         REAL NOT NULL,
    sd           REAL NOT NULL CHECK (sd > 0),
    n            INTEGER NOT NULL,
    period_start TEXT NOT NULL,
    period_end   TEXT NOT NULL,
    PRIMARY KEY (astronaut_id, indicator_id)
);
CREATE TABLE alert_rules (
    id           INTEGER PRIMARY KEY,
    indicator_id INTEGER NOT NULL REFERENCES indicators(id),
    name         TEXT NOT NULL,
    comparison   TEXT NOT NULL CHECK (comparison IN
                     ('sd_above_baseline','sd_below_baseline',
                      'pct_above_baseline','pct_below_baseline',
                      'abs_above','abs_below')),
    threshold    REAL NOT NULL,
    severity     TEXT NOT NULL CHECK (severity IN ('info','warning','critical')),
    active       INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);
CREATE TABLE alerts (
    id                 INTEGER PRIMARY KEY,
    astronaut_id       INTEGER NOT NULL REFERENCES astronauts(id),
    measurement_id     INTEGER REFERENCES measurements(id),
    session_id         INTEGER REFERENCES assessment_sessions(id),
    rule_id            INTEGER REFERENCES alert_rules(id),
    radiation_event_id INTEGER REFERENCES radiation_events(id),
    severity           TEXT NOT NULL CHECK (severity IN ('info','warning','critical')),
    message            TEXT NOT NULL,
    created_at         TEXT NOT NULL,
    acknowledged       INTEGER NOT NULL DEFAULT 0 CHECK (acknowledged IN (0, 1))
);
CREATE INDEX idx_alerts_astronaut ON alerts(astronaut_id, created_at);
CREATE INDEX idx_alerts_event     ON alerts(radiation_event_id);
CREATE INDEX idx_alerts_rule      ON alerts(rule_id);
CREATE VIEW v_astronauts AS
SELECT id, name, mission_name, mission_start_date,
       CAST(julianday(date('now')) - julianday(mission_start_date) AS INTEGER) + 1 AS mission_day
FROM astronauts;
CREATE VIEW v_flux_hourly AS
SELECT interval_start AS hour, proton_flux_pfu AS flux_pfu, noaa_scale
FROM radiation_readings
WHERE source = 'goes';
CREATE VIEW v_session_symptom_score AS
SELECT s.id AS session_id, s.astronaut_id, s.started_at,
       COALESCE(SUM(sy.severity), 0) AS radiation_symptom_score
FROM assessment_sessions s
LEFT JOIN symptoms sy
       ON sy.session_id = s.id
      AND sy.symptom_type_id IN (SELECT id FROM symptom_types WHERE radiation_relevant = 1)
GROUP BY s.id;