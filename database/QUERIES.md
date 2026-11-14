
---

## 1. Dashboard and alerts

### 1.1 Crew status overview
One row per astronaut: mission day, last check-in, open alerts.

```sql
SELECT a.id, a.name, v.mission_day,
       (SELECT MAX(started_at) FROM assessment_sessions s
         WHERE s.astronaut_id = a.id)                      AS last_session,
       (SELECT COUNT(*) FROM alerts l
         WHERE l.astronaut_id = a.id AND l.acknowledged = 0) AS open_alerts,
       (SELECT COUNT(*) FROM alerts l
         WHERE l.astronaut_id = a.id AND l.acknowledged = 0
           AND l.severity = 'critical')                    AS open_critical
FROM astronauts a
JOIN v_astronauts v ON v.id = a.id
ORDER BY open_critical DESC, open_alerts DESC;
```

### 1.2 Open alerts, most severe first

```sql
SELECT l.id, l.created_at, a.name, l.severity, l.message,
       r.name AS rule, l.radiation_event_id
FROM alerts l
JOIN astronauts a        ON a.id = l.astronaut_id
LEFT JOIN alert_rules r  ON r.id = l.rule_id
WHERE l.acknowledged = 0
ORDER BY CASE l.severity WHEN 'critical' THEN 0 WHEN 'warning' THEN 1 ELSE 2 END,
         l.created_at DESC;
```

### 1.3 Acknowledge an alert

```sql
UPDATE alerts SET acknowledged = 1 WHERE id = 1;
```

### 1.4 Alerts raised during a radiation event (with context)

```sql
SELECT e.id AS event_id, e.noaa_scale, a.name, l.created_at, l.severity, l.message
FROM alerts l
JOIN radiation_events e ON e.id = l.radiation_event_id
JOIN astronauts a       ON a.id = l.astronaut_id
ORDER BY l.created_at, a.name;
```

---

## 2. Personal baselines and z-scores

### 2.1 Z-score of every fatigue measurement after the baseline window
Change the slug to look at any indicator (`heart_rate`, `sleep_duration`, `reaction_time`, `lymphocyte_count`, ...).

```sql
SELECT a.name, m.measured_at, m.value,
       ROUND(b.mean, 2)                  AS baseline_mean,
       ROUND((m.value - b.mean) / b.sd, 2) AS z_score
FROM measurements m
JOIN astronauts a ON a.id = m.astronaut_id
JOIN indicators i ON i.id = m.indicator_id
JOIN baselines  b ON b.astronaut_id = m.astronaut_id AND b.indicator_id = m.indicator_id
WHERE i.slug = 'fatigue'
  AND m.measured_at > a.baseline_end
ORDER BY a.id, m.measured_at;
```

### 2.2 Latest value per astronaut and indicator, versus their baseline

```sql
WITH latest AS (
    SELECT astronaut_id, indicator_id, MAX(measured_at) AS t
    FROM measurements
    GROUP BY astronaut_id, indicator_id
)
SELECT a.name, i.name AS indicator, i.unit, m.value,
       ROUND(b.mean, 2)                    AS baseline_mean,
       ROUND((m.value - b.mean) / b.sd, 2) AS z_score,
       m.measured_at
FROM latest l
JOIN measurements m ON m.astronaut_id = l.astronaut_id
                   AND m.indicator_id = l.indicator_id
                   AND m.measured_at  = l.t
JOIN astronauts a   ON a.id = m.astronaut_id
JOIN indicators i   ON i.id = m.indicator_id
LEFT JOIN baselines b ON b.astronaut_id = m.astronaut_id AND b.indicator_id = m.indicator_id
ORDER BY ABS((m.value - b.mean) / b.sd) DESC;
```

### 2.3 Recompute baselines from a window (sample SD)
Use this to refresh the `baselines` table. SQLite has no built-in `STDDEV`, so it is computed from sums.

