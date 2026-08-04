#!/usr/bin/env python3
"""Generate an mm-based inverse lens-distortion CAD pre-warp workbook."""

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
BOUNDARY_FIRST = 27
BOUNDARY_LAST = 227

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
    """Map one absolute sensor-mm point to object-mm and verify forward."""
    ws.cell(row, 10, f'=IF(H{row}="","",H{row}-$B$9)')
    ws.cell(row, 11, f'=IF(I{row}="","",I{row}-$B$10)')
    ws.cell(row, 12, f'=IFERROR(SQRT(J{row}^2+K{row}^2),"")')
    ws.cell(row, 13, inverse_angle_formula(f"L{row}"))
    ws.cell(row, 14, f'=IF(M{row}="","",$B$12*TAN(RADIANS(M{row})))')
    # Sensor uses X-right/Y-down from its top-left. CAD uses X-right/Y-up
    # about the optical-axis projection; the lens inversion is included.
    ws.cell(row, 15, f'=IF(N{row}="","",IF(L{row}=0,0,-N{row}*J{row}/L{row}))')
    ws.cell(row, 16, f'=IF(N{row}="","",IF(L{row}=0,0,N{row}*K{row}/L{row}))')
    ws.cell(row, 24, forward_radius_formula(f"M{row}"))  # X hidden, sensor mm
    ws.cell(row, 17, f'=IF(N{row}="","",IF(N{row}=0,$B$9,$B$9-X{row}*O{row}/N{row}))')
    ws.cell(row, 18, f'=IF(N{row}="","",IF(N{row}=0,$B$10,$B$10+X{row}*P{row}/N{row}))')
    ws.cell(row, 19, f'=IFERROR(SQRT((Q{row}-H{row})^2+(R{row}-I{row})^2),"")')


