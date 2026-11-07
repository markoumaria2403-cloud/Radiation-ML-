# Database Setup

### 1. Install SQLite

**macOS:**
```bash
brew install sqlite
```

**Ubuntu:**
```bash
sudo apt install sqlite3
```

**Windows:** Download SQLite from https://sqlite.org/download.html.

### 2. Create the database

From the repository's root directory:

```bash
sqlite3 database/nasaspacechallenge.db < database/schema.sql
```

### 3. Add sample data

```bash
sqlite3 database/nasaspacechallenge.db < database/seed.sql
```

### 4. View the data

Open the database:

```bash
sqlite3 database/nasaspacechallenge.db
```

Enable readable output:

```sql
.headers on
.mode column
```

**View all tables:**
```sql
.tables
```

**View all astronauts:**
```sql
SELECT * FROM astronauts;
```

**View all health indicators:**
```sql
SELECT * FROM indicators;
```

**View measurements with their indicator names and units:**
```sql
SELECT
    m.id,
    a.name AS astronaut,
    i.name AS indicator,
    m.value,
    i.unit,
    m.measured_at
FROM measurements m
JOIN astronauts a ON m.astronaut_id = a.id
JOIN indicators i ON m.indicator_id = i.id
ORDER BY m.measured_at;
```

**View all reported symptoms:**
```sql
SELECT * FROM symptoms;
```

**View all alerts:**
```sql
SELECT * FROM alerts;
```

To exit SQLite:

```sql
.quit
```

