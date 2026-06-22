# Synergi MDB Validation Tool

## Purpose
Python-based validation tool for detecting GIS-to-MDB conversion inconsistencies in Synergi Electric models.

## Setup
1. Install Python dependencies from list below.
2. Install Microsoft Access Database Engine / ODBC driver.
3. Run `python installverification.py` to verify the environment.
4. Place the MDB file in `data/raw/`.
5. Run `python main.py` to create `data/exports/synergi_validation_results.xlsx`.

Validation check modules are organized under `checks/`.

## Required dependencies
1. pandas
2. pyodbc
3. openpyxl
4. networkx
