#!/usr/bin/env python3
"""Build the Imatest SFR slanted-square workbook for ZWCAD LINE/ARC output."""

from __future__ import annotations

from openpyxl import Workbook
from openpyxl.chart import Reference, ScatterChart, Series
from openpyxl.chart.marker import Marker
from openpyxl.comments import Comment
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation

from sfr_geometry import N_CURVE, POWERS, example_curve

OUT = "/workspace/sfr-pattern/Imatest_SFR_pattern_ZWCAD.xlsx"

N_SAMP = 33
N_EDGE = 4
LAST_I = N_SAMP - 1  # 32
SAMPLE_FIRST = 2
SAMPLE_LAST = SAMPLE_FIRST + N_EDGE * N_SAMP - 1  # 133
CIRCLE_START = 12
DIST_FIRST = 2
DIST_LAST = DIST_FIRST + N_CURVE - 1  # 10001
COEF_NAMES = ("Coef1", "Coef3", "Coef5", "Coef7", "Coef9")
IMG_RANGE = f"'畸變座標'!$A${DIST_FIRST}:$A${DIST_LAST}"
ANG_RANGE = f"'畸變座標'!$B${DIST_FIRST}:$B${DIST_LAST}"

NAVY = "1F4E79"
TEAL = "0E6B6B"
GOLD = "FFF2CC"
INK = "1C2833"
MUTED = "F4F7FA"
WHITE = "FFFFFF"
ORANGE = "C65911"
BLUE = "1F4E79"
GREEN = "1E8449"
RED = "922B21"
AMBER = "B9770E"

thin = Border(
    left=Side(style="thin", color="D5D8DC"),
    right=Side(style="thin", color="D5D8DC"),
    top=Side(style="thin", color="D5D8DC"),
    bottom=Side(style="thin", color="D5D8DC"),
)
fill_in = PatternFill("solid", fgColor=GOLD)
fill_out = PatternFill("solid", fgColor=MUTED)
fill_navy = PatternFill("solid", fgColor=NAVY)
fill_teal = PatternFill("solid", fgColor=TEAL)
fill_white = PatternFill("solid", fgColor=WHITE)
font_in = Font(name="Microsoft JhengHei", size=11, color=INK)
font_label = Font(name="Microsoft JhengHei", size=11, color=INK)
font_head = Font(name="Microsoft JhengHei", size=12, bold=True, color=WHITE)
font_title = Font(name="Microsoft JhengHei", size=20, bold=True, color=NAVY)
font_small = Font(name="Microsoft JhengHei", size=9, color="566573")
font_section = Font(name="Microsoft JhengHei", size=12, bold=True, color=WHITE)
center = Alignment(vertical="center", wrap_text=True)
left_align = Alignment(vertical="center", wrap_text=True, horizontal="left")


def font(size=11, bold=False, color=INK, name="Microsoft JhengHei"):
    return Font(name=name, size=size, bold=bold, color=color)


def apply_input(cell, comment=None):
    cell.fill = fill_in
    cell.font = font_in
    cell.border = thin
    cell.alignment = center
    if comment:
        cell.comment = Comment(comment, "SFR")


def apply_output(cell, fmt=None):
    cell.fill = fill_out
    cell.font = font(bold=True)
    cell.border = thin
    cell.alignment = center
    if fmt:
        cell.number_format = fmt


def section(ws, row, text, cols=4):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=cols)
    cell = ws.cell(row, 1, text)
    cell.fill = fill_teal
    cell.font = font_section
    cell.alignment = Alignment(vertical="center", horizontal="left", indent=1)
    ws.row_dimensions[row].height = 22


def label(ws, row, text, unit, note=""):
    ws.cell(row, 1, text).font = font_label
    ws.cell(row, 1).alignment = left_align
    ws.cell(row, 3, unit).font = font_small
    ws.cell(row, 3).alignment = center
    if note:
        ws.cell(row, 4, note).font = font_small
        ws.cell(row, 4).alignment = left_align
    ws.row_dimensions[row].height = 20


def add_name(wb, name, ref):
    wb.defined_names.add(DefinedName(name=name, attr_text=ref))


def num(expr, digits=6):
    return f'SUBSTITUTE(FIXED({expr},{digits},TRUE),",",".")'


def sample_row(edge, i):
    return SAMPLE_FIRST + (edge - 1) * N_SAMP + i


def circle_row(edge, local):
    return CIRCLE_START + (edge - 1) * 13 + local


def tan_poly(u_expr):
    """Odd polynomial in u. u_expr is an Excel expression already in parentheses-safe form."""
    terms = []
    for name, power in zip(COEF_NAMES, POWERS):
        if power == 1:
            terms.append(f"{name}*({u_expr})")
        else:
            terms.append(f"{name}*({u_expr})^{power}")
    return "(" + "+".join(terms) + ")"


def point_line(x, y, x1, y1, x2, y2):
    return (
        f'IF(SQRT(({x2}-{x1})^2+({y2}-{y1})^2)<0.000000000001,0,'
        f'ABS(({x2}-{x1})*({y}-{y1})-({y2}-{y1})*({x}-{x1}))/'
        f'SQRT(({x2}-{x1})^2+({y2}-{y1})^2))'
    )


def pair(edge, i):
    row = sample_row(edge, i)
    return f'{num(f"取樣!J{row}*CadScale")}&","&{num(f"取樣!K{row}*CadScale")}'


def style_line(series, color, width_pt=1.75):
    series.graphicalProperties.line.solidFill = color
    series.graphicalProperties.line.width = int(width_pt * 12700)
    series.marker = Marker(symbol="none")
    series.smooth = False


def build():
    wb = Workbook()
    ws_p = wb.active
    ws_p.title = "參數"
    ws_rule = wb.create_sheet("規則")
    ws_view = wb.create_sheet("預覽")
    ws_xy = wb.create_sheet("座標")
    ws_scr = wb.create_sheet("指令")
    ws_s = wb.create_sheet("取樣")
    ws_f = wb.create_sheet("擬合")
    ws_dist = wb.create_sheet("畸變座標")
    ws_curve = wb.create_sheet("曲線_勿改")
    ws_help = wb.create_sheet("說明")

    build_distortion(ws_dist)
    build_curve(wb, ws_curve)
    build_params(wb, ws_p)
    build_samples(ws_s)
    build_fit(ws_f)
    build_rules(ws_rule)
    build_script(ws_scr)
    build_coords(ws_xy)
    build_preview(ws_view, ws_s)
    build_help(ws_help)

    ws_curve.sheet_state = "hidden"
    wb.calculation.calcMode = "auto"
    wb.calculation.fullCalcOnLoad = True
    wb.properties.title = "Imatest SFR pattern for ZWCAD"
    wb.properties.creator = "SFR pattern workbook"
    ws_p.sheet_view.showGridLines = False
    ws_rule.sheet_view.showGridLines = False
    ws_view.sheet_view.showGridLines = False
    ws_help.sheet_view.showGridLines = False
    ws_scr.sheet_view.showGridLines = False
    wb.active = ws_p
    wb.save(OUT)
    print(OUT)


def curve_mask():
    return f"(ISNUMBER({IMG_RANGE}))*(ISNUMBER({ANG_RANGE}))*({IMG_RANGE}>=0)"


def build_distortion(ws):
    ws.sheet_properties.tabColor = "7D6608"
    ws["A1"] = "半像高 mm"
    ws["B1"] = "半視場角 度"
    for col in (1, 2):
        ws.cell(1, col).font = font(bold=True, color=WHITE)
        ws.cell(1, col).fill = fill_navy
        ws.cell(1, col).alignment = center
    ws["A1"].comment = Comment(
        "從第 2 列貼上。半像高是主點到該視場的距離，單位公厘。0 是光軸。最多 10000 列，建議就用滿。",
        "SFR",
    )
    ws["B1"].comment = Comment(
        "對應的物方半視場角，單位度。與半像高一一對應，由小到大。桶形鏡頭同一像高的角度會比近軸更大。",
        "SFR",
    )
    heights, angles = example_curve()
    for i, (height, angle) in enumerate(zip(heights, angles)):
        row = DIST_FIRST + i
        cell_h = ws.cell(row, 1, height)
        cell_a = ws.cell(row, 2, angle)
        cell_h.number_format = "0.000000"
        cell_a.number_format = "0.000000"
        cell_h.fill = fill_in
        cell_a.fill = fill_in
        cell_h.font = font_in
        cell_a.font = font_in
    ws["D1"] = "這兩欄是畸變座標。範例 10000 點可整欄覆蓋成自己的量測。空白列會被略過。"
    ws["D1"].font = font_small
    ws.merge_cells("D1:H1")
    status = [
        (3, "點數", "=Npts", "0"),
        (4, "點數判定", '=IF(Npts<1000,"不符合",IF(Npts<10000,"警告","符合建議"))', None),
        (5, "最大半像高", "=Hscale", "0.000"),
        (6, "角度 RMSE", "=FitRmse", "0.000000"),
        (7, "近軸焦距", "=FocalUse", "0.000"),
        (8, "水平視場角", "=HFovOut", "0.000"),
        (9, "垂直視場角", "=VFovOut", "0.000"),
        (10, "對角視場角", "=DFovOut", "0.000"),
    ]
    ws["D2"] = "由這張表擬合出來"
    ws["D2"].font = font(bold=True, color=NAVY)
    for row, text, formula, fmt in status:
        ws.cell(row, 4, text).font = font_label
        cell = ws.cell(row, 5, formula)
        apply_output(cell, fmt)
    ws["F3"] = "列"
    ws["F5"] = "mm"
    ws["F6"] = "度"
    ws["F7"] = "mm"
    ws["F8"] = "度"
    ws["F9"] = "度"
    ws["F10"] = "度"
    for row in range(3, 11):
        ws.cell(row, 6).font = font_small
    ws.column_dimensions["A"].width = 18
    ws.column_dimensions["B"].width = 18
    ws.column_dimensions["C"].width = 3
    ws.column_dimensions["D"].width = 22
    ws.column_dimensions["E"].width = 16
    ws.column_dimensions["F"].width = 8
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:B{DIST_LAST}"
    ws.sheet_view.zoomScale = 110
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.sheet_properties.pageSetUpPr.fitToPage = True