def build_workbook() -> Workbook:
    wb = Workbook()
    wb.properties.created = datetime(*FIXED_TIMESTAMP)
    wb.properties.modified = datetime(*FIXED_TIMESTAMP)
    ws = wb.active
    ws.title = "逆畸變計算器"
    guide = wb.create_sheet("使用說明")

    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "A19"
    ws.merge_cells("A1:S1")
    ws["A1"] = "Lens Distortion 長方形逆向預變形計算器（Sensor／物方皆以 mm）"
    ws["A1"].font = Font(size=18, bold=True, color=WHITE)
    ws["A1"].fill = PatternFill("solid", fgColor=NAVY)
    ws["A1"].alignment = Alignment(horizontal="center")
    ws.row_dimensions[1].height = 30
    ws.merge_cells("A2:S2")
    ws["A2"] = "輸入 sensor 面四點的絕對 mm 座標，輸出可直接放入 CAD 的物方 mm 座標；黃色欄位為輸入。"
    ws["A2"].font = Font(italic=True, color="666666")
    ws["A2"].alignment = Alignment(horizontal="center")

    section(ws, "A3:C3", "Sensor／鏡頭輸入")
    sensor_inputs = [
        (4, "Pixel size", 2.0, "µm/pixel"),
        (5, "Sensor 水平像素", 3840, "pixel"),
        (6, "Sensor 垂直像素", 2160, "pixel"),
        (7, "Sensor 寬度", "=B4*B5/1000", "mm"),
        (8, "Sensor 高度", "=B4*B6/1000", "mm"),
        (9, "光軸中心 X", 3.84, "mm，左上角原點"),
        (10, "光軸中心 Y", 2.16, "mm，左上角原點"),
        (11, "Lens 有效焦距 EFL", 4.0, "mm"),
        (12, "物方平面至入瞳距離", 1000.0, "mm"),
    ]
    for row, label, value, unit in sensor_inputs:
        ws.cell(row, 1, label)
        ws.cell(row, 2, value)
        ws.cell(row, 3, unit)
        ws.cell(row, 2).border = BORDER
        ws.cell(row, 2).fill = PatternFill("solid", fgColor=GREEN if row in (7, 8) else YELLOW)

    section(ws, "D3:F3", "Sensor 目標四點（左上角原點，mm）")
    points = [
        ("P1", 1145 * 0.002, 856 * 0.002),
        ("P2", 1545 * 0.002, 856 * 0.002),
        ("P3", 1545 * 0.002, 656 * 0.002),
        ("P4", 1145 * 0.002, 656 * 0.002),
    ]
    for row, (name, x, y) in enumerate(points, 4):
        ws.cell(row, 4, name)
        ws.cell(row, 5, x)
        ws.cell(row, 6, y)
        for col in (5, 6):
            ws.cell(row, col).fill = PatternFill("solid", fgColor=YELLOW)
            ws.cell(row, col).border = BORDER
            ws.cell(row, col).number_format = "0.000000"
    ws["D9"] = "每邊取樣段數"
    ws["E9"] = 25
    ws["F9"] = "2～50"
    ws["E9"].fill = PatternFill("solid", fgColor=YELLOW)
    ws["E9"].border = BORDER

    section(ws, "G3:I3", "輸入檢查")
    checks = [
        (4, "基本數值", '=IF(AND(B4>0,B5>0,B6>0,B11>0,B12>0,E9>=2,E9<=50),"OK","錯誤：數值範圍")'),
        (5, "邊界點數", "=4*E9+1"),
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
        (8, "目標範圍", f'=IF(MAX(L19:L22)>MAX(D19:D{TABLE_LAST}),"警告：超出表格","OK")'),
    ]
    for row, label, formula in checks:
        ws.cell(row, 7, label)
        ws.cell(row, 8, formula)
        ws.cell(row, 7).fill = PatternFill("solid", fgColor=GRAY)
        ws.cell(row, 8).fill = PatternFill("solid", fgColor=GREEN)
        ws.cell(row, 7).border = ws.cell(row, 8).border = BORDER

    section(ws, "A17:E17", "Lens distortion table（最多 2000 筆）")
    table_headers = [
        "半視角 θ\n(degree)",
        "Optical distortion\n(%)",
        "理想 sensor 半徑\n(mm)",
        "畸變 sensor 半徑\n(mm)",
        "物方半徑\n(mm)",
    ]
    for col, value in enumerate(table_headers, 1):
        cell = ws.cell(18, col, value)
        cell.font = Font(bold=True, color=WHITE)
        cell.fill = PatternFill("solid", fgColor=NAVY)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER
    ws.row_dimensions[18].height = 42
    example_angles = [0, 10, 20, 30, 40]
    example_distortion = [0, -0.5, -2.0, -4.5, -8.0]
    for index, row in enumerate(range(TABLE_FIRST, TABLE_LAST + 1)):
        if index < len(example_angles):
            ws.cell(row, 1, example_angles[index])
            ws.cell(row, 2, example_distortion[index])
        ws.cell(row, 3, f'=IF(A{row}="","",$B$11*TAN(RADIANS(A{row})))')
        ws.cell(row, 4, f'=IF(C{row}="","",C{row}*(1+B{row}/100))')
        ws.cell(row, 5, f'=IF(A{row}="","",$B$12*TAN(RADIANS(A{row})))')
        for col in range(1, 6):
            ws.cell(row, col).border = BORDER
            ws.cell(row, col).number_format = "0.000000"
        ws.cell(row, 1).fill = ws.cell(row, 2).fill = PatternFill("solid", fgColor=YELLOW)

    output_headers = [
        "點",
        "Sensor X\n(mm)",
        "Sensor Y\n(mm)",
        "相對光軸 X\n(mm)",
        "相對光軸 Y\n(mm)",
        "Sensor 半徑\n(mm)",
        "反查半視角\n(degree)",
        "物方半徑\n(mm)",
        "CAD X\n(mm)",
        "CAD Y\n(mm)",
        "驗證 X\n(mm)",
        "驗證 Y\n(mm)",
        "誤差\n(mm)",
    ]
    section(ws, "G17:S17", "物方四點 CAD 座標與正向驗證")
    for col, value in enumerate(output_headers, 7):
        cell = ws.cell(18, col, value)
        cell.font = Font(bold=True, color=WHITE)
        cell.fill = PatternFill("solid", fgColor=NAVY)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER
    for row in range(19, 23):
        input_row = row - 15
        ws.cell(row, 7, f"=D{input_row}")
        ws.cell(row, 8, f"=E{input_row}")
        ws.cell(row, 9, f"=F{input_row}")
        add_mapping_formulas(ws, row)
        for col in range(7, 20):
            ws.cell(row, col).border = BORDER
            ws.cell(row, col).fill = PatternFill("solid", fgColor=GREEN)
            ws.cell(row, col).number_format = "0.000000"

    section(ws, "G25:S25", "完整預變形曲邊 CAD 座標（每邊最多 50 段）")
    for col, value in enumerate(output_headers, 7):
        cell = ws.cell(26, col, value)
        cell.font = Font(bold=True, color=WHITE)
        cell.fill = PatternFill("solid", fgColor=NAVY)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER
    ws.row_dimensions[26].height = 42
    for row in range(BOUNDARY_FIRST, BOUNDARY_LAST + 1):
        ws.cell(row, 20, f"={row - BOUNDARY_FIRST}")  # T hidden index
        ws.cell(row, 21, f'=IF(T{row}>4*$E$9,"",MIN(INT(T{row}/$E$9)+1,4))')
        t = f"MOD(T{row},$E$9)/$E$9"
        ws.cell(
            row,
            8,
            f'=IF(U{row}="","",IF(T{row}=4*$E$9,$E$4,'
            f'CHOOSE(U{row},$E$4+{t}*($E$5-$E$4),$E$5+{t}*($E$6-$E$5),'
            f'$E$6+{t}*($E$7-$E$6),$E$7+{t}*($E$4-$E$7))))',
        )
        ws.cell(
            row,
            9,
            f'=IF(U{row}="","",IF(T{row}=4*$E$9,$F$4,'
            f'CHOOSE(U{row},$F$4+{t}*($F$5-$F$4),$F$5+{t}*($F$6-$F$5),'
            f'$F$6+{t}*($F$7-$F$6),$F$7+{t}*($F$4-$F$7))))',
        )
        ws.cell(row, 7, f'=IF(U{row}="","",T{row})')
        add_mapping_formulas(ws, row)
        for col in range(7, 20):
            ws.cell(row, col).border = BORDER
            ws.cell(row, col).fill = PatternFill("solid", fgColor=GREEN)
            ws.cell(row, col).number_format = "0.000000"

    for col in ("T", "U", "V", "W", "X"):
        ws.column_dimensions[col].hidden = True

    ws.auto_filter.ref = f"A18:B{TABLE_LAST}"
    positive = DataValidation(type="decimal", operator="greaterThan", formula1="0")
    positive.error = "請輸入大於 0 的數值"
    positive.showErrorMessage = True
    ws.add_data_validation(positive)
    positive.add("B4:B6")
    positive.add("B11:B12")
    samples = DataValidation(type="whole", operator="between", formula1="2", formula2="50")
    samples.error = "每邊取樣段數須為 2～50 的整數"
    samples.showErrorMessage = True
    ws.add_data_validation(samples)
    samples.add("E9")
    ws.conditional_formatting.add(
        "H4:H8",
        FormulaRule(formula=['LEFT(H4,2)<>"OK"'], fill=PatternFill("solid", fgColor=RED)),
    )

    widths = {
        "A": 21, "B": 18, "C": 18, "D": 17, "E": 18, "F": 18,
        "G": 14, "H": 15, "I": 15, "J": 16, "K": 16, "L": 15,
        "M": 16, "N": 15, "O": 15, "P": 15, "Q": 15, "R": 15, "S": 13,
    }
    for col, width in widths.items():
        ws.column_dimensions[col].width = width

    sensor_chart = ScatterChart()
    sensor_chart.title = "Sensor 面：目標四邊形與正向驗證"
    sensor_chart.x_axis.title = "Sensor X (mm)"
    sensor_chart.y_axis.title = "Sensor Y (mm，向下為正)"
    sensor_chart.y_axis.scaling.orientation = "maxMin"
    sensor_chart.height = 10
    sensor_chart.width = 17
    target_x = Reference(ws, min_col=8, min_row=BOUNDARY_FIRST, max_row=BOUNDARY_LAST)
    target_y = Reference(ws, min_col=9, min_row=BOUNDARY_FIRST, max_row=BOUNDARY_LAST)
    verify_x = Reference(ws, min_col=17, min_row=BOUNDARY_FIRST, max_row=BOUNDARY_LAST)
    verify_y = Reference(ws, min_col=18, min_row=BOUNDARY_FIRST, max_row=BOUNDARY_LAST)
    target_series = Series(target_y, target_x, title="Sensor 目標")
    target_series.graphicalProperties.line.solidFill = "4472C4"
    verify_series = Series(verify_y, verify_x, title="正向驗證")
    verify_series.graphicalProperties.line.solidFill = "C00000"
    sensor_chart.series.append(target_series)
    sensor_chart.series.append(verify_series)
    ws.add_chart(sensor_chart, "G231")

    object_chart = ScatterChart()
    object_chart.title = "物平面：CAD 預變形曲邊"
    object_chart.x_axis.title = "CAD X (mm)"
    object_chart.y_axis.title = "CAD Y (mm)"
    object_chart.height = 10
    object_chart.width = 17
    object_x = Reference(ws, min_col=15, min_row=BOUNDARY_FIRST, max_row=BOUNDARY_LAST)
    object_y = Reference(ws, min_col=16, min_row=BOUNDARY_FIRST, max_row=BOUNDARY_LAST)
    object_series = Series(object_y, object_x, title="CAD 預變形")
    object_series.graphicalProperties.line.solidFill = "70AD47"
    object_chart.series.append(object_series)
    object_chart.legend = None
    ws.add_chart(object_chart, "G251")

    guide.sheet_view.showGridLines = False
    guide.merge_cells("A1:F1")
    guide["A1"] = "mm 座標逆畸變：使用說明"
    guide["A1"].font = Font(size=18, bold=True, color=WHITE)
    guide["A1"].fill = PatternFill("solid", fgColor=NAVY)
    guide["A1"].alignment = Alignment(horizontal="center")
    guide.column_dimensions["A"].width = 20
    guide.column_dimensions["B"].width = 108
    instructions = [
        ("預設 Sensor", "3840×2160、pixel size 2 µm，因此 sensor 實體尺寸為 7.68×4.32 mm。"
         "Sensor 座標原點在左上角，X 向右、Y 向下，預設光軸中心為 (3.84, 2.16) mm。"),
        ("四點輸入", "P1=(1145×0.002, 856×0.002)、P2=(1545×0.002, 856×0.002)、"
         "P3=(1545×0.002, 656×0.002)、P4=(1145×0.002, 656×0.002)，全部已轉成 mm。可直接修改黃色 X/Y。"),
        ("操作", "1. 輸入 EFL、物方平面至入瞳距離及光軸中心。\\n"
         "2. 輸入 sensor 面目標四點的絕對 mm 座標。\\n"
         "3. 貼上最多 2000 筆半視角／Optical distortion 資料。\\n"
         "4. 從「CAD X/Y」讀取四角，或匯出完整預變形曲邊。"),
        ("CAD 座標", "物方 CAD 原點是光軸投影點，X 向右、Y 向上，單位為 mm；公式已包含鏡頭倒像。"
         "若 CAD 原點或觀看方向不同，匯入後需平移、旋轉或鏡射。"),
        ("內插模型", "由半視角／Distortion 建立「半視角 ↔ 畸變 sensor 半徑」LUT，作分段線性內插，"
         "再用物方半徑 R=Z·tan(θ) 反算。首列半視角必須是 0。"),
        ("四角與曲邊", "四個 CAD 點只保證角落正確；四點直接連成直線只能近似補償。"
         "若 sensor 上的邊必須筆直，請使用完整預變形曲邊座標建立 spline 或 polyline。"),
        ("模型限制", "Z 應從鏡頭入瞳量到物平面。模型只含旋轉對稱徑向畸變，不含 tangential/decentering distortion、"
         "sensor tilt 或姿態透視；近距離實鏡宜用工作距離下的實測資料。"),
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
        guide.row_dimensions[row].height = 66

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