```sql
SELECT m.astronaut_id, m.indicator_id,
       AVG(m.value) AS mean,
       SQRT((SUM(m.value * m.value) - SUM(m.value) * SUM(m.value) / COUNT(*))
            / (COUNT(*) - 1)) AS sd,
       COUNT(*) AS n
FROM measurements m
JOIN astronauts a ON a.id = m.astronaut_id
WHERE m.measured_at BETWEEN a.baseline_start AND a.baseline_end
GROUP BY m.astronaut_id, m.indicator_id
HAVING COUNT(*) > 1;
```

---

## 3. Radiation environment

### 3.1 Event summary

```sql
SELECT id, started_at, ended_at, peak_at, peak_flux_pfu, noaa_scale,
       ROUND((julianday(ended_at) - julianday(started_at)) * 24, 1) AS duration_hours
FROM radiation_events;
```

### 3.2 Hourly proton flux around an event (6 h either side)

```sql
SELECT f.hour, ROUND(f.flux_pfu, 2) AS flux_pfu, f.noaa_scale
FROM v_flux_hourly f
JOIN radiation_events e ON e.id = 1
WHERE f.hour BETWEEN datetime(e.started_at, '-6 hours')
                 AND datetime(e.ended_at,   '+6 hours')
ORDER BY f.hour;
```

### 3.3 Cumulative dose per astronaut, as % of a 600 mSv career limit
Dose rate (µSv/h) times interval length in hours, summed, converted to mSv. Check the current limit in NASA-STD-3001 before quoting it.

```sql
SELECT a.name,
       ROUND(SUM(r.dose_rate_usv_h *
                 (julianday(r.interval_end) - julianday(r.interval_start)) * 24) / 1000.0, 2) AS total_msv,
       ROUND(SUM(r.dose_rate_usv_h *
                 (julianday(r.interval_end) - julianday(r.interval_start)) * 24) / 1000.0 / 600 * 100, 3)
                                                                                          AS pct_of_600_msv
FROM radiation_readings r
JOIN astronauts a ON a.id = r.astronaut_id
WHERE r.source = 'dosimeter'
GROUP BY a.id
ORDER BY total_msv DESC;
```

### 3.4 Dose from the event versus background, per astronaut

```sql
WITH d AS (
    SELECT r.astronaut_id, r.interval_start,
           r.dose_rate_usv_h * (julianday(r.interval_end) - julianday(r.interval_start)) * 24 AS usv
    FROM radiation_readings r
    WHERE r.source = 'dosimeter'
)
SELECT a.name,
       ROUND(SUM(CASE WHEN d.interval_start >= e.started_at
                       AND d.interval_start <  e.ended_at THEN d.usv END) / 1000.0, 2) AS event_msv,
       ROUND(SUM(CASE WHEN d.interval_start <  e.started_at
                       OR  d.interval_start >= e.ended_at THEN d.usv END) / 1000.0, 2) AS other_msv
FROM d
JOIN astronauts a       ON a.id = d.astronaut_id
JOIN radiation_events e ON e.id = 1
GROUP BY a.id;
```

---

## 4. Correlating health with radiation

### 4.1 Before, during and after an event (mean of one indicator)

```sql
SELECT a.name,
       CASE WHEN m.measured_at <  e.started_at THEN '1 before'
            WHEN m.measured_at <= e.ended_at   THEN '2 during'
            ELSE '3 after' END       AS phase,
       ROUND(AVG(m.value), 2)        AS avg_value,
       COUNT(*)                      AS n
FROM measurements m
JOIN astronauts a       ON a.id = m.astronaut_id
JOIN radiation_events e ON e.id = 1
WHERE m.indicator_id = (SELECT id FROM indicators WHERE slug = 'fatigue')
GROUP BY a.id, phase
ORDER BY a.id, phase;
```

### 4.2 Each measurement paired with the flux 6 hours earlier
Change `'-6 hours'` to explore other lags. Flux is matched to the hour it was recorded in.

```sql
SELECT a.name, m.measured_at, m.value AS fatigue,
       ROUND(f.flux_pfu, 2)          AS flux_6h_earlier,
       ROUND(LOG10(f.flux_pfu), 2)   AS log10_flux
FROM measurements m
JOIN astronauts a    ON a.id = m.astronaut_id
JOIN v_flux_hourly f ON f.hour = strftime('%Y-%m-%d %H:00:00', datetime(m.measured_at, '-6 hours'))
WHERE m.indicator_id = (SELECT id FROM indicators WHERE slug = 'fatigue')
ORDER BY m.measured_at, a.id;
```

