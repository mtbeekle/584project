import pandas as pd


def check_capacitors(capacitors):

    results = {}

    # ==========================================
    # DISPLAY CAPACITOR COLUMNS
    # ==========================================

    print("\n========================")
    print("CAPACITOR COLUMNS")
    print("========================")

    print(capacitors.columns.tolist())

    # ==========================================
    # INVALID FIXED KVAR
    # ==========================================

    invalid_fixed_kvar = capacitors[
        (capacitors['FixedKvarPhase1'] <= 0) |
        (capacitors['FixedKvarPhase2'] <= 0) |
        (capacitors['FixedKvarPhase3'] <= 0)
    ]

    results['invalid_fixed_kvar'] = invalid_fixed_kvar

    # ==========================================
    # INVALID MODULE KVAR
    # ==========================================

    invalid_module_kvar = capacitors[
        (capacitors['Module1KvarPerPhase'] <= 0) |
        (capacitors['Module2KvarPerPhase'] <= 0) |
        (capacitors['Module3KvarPerPhase'] <= 0)
    ]

    results['invalid_module_kvar'] = invalid_module_kvar

    return results