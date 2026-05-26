import pandas as pd


def check_open_fuses(fuses):

    results = {}

    # ==========================================
    # DISPLAY FUSE COLUMNS
    # ==========================================

    print("\n========================")
    print("FUSE COLUMNS")
    print("========================")

    print(fuses.columns.tolist())

    # ==========================================
    # FIND OPEN FUSES
    # ==========================================

    open_fuses = fuses[
        fuses['FuseIsOpen'] == True
    ]

    results['open_fuses'] = open_fuses

    return results