### 4.3 Lagged correlation sweep (Pearson r of fatigue vs log10 flux)
Shows which lag fits best. Pooled across all astronauts. Add `a.id` to the CTE and `GROUP BY` to get one curve per person.

```sql
WITH lags(h) AS (VALUES (0), (3), (6), (9), (12), (18), (24), (36), (48)),
pairs AS (
    SELECT l.h, LOG10(f.flux_pfu) AS x, m.value AS y
    FROM lags l
    JOIN measurements m ON m.indicator_id = (SELECT id FROM indicators WHERE slug = 'fatigue')
    JOIN v_flux_hourly f ON f.hour =
         strftime('%Y-%m-%d %H:00:00', datetime(m.measured_at, '-' || l.h || ' hours'))
)
SELECT h AS lag_hours,
       COUNT(*) AS n,
       ROUND((COUNT(*) * SUM(x * y) - SUM(x) * SUM(y)) /
             SQRT((COUNT(*) * SUM(x * x) - SUM(x) * SUM(x)) *
                  (COUNT(*) * SUM(y * y) - SUM(y) * SUM(y))), 3) AS pearson_r
FROM pairs
GROUP BY h
ORDER BY h;
```

> Caveat for the pitch: pooled check-ins from the same few people over one event are not independent samples. Present r as a descriptive signal and not as a statistical proof.

### 4.4 Radiation-relevant symptom score over time

```sql
SELECT a.name, s.started_at, s.radiation_symptom_score
FROM v_session_symptom_score s
JOIN astronauts a ON a.id = s.astronaut_id
ORDER BY a.id, s.started_at;
```

### 4.5 Symptom counts before, during and after an event
The "before" window is much longer than the event, so compare rates and don't read raw counts at face value.

```sql
SELECT st.name,
       SUM(sy.reported_at <  e.started_at)                             AS before_event,
       SUM(sy.reported_at BETWEEN e.started_at AND e.ended_at)         AS during_event,
       SUM(sy.reported_at >  e.ended_at)                               AS after_event,
       ROUND(AVG(sy.severity), 2)                                      AS avg_severity
FROM symptoms sy
JOIN symptom_types st   ON st.id = sy.symptom_type_id
JOIN radiation_events e ON e.id = 1
GROUP BY st.id
ORDER BY during_event DESC;
```

### 4.6 Lymphocyte change versus personal baseline

```sql
SELECT a.name, m.measured_at, m.value AS lymphocytes,
       ROUND(b.mean, 2) AS baseline,
       ROUND((m.value - b.mean) / b.mean * 100, 1) AS pct_change
FROM measurements m
JOIN astronauts a ON a.id = m.astronaut_id
JOIN baselines  b ON b.astronaut_id = m.astronaut_id AND b.indicator_id = m.indicator_id
WHERE m.indicator_id = (SELECT id FROM indicators WHERE slug = 'lymphocyte_count')
ORDER BY a.id, m.measured_at;
```

### 4.7 Prodromal cluster: nausea in the last 24 h plus lymphocytes down 10% or more

```sql
SELECT a.name, m.measured_at, m.value AS lymphocytes,
       ROUND((b.mean - m.value) / b.mean * 100, 1) AS pct_drop,
       MAX(sy.severity) AS worst_nausea_severity
FROM measurements m
JOIN astronauts a ON a.id = m.astronaut_id
JOIN baselines  b ON b.astronaut_id = m.astronaut_id AND b.indicator_id = m.indicator_id
JOIN symptoms  sy ON sy.astronaut_id = m.astronaut_id
                 AND sy.symptom_type_id = (SELECT id FROM symptom_types WHERE name = 'Nausea')
                 AND sy.reported_at >  datetime(m.measured_at, '-24 hours')
                 AND sy.reported_at <= m.measured_at
WHERE m.indicator_id = (SELECT id FROM indicators WHERE slug = 'lymphocyte_count')
  AND (b.mean - m.value) / b.mean >= 0.10
GROUP BY m.id
ORDER BY pct_drop DESC;
```

