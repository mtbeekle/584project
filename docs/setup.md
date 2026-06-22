# Setup

## Platform Requirements
- Windows is required because the current MDB access path depends on the Microsoft Access ODBC driver.
- Use a 64-bit Python installation to match the installed Access ODBC driver.

## Python Environment
- The project virtual environment is located at `.venv`.
- Use `.venv\Scripts\python.exe` when running project scripts on this machine.

## Python Dependencies
The current project requires:

- `pandas`
- `pyodbc`
- `openpyxl`
- `networkx`

Install them with:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## ODBC Driver
Required driver name:

```text
Microsoft Access Driver (*.mdb, *.accdb)
```

## Environment Verification
To verify the Python and ODBC environment, run:

```powershell
.\.venv\Scripts\python.exe installverification.py
```

Validation checks such as `capacitors.py` and `conductorheight.py` are located in `checks/`.
