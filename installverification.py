import sys
import platform

REQUIRED_ODBC_DRIVER = "Microsoft Access Driver (*.mdb, *.accdb)"


def print_section(title: str) -> None:
    print(f"\n{title}")
    print("-" * len(title))


def main() -> int:
    failures = []

    print_section("Python")
    print("Executable:", sys.executable)
    print("Version:", sys.version)
    print("Architecture:", platform.architecture())

    print_section("Python Packages")

    try:
        import pandas as pd
        print("pandas: OK", pd.__version__)
    except Exception as exc:
        print("pandas: FAILED", exc)
        failures.append("pandas")

    try:
        import pyodbc
        print("pyodbc: OK", pyodbc.version)
    except Exception as exc:
        print("pyodbc: FAILED", exc)
        failures.append("pyodbc")
        pyodbc = None

    try:
        import openpyxl
        print("openpyxl: OK", openpyxl.__version__)
    except Exception as exc:
        print("openpyxl: FAILED", exc)
        failures.append("openpyxl")

    print_section("ODBC Drivers")
    if pyodbc is None:
        print("Could not inspect ODBC drivers because pyodbc is unavailable.")
        failures.append("odbc-driver-check")
    else:
        installed_drivers = pyodbc.drivers()
        if installed_drivers:
            for driver in installed_drivers:
                print(" -", driver)
        else:
            print("No ODBC drivers found.")

        if REQUIRED_ODBC_DRIVER in installed_drivers:
            print(f"Required Access driver found: {REQUIRED_ODBC_DRIVER}")
        else:
            print(f"Required Access driver MISSING: {REQUIRED_ODBC_DRIVER}")
            failures.append("access-odbc-driver")

    print_section("Summary")
    if failures:
        print("Environment verification failed.")
        print("Issues:", ", ".join(failures))
        return 1

    print("Environment verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
