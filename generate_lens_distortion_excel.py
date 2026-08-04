#!/usr/bin/env python3
"""Generate an mm-based first-quadrant TV-line inverse-distortion workbook."""

from datetime import datetime
from pathlib import Path
import re
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from openpyxl import Workbook
from openpyxl.chart import Reference, ScatterChart, Series
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation


OUTPUT = Path(__file__).with_name("lens_distortion_line_calculator.xlsx")
FIXED_TIMESTAMP = (2000, 1, 1, 0, 0, 0)
TABLE_FIRST = 19
TABLE_LAST = 2018
TVL_FIRST = 4
TVL_LAST = 14
OUTPUT_FIRST = 19
OUTPUT_LAST = 458

NAVY = "17365D"
BLUE = "D9EAF7"
YELLOW = "FFF2CC"
GREEN = "E2F0D9"
RED = "F4CCCC"
GRAY = "E7E6E6"
WHITE = "FFFFFF"
THIN = Side(style="thin", color="B7B7B7")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def section(ws, cell_range: str, title: str) -> None:
    ws.merge_cells(cell_range)
    cell = ws[cell_range.split(":")[0]]
    cell.value = title
    cell.font = Font(bold=True, color=WHITE)
    cell.fill = PatternFill("solid", fgColor=NAVY)
    cell.alignment = Alignment(horizontal="center")


def inverse_angle_formula(radius_cell: str) -> str:
    count = "$H$6"
    d_range = f"$D$19:$D${TABLE_LAST}"
    a_range = f"$A$19:$A${TABLE_LAST}"
    active_d = f"$D$19:INDEX({d_range},{count})"
    match = f"MATCH({radius_cell},{active_d},1)"
    return (
        f'=IF(OR($H$7<>"OK",{radius_cell}=""),"",'
        f'IF({radius_cell}<=$D$19,$A$19,'
        f'IF({radius_cell}>=INDEX({d_range},{count}),INDEX({a_range},{count}),'
        f'INDEX({a_range},{match})+'
        f'({radius_cell}-INDEX({d_range},{match}))*'
        f'(INDEX({a_range},{match}+1)-INDEX({a_range},{match}))/'
        f'(INDEX({d_range},{match}+1)-INDEX({d_range},{match})))))'
    )


def forward_radius_formula(angle_cell: str) -> str:
    count = "$H$6"
    a_range = f"$A$19:$A${TABLE_LAST}"
    d_range = f"$D$19:$D${TABLE_LAST}"
    active_a = f"$A$19:INDEX({a_range},{count})"
    match = f"MATCH({angle_cell},{active_a},1)"
    return (
        f'=IF(OR($H$7<>"OK",{angle_cell}=""),"",'
        f'IF({angle_cell}<=$A$19,$D$19,'
        f'IF({angle_cell}>=INDEX({a_range},{count}),INDEX({d_range},{count}),'
        f'INDEX({d_range},{match})+'
        f'({angle_cell}-INDEX({a_range},{match}))*'
        f'(INDEX({d_range},{match}+1)-INDEX({d_range},{match}))/'
        f'(INDEX({a_range},{match}+1)-INDEX({a_range},{match})))))'
    )


def add_mapping_formulas(ws, row: int) -> None:
    """Map sensor-mm point L/M to CAD-mm R/S and verify in T/V."""
    ws.cell(row, 14, f'=L{row}-$B$7/2')  # N centered sensor X
    ws.cell(row, 15, f'=M{row}-$B$8/2')  # O centered sensor Y
    ws.cell(row, 16, f'=SQRT(N{row}^2+O{row}^2)')  # P image height
    ws.cell(row, 17, inverse_angle_formula(f"P{row}"))  # Q half field angle
    ws.cell(row, 25, f'=$B$10*TAN(RADIANS(Q{row}))')  # Y hidden object radius
    ws.cell(row, 18, f'=IF(P{row}=0,0,-Y{row}*N{row}/P{row})')  # R CAD X
    ws.cell(row, 19, f'=IF(P{row}=0,0,Y{row}*O{row}/P{row})')  # S CAD Y
    ws.cell(row, 26, forward_radius_formula(f"Q{row}"))  # Z hidden forward radius
    ws.cell(row, 20, f'=IF(Y{row}=0,$B$7/2,$B$7/2-Z{row}*R{row}/Y{row})')
    ws.cell(row, 21, f'=IF(Y{row}=0,$B$8/2,$B$8/2+Z{row}*S{row}/Y{row})')
    ws.cell(row, 22, f'=SQRT((T{row}-L{row})^2+(U{row}-M{row})^2)')


