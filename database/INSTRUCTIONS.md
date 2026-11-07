# Database Setup

ASTRA uses SQLite.

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

That's it! Your local database is ready.

**Note:** The database file is ignored by Git. Do not commit it.