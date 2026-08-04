#!/usr/bin/env python3
"""Generate the inverse lens-distortion rectangle pre-warp workbook."""

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
TABLE_LAST = 218
CORNER_FIRST = 19
CORNER_LAST = 22
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
    """Invert distorted sensor radius to half field angle."""
    count = "$E$12"
    d_range = "$D$19:$D$218"
    a_range = "$A$19:$A$218"
    active_d = f"$D$19:INDEX({d_range},{count})"
    match = f"MATCH({radius_cell},{active_d},1)"
    return (
        f'=IF(OR($E$13<>"OK",{radius_cell}=""),"",'
        f'IF({radius_cell}<=$D$19,$A$19,'
        f'IF({radius_cell}>=INDEX({d_range},{count}),INDEX({a_range},{count}),'
        f'INDEX({a_range},{match})+'
        f'({radius_cell}-INDEX({d_range},{match}))*'
        f'(INDEX({a_range},{match}+1)-INDEX({a_range},{match}))/'
        f'(INDEX({d_range},{match}+1)-INDEX({d_range},{match})))))'
    )


def forward_radius_formula(angle_cell: str) -> str:
    """Interpolate distorted sensor radius at a half field angle."""
    count = "$E$12"
    a_range = "$A$19:$A$218"
    d_range = "$D$19:$D$218"
    active_a = f"$A$19:INDEX({a_range},{count})"
    match = f"MATCH({angle_cell},{active_a},1)"
    return (
        f'=IF(OR($E$13<>"OK",{angle_cell}=""),"",'
        f'IF({angle_cell}<=$A$19,$D$19,'
        f'IF({angle_cell}>=INDEX({a_range},{count}),INDEX({d_range},{count}),'
        f'INDEX({d_range},{match})+'
        f'({angle_cell}-INDEX({a_range},{match}))*'
        f'(INDEX({d_range},{match}+1)-INDEX({d_range},{match}))/'
        f'(INDEX({a_range},{match}+1)-INDEX({a_range},{match})))))'
    )


