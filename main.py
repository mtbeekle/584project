import os
import pyodbc
import pandas as pd

from missingdata import check_missing_data
from capacitors import check_capacitors
from fuses import check_open_fuses


# =====================================================
# MDB FILE LOCATION
# =====================================================

mdb_file = r"C:\Users\Corey\Documents\NCSU\ECE584\SampleModel (1)\SampleModel.mdb"


# =====================================================
# VERIFY FILE EXISTS
# =====================================================

if os.path.exists(mdb_file):
    print("MDB file found!")
else:
    print("MDB file NOT found!")
    raise FileNotFoundError(mdb_file)


# =====================================================
# CONNECT TO MDB
# =====================================================

conn_str = (
    r"DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};"
    rf"DBQ={mdb_file};"
)

conn = pyodbc.connect(conn_str)

print("Connected successfully!")


# =====================================================
# LIST TABLES
# =====================================================

print("\n========================")
print("TABLES IN MDB")
print("========================\n")

cursor = conn.cursor()

tables = []

for row in cursor.tables(tableType='TABLE'):
    tables.append(row.table_name)
    print(row.table_name)


# =====================================================
# LOAD TABLES
# =====================================================

print("\n========================")
print("LOADING TABLES")
print("========================")

nodes = pd.read_sql(
    "SELECT * FROM [Node]",
    conn
)

sections = pd.read_sql(
    "SELECT * FROM [InstSection]",
    conn
)

loads = pd.read_sql(
    "SELECT * FROM [Loads]",
    conn
)

capacitors = pd.read_sql(
    "SELECT * FROM [InstCapacitors]",
    conn
)

fuses = pd.read_sql(
    "SELECT * FROM [InstFuses]",
    conn
)

print(f"Nodes Loaded: {len(nodes)}")
print(f"Sections Loaded: {len(sections)}")
print(f"Loads Loaded: {len(loads)}")
print(f"Capacitors Loaded: {len(capacitors)}")
print(f"Fuses Loaded: {len(fuses)}")


# =====================================================
# DISPLAY COLUMNS
# =====================================================

print("\n========================")
print("NODE COLUMNS")
print("========================")

print(nodes.columns.tolist())

print("\n========================")
print("SECTION COLUMNS")
print("========================")

print(sections.columns.tolist())


# =====================================================
# RUN VALIDATION CHECKS
# =====================================================

missing_results = check_missing_data(sections)

capacitor_results = check_capacitors(capacitors)

fuse_results = check_open_fuses(fuses)


# =====================================================
# PRINT RESULTS
# =====================================================

print("\n========================")
print("MISSING DATA CHECKS")
print("========================\n")

print(
    "Sections missing connectivity:",
    len(missing_results['missing_connectivity'])
)

print(
    "Sections missing length:",
    len(missing_results['missing_length'])
)

print(
    "Sections missing phase data:",
    len(missing_results['missing_phase'])
)

print(
    "Sections missing conductor:",
    len(missing_results['missing_conductor'])
)

print(
    "Duplicate Section IDs:",
    len(missing_results['duplicate_sections'])
)

print(
    "Invalid fixed capacitor kvar:",
    len(capacitor_results['invalid_fixed_kvar'])
)

print(
    "Invalid module capacitor kvar:",
    len(capacitor_results['invalid_module_kvar'])
)

print(
    "Open fuses found:",
    len(fuse_results['open_fuses'])
)


# =====================================================
# EXPORT RESULTS
# =====================================================

print("\n========================")
print("EXPORTING RESULTS")
print("========================")

output_file = (
    r"C:\Users\Corey\Desktop\synergi_validation_results.xlsx"
)

with pd.ExcelWriter(output_file) as writer:

    # ==========================================
    # MISSING DATA
    # ==========================================

    missing_results['missing_connectivity'].to_excel(
        writer,
        sheet_name='MissingConnectivity',
        index=False
    )

    missing_results['missing_length'].to_excel(
        writer,
        sheet_name='MissingLength',
        index=False
    )

    missing_results['missing_phase'].to_excel(
        writer,
        sheet_name='MissingPhase',
        index=False
    )

    missing_results['missing_conductor'].to_excel(
        writer,
        sheet_name='MissingConductor',
        index=False
    )

    missing_results['duplicate_sections'].to_excel(
        writer,
        sheet_name='DuplicateSections',
        index=False
    )

    # ==========================================
    # CAPACITORS
    # ==========================================

    capacitor_results['invalid_fixed_kvar'].to_excel(
        writer,
        sheet_name='InvalidFixedCapKvar',
        index=False
    )

    capacitor_results['invalid_module_kvar'].to_excel(
        writer,
        sheet_name='InvalidModuleCapKvar',
        index=False
    )

    # ==========================================
    # OPEN FUSES
    # ==========================================

    fuse_results['open_fuses'].to_excel(
        writer,
        sheet_name='OpenFuses',
        index=False
    )

print(f"\nValidation report exported to:\n{output_file}")


# =====================================================
# CLOSE MDB CONNECTION
# =====================================================

conn.close()

print("\nMDB connection closed.")
