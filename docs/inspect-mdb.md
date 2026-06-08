# Inspect MDB

Use `inspect_mdb.py` to inspect a Synergi `.mdb` file before writing or adjusting validation logic.

## Examples

List all user tables:

```powershell
.\.venv\Scripts\python.exe inspect_mdb.py path\to\model.mdb
```

List tables and columns:

```powershell
.\.venv\Scripts\python.exe inspect_mdb.py path\to\model.mdb --columns
```

Export all tables to CSV:

```powershell
.\.venv\Scripts\python.exe inspect_mdb.py path\to\model.mdb --export-all --out data\exports
```

Export selected tables to CSV:

```powershell
.\.venv\Scripts\python.exe inspect_mdb.py path\to\model.mdb --export TableA TableB --out data\exports
```

Preview sample rows from each table:

```powershell
.\.venv\Scripts\python.exe inspect_mdb.py path\to\model.mdb --preview 5
```

If there is exactly one `.mdb` or `.accdb` file in `data/raw/`, `inspect_mdb.py` can also be run without passing `mdb_path`.
