#!/usr/bin/env python3
"""Generate the spherical-wall TV-line predistortion workbook."""

from datetime import datetime
import math
from pathlib import Path
import re
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.chart import Reference, ScatterChart, Series
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.formula import ArrayFormula


OUTPUT = Path(__file__).with_name("spherical_chart_predistortion.xlsx")
FIXED_TIMESTAMP = (2000, 1, 1, 0, 0, 0)
TABLE_FIRST = 19
TABLE_LAST = 2018
TVL_FIRST = 4
TVL_LAST = 14
OUTPUT_FIRST = 19
OUTPUT_LAST = 458
MAIN = "球面圖卡計算器"
CAD_BLOCKS = 110

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


def add_tail_fit(ws) -> None:
    """Fit θ = a + b·h + c·h² to the last 10 rows and expose its end slope."""
    for row in range(TABLE_FIRST, TABLE_LAST + 1):
        ws.cell(row, 34, f'=IF(B{row}="","",B{row})')
        ws.cell(row, 35, f'=IF(B{row}="","",B{row}^2)')
    ws.column_dimensions["AH"].hidden = True
    ws.column_dimensions["AI"].hidden = True
    ws["J15"] = "外推擬合"
    ws["J15"].font = Font(bold=True, color=WHITE)
    ws["J15"].fill = PatternFill("solid", fgColor=NAVY)
    ws["K15"] = ArrayFormula(
        ref="K15:M15",
        text=(
            '=IF($H$6<6,"",LINEST(OFFSET($A$19,$H$6-MIN(10,$H$6),0,MIN(10,$H$6),1),'
            'OFFSET($AH$19,$H$6-MIN(10,$H$6),0,MIN(10,$H$6),2),TRUE,FALSE))'
        ),
    )
    ws["N15"] = (
        '=IF($H$6<6,'
        '(INDEX($A$19:$A$2018,$H$6)-INDEX($A$19:$A$2018,$H$6-1))/'
        '(INDEX($B$19:$B$2018,$H$6)-INDEX($B$19:$B$2018,$H$6-1)),'
        '$L$15+2*$K$15*INDEX($B$19:$B$2018,$H$6))'
    )
    ws["O15"] = "degree/mm"
    for col in ("K", "L", "M", "N"):
        ws[f"{col}15"].number_format = "0.000000"
        ws[f"{col}15"].fill = PatternFill("solid", fgColor=GREEN)


def inverse_angle_formula(radius_cell: str) -> str:
    count = "$H$6"
    h_range = f"$B$19:$B${TABLE_LAST}"
    a_range = f"$A$19:$A${TABLE_LAST}"
    active_h = f"$B$19:INDEX({h_range},{count})"
    match = f"MATCH({radius_cell},{active_h},1)"
    inside = (
        f'INDEX({a_range},{match})+({radius_cell}-INDEX({h_range},{match}))*'
        f'(INDEX({a_range},{match}+1)-INDEX({a_range},{match}))/'
        f'(INDEX({h_range},{match}+1)-INDEX({h_range},{match}))'
    )
    low = (
        f'$A$19+({radius_cell}-$B$19)*(INDEX({a_range},2)-$A$19)/'
        f'(INDEX({h_range},2)-$B$19)'
    )
    high = f'INDEX({a_range},{count})+({radius_cell}-INDEX({h_range},{count}))*$N$15'
    return (
        f'=IF({radius_cell}="","",IF({radius_cell}<=$B$19,{low},'
        f'IF({radius_cell}>=INDEX({h_range},{count}),{high},{inside})))'
    )