### 4.8 Who responded most? Peak fatigue z-score during the event

```sql
SELECT a.name,
       ROUND(MAX((m.value - b.mean) / b.sd), 2) AS peak_fatigue_z,
       MAX(m.value)                              AS peak_fatigue_score
FROM measurements m
JOIN astronauts a       ON a.id = m.astronaut_id
JOIN baselines  b       ON b.astronaut_id = m.astronaut_id AND b.indicator_id = m.indicator_id
JOIN radiation_events e ON e.id = 1
WHERE m.indicator_id = (SELECT id FROM indicators WHERE slug = 'fatigue')
  AND m.measured_at BETWEEN e.started_at AND datetime(e.ended_at, '+24 hours')
GROUP BY a.id
ORDER BY peak_fatigue_z DESC;
```

---

## 5. System performance (useful for the pitch)

### 5.1 Detection latency: hours from event onset to each astronaut's first rule-based alert

```sql
SELECT a.name,
       MIN(l.created_at) AS first_rule_alert,
       ROUND((julianday(MIN(l.created_at)) - julianday(e.started_at)) * 24, 1) AS hours_after_onset
FROM alerts l
JOIN astronauts a       ON a.id = l.astronaut_id
JOIN radiation_events e ON e.id = l.radiation_event_id
WHERE l.rule_id IS NOT NULL
GROUP BY a.id
ORDER BY hours_after_onset;
```

### 5.2 Which rules fire most
Alerts with no rule are flux-level or cluster alerts.

```sql
SELECT COALESCE(r.name, '(flux-level or cluster alert)') AS rule,
       l.severity, COUNT(*) AS alerts_fired
FROM alerts l
LEFT JOIN alert_rules r ON r.id = l.rule_id
GROUP BY r.id, l.severity
ORDER BY alerts_fired DESC;
```

### 5.3 Event-triggered check-ins completed per astronaut

```sql
SELECT a.name, COUNT(*) AS event_checkins,
       MIN(s.started_at) AS first, MAX(s.started_at) AS last
FROM assessment_sessions s
JOIN astronauts a ON a.id = s.astronaut_id
WHERE s.assessment_type = 'event_triggered'
GROUP BY a.id;
```

---

## 6. Data quality checks
Each of these should return zero rows.

### 6.1 Measurement or symptom whose astronaut differs from its session's astronaut
The schema doesn't enforce this, so check it (or add a trigger).

```sql
SELECT 'measurement' AS kind, m.id
FROM measurements m JOIN assessment_sessions s ON s.id = m.session_id
WHERE s.astronaut_id <> m.astronaut_id
UNION ALL
SELECT 'symptom', y.id
FROM symptoms y JOIN assessment_sessions s ON s.id = y.session_id
WHERE s.astronaut_id <> y.astronaut_id;
```

### 6.2 Measurement timestamped before its session started

```sql
SELECT m.id, m.measured_at, s.started_at
FROM measurements m JOIN assessment_sessions s ON s.id = m.session_id
WHERE m.measured_at < s.started_at;
```

### 6.3 Sessions with no measurements

```sql
SELECT s.id, s.astronaut_id, s.assessment_type, s.started_at
FROM assessment_sessions s
WHERE NOT EXISTS (SELECT 1 FROM measurements m WHERE m.session_id = s.id);
```

### 6.4 Missed daily check-ins

```sql
WITH RECURSIVE days(d) AS (
    SELECT date(MIN(started_at)) FROM assessment_sessions
    UNION ALL
    SELECT date(d, '+1 day') FROM days
    WHERE d < (SELECT date(MAX(started_at)) FROM assessment_sessions)
)
SELECT a.name, days.d AS missed_date
FROM astronauts a
CROSS JOIN days
WHERE NOT EXISTS (
    SELECT 1 FROM assessment_sessions s
    WHERE s.astronaut_id = a.id
      AND s.assessment_type = 'daily_checkin'
      AND date(s.started_at) = days.d
)
ORDER BY a.id, days.d;
```