def build_curve(wb, ws):
    """Normal equations of tan(θ) on u, u^3, …, u^9, solved by Gaussian elimination."""
    ws.sheet_properties.tabColor = "AEB6BF"
    add_name(wb, "ImgH", IMG_RANGE)
    add_name(wb, "HalfAng", ANG_RANGE)
    mask = curve_mask()
    ws["B2"] = f"=SUMPRODUCT({mask})"
    ws["B3"] = f"=IF(COUNT({IMG_RANGE})=0,0,MAX({IMG_RANGE}))"
    add_name(wb, "Npts", "'曲線_勿改'!$B$2")
    add_name(wb, "Hscale", "'曲線_勿改'!$B$3")

    exponents = []
    for i, pi in enumerate(POWERS):
        for pj in POWERS[i:]:
            total = pi + pj
            if total not in exponents:
                exponents.append(total)
    for index, exponent in enumerate(exponents):
        row = 2 + index
        ws.cell(row, 4, exponent)
        ws.cell(
            row,
            5,
            f'=IF(Hscale<=0,0,SUMPRODUCT({mask}*POWER({IMG_RANGE}/Hscale,{exponent})))',
        )
    for index, power in enumerate(POWERS):
        row = 2 + index
        ws.cell(row, 7, power)
        ws.cell(
            row,
            8,
            f'=IF(Hscale<=0,0,SUMPRODUCT({mask}*POWER({IMG_RANGE}/Hscale,{power})*TAN(RADIANS({ANG_RANGE}))))',
        )
    ws["I2"] = (
        f'=IF(Hscale<=0,0,SUMPRODUCT({mask}*TAN(RADIANS({ANG_RANGE}))*TAN(RADIANS({ANG_RANGE}))))'
    )

    def moment_ref(exponent):
        return f"E{2 + exponents.index(exponent)}"

    def rhs_ref(index):
        return f"H{2 + index}"

    def cell_ref(stage, i, j):
        return f"{get_column_letter(2 + j)}{14 + stage * 6 + i}"

    for i in range(5):
        for j in range(5):
            ws[cell_ref(0, i, j)] = f"={moment_ref(POWERS[i] + POWERS[j])}"
        ws[cell_ref(0, i, 5)] = f"={rhs_ref(i)}"

    for stage in range(1, 5):
        pivot = stage - 1
        for i in range(5):
            for j in range(6):
                prev_ij = cell_ref(stage - 1, i, j)
                if i <= pivot:
                    ws[cell_ref(stage, i, j)] = f"={prev_ij}"
                else:
                    prev_ik = cell_ref(stage - 1, i, pivot)
                    prev_kk = cell_ref(stage - 1, pivot, pivot)
                    prev_kj = cell_ref(stage - 1, pivot, j)
                    ws[cell_ref(stage, i, j)] = (
                        f'=IF(ABS({prev_kk})<0.000000000001,NA(),'
                        f'{prev_ij}-{prev_ik}/{prev_kk}*{prev_kj})'
                    )

    # Back-substitution into column J, rows 14..18, highest power first.
    for i in range(4, -1, -1):
        row = 14 + i
        diag = cell_ref(4, i, i)
        rhs = cell_ref(4, i, 5)
        if i == 4:
            expr = f"{rhs}/{diag}"
        else:
            sub = "+".join(f"{cell_ref(4, i, j)}*J{14 + j}" for j in range(i + 1, 5))
            expr = f"({rhs}-({sub}))/{diag}"
        ws.cell(row, 10, f'=IF(ABS({diag})<0.000000000001,NA(),{expr})')
        add_name(wb, COEF_NAMES[i], f"'曲線_勿改'!$J${row}")

    poly = "+".join(
        f"{name}*POWER({IMG_RANGE}/Hscale,{power})" if power > 1 else f"{name}*({IMG_RANGE}/Hscale)"
        for name, power in zip(COEF_NAMES, POWERS)
    )
    ws["B5"] = (
        f'=IF(OR(Npts<5,Hscale<=0),NA(),'
        f'SQRT(SUMPRODUCT({mask}*(DEGREES(ATAN({poly}))-{ANG_RANGE})^2)/Npts))'
    )
    add_name(wb, "FitRmse", "'曲線_勿改'!$B$5")
    ws["A2"] = "點數"
    ws["A3"] = "h_scale"
    ws["A5"] = "角度 RMSE"
    ws.sheet_view.zoomScale = 80


def chart_radius_factor(h_expr):
    """Excel expression for tan(θ) at image height h_expr."""
    return tan_poly(f"({h_expr})/Hscale")