def build_workbook() -> Workbook:
    wb = Workbook()
    wb.properties.created = datetime(*FIXED_TIMESTAMP)
    wb.properties.modified = datetime(*FIXED_TIMESTAMP)
    ws = wb.active
    ws.title = "TV本逆畸變計算器"
    guide = wb.create_sheet("使用說明")

    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "A19"
    ws.merge_cells("A1:V1")
    ws["A1"] = "第一象限 TV本 Chart 逆向預變形計算器（Sensor／CAD 皆為 mm）"
    ws["A1"].font = Font(size=18, bold=True, color=WHITE)
    ws["A1"].fill = PatternFill("solid", fgColor=NAVY)
    ws["A1"].alignment = Alignment(horizontal="center")
    ws.row_dimensions[1].height = 30
    ws.merge_cells("A2:V2")
    ws["A2"] = "由指定 TV本自動產生上下各 5 級，共 11 級、110 條線、440 個角點；黃色欄位為輸入。"
    ws["A2"].font = Font(italic=True, color="666666")
    ws["A2"].alignment = Alignment(horizontal="center")

    section(ws, "A3:C3", "Sensor／鏡頭輸入")
    inputs = [
        (4, "Pixel size", 2.0, "µm/pixel"),
        (5, "Sensor 水平像素", 3840, "pixel"),
        (6, "Sensor 垂直像素", 2160, "pixel"),
        (7, "Sensor 寬度", "=B4*B5/1000", "mm"),
        (8, "Sensor 高度", "=B4*B6/1000", "mm"),
        (9, "Lens 有效焦距 EFL", 4.0, "mm"),
        (10, "物方平面至入瞳距離", 1000.0, "mm"),
    ]
    for row, label, value, unit in inputs:
        ws.cell(row, 1, label)
        ws.cell(row, 2, value)
        ws.cell(row, 3, unit)
        ws.cell(row, 2).border = BORDER
        ws.cell(row, 2).fill = PatternFill("solid", fgColor=GREEN if row in (7, 8) else YELLOW)

    section(ws, "D3:F3", "TV本 Chart 參數")
    chart_inputs = [
        (4, "指定 TV本", 1500, "TV本"),
        (5, "TV本間隔", 100, "TV本"),
        (6, "視場位置", 0.7, "半對角線倍率"),
        (7, "每組線條數", 5, "固定"),
    ]
    for row, label, value, unit in chart_inputs:
        ws.cell(row, 4, label)
        ws.cell(row, 5, value)
        ws.cell(row, 6, unit)
        ws.cell(row, 5).border = BORDER
        ws.cell(row, 5).fill = PatternFill("solid", fgColor=GREEN if row == 7 else YELLOW)
    ws.merge_cells("D9:F12")
    ws["D9"] = (
        "第一象限位置：X 向右、Y 向上。\n"
        "指定 TV本的橫／豎線組合中心位於半對角線指定倍率。\n"
        "橫線組在左、豎線組在右；11 級由低至高向右排列。"
    )
    ws["D9"].alignment = Alignment(wrap_text=True, vertical="top")
    ws["D9"].fill = PatternFill("solid", fgColor=BLUE)

    section(ws, "G3:I3", "輸入檢查")
    checks = [
        (4, "基本數值", '=IF(AND(B4>0,B5>0,B6>0,B9>0,B10>0,E4-5*E5>0,E5>0,E6>=0,E6<=1),"OK","錯誤：數值範圍")'),
        (5, "輸出點數", "=11*2*5*4"),
        (6, "有效畸變表列數", f"=COUNT(A{TABLE_FIRST}:A{TABLE_LAST})"),
        (
            7,
            "畸變表狀態",
            '=IF(H6<2,"錯誤：至少 2 列",'
            'IF(A19<>0,"錯誤：首列半視角須為 0",'
            'IF(COUNTBLANK(A19:INDEX(A:A,18+H6))+COUNTBLANK(B19:INDEX(B:B,18+H6))>0,'
            '"錯誤：中間不可空白",'
            'IF(SUMPRODUCT(--(A20:INDEX(A:A,18+H6)<=A19:INDEX(A:A,17+H6)))>0,'
            '"錯誤：半視角須遞增",'
            'IF(SUMPRODUCT(--(D20:INDEX(D:D,18+H6)<=D19:INDEX(D:D,17+H6)))>0,'
            '"錯誤：畸變像高須遞增","OK")))))',
        ),
        (8, "目標範圍", f'=IF(MAX(P{OUTPUT_FIRST}:P{OUTPUT_LAST})>MAX(D19:D{TABLE_LAST}),"警告：超出畸變表","OK")'),
        (
            9,
            "Sensor 裁切",
            f'=IF(OR(MIN(L{OUTPUT_FIRST}:L{OUTPUT_LAST})<0,MAX(L{OUTPUT_FIRST}:L{OUTPUT_LAST})>$B$7,'
            f'MIN(M{OUTPUT_FIRST}:M{OUTPUT_LAST})<0,MAX(M{OUTPUT_FIRST}:M{OUTPUT_LAST})>$B$8),'
            '"警告：Chart 超出 Sensor","OK")',
        ),
    ]
    for row, label, formula in checks:
        ws.cell(row, 7, label)
        ws.cell(row, 8, formula)
        ws.cell(row, 7).fill = PatternFill("solid", fgColor=GRAY)
        ws.cell(row, 8).fill = PatternFill("solid", fgColor=GREEN)
        ws.cell(row, 7).border = ws.cell(row, 8).border = BORDER

    geometry_headers = ["級數", "TV本", "線寬\n(mm)", "單組邊長\n(mm)", "雙組總寬\n(mm)", "組合中心 X\n(mm)", "組合中心 Y\n(mm)"]
    for col, value in enumerate(geometry_headers, 10):
        cell = ws.cell(3, col, value)
        cell.font = Font(bold=True, color=WHITE)
        cell.fill = PatternFill("solid", fgColor=NAVY)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for row in range(TVL_FIRST, TVL_LAST + 1):
        level = row - 9
        ws.cell(row, 10, level)
        ws.cell(row, 11, f"=$E$4+J{row}*$E$5")
        ws.cell(row, 12, f"=$B$8/K{row}")
        ws.cell(row, 13, f"=(2*$E$7-1)*L{row}")
        ws.cell(row, 14, f"=2*M{row}+L{row}")
        ws.cell(row, 16, f"=$B$8/2-$E$6*$B$8/2")
        for col in range(10, 17):
            ws.cell(row, col).border = BORDER
            ws.cell(row, col).fill = PatternFill("solid", fgColor=GREEN)
            ws.cell(row, col).number_format = "0.000000"
    # The specified TVL (level 0, row 9) is centered at 0.7 of the half diagonal.
    ws["O9"] = "=$B$7/2+$E$6*$B$7/2"
    for row in range(10, TVL_LAST + 1):
        ws.cell(row, 15, f"=O{row-1}+N{row-1}/2+MIN(L{row-1},L{row})+N{row}/2")
    for row in range(8, TVL_FIRST - 1, -1):
        ws.cell(row, 15, f"=O{row+1}-N{row+1}/2-MIN(L{row},L{row+1})-N{row}/2")

    section(ws, "A17:E17", "Lens distortion table（最多 2000 筆）")
    table_headers = [
        "半視角 θ\n(degree)", "Optical distortion\n(%)", "理想像高\n(mm)",
        "畸變像高\n(mm)", "物方半徑\n(mm)",
    ]
    for col, value in enumerate(table_headers, 1):
        cell = ws.cell(18, col, value)
        cell.font = Font(bold=True, color=WHITE)
        cell.fill = PatternFill("solid", fgColor=NAVY)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER
    ws.row_dimensions[18].height = 42
    example_angles = [0, 10, 20, 30, 40, 50]
    example_distortion = [0, -0.5, -2.0, -4.5, -8.0, -12.0]
    for index, row in enumerate(range(TABLE_FIRST, TABLE_LAST + 1)):
        if index < len(example_angles):
            ws.cell(row, 1, example_angles[index])
            ws.cell(row, 2, example_distortion[index])
        ws.cell(row, 3, f'=IF(A{row}="","",$B$9*TAN(RADIANS(A{row})))')
        ws.cell(row, 4, f'=IF(C{row}="","",C{row}*(1+B{row}/100))')
        ws.cell(row, 5, f'=IF(A{row}="","",$B$10*TAN(RADIANS(A{row})))')
        for col in range(1, 6):
            ws.cell(row, col).border = BORDER
            ws.cell(row, col).number_format = "0.000000"
        ws.cell(row, 1).fill = ws.cell(row, 2).fill = PatternFill("solid", fgColor=YELLOW)

    section(ws, "G17:V17", "440 點：Sensor 圖形、物方 CAD 座標與正向驗證")
    output_headers = [
        "ID", "TV本", "方向", "線號", "角點", "Sensor X\n(mm)", "Sensor Y\n(mm)",
        "中心座標 X\n(mm)", "中心座標 Y\n(mm)", "像高\n(mm)", "半視角\n(degree)",
        "CAD X\n(mm)", "CAD Y\n(mm)", "驗證 X\n(mm)", "驗證 Y\n(mm)", "誤差\n(mm)",
    ]
    for col, value in enumerate(output_headers, 7):
        cell = ws.cell(18, col, value)
        cell.font = Font(bold=True, color=WHITE)
        cell.fill = PatternFill("solid", fgColor=NAVY)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER

    row = OUTPUT_FIRST
    corner_signs = [(-1, -1, "左上"), (1, -1, "右上"), (1, 1, "右下"), (-1, 1, "左下")]
    for level_index, geometry_row in enumerate(range(TVL_FIRST, TVL_LAST + 1)):
        for orientation in ("橫", "豎"):
            for line_number in range(1, 6):
                for corner_x, corner_y, corner_name in corner_signs:
                    ws.cell(row, 7, row - OUTPUT_FIRST + 1)
                    ws.cell(row, 8, f"=$K${geometry_row}")
                    ws.cell(row, 9, orientation)
                    ws.cell(row, 10, line_number)
                    ws.cell(row, 11, corner_name)
                    w = f"$L${geometry_row}"
                    g = f"$M${geometry_row}"
                    cx = f"$O${geometry_row}"
                    cy = f"$P${geometry_row}"
                    group_offset = f"({g}+{w})/2"
                    if orientation == "橫":
                        group_cx = f"{cx}-{group_offset}"
                        line_cy = f"{cy}-{g}/2+{w}/2+{line_number-1}*2*{w}"
                        ws.cell(row, 12, f"={group_cx}+({corner_x})*{g}/2")
                        ws.cell(row, 13, f"={line_cy}+({corner_y})*{w}/2")
                    else:
                        group_cx = f"{cx}+{group_offset}"
                        line_cx = f"{group_cx}-{g}/2+{w}/2+{line_number-1}*2*{w}"
                        ws.cell(row, 12, f"={line_cx}+({corner_x})*{w}/2")
                        ws.cell(row, 13, f"={cy}+({corner_y})*{g}/2")
                    add_mapping_formulas(ws, row)
                    for col in range(7, 23):
                        ws.cell(row, col).border = BORDER
                        ws.cell(row, col).fill = PatternFill("solid", fgColor=GREEN)
                        if col not in (9, 11):
                            ws.cell(row, col).number_format = "0.000000"
                    row += 1
    assert row - 1 == OUTPUT_LAST

    for col in ("W", "X", "Y", "Z"):
        ws.column_dimensions[col].hidden = True

    ws.auto_filter.ref = f"A18:B{TABLE_LAST}"
    positive = DataValidation(type="decimal", operator="greaterThan", formula1="0")
    positive.error = "請輸入大於 0 的數值"
    positive.showErrorMessage = True
    ws.add_data_validation(positive)
    positive.add("B4:B6")
    positive.add("B9:B10")
    positive.add("E4:E5")
    field = DataValidation(type="decimal", operator="between", formula1="0", formula2="1")
    field.error = "視場位置須介於 0～1"
    field.showErrorMessage = True
    ws.add_data_validation(field)
    field.add("E6")
    ws.conditional_formatting.add(
        "H4:H9",
        FormulaRule(formula=['LEFT(H4,2)<>"OK"'], fill=PatternFill("solid", fgColor=RED)),
    )

    widths = {
        "A": 18, "B": 18, "C": 16, "D": 18, "E": 17, "F": 17,
        "G": 9, "H": 12, "I": 10, "J": 10, "K": 11, "L": 15, "M": 15,
        "N": 16, "O": 16, "P": 14, "Q": 15, "R": 15, "S": 15,
        "T": 15, "U": 15, "V": 13,
    }
    for col, width in widths.items():
        ws.column_dimensions[col].width = width

    sensor_chart = ScatterChart()
    sensor_chart.title = "Sensor 第一象限：11 級 TV本圖形"
    sensor_chart.x_axis.title = "Sensor X (mm)"
    sensor_chart.y_axis.title = "Sensor Y (mm，向下為正)"
    sensor_chart.y_axis.scaling.orientation = "maxMin"
    sensor_chart.height = 11
    sensor_chart.width = 18
    sensor_x = Reference(ws, min_col=12, min_row=OUTPUT_FIRST, max_row=OUTPUT_LAST)
    sensor_y = Reference(ws, min_col=13, min_row=OUTPUT_FIRST, max_row=OUTPUT_LAST)
    sensor_series = Series(sensor_y, sensor_x, title="Sensor TV本角點")
    sensor_series.graphicalProperties.line.noFill = True
    sensor_series.marker.symbol = "circle"
    sensor_series.marker.size = 2
    sensor_chart.series.append(sensor_series)
    sensor_chart.legend = None
    ws.add_chart(sensor_chart, "G462")

    cad_chart = ScatterChart()
    cad_chart.title = "物平面：逆畸變 CAD 角點"
    cad_chart.x_axis.title = "CAD X (mm)"
    cad_chart.y_axis.title = "CAD Y (mm)"
    cad_chart.height = 11
    cad_chart.width = 18
    cad_x = Reference(ws, min_col=18, min_row=OUTPUT_FIRST, max_row=OUTPUT_LAST)
    cad_y = Reference(ws, min_col=19, min_row=OUTPUT_FIRST, max_row=OUTPUT_LAST)
    cad_series = Series(cad_y, cad_x, title="CAD 角點")
    cad_series.graphicalProperties.line.noFill = True
    cad_series.marker.symbol = "circle"
    cad_series.marker.size = 2
    cad_chart.series.append(cad_series)
    cad_chart.legend = None
    ws.add_chart(cad_chart, "G484")

    guide.sheet_view.showGridLines = False
    guide.merge_cells("A1:F1")
    guide["A1"] = "第一象限 TV本 Chart：定義與使用說明"
    guide["A1"].font = Font(size=18, bold=True, color=WHITE)
    guide["A1"].fill = PatternFill("solid", fgColor=NAVY)
    guide["A1"].alignment = Alignment(horizontal="center")
    guide.column_dimensions["A"].width = 21
    guide.column_dimensions["B"].width = 110
    instructions = [
        ("位置", "只生成第一象限。Sensor 中心為座標中心；第一象限是 X 向右、Y 向上。"
         "指定 TV本的橫線組與豎線組之組合中心位於中心至右上角半對角線的指定倍率，預設 0.7。"),
        ("11 級 TV本", "預設指定 1500 TV本、間隔 100 TV本，自動產生 1000～2000 TV本，共 11 級。"
         "相鄰圖樣的間隔採兩級中較細的線寬。"),
        ("線條幾何", "每級包含 5 條橫線與 5 條豎線。線寬=Sensor 高度/TV本；線間空白等於線寬。"
         "5 條線加 4 個空白形成邊長 9×線寬的正方形線組；橫線組在左、豎線組在右，兩組間隔一個線寬。"),
        ("440 點", "11級×2方向×5條線×4角=440點。每條線以四個角點輸出，不重複首點。"
         "這是直邊四角近似；若需要補償每條邊的微小曲率，點數必須增加。"),
        ("CAD 座標", "Sensor 與 CAD 均為 1 unit = 1 mm。CAD 原點為光軸在物平面的投影，X 向右、Y 向上，並包含鏡頭倒像。"),
        ("畸變模型", "由最多 2000 筆半視角／Optical distortion 建立半視角與畸變像高 LUT，分段線性反查後以 R=Z·tan(θ) 求 CAD 座標。"),
        ("中心 Chart", "本工作簿不生成中心 chart；目前只有第一象限的 0.7 視場 chart。"),
    ]
    for row, (title, body) in enumerate(instructions, 3):
        guide.cell(row, 1, title)
        guide.cell(row, 2, body)
        guide.cell(row, 1).font = Font(bold=True, color=WHITE)
        guide.cell(row, 1).fill = PatternFill("solid", fgColor=NAVY)
        guide.cell(row, 2).fill = PatternFill("solid", fgColor=BLUE)
        guide.cell(row, 1).alignment = Alignment(vertical="top")
        guide.cell(row, 2).alignment = Alignment(wrap_text=True, vertical="top")
        guide.cell(row, 1).border = guide.cell(row, 2).border = BORDER
        guide.row_dimensions[row].height = 68

    wb.calculation.fullCalcOnLoad = True
    wb.calculation.forceFullCalc = True
    wb.calculation.calcMode = "auto"
    wb.active = 0
    return wb


def save_deterministic(workbook: Workbook, output: Path) -> None:
    workbook.save(output)
    normalized = output.with_suffix(".normalized.xlsx")
    with ZipFile(output, "r") as source, ZipFile(
        normalized, "w", compression=ZIP_DEFLATED, compresslevel=9
    ) as target:
        for name in sorted(source.namelist()):
            original = source.getinfo(name)
            info = ZipInfo(name, date_time=FIXED_TIMESTAMP)
            info.compress_type = ZIP_DEFLATED
            info.external_attr = original.external_attr
            info.create_system = original.create_system
            data = source.read(name)
            if name == "docProps/core.xml":
                data = re.sub(
                    rb"(<dcterms:modified[^>]*>)[^<]*(</dcterms:modified>)",
                    rb"\g<1>2000-01-01T00:00:00Z\g<2>",
                    data,
                )
            target.writestr(info, data)
    normalized.replace(output)


if __name__ == "__main__":
    workbook = build_workbook()
    save_deterministic(workbook, OUTPUT)
    print(f"Created {OUTPUT}")
