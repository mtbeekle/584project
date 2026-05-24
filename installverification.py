import sys
import platform

print("Python executable:")
print(sys.executable)

print("\nPython version:")
print(sys.version)

print("\nArchitecture:")
print(platform.architecture())

try:
    import pandas as pd
    print("\npandas OK:", pd.__version__)
except Exception as e:
    print("\npandas FAILED:", e)

try:
    import pyodbc
    print("\npyodbc OK:", pyodbc.version)
    print("\nInstalled ODBC drivers:")
    for driver in pyodbc.drivers():
        print(" -", driver)
except Exception as e:
    print("\npyodbc FAILED:", e)