def add_wall_formulas(ws, row: int) -> None:
    """Intersect each optical ray with the tilted peripheral wall."""
    ws.cell(row, 14, f'=L{row}-$B$7/2')
    ws.cell(row, 15, f'=M{row}-$B$8/2')
    ws.cell(row, 16, f'=SQRT(N{row}^2+O{row}^2)')
    ws.cell(row, 17, inverse_angle_formula(f"P{row}"))
    ws.cell(row, 27, f'=IF(P{row}=0,0,-N{row}/P{row})')
    ws.cell(row, 28, f'=IF(P{row}=0,0,O{row}/P{row})')
    ws.cell(row, 29, f'=$C$12*AA{row}+$C$13*AB{row}')
    ws.cell(
        row,
        30,
        f'=IF(Q{row}="","",SIN(RADIANS($B$10))*SIN(RADIANS(Q{row}))*AC{row}'
        f'+COS(RADIANS($B$10))*COS(RADIANS(Q{row})))',
    )
    ws.cell(row, 31, f'=IF(OR(AD{row}="",AD{row}<=0),"",$B$9*COS(RADIANS($B$10))/AD{row})')
    ws.cell(row, 18, f'=IF(AE{row}="","",AE{row}*SIN(RADIANS(Q{row}))*AA{row})')
    ws.cell(row, 19, f'=IF(AE{row}="","",AE{row}*SIN(RADIANS(Q{row}))*AB{row})')
    ws.cell(row, 20, f'=IF(AE{row}="","",AE{row}*COS(RADIANS(Q{row}))-$B$9)')
    ws.cell(row, 23, f'=IF(AE{row}="","未相交","OK")')
    dot = f'(-$C$13*R{row}+$C$12*S{row})'
    ws.cell(
        row,
        21,
        f'=IF(R{row}="","",R{row}*COS(RADIANS($B$10))-($C$12*T{row})*SIN(RADIANS($B$10))'
        f'+(-$C$13)*{dot}*(1-COS(RADIANS($B$10))))',
    )
    ws.cell(
        row,
        22,
        f'=IF(S{row}="","",S{row}*COS(RADIANS($B$10))-($C$13*T{row})*SIN(RADIANS($B$10))'
        f'+$C$12*{dot}*(1-COS(RADIANS($B$10))))',
    )


def style_command_sheet(ws, title: str, instructions: str) -> None:
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "A8"
    ws.merge_cells("A1:B1")
    ws["A1"] = title
    ws["A1"].font = Font(size=18, bold=True, color=WHITE)
    ws["A1"].fill = PatternFill("solid", fgColor=NAVY)
    ws.merge_cells("A2:B5")
    ws["A2"] = instructions
    ws["A2"].alignment = Alignment(wrap_text=True, vertical="top")
    ws["A2"].fill = PatternFill("solid", fgColor=BLUE)
    for row in range(2, 6):
        ws.row_dimensions[row].height = 18
    for col, heading in ((1, "命令（只複製此欄）"), (2, "線段")):
        cell = ws.cell(7, col, heading)
        cell.font = Font(bold=True, color=WHITE)
        cell.fill = PatternFill("solid", fgColor=NAVY)


def add_zwcad_sheet(wb: Workbook) -> None:
    ws = wb.create_sheet("中望CAD")
    style_command_sheet(
        ws,
        "中望CAD 立體牆 3D 多段線",
        "1. 按 Esc，直到命令列回到待命。\n"
        "2. 只複製 A8:A667，貼到命令列。\n"
        "3. 每條線是 _3DPOLY 加四個 X,Y,Z 角點，再以 C 封閉。\n"
        "4. 牆面角度為 0 時 Z=0，圖形落在與平面圖卡相同的 XY 平面。",
    )
    output_row = 8
    for block in range(CAD_BLOCKS):
        source = OUTPUT_FIRST + block * 4
        ws.cell(output_row, 1, "_3DPOLY")
        ws.cell(
            output_row,
            2,
            f'=TEXT(\'{MAIN}\'!H{source},"0")&" TV本 "'
            f'&\'{MAIN}\'!I{source}&" 第"&\'{MAIN}\'!J{source}&"條"',
        )
        for offset in range(4):
            point = source + offset
            ws.cell(
                output_row + 1 + offset,
                1,
                f'=TEXT(\'{MAIN}\'!R{point},"0.000000")&","&'
                f'TEXT(\'{MAIN}\'!S{point},"0.000000")&","&'
                f'TEXT(\'{MAIN}\'!T{point},"0.000000")',
            )
        ws.cell(output_row + 5, 1, "C")
        for offset in range(6):
            ws.cell(output_row + offset, 1).font = Font(name="Consolas")
            ws.cell(output_row + offset, 1).fill = PatternFill("solid", fgColor=GREEN)
        output_row += 6
    ws.column_dimensions["A"].width = 54
    ws.column_dimensions["B"].width = 28