def build_params(wb, ws):
    ws.sheet_properties.tabColor = NAVY
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    ws.freeze_panes = "A5"
    ws.row_dimensions[1].height = 28
    ws.row_dimensions[2].height = 36
    ws.merge_cells("A1:D1")
    ws["A1"] = "Imatest SFR 斜方塊邊線"
    ws["A1"].font = font_title
    ws.merge_cells("A2:D2")
    ws["A2"] = (
        "只畫邊線。黃底可改。水平視場角由 sensor 像素、像素尺寸和「畸變座標」的半像高–半視場角曲線算出。"
        "圖卡座標已按這條曲線預變形，給中望 CAD 的 LINE / ARC 用。"
    )
    ws["A2"].font = font_small
    ws["A2"].alignment = left_align

    ws.merge_cells("I1:K2")
    ws["I1"] = "=RuleAll"
    ws["I1"].font = font(size=22, bold=True, color=NAVY)
    ws["I1"].alignment = Alignment(horizontal="center", vertical="center")
    ws["I1"].fill = fill_out
    ws["L1"] = "規則總判"
    ws["L1"].font = font_small

    section(ws, 4, "一、Sensor 與拍攝位置")
    rows = [
        (5, "水平像素", "px", "Sensor 寬方向的有效像素。水平半像高 = 這個數 × 像素尺寸 / 2", "PixW", 4000, "0"),
        (6, "垂直像素", "px", "Sensor 高方向的有效像素", "PixH", 3000, "0"),
        (7, "像素尺寸", "μm", "正方像素邊長", "PixUm", 1.55, "0.000"),
        (8, "周邊視場位置", "0–1", "0 = 主點，1 = 下方所選基準的邊緣", "FieldPos", 0.7, "0.00"),
        (9, "視場方位角", "度", "0° 向右（+X），90° 向上（+Y），45° 為對角", "AzimuthDeg", 45, "0.00"),
        (11, "測試距離", "mm", "入瞳（節點）到圖卡平面。圖卡半徑 = 距離 × tan(半視場角)", "TestDist", 500, "0.00"),
        (12, "主點偏移 X", "px", "相對 sensor 中心，右為正", "PrinPx", 0, "0.00"),
        (13, "主點偏移 Y", "px", "相對 sensor 中心，上為正", "PrinPy", 0, "0.00"),
    ]
    for row, text, unit, note, name, value, fmt in rows:
        label(ws, row, text, unit, note)
        cell = ws.cell(row, 2, value)
        apply_input(cell)
        cell.number_format = fmt
        add_name(wb, name, f"'參數'!$B${row}")

    label(ws, 10, "視場 1.0 的基準", "", "對角 = 半對角；這是鏡頭規格裡的 1.0 視場")
    ws["B10"] = "對角"
    apply_input(ws["B10"], "1.0 視場的長度。對角是 sensor 半對角，最常用。")
    add_name(wb, "FieldRef", "'參數'!$B$10")

    section(ws, 15, "二、SFR 斜方塊（Imatest 斜邊）")
    label(ws, 16, "傾斜角", "度", "方塊相對水平軸。ISO 常用 5° 或 5.71°")
    ws["B16"] = 5
    apply_input(ws["B16"], "必須離開 0°、90° 和 45° 至少 2°。建議 3° 到 7°。5.71° = arctan(0.1)。")
    ws["B16"].number_format = "0.00"
    add_name(wb, "TiltDeg", "'參數'!$B$16")

    label(ws, 17, "目標邊長", "px", "這條邊在 sensor 上的直線長度，用來決定圖卡尺寸")
    ws["B17"] = 200
    apply_input(ws["B17"], "Imatest 建議沿邊約 80–300 px。預設 200。只決定邊線長度，不含填色。")
    ws["B17"].number_format = "0"
    add_name(wb, "EdgePx", "'參數'!$B$17")

    section(ws, 19, "三、鏡頭畸變座標")
    ws.merge_cells("A20:D21")
    ws["A20"] = (
        "不要在這裡填視場角或 k。到「畸變座標」貼上半像高（mm）對半視場角（度），至少超過 1000 點，建議 10000。"
        "範例已放 10000 點。曲線用 u = 半像高 / 表中最大半像高，擬合 tan(θ) = d1·u + d3·u³ + d5·u⁵ + d7·u⁷ + d9·u⁹。"
        "水平視場角 = 2 × 這條曲線在「水平半像高」處的角度。"
    )
    ws["A20"].alignment = Alignment(wrap_text=True, vertical="center")
    ws["A20"].font = font()
    ws.row_dimensions[20].height = 22
    ws.row_dimensions[21].height = 36

    section(ws, 23, "四、中望 CAD")
    label(ws, 24, "擬合公差", "mm", "取樣點到直線或圓弧的最大允許距離")
    ws["B24"] = 0.02
    apply_input(ws["B24"], "小於此值就用一條 LINE 或 ARC。超過就拆成更多 ARC，最後才用折線。")
    ws["B24"].number_format = "0.000"
    add_name(wb, "CadTol", "'參數'!$B$24")

    label(ws, 25, "座標縮放", "", "1 = 公厘。圖紙若用公尺，填 0.001")
    ws["B25"] = 1
    apply_input(ws["B25"])
    ws["B25"].number_format = "0.0000"
    add_name(wb, "CadScale", "'參數'!$B$25")

    h_center = "SQRT(CenterX^2+CenterY^2)"
    tan_center = chart_radius_factor(h_center)
    derived = [
        (5, "Sensor 寬", "SensW", "=PixW*PixUm/1000", "0.000", "mm"),
        (6, "Sensor 高", "SensH", "=PixH*PixUm/1000", "0.000", "mm"),
        (7, "畸變點數", "NptsOut", "=Npts", "0", "點"),
        (8, "曲線最大半像高", "HscaleOut", "=Hscale", "0.000", "mm"),
        (9, "近軸焦距", "FocalUse", '=IF(OR(Coef1<=0,Hscale<=0),NA(),Hscale/Coef1)', "0.000", "mm"),
        (10, "水平視場角", "HFovOut",
         f'=IF(OR(Hscale<=0,SensW<=0),NA(),IF({chart_radius_factor("SensW/2")}<=0,NA(),2*DEGREES(ATAN({chart_radius_factor("SensW/2")}))))',
         "0.000", "度"),
        (11, "垂直視場角", "VFovOut",
         f'=IF(OR(Hscale<=0,SensH<=0),NA(),IF({chart_radius_factor("SensH/2")}<=0,NA(),2*DEGREES(ATAN({chart_radius_factor("SensH/2")}))))',
         "0.000", "度"),
        (12, "對角視場角", "DFovOut",
         f'=IF(OR(Hscale<=0,HalfDiag<=0),NA(),IF({chart_radius_factor("HalfDiag")}<=0,NA(),2*DEGREES(ATAN({chart_radius_factor("HalfDiag")}))))',
         "0.000", "度"),
        (13, "曲線角度 RMSE", "FitRmseOut", "=FitRmse", "0.000000", "度"),
        (14, "半對角", "HalfDiag", "=SQRT((SensW/2)^2+(SensH/2)^2)", "0.000", "mm"),
        (15, "1.0 視場長度", "FieldR",
         '=IF(FieldRef="水平半寬",SensW/2,IF(FieldRef="垂直半高",SensH/2,HalfDiag))',
         "0.000", "mm"),
        (16, "主點 X", "PrinX", "=PrinPx*PixUm/1000", "0.000", "mm"),
        (17, "主點 Y", "PrinY", "=PrinPy*PixUm/1000", "0.000", "mm"),
        (18, "方塊中心 X", "CenterX", "=PrinX+FieldPos*FieldR*COS(RADIANS(AzimuthDeg))", "0.000", "mm"),
        (19, "方塊中心 Y", "CenterY", "=PrinY+FieldPos*FieldR*SIN(RADIANS(AzimuthDeg))", "0.000", "mm"),
        (20, "方塊邊長", "SideMm", "=EdgePx*PixUm/1000", "0.0000", "mm"),
        (21, "離水平/垂直", "BetaDeg",
         "=MIN(MOD(ABS(TiltDeg),90),90-MOD(ABS(TiltDeg),90))", "0.00", "度"),
        (23, "圖卡中心 X", "ChartCx",
         f'=IF(OR({h_center}<0.000000000001,Hscale<=0),0,TestDist*{tan_center}*CenterX/{h_center})',
         "0.000", "mm"),
        (24, "圖卡中心 Y", "ChartCy",
         f'=IF(OR({h_center}<0.000000000001,Hscale<=0),0,TestDist*{tan_center}*CenterY/{h_center})',
         "0.000", "mm"),
        (25, "未變形圖卡中心 X", "IdealCx", "=IF(FocalUse<=0,NA(),TestDist*CenterX/FocalUse)", "0.000", "mm"),
        (26, "未變形圖卡中心 Y", "IdealCy", "=IF(FocalUse<=0,NA(),TestDist*CenterY/FocalUse)", "0.000", "mm"),
        (27, "預變形最大位移", "MaxDisp", f"=MAX(取樣!Q{SAMPLE_FIRST}:Q{SAMPLE_LAST})", "0.000", "mm"),
        (28, "規則總判", "RuleCell", "=RuleAll", None, ""),
    ]
    # HalfDiag is used by DFovOut above it. Excel allows forward named-range refs. OK.
    ws["I4"] = "算出來的視場、位置與尺寸"
    ws["I4"].font = font(bold=True, color=NAVY)
    ws.merge_cells("I4:L4")
    for row, text, name, formula, fmt, unit in derived:
        ws.cell(row, 9, text).font = font_label
        ws.cell(row, 9).alignment = left_align
        cell = ws.cell(row, 10, formula)
        apply_output(cell, fmt)
        ws.cell(row, 11, unit).font = font_small
        if name not in ("NptsOut", "HscaleOut", "FitRmseOut", "RuleCell"):
            add_name(wb, name, f"'參數'!$J${row}")

    # Helpers used by the square. Kept named so the corner formulas stay readable.
    helpers = [
        (30, "cos(傾斜)", "CosT", "=COS(RADIANS(TiltDeg))", "0.000000"),
        (31, "sin(傾斜)", "SinT", "=SIN(RADIANS(TiltDeg))", "0.000000"),
        (32, "半邊長", "HalfSide", "=SideMm/2", "0.0000"),
        (33, "外接半寬", "AabbHalf", "=HalfSide*(ABS(CosT)+ABS(SinT))", "0.0000"),
        (34, "像素尺寸", "PixMm", "=PixUm/1000", "0.000000"),
        (35, "邊到畫面邊緣", "ClearPx",
         "=(MIN(SensW/2-ABS(CenterX)-AabbHalf,SensH/2-ABS(CenterY)-AabbHalf))/PixMm", "0.0"),
    ]
    for row, text, name, formula, fmt in helpers:
        ws.cell(row, 9, text).font = font_label
        cell = ws.cell(row, 10, formula)
        apply_output(cell, fmt)
        add_name(wb, name, f"'參數'!$J${row}")

    ws["I39"] = "Sensor 上的四個角（直的，尚未預變形）"
    ws["I39"].font = font(bold=True, color=NAVY)
    ws.merge_cells("I39:L39")
    locals_ = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
    ws["I40"] = "角"
    ws["J40"] = "X mm"
    ws["K40"] = "Y mm"
    for col in range(9, 12):
        ws.cell(40, col).font = font(bold=True, size=9)
    for i, (sx, sy) in enumerate(locals_):
        row = 41 + i
        ws.cell(row, 9, i + 1).font = font()
        xsign = f"({sx}*HalfSide)"
        ysign = f"({sy}*HalfSide)"
        ws.cell(row, 10, f"=CenterX+{xsign}*CosT-{ysign}*SinT")
        ws.cell(row, 11, f"=CenterY+{xsign}*SinT+{ysign}*CosT")
        apply_output(ws.cell(row, 10), "0.000000")
        apply_output(ws.cell(row, 11), "0.000000")
    add_name(wb, "CornX", "'參數'!$J$41:$J$44")
    add_name(wb, "CornY", "'參數'!$K$41:$K$44")

    ws["I46"] = "ISO 另一個常用角 arctan(0.1)"
    ws["J46"] = "=DEGREES(ATAN(0.1))"
    apply_output(ws["J46"], "0.00")
    ws["K46"] = "度"
    ws["K46"].font = font_small

    ws["I48"] = "此方位建議最大視場"
    limx = "(SensW/2-AabbHalf)"
    limy = "(SensH/2-AabbHalf)"
    rx = "(FieldR*COS(RADIANS(AzimuthDeg)))"
    ry = "(FieldR*SIN(RADIANS(AzimuthDeg)))"
    tx = (
        f'IF(ABS({rx})<0.000000000001,IF(ABS(PrinX)<={limx},1,-1),'
        f'IF({rx}>0,({limx}-PrinX)/{rx},(-{limx}-PrinX)/{rx}))'
    )
    ty = (
        f'IF(ABS({ry})<0.000000000001,IF(ABS(PrinY)<={limy},1,-1),'
        f'IF({ry}>0,({limy}-PrinY)/{ry},(-{limy}-PrinY)/{ry}))'
    )
    ws["J48"] = f"=MAX(0,MIN(1,{tx},{ty}))"
    apply_output(ws["J48"], "0.000")
    add_name(wb, "FieldMax", "'參數'!$J$48")
    ws["K48"] = "0–1"
    ws["K48"].font = font_small

    ws["I50"] = "四邊 CAD 模式"
    ws["J50"] = '=擬合!B2&" / "&擬合!B3&" / "&擬合!B4&" / "&擬合!B5'
    apply_output(ws["J50"])

    ws["I52"] = "tan(θ) 的奇次係數，u = 半像高 / 最大半像高"
    ws["I52"].font = font(bold=True, color=NAVY)
    ws.merge_cells("I52:L52")
    for index, name in enumerate(COEF_NAMES):
        row = 53 + index
        power = POWERS[index]
        ws.cell(row, 9, f"d{power}").font = font_label
        ws.cell(row, 10, f"={name}")
        apply_output(ws.cell(row, 10), "0.000000")

    ws["I59"] = "中心像素（左下為原點，Y 向上）"
    ws["J59"] = "=CenterX/PixMm+PixW/2"
    ws["K59"] = "=CenterY/PixMm+PixH/2"
    apply_output(ws["J59"], "0.0")
    apply_output(ws["K59"], "0.0")
    ws["L59"] = "X , Y"
    ws["L59"].font = font_small
    ws["I60"] = "中心影像列（上為 0）"
    ws["J60"] = "=PixH-K59"
    apply_output(ws["J60"], "0.0")

    dv_ref = DataValidation(type="list", formula1='"對角,水平半寬,垂直半高"', allow_blank=False)
    dv_field = DataValidation(type="decimal", operator="between", formula1="0", formula2="1", allow_blank=False)
    dv_field.error = "視場要在 0 到 1"
    dv_field.errorTitle = "視場"
    dv_ref.add(ws["B10"])
    dv_field.add(ws["B8"])
    ws.add_data_validation(dv_ref)
    ws.add_data_validation(dv_field)

    ws.conditional_formatting.add("I1:K2", CellIsRule(operator="equal", formula=['"通過"'], fill=PatternFill("solid", fgColor="D5F5E3"), font=font(size=22, bold=True, color=GREEN)))
    ws.conditional_formatting.add("I1:K2", CellIsRule(operator="equal", formula=['"有警告"'], fill=PatternFill("solid", fgColor="FDEBD0"), font=font(size=22, bold=True, color=AMBER)))
    ws.conditional_formatting.add("I1:K2", CellIsRule(operator="equal", formula=['"不符合"'], fill=PatternFill("solid", fgColor="FADBD8"), font=font(size=22, bold=True, color=RED)))

    widths = {"A": 24, "B": 22, "C": 14, "D": 62, "E": 3, "F": 3, "G": 3, "H": 3, "I": 28, "J": 18, "K": 16, "L": 16}
    for col, width in widths.items():
        ws.column_dimensions[col].width = width
    ws.sheet_view.zoomScale = 110
    ws.oddHeader.left.text = "Imatest SFR pattern"
    ws.print_title_rows = "1:2"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.sheet_properties.pageSetUpPr.fitToPage = True