def add_mapping_formulas(ws, row: int) -> None:
    """Add inverse mapping and forward-verification formulas to one row."""
    ws.cell(row, 10, f'=IF(H{row}="","",H{row}-$B$7)')  # J sensor dx
    ws.cell(row, 11, f'=IF(I{row}="","",I{row}-$B$8)')  # K sensor dy
    ws.cell(row, 12, f'=IFERROR(SQRT(J{row}^2+K{row}^2)*$B$4/1000,"")')
    ws.cell(row, 13, inverse_angle_formula(f"L{row}"))
    ws.cell(row, 14, f'=IF(M{row}="","",$B$6*TAN(RADIANS(M{row})))')
    # Pinhole image inversion: sensor x is opposite object X. Pixel Y-down
    # corresponds to positive object Y-up after the optical inversion.
    ws.cell(row, 15, f'=IF(N{row}="","",IF(L{row}=0,0,-N{row}*J{row}/SQRT(J{row}^2+K{row}^2)))')
    ws.cell(row, 16, f'=IF(N{row}="","",IF(L{row}=0,0,N{row}*K{row}/SQRT(J{row}^2+K{row}^2)))')
    ws.cell(row, 24, forward_radius_formula(f"M{row}"))  # X hidden, mm
    ws.cell(row, 25, f'=IF(X{row}="","",X{row}*1000/$B$4)')  # Y hidden, pixel
    ws.cell(row, 17, f'=IF(N{row}="","",IF(N{row}=0,$B$7,$B$7-Y{row}*O{row}/N{row}))')
    ws.cell(row, 18, f'=IF(N{row}="","",IF(N{row}=0,$B$8,$B$8+Y{row}*P{row}/N{row}))')
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
    ws["A1"] = "Lens Distortion 長方形逆向預變形計算器"
    ws["A1"].font = Font(size=18, bold=True, color=WHITE)
    ws["A1"].fill = PatternFill("solid", fgColor=NAVY)
    ws["A1"].alignment = Alignment(horizontal="center")
    ws.row_dimensions[1].height = 30
    ws.merge_cells("A2:S2")
    ws["A2"] = "先定義 sensor 上希望看到的正常長方形，再反算物方預變形邊界；黃色欄位為輸入。"
    ws["A2"].font = Font(italic=True, color="666666")
    ws["A2"].alignment = Alignment(horizontal="center")

    section(ws, "A3:C3", "鏡頭／Sensor 輸入")
    section(ws, "D3:F3", "Sensor 目標長方形")
    lens_inputs = [
        (4, "Sensor pixel size", 3.45, "µm/pixel"),
        (5, "Lens 有效焦距 EFL", 4.0, "mm"),
        (6, "物方平面至入瞳距離", 1000.0, "mm"),
        (7, "光軸中心 X", 960.0, "pixel"),
        (8, "光軸中心 Y", 540.0, "pixel"),
    ]
    for row, label, value, unit in lens_inputs:
        ws.cell(row, 1, label)
        ws.cell(row, 2, value)
        ws.cell(row, 3, unit)
        ws.cell(row, 2).fill = PatternFill("solid", fgColor=YELLOW)
        ws.cell(row, 2).border = BORDER

    rectangle_inputs = [
        (4, "中心 X", 960.0, "pixel"),
        (5, "中心 Y", 540.0, "pixel"),
        (6, "寬度", 800.0, "pixel"),
        (7, "高度", 400.0, "pixel"),
        (8, "旋轉角", 0.0, "degree，順時針"),
        (9, "每邊取樣段數", 25, "2～50"),
    ]
    for row, label, value, unit in rectangle_inputs:
        ws.cell(row, 4, label)
        ws.cell(row, 5, value)
        ws.cell(row, 6, unit)
        ws.cell(row, 5).fill = PatternFill("solid", fgColor=YELLOW)
        ws.cell(row, 5).border = BORDER

    ws["A11"] = "輸入檢查"
    ws["A11"].font = Font(bold=True, color=WHITE)
    ws["A11"].fill = PatternFill("solid", fgColor=NAVY)
    ws["B11"] = '=IF(AND(B4>0,B5>0,B6>0,E6>0,E7>0,E9>=2,E9<=50),"OK","錯誤：數值範圍")'
    ws["D11"] = "最大邊界點數"
    ws["E11"] = "=4*E9+1"
    ws["D12"] = "有效畸變表列數"
    ws["E12"] = f"=COUNT(A{TABLE_FIRST}:A{TABLE_LAST})"
    ws["D13"] = "畸變表狀態"
    ws["E13"] = (
        '=IF(E12<2,"錯誤：至少 2 列",'
        'IF(A19<>0,"錯誤：首列半視角須為 0",'
        'IF(COUNTBLANK(A19:INDEX(A:A,18+E12))+COUNTBLANK(B19:INDEX(B:B,18+E12))>0,'
        '"錯誤：中間不可空白",'
        'IF(SUMPRODUCT(--(A20:INDEX(A:A,18+E12)<=A19:INDEX(A:A,17+E12)))>0,'
        '"錯誤：半視角須遞增",'
        'IF(SUMPRODUCT(--(D20:INDEX(D:D,18+E12)<=D19:INDEX(D:D,17+E12)))>0,'
        '"錯誤：畸變像高須遞增","OK")))))'
    )
    ws["D14"] = "目標範圍"
    ws["E14"] = '=IF(MAX(L19:L22)>MAX(D19:D218),"警告：超出表格，使用端點角度","OK")'
    for row in range(11, 15):
        for col in range(1, 6):
            ws.cell(row, col).border = BORDER
        if row > 11:
            ws.cell(row, 4).fill = PatternFill("solid", fgColor=GRAY)
            ws.cell(row, 5).fill = PatternFill("solid", fgColor=GREEN)

    section(ws, "A17:E17", "Lens distortion table（最多 200 筆）")
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
        ws.cell(row, 3, f'=IF(A{row}="","",$B$5*TAN(RADIANS(A{row})))')
        ws.cell(row, 4, f'=IF(C{row}="","",C{row}*(1+B{row}/100))')
        ws.cell(row, 5, f'=IF(A{row}="","",$B$6*TAN(RADIANS(A{row})))')
        for col in range(1, 6):
            ws.cell(row, col).border = BORDER
            ws.cell(row, col).number_format = "0.000000"
        ws.cell(row, 1).fill = ws.cell(row, 2).fill = PatternFill("solid", fgColor=YELLOW)

    section(ws, "G17:S17", "物方預變形四角與正向驗證")
    output_headers = [
        "點",
        "目標 X\n(pixel)",
        "目標 Y\n(pixel)",
        "相對 X\n(pixel)",
        "相對 Y\n(pixel)",
        "目標半徑\n(mm)",
        "反查半視角\n(degree)",
        "物方半徑\n(mm)",
        "物方 X\n(mm)",
        "物方 Y\n(mm)",
        "驗證 X\n(pixel)",
        "驗證 Y\n(pixel)",
        "誤差\n(pixel)",
    ]
    for col, value in enumerate(output_headers, 7):
        cell = ws.cell(18, col, value)
        cell.font = Font(bold=True, color=WHITE)
        cell.fill = PatternFill("solid", fgColor=NAVY)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER

    corner_uv = [
        ("P1", "-$E$6/2", "-$E$7/2"),
        ("P2", "$E$6/2", "-$E$7/2"),
        ("P3", "$E$6/2", "$E$7/2"),
        ("P4", "-$E$6/2", "$E$7/2"),
    ]
    for row, (name, u, v) in zip(range(CORNER_FIRST, CORNER_LAST + 1), corner_uv):
        ws.cell(row, 7, name)
        ws.cell(row, 22, f"={u}")  # V hidden local U
        ws.cell(row, 23, f"={v}")  # W hidden local V
        ws.cell(row, 8, f'=$E$4+V{row}*COS(RADIANS($E$8))-W{row}*SIN(RADIANS($E$8))')
        ws.cell(row, 9, f'=$E$5+V{row}*SIN(RADIANS($E$8))+W{row}*COS(RADIANS($E$8))')
        add_mapping_formulas(ws, row)
        for col in range(7, 20):
            ws.cell(row, col).border = BORDER
            ws.cell(row, col).fill = PatternFill("solid", fgColor=GREEN)
            ws.cell(row, col).number_format = "0.000000"

    section(ws, "G25:S25", "完整預變形曲邊座標（每邊最多 50 段）")
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
        ws.cell(
            row,
            22,
            f'=IF(U{row}="","",CHOOSE(U{row},-$E$6/2+MOD(T{row},$E$9)/$E$9*$E$6,'
            f'$E$6/2,$E$6/2-MOD(T{row},$E$9)/$E$9*$E$6,-$E$6/2))',
        )
        ws.cell(
            row,
            23,
            f'=IF(U{row}="","",CHOOSE(U{row},-$E$7/2,-$E$7/2+MOD(T{row},$E$9)/$E$9*$E$7,'
            f'$E$7/2,$E$7/2-MOD(T{row},$E$9)/$E$9*$E$7))',
        )
        # The final point closes edge 4; MOD would otherwise return zero.
        ws.cell(row, 22, f'=IF(T{row}=4*$E$9,-$E$6/2,{ws.cell(row, 22).value[1:]})')
        ws.cell(row, 23, f'=IF(T{row}=4*$E$9,-$E$7/2,{ws.cell(row, 23).value[1:]})')
        ws.cell(row, 7, f'=IF(U{row}="","",T{row})')
        ws.cell(row, 8, f'=IF(U{row}="","",$E$4+V{row}*COS(RADIANS($E$8))-W{row}*SIN(RADIANS($E$8)))')
        ws.cell(row, 9, f'=IF(U{row}="","",$E$5+V{row}*SIN(RADIANS($E$8))+W{row}*COS(RADIANS($E$8)))')
        add_mapping_formulas(ws, row)
        for col in range(7, 20):
            ws.cell(row, col).border = BORDER
            ws.cell(row, col).fill = PatternFill("solid", fgColor=GREEN)
            ws.cell(row, col).number_format = "0.000000"

    # Hide implementation helpers: perimeter index/edge/local coordinates and verification radius.
    for col in ("T", "U", "V", "W", "X", "Y"):
        ws.column_dimensions[col].hidden = True

    ws.auto_filter.ref = f"A18:B{TABLE_LAST}"
    positive = DataValidation(type="decimal", operator="greaterThan", formula1="0")
    positive.error = "請輸入大於 0 的數值"
    positive.showErrorMessage = True
    ws.add_data_validation(positive)
    positive.add("B4:B6")
    positive.add("E6:E7")
    samples = DataValidation(type="whole", operator="between", formula1="2", formula2="50")
    samples.error = "每邊取樣段數須為 2～50 的整數"
    samples.showErrorMessage = True
    ws.add_data_validation(samples)
    samples.add("E9")
    ws.conditional_formatting.add(
        "B11",
        FormulaRule(formula=['B11<>"OK"'], fill=PatternFill("solid", fgColor=RED)),
    )
    ws.conditional_formatting.add(
        "E13:E14",
        FormulaRule(formula=['LEFT(E13,2)<>"OK"'], fill=PatternFill("solid", fgColor=RED)),
    )

    widths = {
        "A": 18, "B": 18, "C": 18, "D": 19, "E": 18, "F": 16,
        "G": 9, "H": 14, "I": 14, "J": 14, "K": 14, "L": 15,
        "M": 16, "N": 15, "O": 15, "P": 15, "Q": 15, "R": 15, "S": 13,
    }
    for col, width in widths.items():
        ws.column_dimensions[col].width = width

    sensor_chart = ScatterChart()
    sensor_chart.title = "Sensor：目標長方形與正向驗證"
    sensor_chart.x_axis.title = "X (pixel)"
    sensor_chart.y_axis.title = "Y (pixel，向下為正)"
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
    ws.add_chart(sensor_chart, "A231")

    object_chart = ScatterChart()
    object_chart.title = "物方：需要製作的預變形曲邊"
    object_chart.x_axis.title = "物方 X (mm)"
    object_chart.y_axis.title = "物方 Y (mm)"
    object_chart.height = 10
    object_chart.width = 17
    object_x = Reference(ws, min_col=15, min_row=BOUNDARY_FIRST, max_row=BOUNDARY_LAST)
    object_y = Reference(ws, min_col=16, min_row=BOUNDARY_FIRST, max_row=BOUNDARY_LAST)
    object_series = Series(object_y, object_x, title="物方預變形")
    object_series.graphicalProperties.line.solidFill = "70AD47"
    object_chart.series.append(object_series)
    object_chart.legend = None
    ws.add_chart(object_chart, "J231")

    guide.sheet_view.showGridLines = False
    guide.merge_cells("A1:F1")
    guide["A1"] = "逆畸變預變形：使用說明與模型限制"
    guide["A1"].font = Font(size=18, bold=True, color=WHITE)
    guide["A1"].fill = PatternFill("solid", fgColor=NAVY)
    guide["A1"].alignment = Alignment(horizontal="center")
    guide.column_dimensions["A"].width = 20
    guide.column_dimensions["B"].width = 105
    instructions = [
        ("目的", "先在 sensor 座標中定義正常長方形。本檔反向求出物方應製作的預變形邊界，使其經鏡頭後回到指定長方形。"),
        ("操作", "1. 輸入 pixel size、EFL、物方平面至入瞳距離及光軸中心。\\n"
         "2. 輸入 sensor 目標長方形的中心、寬、高、順時針旋轉角。\\n"
         "3. 將黃色示例表換成鏡頭的半視角／Optical distortion 資料，可貼入最多 200 筆。\\n"
         "4. 讀取四角或完整曲邊的物方 X/Y。"),
        ("畸變定義", "Distortion(%)=(畸變 sensor 半徑/理想 sensor 半徑−1)×100%。"
         "正值向外（通常 pincushion），負值向內（通常 barrel）。TV distortion 或相反符號必須先轉換。"),
        ("反向算法", "由每筆半視角／Distortion 先建立「半視角 ↔ 畸變 sensor 半徑」LUT，並在相鄰資料點間做分段線性內插；"
         "再用 R=Z·tan(θ) 求物方半徑。首列半視角必須為 0；超出表格時使用端點角度，不外插。"),
        ("四角與曲邊", "P1～P4 只能保證四個角落正確。徑向逆畸變通常使物方直邊變成曲線；若要 sensor 邊緣筆直，"
         "請使用「完整預變形曲邊座標」。每邊取樣越多，折線近似越準。"),
        ("座標方向", "Sensor X 向右、Y 向下。物方 X 向右、Y 向上，並包含鏡頭形成的倒像：sensor X 與物方 X 符號相反。"
         "若加工設備使用其他觀看方向，需做鏡射或旋轉轉換。"),
        ("距離與實鏡限制", "Z 應從鏡頭入瞳位置量到物方平面，不一定等於鏡頭外殼距離。模型假設旋轉對稱徑向畸變，"
         "不含 tangential/decentering distortion、sensor tilt 或姿態透視。近距離與多片鏡頭宜用工作距離下的實測映射校正。"),
        ("驗證", "「驗證 X/Y」把預變形物方點重新正向投影；誤差應接近 0 pixel。這是數學模型內部驗證，不代表實鏡製造與裝配誤差。"),
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
    """Save an XLSX with stable entry order, metadata, and ZIP timestamps."""
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