def add_librecad_sheet(wb: Workbook) -> None:
    ws = wb.create_sheet("LibreCAD")
    style_command_sheet(
        ws,
        "LibreCAD 牆面展開線框",
        "1. 只複製 A8:A117。\n"
        "2. 使用命令列選單的 Paste commands（貼上命令）。\n"
        "3. LibreCAD 是 2D，這裡使用攤平後的牆面座標。\n"
        "4. 牆面角度為 0 時，展開座標與平面圖卡的 CAD X/Y 相同。",
    )
    for block in range(CAD_BLOCKS):
        source = OUTPUT_FIRST + block * 4
        points = "&CHAR(59)&".join(
            f'TEXT(\'{MAIN}\'!U{source + offset},"0.000000")&","&'
            f'TEXT(\'{MAIN}\'!V{source + offset},"0.000000")'
            for offset in range(4)
        )
        row = 8 + block
        ws.cell(row, 1, f'="pl"&CHAR(59)&{points}&CHAR(59)&"close"')
        ws.cell(
            row,
            2,
            f'=TEXT(\'{MAIN}\'!H{source},"0")&" TV本 "'
            f'&\'{MAIN}\'!I{source}&" 第"&\'{MAIN}\'!J{source}&"條"',
        )
        ws.cell(row, 1).font = Font(name="Consolas")
        ws.cell(row, 1).fill = PatternFill("solid", fgColor=GREEN)
    ws.column_dimensions["A"].width = 120
    ws.column_dimensions["B"].width = 28


