
---

## 1. JOIN — Combine related tables

A `JOIN` allows you to combine information from multiple tables using their relationships.

For example, retrieve measurements together with the astronaut's name and the indicator's name.

```sql
SELECT
    a.name AS astronaut,
    i.name AS indicator,
    m.value,
    i.unit,
    m.measured_at
FROM measurements m
JOIN astronauts a
    ON m.astronaut_id = a.id
JOIN indicators i
    ON m.indicator_id = i.id;
```

**Aliases:**
- `m` = measurements
- `a` = astronauts
- `i` = indicators

### Filter for a specific astronaut

Add this condition before the final semicolon:

```sql
WHERE a.name = 'Sarah Chen'
```

---

## 2. Aggregate functions

Aggregate functions perform calculations across multiple rows.

### COUNT — Count measurements per astronaut

```sql
SELECT
    a.name,
    COUNT(m.id) AS total_measurements
FROM astronauts a
LEFT JOIN measurements m
    ON a.id = m.astronaut_id
GROUP BY a.id;
```

### AVG — Calculate average heart rate per astronaut

```sql
SELECT
    a.name,
    AVG(m.value) AS average_heart_rate
FROM measurements m
JOIN astronauts a
    ON m.astronaut_id = a.id
JOIN indicators i
    ON m.indicator_id = i.id
WHERE i.slug = 'heart_rate'
GROUP BY a.id;
```

### MIN and MAX — Find minimum and maximum heart rate

```sql
SELECT
    MIN(value) AS lowest_heart_rate,
    MAX(value) AS highest_heart_rate
FROM measurements
WHERE indicator_id = 1;
```

### Other useful aggregate functions

| Function | Purpose |
|---|---|
| `COUNT()` | Count rows |
| `AVG()` | Calculate an average |
| `SUM()` | Calculate a total |
| `MIN()` | Find the minimum |
| `MAX()` | Find the maximum |

---

## 3. GROUP BY and HAVING

`GROUP BY` groups rows that share a particular value.

### Count measurements for each indicator

```sql
SELECT
    i.name,
    COUNT(m.id) AS measurement_count
FROM indicators i
LEFT JOIN measurements m
    ON i.id = m.indicator_id
GROUP BY i.id;
```

### Show only indicators with more than five measurements

```sql
SELECT
    i.name,
    COUNT(m.id) AS measurement_count
FROM indicators i
LEFT JOIN measurements m
    ON i.id = m.indicator_id
GROUP BY i.id
HAVING COUNT(m.id) > 5;
```

**Difference between WHERE and HAVING:**

- `WHERE` filters individual rows before grouping.
- `HAVING` filters groups after grouping.

---

## 4. Working with alerts

Let's create a query that could power your ASTRA alerts page.

Retrieve:
- Astronaut name
- Alert severity
- Alert message
- Related indicator, if available
- Alert creation date

```sql
SELECT
    a.name AS astronaut,
    al.severity,
    al.message,
    i.name AS indicator,
    al.created_at
FROM alerts al
JOIN astronauts a
    ON al.astronaut_id = a.id
LEFT JOIN measurements m
    ON al.measurement_id = m.id
LEFT JOIN indicators i
    ON m.indicator_id = i.id
ORDER BY al.created_at DESC;
```

### Why LEFT JOIN?

Some alerts have `measurement_id = NULL`.

We still want those alerts to appear.

- `JOIN` (INNER JOIN) returns matching records only.
- `LEFT JOIN` keeps every record from the left table, even when there is no matching record on the right.

---

## 5. Retrieving data for health charts

Your frontend will eventually need historical measurements to draw charts.

### Heart-rate history for astronaut 1

```sql
SELECT
    measured_at,
    value
FROM measurements
WHERE astronaut_id = 1
AND indicator_id = 1
ORDER BY measured_at ASC;
```

### Use the indicator slug instead of its ID

```sql
SELECT
    m.measured_at,
    m.value,
    i.unit
FROM measurements m
JOIN indicators i
    ON m.indicator_id = i.id
WHERE m.astronaut_id = 1
AND i.slug = 'heart_rate'
ORDER BY m.measured_at ASC;
```

These timestamp/value results can be returned by Flask to the frontend for plotting a chart.

---
