from __future__ import annotations

from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from codemap.models import ScanResult


_HEADER_FILL = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
_HEADER_FONT = Font(bold=True, color="FFFFFF")
_THIN_BORDER = Border(
    left=Side(style="thin"),
    right=Side(style="thin"),
    top=Side(style="thin"),
    bottom=Side(style="thin"),
)


def _style_header_row(ws, row: int, col_count: int) -> None:
    for col in range(1, col_count + 1):
        cell = ws.cell(row=row, column=col)
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = Alignment(horizontal="center")
        cell.border = _THIN_BORDER


def _auto_width(ws) -> None:
    for col_cells in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col_cells[0].column)
        for cell in col_cells:
            if cell.value is not None:
                max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[col_letter].width = max_len + 4


def _apply_border(ws, row: int, col_count: int) -> None:
    for col in range(1, col_count + 1):
        ws.cell(row=row, column=col).border = _THIN_BORDER


def export_table_spec_xlsx(scan: ScanResult, output: Path) -> None:
    wb = openpyxl.Workbook()

    # -- Index sheet ("목차") --
    ws_index = wb.active
    ws_index.title = "목차"
    index_headers = ["No", "테이블명", "설명"]
    for ci, h in enumerate(index_headers, 1):
        ws_index.cell(row=1, column=ci, value=h)
    _style_header_row(ws_index, 1, len(index_headers))

    for ti, table in enumerate(scan.database.tables, 1):
        ws_index.cell(row=ti + 1, column=1, value=ti)
        ws_index.cell(row=ti + 1, column=2, value=table.name)
        ws_index.cell(row=ti + 1, column=3, value="")
        _apply_border(ws_index, ti + 1, len(index_headers))

    _auto_width(ws_index)

    # -- Per-table sheets --
    fk_map: dict[str, str] = {}
    for table in scan.database.tables:
        for fk in table.foreignKeys:
            fk_map[fk.column] = fk.references

    for table in scan.database.tables:
        ws = wb.create_sheet(title=table.name)

        col_headers = ["No", "컬럼명", "타입", "PK", "FK", "Nullable", "설명"]
        for ci, h in enumerate(col_headers, 1):
            ws.cell(row=1, column=ci, value=h)
        _style_header_row(ws, 1, len(col_headers))

        row = 2
        for ci, col in enumerate(table.columns, 1):
            fk_ref = ""
            if col.name in fk_map:
                fk_ref = fk_map[col.name]
            ws.cell(row=row, column=1, value=ci)
            ws.cell(row=row, column=2, value=col.name)
            ws.cell(row=row, column=3, value=col.type)
            ws.cell(row=row, column=4, value="Y" if col.pk else "")
            ws.cell(row=row, column=5, value=fk_ref)
            ws.cell(row=row, column=6, value="Y" if col.nullable else "N")
            ws.cell(row=row, column=7, value="")
            _apply_border(ws, row, len(col_headers))
            row += 1

        # Index section
        if table.indexes:
            row += 1
            idx_headers = ["No", "인덱스명", "컬럼", "Unique"]
            for ci, h in enumerate(idx_headers, 1):
                ws.cell(row=row, column=ci, value=h)
            _style_header_row(ws, row, len(idx_headers))
            row += 1
            for ii, idx in enumerate(table.indexes, 1):
                ws.cell(row=row, column=1, value=ii)
                ws.cell(row=row, column=2, value=idx.name)
                ws.cell(row=row, column=3, value=", ".join(idx.columns))
                ws.cell(row=row, column=4, value="Y" if idx.unique else "N")
                _apply_border(ws, row, len(idx_headers))
                row += 1

        _auto_width(ws)

    wb.save(output)


def export_api_spec_xlsx(scan: ScanResult, output: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "엔드포인트 목록"

    headers = ["No", "메서드", "경로", "컨트롤러", "서비스", "호출"]
    for ci, h in enumerate(headers, 1):
        ws.cell(row=1, column=ci, value=h)
    _style_header_row(ws, 1, len(headers))

    for ei, ep in enumerate(scan.api.endpoints, 1):
        row = ei + 1
        ws.cell(row=row, column=1, value=ei)
        ws.cell(row=row, column=2, value=ep.method)
        ws.cell(row=row, column=3, value=ep.path)
        ws.cell(row=row, column=4, value=ep.controller)
        ws.cell(row=row, column=5, value=ep.service)
        ws.cell(row=row, column=6, value=", ".join(ep.calls))
        _apply_border(ws, row, len(headers))

    _auto_width(ws)
    wb.save(output)