def build_samples(ws):
    ws.sheet_properties.tabColor = "5D6D7E"
    headers = [
        "邊", "點", "t", "sensor X mm", "sensor Y mm", "像高 h mm", "u", "tanθ", "θ 度",
        "圖卡 X mm", "圖卡 Y mm", "未變形 X", "未變形 Y", "", "", "",
        "預變形位移 mm", "整邊弦高", "單弧誤差", "四段弧誤差",
        "八段弧誤差", "四段弦高", "八段弦高", "折線拱高估計",
    ]
    for c, h in enumerate(headers, 1):
        cell = ws.cell(1, c, h)
        cell.font = font(bold=True, size=9, color=WHITE)
        cell.fill = fill_navy
        cell.alignment = center
    ws.auto_filter.ref = f"A1:X{SAMPLE_LAST}"
    ws.freeze_panes = "A2"
    for edge in range(1, N_EDGE + 1):
        row0 = sample_row(edge, 0)
        row1 = sample_row(edge, LAST_I)
        for i in range(N_SAMP):
            row = sample_row(edge, i)
            ws.cell(row, 1, edge)
            ws.cell(row, 2, i)
            ws.cell(row, 3, f"=B{row}/{LAST_I}")
            ws.cell(row, 4, f"=INDEX(CornX,A{row})*(1-C{row})+INDEX(CornX,MOD(A{row},4)+1)*C{row}")
            ws.cell(row, 5, f"=INDEX(CornY,A{row})*(1-C{row})+INDEX(CornY,MOD(A{row},4)+1)*C{row}")
            ws.cell(row, 6, f"=SQRT(D{row}^2+E{row}^2)")
            ws.cell(row, 7, f"=IF(Hscale<=0,NA(),F{row}/Hscale)")
            ws.cell(row, 8, f"={tan_poly(f'G{row}')}")
            ws.cell(row, 9, f"=IF(H{row}<=0,NA(),DEGREES(ATAN(H{row})))")
            ws.cell(row, 10, f"=IF(F{row}<0.000000000001,0,TestDist*H{row}*D{row}/F{row})")
            ws.cell(row, 11, f"=IF(F{row}<0.000000000001,0,TestDist*H{row}*E{row}/F{row})")
            ws.cell(row, 12, f"=IF(OR(NOT(ISNUMBER(FocalUse)),FocalUse<=0),NA(),TestDist*D{row}/FocalUse)")
            ws.cell(row, 13, f"=IF(OR(NOT(ISNUMBER(FocalUse)),FocalUse<=0),NA(),TestDist*E{row}/FocalUse)")
            ws.cell(row, 17, f"=SQRT((J{row}-L{row})^2+(K{row}-M{row})^2)")
            # deviations in chart mm
            x, y = f"J{row}", f"K{row}"
            x1, y1 = f"$J${row0}", f"$K${row0}"
            x2, y2 = f"$J${row1}", f"$K${row1}"
            ws.cell(row, 18, f"={point_line(x, y, x1, y1, x2, y2)}")
            # arc1 circle row local 0
            cr1 = circle_row(edge, 0)
            ws.cell(row, 19, arc_dist_formula(row, cr1, f"R{row}"))
            sub4 = min(3, i // 8)
            cr4 = circle_row(edge, 1 + sub4)
            i0 = sub4 * 8
            i1 = i0 + 8
            c4 = point_line(x, y, f"$J${sample_row(edge, i0)}", f"$K${sample_row(edge, i0)}",
                            f"$J${sample_row(edge, i1)}", f"$K${sample_row(edge, i1)}")
            ws.cell(row, 22, f"={c4}")
            ws.cell(row, 20, arc_dist_formula(row, cr4, f"V{row}"))
            sub8 = min(7, i // 4)
            cr8 = circle_row(edge, 5 + sub8)
            j0 = sub8 * 4
            j1 = j0 + 4
            c8 = point_line(x, y, f"$J${sample_row(edge, j0)}", f"$K${sample_row(edge, j0)}",
                            f"$J${sample_row(edge, j1)}", f"$K${sample_row(edge, j1)}")
            ws.cell(row, 23, f"={c8}")
            ws.cell(row, 21, arc_dist_formula(row, cr8, f"W{row}"))
            if 1 <= i <= LAST_I - 1:
                sag = point_line(
                    x, y,
                    f"J{sample_row(edge, i - 1)}", f"K{sample_row(edge, i - 1)}",
                    f"J{sample_row(edge, i + 1)}", f"K{sample_row(edge, i + 1)}",
                )
                ws.cell(row, 24, f"=({sag})/4")
            else:
                ws.cell(row, 24, 0)
    for col in range(1, 25):
        ws.column_dimensions[get_column_letter(col)].width = 14
    ws.column_dimensions["A"].width = 6
    ws.column_dimensions["B"].width = 6
    ws.sheet_view.zoomScale = 90


def arc_dist_formula(sample, circle, chord_expr):
    # circle columns: N Ux, O Uy, P R, Q colinear. See build_fit.
    return (
        f'=IF(擬合!Q{circle}=1,{chord_expr},'
        f'ABS(SQRT((J{sample}-擬合!N{circle})^2+(K{sample}-擬合!O{circle})^2)-擬合!P{circle}))'
    )


def build_fit(ws):
    ws.sheet_properties.tabColor = "5D6D7E"
    headers = ["邊", "CAD模式", "方向", "影像角度", "整邊弦高 mm", "單弧誤差 mm", "四段可擬合", "八段可擬合", "折線拱高估計 mm"]
    for c, h in enumerate(headers, 1):
        cell = ws.cell(1, c, h)
        cell.font = font(bold=True, size=9, color=WHITE)
        cell.fill = fill_navy
        cell.alignment = center
    # Circle table header
    circle_headers = [
        "邊", "族", "段", "i0", "i1", "i2", "Ax", "Ay", "Bx", "By", "Cx", "Cy",
        "D", "Ux", "Uy", "R", "共線", "弦高", "弧誤差", "用ARC", "此段合格",
    ]
    for c, h in enumerate(circle_headers, 1):
        cell = ws.cell(CIRCLE_START - 1, c, h)
        cell.font = font(bold=True, size=8, color=WHITE)
        cell.fill = PatternFill("solid", fgColor="1A5276")
    for edge in range(1, 5):
        blocks = [("1", 0, 0, 16, 32)]
        for s in range(4):
            blocks.append(("4", s, s * 8, s * 8 + 4, s * 8 + 8))
        for s in range(8):
            blocks.append(("8", s, s * 4, s * 4 + 2, s * 4 + 4))
        assert len(blocks) == 13
        for local, (family, sub, i0, i1, i2) in enumerate(blocks):
            row = circle_row(edge, local)
            r0 = sample_row(edge, i0)
            r1 = sample_row(edge, i1)
            r2 = sample_row(edge, i2)
            ws.cell(row, 1, edge)
            ws.cell(row, 2, family)
            ws.cell(row, 3, sub)
            ws.cell(row, 4, i0)
            ws.cell(row, 5, i1)
            ws.cell(row, 6, i2)
            ws.cell(row, 7, f"=取樣!J{r0}")
            ws.cell(row, 8, f"=取樣!K{r0}")
            ws.cell(row, 9, f"=取樣!J{r1}")
            ws.cell(row, 10, f"=取樣!K{r1}")
            ws.cell(row, 11, f"=取樣!J{r2}")
            ws.cell(row, 12, f"=取樣!K{r2}")
            ws.cell(row, 13, f"=2*(G{row}*(J{row}-L{row})+I{row}*(L{row}-H{row})+K{row}*(H{row}-J{row}))")
            ws.cell(
                row, 14,
                f'=IF(ABS(M{row})<0.000000001,G{row},((G{row}^2+H{row}^2)*(J{row}-L{row})+(I{row}^2+J{row}^2)*(L{row}-H{row})+(K{row}^2+L{row}^2)*(H{row}-J{row}))/M{row})',
            )
            ws.cell(
                row, 15,
                f'=IF(ABS(M{row})<0.000000001,H{row},((G{row}^2+H{row}^2)*(K{row}-I{row})+(I{row}^2+J{row}^2)*(G{row}-K{row})+(K{row}^2+L{row}^2)*(I{row}-G{row}))/M{row})',
            )
            ws.cell(row, 16, f'=IF(ABS(M{row})<0.000000001,10^99,SQRT((G{row}-N{row})^2+(H{row}-O{row})^2))')
            ws.cell(row, 17, f'=IF(OR(ABS(M{row})<0.000000001,P{row}>1000000),1,0)')
            # chord / arc max over the piece samples
            if family == "1":
                a, b = sample_row(edge, 0), sample_row(edge, 32)
                ws.cell(row, 18, f"=MAX(取樣!R{a}:R{b})")
                ws.cell(row, 19, f"=MAX(取樣!S{a}:S{b})")
            elif family == "4":
                a, b = sample_row(edge, i0), sample_row(edge, i2)
                ws.cell(row, 18, f"=MAX(取樣!V{a}:V{b})")
                ws.cell(row, 19, f"=MAX(取樣!T{a}:T{b})")
            else:
                a, b = sample_row(edge, i0), sample_row(edge, i2)
                ws.cell(row, 18, f"=MAX(取樣!W{a}:W{b})")
                ws.cell(row, 19, f"=MAX(取樣!U{a}:U{b})")
            ws.cell(row, 20, f'=IF(AND(Q{row}=0,S{row}<=CadTol),1,0)')
            ws.cell(row, 21, f'=IF(OR(R{row}<=CadTol,T{row}=1),1,0)')
        # summary row 2..5
        srow = 1 + edge
        fam1 = circle_row(edge, 0)
        arc4_rows = [circle_row(edge, 1 + s) for s in range(4)]
        arc8_rows = [circle_row(edge, 5 + s) for s in range(8)]
        arc4_ok = ",".join(f"U{r}=1" for r in arc4_rows)
        arc8_ok = ",".join(f"U{r}=1" for r in arc8_rows)
        p0 = sample_row(edge, 0)
        p1 = sample_row(edge, 32)
        ws.cell(srow, 1, edge)
        ws.cell(
            srow, 2,
            f'=IF(R{fam1}<=CadTol,"LINE",IF(T{fam1}=1,"ARC",IF(AND({arc4_ok}),"ARC4",IF(AND({arc8_ok}),"ARC8","POLY"))))',
        )
        ws.cell(srow, 4, f"=DEGREES(ATAN2(取樣!D{p1}-取樣!D{p0},取樣!E{p1}-取樣!E{p0}))")
        ws.cell(
            srow, 3,
            f'=IF(ABS(MOD(D{srow}+360,180)-90)<45,"near-vertical","near-horizontal")',
        )
        ws.cell(srow, 5, f"=R{fam1}")
        ws.cell(srow, 6, f"=S{fam1}")
        ws.cell(srow, 7, f'=IF(AND({arc4_ok}),"是","否")')
        ws.cell(srow, 8, f'=IF(AND({arc8_ok}),"是","否")')
        ws.cell(srow, 9, f"=MAX(取樣!X{p0}:X{p1})")
        for col in range(1, 10):
            ws.cell(srow, col).font = font()
            ws.cell(srow, col).border = thin
            ws.cell(srow, col).fill = fill_out
        ws.cell(srow, 4).number_format = "0.00"
        for col in (5, 6, 9):
            ws.cell(srow, col).number_format = "0.0000"
    ws.column_dimensions["A"].width = 8
    ws.column_dimensions["B"].width = 14
    ws.column_dimensions["C"].width = 18
    for col in range(4, 22):
        ws.column_dimensions[get_column_letter(col)].width = 14
    ws.freeze_panes = "A2"
    ws.sheet_view.zoomScale = 100


def build_rules(ws):
    ws.sheet_properties.tabColor = "0E6B6B"
    ws.merge_cells("A1:E1")
    ws["A1"] = "Imatest SFR 斜邊規則"
    ws["A1"].font = font_title
    ws.merge_cells("A2:E2")
    ws["A2"] = "只檢查邊線本身：角度、長度、是否在畫面裡。不檢查亮暗或對比。"
    ws["A2"].font = font_small
    ws["A2"].alignment = left_align
    ws["G1"] = "總結果"
    ws["G1"].font = font_small
    ws.merge_cells("H1:I2")
    ws["H1"] = "=RuleAll"
    ws["H1"].font = font(size=22, bold=True, color=NAVY)
    ws["H1"].alignment = Alignment(horizontal="center", vertical="center")
    ws["H1"].fill = fill_out

    headers = ["項目", "數值", "判定", "Imatest / ISO 依據"]
    for c, h in enumerate(headers, 1):
        cell = ws.cell(4, c, h)
        cell.font = font(bold=True, color=WHITE)
        cell.fill = fill_navy
        cell.alignment = center
    ws.row_dimensions[4].height = 22

    # Each check: row, name, value formula, judgement formula, basis
    checks = [
        (5, "像素與像素尺寸",
         '=PixW&" × "&PixH&" px，"&TEXT(PixUm,"0.000")&" μm"',
         '=IF(AND(PixW>=100,PixH>=100,PixUm>0),"符合","不符合")',
         "需要知道 sensor 的實際寬高，邊長才換得成公厘。"),
        (6, "測試距離",
         '=TEXT(TestDist,"0.00")&" mm，近軸焦距 "&TEXT(FocalUse,"0.000")&" mm"',
         '=IF(AND(ISNUMBER(TestDist),TestDist>0,ISNUMBER(FocalUse),FocalUse>0),"符合","不符合")',
         "測試距離是入瞳到圖卡。圖卡半徑 = 距離 × tan(半視場角)。近軸焦距由畸變曲線在光軸附近的斜率算出。"),
        (7, "視場位置",
         '=TEXT(FieldPos,"0.00")&" @ "&TEXT(AzimuthDeg,"0.0")&"°，基準 "&FieldRef',
         '=IF(AND(FieldPos>=0,FieldPos<=1),"符合","不符合")',
         "0 在主點，1 在所選基準的邊緣。對角 1.0 是四個角落。"),
        (8, "傾斜角離開 0° / 90° / 45°",
         '=TEXT(TiltDeg,"0.00")&"°，離水平或垂直 "&TEXT(BetaDeg,"0.00")&"°"',
         '=IF(OR(BetaDeg<2,BetaDeg>43),"不符合","符合")',
         "Imatest：邊要離開最近的水平、垂直或 45° 超過約 2°，否則相位敏感、結果不穩。"),
        (9, "傾斜角建議範圍",
         '=TEXT(BetaDeg,"0.00")&"°（ISO 5° 或 "&TEXT(DEGREES(ATAN(0.1)),"0.00")&"°）"',
         '=IF(OR(BetaDeg<2,BetaDeg>43),"不符合",IF(AND(BetaDeg>=3,BetaDeg<=7),"符合建議","警告"))',
         "3°–7° 最好。超過約 8° 時 MTF 要做 cos 修正，Imatest 會自己除以 cos。太大也會吃掉 ROI。"),
        (10, "Sensor 上的邊長",
         '=TEXT(EdgePx,"0")&" px（"&TEXT(SideMm,"0.000")&" mm）"',
         '=IF(OR(EdgePx<10,EdgePx>2000),"不符合",IF(OR(EdgePx<80,EdgePx>500),"警告",IF(EdgePx<=300,"符合建議","符合")))',
         "沿邊建議 80–500 px，80–300 最有用。短於 10 或長於 2000 不適合 SFR。"),
        (11, "邊線可用長度",
         '=TEXT(0.7*EdgePx*COS(RADIANS(BetaDeg)),"0.0")&" px"',
         '=IF(0.7*EdgePx*COS(RADIANS(BetaDeg))>=100,"符合",IF(0.7*EdgePx*COS(RADIANS(BetaDeg))>=80,"符合",IF(0.7*EdgePx*COS(RADIANS(BetaDeg))>=40,"警告","不符合")))',
         "斜邊兩端是方塊角落，分析時用不到。可用長度約為邊長的 70%，建議仍有 80 px 以上。"),
        (12, "邊線在 sensor 內",
         '=TEXT(ClearPx,"0.0")&" px（此方位最大視場 "&TEXT(FieldMax,"0.00")&"）"',
         '=IF(ClearPx<0,"不符合","符合")',
         "四條邊的外接矩形要落在 sensor 裡面，否則這條邊拍不到。"),
        (13, "畸變座標點數",
         '=TEXT(Npts,"0")&" 點"',
         '=IF(Npts<1000,"不符合",IF(Npts<10000,"警告","符合建議"))',
         "半像高對半視場角至少要超過 1000 點。建議貼到 10000 點，曲線才穩。"),
        (14, "曲線蓋得住 sensor",
         '=TEXT(Hscale,"0.000")&" mm，半對角 "&TEXT(HalfDiag,"0.000")&" mm"',
         '=IF(AND(ISNUMBER(Hscale),Hscale+0.000000001>=HalfDiag,Hscale+0.000000001>=MAX(取樣!F2:F133)),"符合","不符合")',
         "表中最大半像高要蓋過 sensor 半對角，也要蓋過這顆方塊。否則視場角和角落都是外推。"),
        (15, "曲線擬合殘差",
         '=TEXT(FitRmse,"0.000000")&" °"',
         '=IF(NOT(ISNUMBER(FitRmse)),"不符合",IF(FitRmse<=0.01,"符合",IF(FitRmse<=0.05,"警告","不符合")))',
         "tan(θ) 對 u 的 1、3、5、7、9 次擬合，再換回角度。RMSE 超過 0.05° 就不要用這條曲線畫邊。"),
        (16, "水平視場角",
         '=TEXT(HFovOut,"0.000")&" °（垂直 "&TEXT(VFovOut,"0.000")&"°，對角 "&TEXT(DFovOut,"0.000")&"°）"',
         '=IF(AND(ISNUMBER(HFovOut),HFovOut>0,HFovOut<180,ISNUMBER(VFovOut),ISNUMBER(DFovOut)),"符合","不符合")',
         "水平視場角 = 2 × 曲線在水平半像高處的角度。水平半像高 = 水平像素 × 像素尺寸 / 2。"),
        (17, "圖卡座標是有限數",
         '=TEXT(TestDist,"0.00")&" mm"',
         '=IF(AND(ISNUMBER(ChartCx),ISNUMBER(ChartCy),COUNT(取樣!J2:J133)=132,COUNT(取樣!K2:K133)=132),"符合","不符合")',
         "半視場角的正切要是有限正數，圖卡座標才畫得出來。"),
        (18, "折線剩餘拱高",
         '=TEXT(MAX(擬合!I2:I5),"0.0000")&" mm"',
         '=IF(COUNTIF(擬合!B2:B5,"POLY")=0,"符合",IF(MAX(擬合!I2:I5)<=CadTol,"符合","警告"))',
         "能用 LINE 或 ARC 就不用折線。真的用折線時，相鄰取樣點之間的估計拱高應小於公差。"),
    ]
    for row, item, value, judge, basis in checks:
        ws.cell(row, 1, item).font = font()
        ws.cell(row, 1).alignment = left_align
        ws.cell(row, 2, value).font = font()
        ws.cell(row, 2).alignment = left_align
        ws.cell(row, 3, judge).font = font(bold=True)
        ws.cell(row, 3).alignment = center
        ws.cell(row, 4, basis).font = font_small
        ws.cell(row, 4).alignment = left_align
        for col in range(1, 5):
            ws.cell(row, col).border = thin
            ws.cell(row, col).fill = fill_white
        ws.row_dimensions[row].height = 36

    ws["G4"] = "不符合"
    ws["H4"] = '=COUNTIF(C5:C18,"不符合")'
    ws["G5"] = "警告"
    ws["H5"] = '=COUNTIF(C5:C18,"警告")'
    ws["G6"] = "總結果"
    ws["H6"] = '=IF(H4>0,"不符合",IF(H5>0,"有警告","通過"))'
    add_name(ws.parent, "RuleAll", "'規則'!$H$6")
    for row in range(4, 7):
        ws.cell(row, 7).font = font_small
        apply_output(ws.cell(row, 8))

    ws.conditional_formatting.add("C5:C18", CellIsRule(operator="equal", formula=['"不符合"'], fill=PatternFill("solid", fgColor="FADBD8"), font=font(bold=True, color=RED)))
    ws.conditional_formatting.add("C5:C18", CellIsRule(operator="equal", formula=['"警告"'], fill=PatternFill("solid", fgColor="FDEBD0"), font=font(bold=True, color=AMBER)))
    ws.conditional_formatting.add("C5:C18", FormulaRule(formula=['LEFT(C5,2)="符合"'], fill=PatternFill("solid", fgColor="D5F5E3"), font=font(bold=True, color=GREEN)))
    ws.conditional_formatting.add("H1:I2", CellIsRule(operator="equal", formula=['"通過"'], fill=PatternFill("solid", fgColor="D5F5E3"), font=font(size=22, bold=True, color=GREEN)))
    ws.conditional_formatting.add("H1:I2", CellIsRule(operator="equal", formula=['"有警告"'], fill=PatternFill("solid", fgColor="FDEBD0"), font=font(size=22, bold=True, color=AMBER)))
    ws.conditional_formatting.add("H1:I2", CellIsRule(operator="equal", formula=['"不符合"'], fill=PatternFill("solid", fgColor="FADBD8"), font=font(size=22, bold=True, color=RED)))

    ws.merge_cells("A19:D21")
    ws["A19"] = (
        "方塊四邊就是 SFR 的斜邊：兩條接近垂直、兩條接近水平，和 SFRplus / eSFR 的斜方塊相同。"
        "傾斜 5° 時，四邊都會離開水平、垂直和 45°。"
        "預變形只發生在圖卡上：半徑 = 測試距離 × tan(θ)，θ 由半像高對半視場角的曲線讀出。"
        "拍進 sensor 之後，這四邊應是直的，角度就是你填的傾斜角。"
    )
    ws["A19"].alignment = Alignment(wrap_text=True, vertical="top")
    ws["A19"].font = font()
    ws.row_dimensions[19].height = 22
    ws.row_dimensions[20].height = 22
    ws.row_dimensions[21].height = 22

    ws.column_dimensions["A"].width = 32
    ws.column_dimensions["B"].width = 62
    ws.column_dimensions["C"].width = 14
    ws.column_dimensions["D"].width = 88
    ws.column_dimensions["G"].width = 12
    ws.column_dimensions["H"].width = 16
    ws.freeze_panes = "A5"
    ws.sheet_view.zoomScale = 110
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.print_options.horizontalCentered = True
    ws.page_setup.horizontalCentered = True
    ws.sheet_properties.pageSetUpPr.fitToPage = True


def build_script(ws):
    ws.sheet_properties.tabColor = ORANGE
    ws.merge_cells("A1:A1")
    ws["A1"] = "中望 CAD 指令"
    ws["A1"].font = font_title
    ws.merge_cells("A2:A8")
    ws["A2"] = (
        "1. 點選右邊儲存格，複製全部文字。\n"
        "2. 貼到純文字檔，存成 sfr_pattern.scr。\n"
        "3. 中望 CAD 指令列輸入 SCRIPT，選這個檔。\n"
        "4. _.LINE 與 _.ARC 在中文介面也是英文指令，不用改成「直線」。\n"
        "5. 原點是光軸打在圖卡上的位置，+X 向右，+Y 向上，預設單位公厘。\n"
        "6. LINE 後面的空白行是故意的，用來結束畫線。不要刪。\n"
        "7. 改了黃底參數後，這個儲存格會重算，請重新複製。\n"
        "8. 指令用 & 串接，Excel 2016 以前也能算。"
    )
    ws["A2"].alignment = Alignment(wrap_text=True, vertical="top")
    ws["A2"].font = font(size=11)
    ws.column_dimensions["A"].width = 46
    ws.column_dimensions["B"].width = 110
    ws.row_dimensions[2].height = 36

    # Blocks live in column AA (27), stacked. Record ranges.
    col = 27
    row = 1
    header_rows = []
    static_header = [
        "; Imatest SFR slanted-square edges for ZWCAD",
        "; _.LINE and _.ARC use English command names in Chinese ZWCAD",
        "; origin = optical axis on the chart, +X right, +Y up",
        "; square is straight on the sensor; coordinates below are pre-distorted",
    ]
    for text in static_header:
        ws.cell(row, col, text)
        header_rows.append(row)
        row += 1
    dynamic = [
        f'="; tilt_deg="&{num("TiltDeg",4)}&" field="&{num("FieldPos",4)}&" azimuth_deg="&{num("AzimuthDeg",2)}',
        f'="; hfov_deg="&{num("HFovOut",4)}&" vfov_deg="&{num("VFovOut",4)}&" dfov_deg="&{num("DFovOut",4)}',
        f'="; paraxial_f_mm="&{num("FocalUse",4)}&" distance_mm="&{num("TestDist",2)}&" edge_px="&{num("EdgePx",2)}',
        f'="; distortion_points="&{num("Npts",0)}&" h_scale_mm="&{num("Hscale",4)}&" fit_rmse_deg="&{num("FitRmse",6)}',
        f'="; scale="&{num("CadScale",6)}&" tolerance_mm="&{num("CadTol",4)}',
    ]
    for formula in dynamic:
        ws.cell(row, col, formula)
        header_rows.append(row)
        row += 1
    header_range = (header_rows[0], header_rows[-1])

    def emit(value):
        nonlocal row
        ws.cell(row, col, value)
        row += 1
        return row - 1

    edge_ranges = {}
    for edge in range(1, 5):
        srow = 1 + edge
        comment = f'="; edge "&{edge}&" "&擬合!C{srow}&" image_angle_deg "&{num(f"擬合!D{srow}",2)}'
        # LINE block
        r1 = row
        emit(comment)
        emit("_.LINE")
        emit(f"={pair(edge, 0)}")
        emit(f"={pair(edge, LAST_I)}")
        emit('=""')
        line_range = (r1, row - 1)
        # ARC block
        r1 = row
        emit(comment)
        emit("_.ARC")
        emit(f"={pair(edge, 0)}")
        emit(f"={pair(edge, 16)}")
        emit(f"={pair(edge, LAST_I)}")
        arc_range = (r1, row - 1)
        # ARC4
        r1 = row
        emit(comment)
        for s in range(4):
            cr = circle_row(edge, 1 + s)
            i0, i1, i2 = s * 8, s * 8 + 4, s * 8 + 8
            emit(f'=IF(擬合!T{cr}=1,"_.ARC","_.LINE")')
            emit(f"={pair(edge, i0)}")
            emit(f'=IF(擬合!T{cr}=1,{pair(edge, i1)},{pair(edge, i2)})')
            emit(f'=IF(擬合!T{cr}=1,{pair(edge, i2)},"")')
        arc4_range = (r1, row - 1)
        # ARC8
        r1 = row
        emit(comment)
        for s in range(8):
            cr = circle_row(edge, 5 + s)
            i0, i1, i2 = s * 4, s * 4 + 2, s * 4 + 4
            emit(f'=IF(擬合!T{cr}=1,"_.ARC","_.LINE")')
            emit(f"={pair(edge, i0)}")
            emit(f'=IF(擬合!T{cr}=1,{pair(edge, i1)},{pair(edge, i2)})')
            emit(f'=IF(擬合!T{cr}=1,{pair(edge, i2)},"")')
        arc8_range = (r1, row - 1)
        # POLY
        r1 = row
        emit(comment)
        for i in range(LAST_I):
            emit("_.LINE")
            emit(f"={pair(edge, i)}")
            emit(f"={pair(edge, i + 1)}")
            emit('=""')
        poly_range = (r1, row - 1)
        edge_ranges[edge] = {
            "LINE": line_range,
            "ARC": arc_range,
            "ARC4": arc4_range,
            "ARC8": arc8_range,
            "POLY": poly_range,
        }

    # Excel 2016 and earlier have no TEXTJOIN. Each block is joined with &.
    join_col = col + 1

    def join_range(a, b):
        ws.cell(a, join_col, f"=AA{a}")
        for r in range(a + 1, b + 1):
            ws.cell(r, join_col, f"=AB{r - 1}&CHAR(10)&AA{r}")
        return f"AB{b}"

    parts = [join_range(*header_range)]
    for edge in range(1, 5):
        ranges = edge_ranges[edge]
        mode = f"擬合!B{1+edge}"
        choice = (
            f'IF({mode}="LINE",{join_range(*ranges["LINE"])},'
            f'IF({mode}="ARC",{join_range(*ranges["ARC"])},'
            f'IF({mode}="ARC4",{join_range(*ranges["ARC4"])},'
            f'IF({mode}="ARC8",{join_range(*ranges["ARC8"])},'
            f'{join_range(*ranges["POLY"])}))))'
        )
        parts.append(choice)
    ws["B2"] = "=" + '&CHAR(10)&'.join(parts)
    ws["B2"].alignment = Alignment(wrap_text=True, vertical="top")
    ws["B2"].font = Font(name="Consolas", size=9, color=INK)
    ws["B2"].fill = PatternFill("solid", fgColor="F8F1E7")
    ws.merge_cells("B2:B18")
    ws["B1"] = "複製這個儲存格"
    ws["B1"].font = font(bold=True, color=ORANGE)
    ws.row_dimensions[2].height = 48
    ws.column_dimensions["AA"].hidden = True
    ws.column_dimensions["AB"].hidden = True
    ws.sheet_view.zoomScale = 110
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.freeze_panes = "A2"
    ws.oddFooter.center.text = "ZWCAD SCRIPT  ·  _.LINE  _.ARC"


def build_coords(ws):
    ws.sheet_properties.tabColor = "1A5276"
    headers = ["邊", "點序", "CAD X", "CAD Y", "sensor X mm", "sensor Y mm", "此邊模式"]
    for c, h in enumerate(headers, 1):
        cell = ws.cell(1, c, h)
        cell.font = font(bold=True, color=WHITE)
        cell.fill = fill_navy
        cell.alignment = center
    for edge in range(1, 5):
        for i in range(N_SAMP):
            row = sample_row(edge, i)
            ws.cell(row, 1, f"=取樣!A{row}")
            ws.cell(row, 2, f"=取樣!B{row}")
            ws.cell(row, 3, f"=取樣!J{row}*CadScale")
            ws.cell(row, 4, f"=取樣!K{row}*CadScale")
            ws.cell(row, 5, f"=取樣!D{row}")
            ws.cell(row, 6, f"=取樣!E{row}")
            ws.cell(row, 7, f"=擬合!B{1+edge}")
            for col in range(3, 7):
                ws.cell(row, col).number_format = "0.000000"
    ws.auto_filter.ref = f"A1:G{SAMPLE_LAST}"
    ws.freeze_panes = "A2"
    for col, width in enumerate([8, 8, 16, 16, 16, 16, 12], 1):
        ws.column_dimensions[get_column_letter(col)].width = width
    ws.auto_filter.ref = f"A1:G{SAMPLE_LAST}"
    note_row = SAMPLE_LAST + 2
    ws.cell(note_row, 1, "CAD X/Y 已乘座標縮放。原點是光軸與圖卡的交點。每一邊 33 個點，點 0 與下一邊的點 0 是同一個角。")
    ws.merge_cells(start_row=note_row, start_column=1, end_row=note_row, end_column=7)
    ws.cell(note_row, 1).font = font_small


def build_preview(ws, ws_s):
    ws.sheet_properties.tabColor = "1A5276"
    ws["A1"] = "預覽"
    ws["A1"].font = font_title
    ws.merge_cells("A2:G2")
    ws["A2"] = "左圖是 sensor 上要拍到的直斜方塊。右圖是圖卡：灰線是沒有預變形的位置，橘線是要畫的邊。Excel 橫縱軸比例可能不完全相等，尺寸以座標表為準。"
    ws["A2"].font = font_small
    ws["A2"].alignment = left_align
    ws.merge_cells("A3:G3")
    ws["A3"] = '="模式 "&擬合!B2&" / "&擬合!B3&" / "&擬合!B4&" / "&擬合!B5&"    水平視場 "&TEXT(HFovOut,"0.000")&"°    預變形最大位移 "&TEXT(MaxDisp,"0.00")&" mm    曲線 RMSE "&TEXT(FitRmse,"0.0000")&"°"'
    ws["A3"].font = font(bold=True, color=NAVY)

    # Sensor rectangle
    ws["A6"] = "sensor 框"
    for i, (fx, fy) in enumerate([( -1, -1), (1, -1), (1, 1), (-1, 1), (-1, -1)]):
        ws.cell(7 + i, 1, f"={fx}*SensW/2")
        ws.cell(7 + i, 2, f"={fy}*SensH/2")
    # center crosshair
    ws["C6"] = "主點"
    ws["C7"] = "=PrinX"
    ws["D7"] = "=PrinY"

    chart1 = ScatterChart()
    chart1.title = "Sensor：直的斜方塊"
    chart1.x_axis.title = "X mm（右為正）"
    chart1.y_axis.title = "Y mm（上為正）"
    chart1.style = 10
    chart1.legend.position = "b"
    chart1.x_axis.scaling.orientation = "minMax"
    chart1.y_axis.scaling.orientation = "minMax"
    chart1.x_axis.crosses = "min"
    chart1.y_axis.crosses = "min"
    xref = Reference(ws, min_col=1, min_row=7, max_row=11)
    yref = Reference(ws, min_col=2, min_row=7, max_row=11)
    box = Series(yref, xref, title="sensor")
    style_line(box, "AEB6BF", 1.25)
    chart1.series.append(box)
    colors = ["1F4E79", "1A5276", "117A65", "6C3483"]
    for edge in range(1, 5):
        r1 = sample_row(edge, 0)
        r2 = sample_row(edge, LAST_I)
        xvalues = Reference(ws_s, min_col=4, min_row=r1, max_row=r2)
        yvalues = Reference(ws_s, min_col=5, min_row=r1, max_row=r2)
        series = Series(yvalues, xvalues, title=f"邊 {edge}")
        style_line(series, colors[edge - 1], 1.75)
        chart1.series.append(series)
    chart1.width = 15
    chart1.height = 10
    ws.add_chart(chart1, "A13")

    chart2 = ScatterChart()
    chart2.title = "圖卡：預變形邊線"
    chart2.x_axis.title = "X mm"
    chart2.y_axis.title = "Y mm"
    chart2.style = 10
    chart2.legend.position = "b"
    for edge in range(1, 5):
        r1 = sample_row(edge, 0)
        r2 = sample_row(edge, LAST_I)
        x_ideal = Reference(ws_s, min_col=12, min_row=r1, max_row=r2)
        y_ideal = Reference(ws_s, min_col=13, min_row=r1, max_row=r2)
        ideal = Series(y_ideal, x_ideal, title=f"未變形 {edge}" if edge == 1 else None)
        style_line(ideal, "AEB6BF", 1.0)
        chart2.series.append(ideal)
        x_pre = Reference(ws_s, min_col=10, min_row=r1, max_row=r2)
        y_pre = Reference(ws_s, min_col=11, min_row=r1, max_row=r2)
        pre = Series(y_pre, x_pre, title=f"預變形 {edge}")
        style_line(pre, "C65911", 1.75)
        chart2.series.append(pre)
    chart2.width = 15
    chart2.height = 10
    ws.add_chart(chart2, "I13")
    ws.column_dimensions["A"].width = 18
    ws.column_dimensions["B"].width = 14
    ws.sheet_view.zoomScale = 110
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_area = "A1:R32"


def build_help(ws):
    ws.sheet_properties.tabColor = "7D6608"
    ws.column_dimensions["A"].width = 118
    lines = [
        ("Imatest SFR pattern 怎麼用", True, 20),
        ("這張表只產生斜方塊的四條邊。Sensor 上這四邊是直的，傾斜角由你決定。圖卡上的邊已經做過逆畸變，鏡頭照進去才會變直。", False, 12),
        ("", False, 8),
        ("要改的東西都在「參數」，黃底儲存格。改完看「規則」是不是通過，再到「指令」複製 SCR。", False, 12),
        ("", False, 8),
        ("1. 傾斜角", True, 16),
        ("方塊相對 sensor 水平軸旋轉。ISO 12233 常用 5° 或 5.71°（arctan 0.1）。Imatest 要求離開最近的水平、垂直、45° 至少約 2°，3°–7° 最合適。四邊會同時得到接近水平與接近垂直的 SFR。", False, 12),
        ("", False, 8),
        ("2. 畸變座標與水平視場角", True, 16),
        ("水平視場角不是輸入。到「畸變座標」貼兩欄：A 半像高（mm，主點到該視場的距離），B 半視場角（度，物方）。點數要超過 1000，建議 10000。空白列會略過。表內最大半像高記成 h_scale，u = 半像高 / h_scale，擬合 tan(θ) = d1·u + d3·u³ + d5·u⁵ + d7·u⁷ + d9·u⁹。近軸焦距 = h_scale / d1。水平半像高 = 水平像素 × 像素尺寸 / 2，代入曲線得到半角，乘 2 就是水平視場角。垂直、對角視場角用同樣方法。", False, 12),
        ("", False, 8),
        ("範例 10000 點是一條桶形曲線，只為了打開檔就能看到預彎的 ARC。請用自己的量測整欄蓋掉。同一條半像高，桶形鏡頭的半視場角會比近軸更大，圖卡上的邊會被推離光軸，邊的中段相對兩端靠近光軸。", False, 12),
        ("", False, 8),
        ("3. 大小與位置", True, 16),
        ("視場 0 在主點，1 在基準邊緣。基準選「對角」時，1 就是 sensor 角落。方塊在 sensor 上先擺成直的。圖卡上同一點的半徑 = 測試距離 × tan(θ(h))，方向與 sensor 上相同。測試距離是入瞳（節點）到圖卡，不是 (距離−焦距)/焦距。未變形的對照線用近軸焦距：半徑 = 測試距離 × h / f。", False, 12),
        ("", False, 8),
        ("4. Imatest 規則（這張表會擋）", True, 16),
        ("只看邊線。傾斜角要離開 0°、90°、45°，建議 3°–7°。邊長建議 80–300 px。四條邊要落在 sensor 裡面。畸變表要超過 1000 點並蓋過 sensor 半對角。不檢查亮暗或對比，因為這裡沒有填色。", False, 12),
        ("", False, 8),
        ("5. 中望 CAD", True, 16),
        ("指令是 _.LINE 與 _.ARC。三點 ARC 的順序是起點、弧上中點、終點。原點請放在光軸與圖卡的交點，單位與「座標縮放」一致，預設公厘。公差內能用一條直線就用 LINE，否則用 ARC；彎得更厲害就拆成 4 段或 8 段，仍不夠才用 33 點折線。每一邊的點都在「座標」工作表。", False, 12),
        ("", False, 8),
        ("座標方向：sensor 與圖卡都是 +X 向右、+Y 向上，原點在主點 / 光軸。影像檔的列號通常上為 0，參數頁有換算。", False, 12),
    ]
    for i, (text, title, size) in enumerate(lines, 1):
        ws.cell(i, 1, text)
        ws.cell(i, 1).font = font(size=size, bold=title, color=NAVY if title else INK)
        ws.cell(i, 1).alignment = Alignment(wrap_text=True, vertical="center")
        ws.row_dimensions[i].height = 28 if title else (18 if len(text) < 40 else min(108, 32 + len(text) // 28 * 12))
    ws.page_setup.orientation = "portrait"
    ws.page_setup.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.leftMargin = 0.6
    ws.page_setup.rightMargin = 0.6
    ws.print_options.horizontalCentered = True


if __name__ == "__main__":
    build()
