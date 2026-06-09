from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.worksheet import Worksheet


HEADER_FILL = PatternFill(fill_type="solid", fgColor="1F4E78")
HEADER_FONT = Font(color="FFFFFF", bold=True)
HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="center")
ERROR_FILL = PatternFill(fill_type="solid", fgColor="FFC7CE")
WARNING_FILL = PatternFill(fill_type="solid", fgColor="FFEB9C")


def _autofit_columns(worksheet: Worksheet) -> None:
    for column_cells in worksheet.columns:
        column_letter = column_cells[0].column_letter
        max_length = max(
            (
                len(str(cell.value))
                for cell in column_cells
                if cell.value is not None
            ),
            default=0,
        )
        worksheet.column_dimensions[column_letter].width = min(max_length + 2, 60)


def _format_severity_cells(worksheet: Worksheet) -> None:
    header_cells = list(worksheet[1])
    severity_column = None

    for cell in header_cells:
        if cell.value == "Severity":
            severity_column = cell.column
            break

    if severity_column is None:
        return

    for row in range(2, worksheet.max_row + 1):
        cell = worksheet.cell(row=row, column=severity_column)
        if cell.value == "Error":
            cell.fill = ERROR_FILL
        elif cell.value == "Warning":
            cell.fill = WARNING_FILL


def format_report_sheet(worksheet: Worksheet) -> None:
    worksheet.freeze_panes = "A2"
    worksheet.auto_filter.ref = worksheet.dimensions

    for cell in worksheet[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = HEADER_ALIGNMENT

    _format_severity_cells(worksheet)
    _autofit_columns(worksheet)