def build_workbook() -> Workbook:
    wb = Workbook()
    wb.properties.created = datetime(*FIXED_TIMESTAMP)
    wb.properties.modified = datetime(*FIXED_TIMESTAMP)
    ws = wb.active
    ws.title = MAIN
    guide = wb.create_sheet("使用說明")
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "A19"
    ws.merge_cells("A1:W1")
    ws["A1"] = "魚眼／大角度鏡頭：球面立體牆 TV本預變形"
    ws["A1"].font = Font(size=18, bold=True, color=WHITE)
    ws["A1"].fill = PatternFill("solid", fgColor=NAVY)
    ws["A1"].alignment = Alignment(horizontal="center")
    ws.row_dimensions[1].height = 30
    ws.merge_cells("A2:W2")
    ws["A2"] = "周邊牆面角度 0° 等於正向平面圖卡；角度增大後，圖卡改放在朝周邊傾斜的立體牆上。黃色欄位為輸入。"
    ws["A2"].font = Font(italic=True, color="666666")

    section(ws, "A3:C3", "Sensor／鏡頭輸入")
    inputs = [
        (4, "Pixel size", 2.0, "µm/pixel"),
        (5, "Sensor 水平像素", 3840, "pixel"),
        (6, "Sensor 垂直像素", 2160, "pixel"),
        (7, "Sensor 寬度", "=B4*B5/1000", "mm"),
        (8, "Sensor 高度", "=B4*B6/1000", "mm"),
        (9, "入瞳至牆軸距離", 1000.0, "mm"),
        (10, "周邊牆面角度", 0.0, "degree，平面為 0"),
    ]
    for row, label, value, unit in inputs:
        ws.cell(row, 1, label)
        ws.cell(row, 2, value)
        ws.cell(row, 3, unit)
        ws.cell(row, 2).border = BORDER
        ws.cell(row, 2).fill = PatternFill("solid", fgColor=GREEN if row in (7, 8) else YELLOW)
    ws["A12"] = "牆面方位 X"
    ws["C12"] = '=IF(SQRT((O9-$B$7/2)^2+(P9-$B$8/2)^2)=0,1,-(O9-$B$7/2)/SQRT((O9-$B$7/2)^2+(P9-$B$8/2)^2))'
    ws["A13"] = "牆面方位 Y"
    ws["C13"] = '=IF(SQRT((O9-$B$7/2)^2+(P9-$B$8/2)^2)=0,0,(P9-$B$8/2)/SQRT((O9-$B$7/2)^2+(P9-$B$8/2)^2))'
    for row in (12, 13):
        ws.cell(row, 3).number_format = "0.000000"
        ws.cell(row, 3).fill = PatternFill("solid", fgColor=GREEN)

    section(ws, "D3:F3", "TV本 Chart 參數")
    chart_inputs = [
        (4, "指定 TV本", 1500, "TV本"),
        (5, "TV本間隔", 100, "TV本"),
        (6, "視場位置", 0.7, "半對角線倍率"),
        (7, "方位角", 29.3577535428, "degree，+X 往上"),
        (8, "每組線條數", 5, "固定"),
    ]
    for row, label, value, unit in chart_inputs:
        ws.cell(row, 4, label)
        ws.cell(row, 5, value)
        ws.cell(row, 6, unit)
        ws.cell(row, 5).border = BORDER
        ws.cell(row, 5).fill = PatternFill("solid", fgColor=GREEN if row == 8 else YELLOW)

    section(ws, "G3:I3", "輸入檢查")
    checks = [
        (4, "基本數值", '=IF(AND(B4>0,B5>0,B6>0,B9>0,ABS(B10)<=80,E4-5*E5>0,E5>0,E6>=0,E6<=1,E7>=0,E7<=90),"OK","錯誤：數值範圍")'),
        (5, "輸出點數", "=11*2*5*4"),
        (6, "有效實像高列數", f"=COUNT(A{TABLE_FIRST}:A{TABLE_LAST})"),
        (7, "實像高表狀態", '=IF(H6<2,"錯誤：至少 2 列",IF(COUNTBLANK(A19:INDEX(A:A,18+H6))+COUNTBLANK(B19:INDEX(B:B,18+H6))>0,"錯誤：中間不可空白",IF(SUMPRODUCT(--(A20:INDEX(A:A,18+H6)<=A19:INDEX(A:A,17+H6)))>0,"錯誤：半視角須遞增",IF(SUMPRODUCT(--(B20:INDEX(B:B,18+H6)<=B19:INDEX(B:B,17+H6)))>0,"錯誤：實像高須遞增","OK"))))'),
        (8, "目標範圍", f'=IF(MAX(P{OUTPUT_FIRST}:P{OUTPUT_LAST})>MAX(B19:B{TABLE_LAST}),"OK，外推","OK")'),
        (9, "牆面交點", f'=IF(COUNTIF(W{OUTPUT_FIRST}:W{OUTPUT_LAST},"未相交")>0,"警告：有光線未打到牆","OK")'),
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
        ws.cell(row, 10, row - 9)
        ws.cell(row, 11, f"=$E$4+J{row}*$E$5")
        ws.cell(row, 12, f"=$B$8/K{row}")
        ws.cell(row, 13, f"=(2*$E$8-1)*L{row}")
        ws.cell(row, 14, f"=2*M{row}+L{row}")
        ws.cell(row, 15, f"=$B$7/2+$E$6*SQRT(($B$7/2)^2+($B$8/2)^2)*COS(RADIANS($E$7))")
        for col in range(10, 17):
            ws.cell(row, col).border = BORDER
            ws.cell(row, col).fill = PatternFill("solid", fgColor=GREEN)
            ws.cell(row, col).number_format = "0.000000"
    ws["P9"] = "=$B$8/2-$E$6*SQRT(($B$7/2)^2+($B$8/2)^2)*SIN(RADIANS($E$7))"
    for row in range(10, TVL_LAST + 1):
        ws.cell(row, 16, f"=P{row-1}+M{row-1}/2+MIN(L{row-1},L{row})+M{row}/2")
    for row in range(8, TVL_FIRST - 1, -1):
        ws.cell(row, 16, f"=P{row+1}-M{row+1}/2-MIN(L{row},L{row+1})-M{row}/2")

    section(ws, "A17:C17", "半視角／實像高表（最多 2000 筆）")
    for col, value in enumerate(("半視角 θ\n(degree)", "實像高 h\n(mm)", "平面參考半徑\n(mm)"), 1):
        cell = ws.cell(18, col, value)
        cell.font = Font(bold=True, color=WHITE)
        cell.fill = PatternFill("solid", fgColor=NAVY)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER
    example_angles = list(range(0, 121, 10))
    example_heights = [2.5 * math.radians(angle) for angle in example_angles]
    for index, row in enumerate(range(TABLE_FIRST, TABLE_LAST + 1)):
        if index < len(example_angles):
            ws.cell(row, 1, example_angles[index])
            ws.cell(row, 2, example_heights[index])
        ws.cell(row, 3, f'=IF(OR(A{row}="",A{row}>=90),"",$B$9*TAN(RADIANS(A{row})))')
        for col in range(1, 4):
            ws.cell(row, col).border = BORDER
            ws.cell(row, col).number_format = "0.000000"
        ws.cell(row, 1).fill = ws.cell(row, 2).fill = PatternFill("solid", fgColor=YELLOW)

    section(ws, "G17:W17", "440 點：立體牆世界座標與牆面展開座標")
    headers = [
        "ID", "TV本", "方向", "線號", "角點", "Sensor X\n(mm)", "Sensor Y\n(mm)",
        "中心座標 X\n(mm)", "中心座標 Y\n(mm)", "像高\n(mm)", "半視角\n(degree)",
        "世界 X\n(mm)", "世界 Y\n(mm)", "世界 Z\n(mm)", "牆面 X\n(mm)", "牆面 Y\n(mm)", "交點",
    ]
    for col, value in enumerate(headers, 7):
        cell = ws.cell(18, col, value)
        cell.font = Font(bold=True, color=WHITE)
        cell.fill = PatternFill("solid", fgColor=NAVY)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER
    row = OUTPUT_FIRST
    corners = [(-1, -1, "左上"), (1, -1, "右上"), (1, 1, "右下"), (-1, 1, "左下")]
    for geometry_row in range(TVL_FIRST, TVL_LAST + 1):
        for orientation in ("橫", "豎"):
            for line_number in range(1, 6):
                for corner_x, corner_y, corner_name in corners:
                    ws.cell(row, 7, row - OUTPUT_FIRST + 1)
                    ws.cell(row, 8, f"=$K${geometry_row}")
                    ws.cell(row, 9, orientation)
                    ws.cell(row, 10, line_number)
                    ws.cell(row, 11, corner_name)
                    width = f"$L${geometry_row}"
                    group = f"$M${geometry_row}"
                    center_x = f"$O${geometry_row}"
                    center_y = f"$P${geometry_row}"
                    offset = f"({group}+{width})/2"
                    if orientation == "橫":
                        ws.cell(row, 12, f"={center_x}-{offset}+({corner_x})*{group}/2")
                        ws.cell(row, 13, f"={center_y}-{group}/2+{width}/2+{line_number-1}*2*{width}+({corner_y})*{width}/2")
                    else:
                        group_center = f"{center_x}+{offset}"
                        ws.cell(row, 12, f"={group_center}-{group}/2+{width}/2+{line_number-1}*2*{width}+({corner_x})*{width}/2")
                        ws.cell(row, 13, f"={center_y}+({corner_y})*{group}/2")
                    add_wall_formulas(ws, row)
                    for col in range(7, 24):
                        ws.cell(row, col).border = BORDER
                        ws.cell(row, col).fill = PatternFill("solid", fgColor=GREEN)
                        if col not in (9, 11, 23):
                            ws.cell(row, col).number_format = "0.000000"
                    row += 1
    for col in ("AA", "AB", "AC", "AD", "AE"):
        ws.column_dimensions[col].hidden = True

    positive = DataValidation(type="decimal", operator="greaterThan", formula1="0")
    positive.showErrorMessage = True
    ws.add_data_validation(positive)
    positive.add("B4:B6")
    positive.add("B9")
    positive.add("E4:E5")
    tilt = DataValidation(type="decimal", operator="between", formula1="-80", formula2="80")
    tilt.error = "周邊牆面角度須介於 -80～80°"
    tilt.showErrorMessage = True
    ws.add_data_validation(tilt)
    tilt.add("B10")
    field = DataValidation(type="decimal", operator="between", formula1="0", formula2="1")
    field.showErrorMessage = True
    ws.add_data_validation(field)
    field.add("E6")
    azimuth = DataValidation(type="decimal", operator="between", formula1="0", formula2="90")
    azimuth.showErrorMessage = True
    ws.add_data_validation(azimuth)
    azimuth.add("E7")
    ws.conditional_formatting.add("H4:H9", FormulaRule(formula=['LEFT(H4,2)<>"OK"'], fill=PatternFill("solid", fgColor=RED)))

    widths = {"A": 18, "B": 18, "C": 18, "D": 16, "E": 16, "F": 18, "G": 12, "H": 14, "I": 10, "J": 10, "K": 12, "L": 14, "M": 14, "N": 14, "O": 14, "P": 14, "Q": 14, "R": 14, "S": 14, "T": 14, "U": 14, "V": 14, "W": 12}
    for col, width in widths.items():
        ws.column_dimensions[col].width = width

    sensor_chart = ScatterChart()
    sensor_chart.title = "Sensor 第一象限 TV本"
    sensor_chart.y_axis.scaling.orientation = "maxMin"
    sensor_chart.height = 9
    sensor_chart.width = 16
    sensor_chart.legend = None
    sensor_series = Series(Reference(ws, min_col=13, min_row=OUTPUT_FIRST, max_row=OUTPUT_LAST), Reference(ws, min_col=12, min_row=OUTPUT_FIRST, max_row=OUTPUT_LAST), title="Sensor")
    sensor_series.graphicalProperties.line.noFill = True
    sensor_series.marker.symbol = "circle"
    sensor_series.marker.size = 2
    sensor_chart.series.append(sensor_series)
    ws.add_chart(sensor_chart, "G462")
    wall_chart = ScatterChart()
    wall_chart.title = "牆面展開線框"
    wall_chart.height = 9
    wall_chart.width = 16
    wall_chart.legend = None
    wall_series = Series(Reference(ws, min_col=22, min_row=OUTPUT_FIRST, max_row=OUTPUT_LAST), Reference(ws, min_col=21, min_row=OUTPUT_FIRST, max_row=OUTPUT_LAST), title="牆面")
    wall_series.graphicalProperties.line.noFill = True
    wall_series.marker.symbol = "circle"
    wall_series.marker.size = 2
    wall_chart.series.append(wall_series)
    ws.add_chart(wall_chart, "G482")

    guide.sheet_view.showGridLines = False
    guide.merge_cells("A1:B1")
    guide["A1"] = "球面立體牆：模型與使用"
    guide["A1"].font = Font(size=18, bold=True, color=WHITE)
    guide["A1"].fill = PatternFill("solid", fgColor=NAVY)
    guide.column_dimensions["A"].width = 20
    guide.column_dimensions["B"].width = 112
    instructions = [
        ("牆面角度", "這是斜牆和正向平面的夾角，不是半視角。鉸鏈在光軸打到圖卡的點。正角度時，圖卡外緣往鏡頭折；0° 時牆面與光軸垂直。"),
        ("座標", "世界 X/Y/Z 是裝上斜牆後的三維位置，Z 以正向平面為 0。牆面 X/Y 是把斜牆轉回平面後的製造座標，可直接在 2D CAD 畫線。"),
        ("大角度", "半視角接近或超過 90° 時，正向平面沒有有限交點；只要傾斜後的牆面仍被該光線打到，就會得到有限座標。半視角超過 90° 的平面參考半徑留白。"),
        ("實像高", "表內用相鄰點線性內插。超出最後一筆時，用尾端最多 10 筆擬合曲線的終點斜率繼續外推。牆面角度仍決定這條光線打在哪一面牆上。"),
        ("CAD", "中望CAD 使用世界 X,Y,Z 的 _3DPOLY。LibreCAD 只使用牆面展開的 2D 座標，並以 Paste commands 貼上。"),
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
        guide.row_dimensions[row].height = 62
    diagram = XLImage(Path(__file__).with_name("assets") / "wall_angle_side_view.png")
    diagram.width = 720
    diagram.height = 441
    guide.add_image(diagram, "A9")
    guide.row_dimensions[9].height = 330

    add_tail_fit(ws)
    add_zwcad_sheet(wb)
    add_librecad_sheet(wb)
    wb.calculation.fullCalcOnLoad = True
    wb.calculation.forceFullCalc = True
    wb.calculation.calcMode = "auto"
    wb.active = 0
    return wb


def save_deterministic(workbook: Workbook, output: Path) -> None:
    workbook.save(output)
    normalized = output.with_suffix(".normalized.xlsx")
    with ZipFile(output, "r") as source, ZipFile(normalized, "w", compression=ZIP_DEFLATED, compresslevel=9) as target:
        for name in sorted(source.namelist()):
            original = source.getinfo(name)
            info = ZipInfo(name, date_time=FIXED_TIMESTAMP)
            info.compress_type = ZIP_DEFLATED
            info.external_attr = original.external_attr
            info.create_system = original.create_system
            data = source.read(name)
            if name == "docProps/core.xml":
                data = re.sub(rb"(<dcterms:modified[^>]*>)[^<]*(</dcterms:modified>)", rb"\g<1>2000-01-01T00:00:00Z\g<2>", data)
            target.writestr(info, data)
    normalized.replace(output)


if __name__ == "__main__":
    workbook = build_workbook()
    save_deterministic(workbook, OUTPUT)
    print(f"Created {OUTPUT}")
