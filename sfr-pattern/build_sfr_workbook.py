#!/usr/bin/env python3
"""Build the Imatest SFR slanted-square workbook for ZWCAD LINE/ARC output."""

from __future__ import annotations

from openpyxl import Workbook
from openpyxl.chart import Reference, ScatterChart, Series
from openpyxl.chart.marker import Marker
from openpyxl.chart.shapes import GraphicalProperties
from openpyxl.comments import Comment
from openpyxl.drawing.line import LineProperties
from openpyxl.formatting.rule import CellIsRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.chart.legend import Legend

OUT = "/workspace/sfr-pattern/Imatest_SFR_pattern_ZWCAD.xlsx"

N_SAMP = 33
N_EDGE = 4
N_ITER = 8
LAST_I = N_SAMP - 1  # 32
SAMPLE_FIRST = 2
SAMPLE_LAST = SAMPLE_FIRST + N_EDGE * N_SAMP - 1  # 133
CENTER_ROW = SAMPLE_LAST + 1  # 134 on 迭代
CIRCLE_START = 12

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


def iter_col(it, offset):
    """1-based column. it is 1..N_ITER, offset 0..14 within the Newton block."""
    return 3 + (it - 1) * 15 + offset


def iter_letter(it, offset):
    return get_column_letter(iter_col(it, offset))


OFFSETS = {
    "r2": 0,
    "r4": 1,
    "rad": 2,
    "q": 3,
    "tx": 4,
    "ty": 5,
    "Fx": 6,
    "Fy": 7,
    "Jxx": 8,
    "Jxy": 9,
    "Jyx": 10,
    "Jyy": 11,
    "det": 12,
    "x": 13,
    "y": 14,
}


def write_newton_row(ws, row, xd_formula, yd_formula):
    ws.cell(row, 1, xd_formula)
    ws.cell(row, 2, yd_formula)
    for it in range(1, N_ITER + 1):
        if it == 1:
            px, py = f"A{row}", f"B{row}"
        else:
            px = f"{iter_letter(it - 1, OFFSETS['x'])}{row}"
            py = f"{iter_letter(it - 1, OFFSETS['y'])}{row}"
        base = iter_col(it, 0)
        cells = {}
        for key, off in OFFSETS.items():
            cells[key] = f"{get_column_letter(base + off)}{row}"
        r2, r4, rad, q = cells["r2"], cells["r4"], cells["rad"], cells["q"]
        tx, ty, fx, fy = cells["tx"], cells["ty"], cells["Fx"], cells["Fy"]
        jxx, jxy, jyx, jyy, det = cells["Jxx"], cells["Jxy"], cells["Jyx"], cells["Jyy"], cells["det"]
        ws.cell(row, base + 0, f"={px}^2+{py}^2")
        ws.cell(row, base + 1, f"={r2}^2")
        ws.cell(row, base + 2, f"=1+EffK1*{r2}+EffK2*{r4}+EffK3*{r2}*{r4}")
        ws.cell(row, base + 3, f"=EffK1+2*EffK2*{r2}+3*EffK3*{r4}")
        ws.cell(row, base + 4, f"=2*EffP1*{px}*{py}+EffP2*({r2}+2*{px}^2)")
        ws.cell(row, base + 5, f"=EffP1*({r2}+2*{py}^2)+2*EffP2*{px}*{py}")
        ws.cell(row, base + 6, f"={px}*{rad}+{tx}-A{row}")
        ws.cell(row, base + 7, f"={py}*{rad}+{ty}-B{row}")
        ws.cell(row, base + 8, f"={rad}+2*{q}*{px}^2+(2*EffP1*{py}+6*EffP2*{px})")
        ws.cell(row, base + 9, f"=2*{q}*{px}*{py}+(2*EffP1*{px}+2*EffP2*{py})")
        ws.cell(row, base + 10, f"=2*{q}*{px}*{py}+(2*EffP1*{px}+2*EffP2*{py})")
        ws.cell(row, base + 11, f"={rad}+2*{q}*{py}^2+(6*EffP1*{py}+2*EffP2*{px})")
        ws.cell(row, base + 12, f"={jxx}*{jyy}-{jxy}*{jyx}")
        ws.cell(
            row,
            base + 13,
            f'=IF(ABS({det})<0.00000000000001,{px},{px}+((-{jyy}*{fx}+{jxy}*{fy})/{det}))',
        )
        ws.cell(
            row,
            base + 14,
            f'=IF(ABS({det})<0.00000000000001,{py},{py}+(({jyx}*{fx}-{jxx}*{fy})/{det}))',
        )


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
    ws_it = wb.create_sheet("迭代_勿改")
    ws_help = wb.create_sheet("說明")

    build_params(wb, ws_p)
    build_iteration(ws_it)
    build_samples(ws_s)
    build_fit(ws_f)
    build_rules(ws_rule)
    build_script(ws_scr)
    build_coords(ws_xy)
    build_preview(ws_view, ws_s)
    build_help(ws_help)
    link_param_outputs(ws_p)

    ws_it.sheet_state = "hidden"
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


def build_params(wb, ws):
    ws.sheet_properties.tabColor = NAVY
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 1
    ws.freeze_panes = "A5"
    ws.row_dimensions[1].height = 28
    ws.row_dimensions[2].height = 32
    ws.merge_cells("A1:D1")
    ws["A1"] = "Imatest SFR 斜方塊邊線"
    ws["A1"].font = font_title
    ws.merge_cells("A2:D2")
    ws["A2"] = "只畫邊線。黃底可改。Sensor 上是直的斜方塊；指令裡的座標已逆畸變，給中望 CAD 的 LINE / ARC 用。"
    ws["A2"].font = font_small
    ws["A2"].alignment = left_align

    ws.merge_cells("I1:K2")
    ws["I1"] = '=RuleAll'
    ws["I1"].font = font(size=22, bold=True, color=NAVY)
    ws["I1"].alignment = Alignment(horizontal="center", vertical="center")
    ws["I1"].fill = fill_out
    ws["L1"] = "規則總判"
    ws["L1"].font = font_small

    section(ws, 4, "一、Sensor 與拍攝位置")
    rows = [
        (5, "水平像素", "px", "Sensor 寬方向的有效像素", "PixW", 4000, "0"),
        (6, "垂直像素", "px", "Sensor 高方向的有效像素", "PixH", 3000, "0"),
        (7, "像素尺寸", "μm", "正方像素邊長", "PixUm", 1.55, "0.000"),
        (8, "周邊視場位置", "0–1", "0 = 主點，1 = 下方所選基準的邊緣", "FieldPos", 0.7, "0.00"),
        (9, "視場方位角", "度", "0° 向右（+X），90° 向上（+Y），45° 為對角", "AzimuthDeg", 45, "0.00"),
        (11, "測試距離", "mm", "前主點到圖卡平面", "TestDist", 500, "0.00"),
        (13, "焦距", "mm", "近軸焦距。不要用已經含畸變的等效焦距再疊一次 k", "FocalMm", 6, "0.000"),
        (14, "水平視場角", "度", "只有焦距來源選「由水平視場角」時才用", "HFovDeg", 60, "0.00"),
        (16, "主點偏移 X", "px", "相對 sensor 中心，右為正", "PrinPx", 0, "0.00"),
        (17, "主點偏移 Y", "px", "相對 sensor 中心，上為正", "PrinPy", 0, "0.00"),
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

    label(ws, 12, "焦距來源", "", "沒有焦距時，用水平視場角反推近軸焦距")
    ws["B12"] = "直接輸入焦距"
    apply_input(ws["B12"])
    add_name(wb, "FocalSrc", "'參數'!$B$12")

    label(ws, 15, "投影模型", "", "薄透鏡用 (測試距離−焦距)/焦距")
    ws["B15"] = "薄透鏡"
    apply_input(ws["B15"], "圖卡在有限距離時用薄透鏡。距離遠大於焦距時，兩種結果接近。")
    add_name(wb, "ProjModel", "'參數'!$B$15")

    section(ws, 19, "二、SFR 斜方塊（Imatest 斜邊）")
    label(ws, 20, "傾斜角", "度", "方塊相對水平軸。ISO 常用 5° 或 5.71°")
    ws["B20"] = 5
    apply_input(ws["B20"], "必須離開 0°、90° 和 45° 至少 2°。建議 3° 到 7°。5.71° = arctan(0.1)。")
    ws["B20"].number_format = "0.00"
    add_name(wb, "TiltDeg", "'參數'!$B$20")

    label(ws, 21, "目標邊長", "px", "這條邊在 sensor 上的直線長度，用來決定圖卡尺寸")
    ws["B21"] = 200
    apply_input(ws["B21"], "Imatest 建議沿邊約 80–300 px。預設 200。只決定邊線長度，不含填色。")
    ws["B21"].number_format = "0"
    add_name(wb, "EdgePx", "'參數'!$B$21")

    section(ws, 24, "三、鏡頭畸變（預變形）")
    label(ws, 25, "畸變模型", "", "三種都是把「想在 sensor 上看到的直邊」反算回圖卡")
    ws["B25"] = "Brown-Conrady"
    apply_input(ws["B25"], "Brown-Conrady 用 k1 k2 k3 p1 p2。百分比多項式與視場表用 Zemax 同號的畸變%。")
    add_name(wb, "DistModel", "'參數'!$B$25")

    for row, text, name, value, note in [
        (26, "k1", "RadK1", -0.3, "r = 像高/焦距。k1 < 0 是桶形，圖卡會預彎成枕形"),
        (27, "k2", "RadK2", 0.05, "r^4 項"),
        (28, "k3", "RadK3", 0, "r^6 項"),
        (29, "p1", "TanP1", 0, "切向，通常很小"),
        (30, "p2", "TanP2", 0, "切向"),
    ]:
        label(ws, row, text, "", note)
        cell = ws.cell(row, 2, value)
        apply_input(cell)
        cell.number_format = "0.000000"
        add_name(wb, name, f"'參數'!$B${row}")

    for row, text, name, note in [
        (31, "D2", "PolyD2", "δ = D2·ρ² + D4·ρ⁴ + D6·ρ⁶，δ 是分數，ρ = 理想像高/半對角"),
        (32, "D4", "PolyD4", "百分比多項式才使用。−0.03 代表二次項在全視場約 −3%"),
        (33, "D6", "PolyD6", "高次項"),
    ]:
        label(ws, row, text, "分數", note)
        cell = ws.cell(row, 2, 0)
        apply_input(cell)
        cell.number_format = "0.000000"
        add_name(wb, name, f"'參數'!$B${row}")

    section(ws, 35, "視場–畸變對照表（模型選「視場畸變表」才用）", cols=4)
    ws["A36"] = "表列"
    ws["B36"] = "理想相對視場 ρ"
    ws["C36"] = "畸變 %"
    for col in (1, 2, 3):
        ws.cell(36, col).font = font(bold=True, size=9)
    rhos = [0, 0.2, 0.4, 0.5, 0.6, 0.7, 0.85, 1]
    for i, rho in enumerate(rhos):
        row = 37 + i
        ws.cell(row, 1, f"視場 {i+1}").font = font_small
        cell_rho = ws.cell(row, 2, rho)
        cell_rho.number_format = "0.00"
        apply_input(cell_rho, "由小到大。0 是光軸，1 是半對角。")
        cell_pct = ws.cell(row, 3, 0)
        cell_pct.number_format = "0.000"
        apply_input(cell_pct, "與 Zemax Distortion 同號：(實際像高−理想像高)/理想像高×100。桶形為負。")
        ws.cell(row, 27, f"=B{row}^2")
        ws.cell(row, 28, f"=B{row}^4")
        ws.cell(row, 29, f"=B{row}^6")
        ws.cell(row, 30, f"=IF(C{row}=\"\",0,C{row}/100)")

    # Least-squares sums in column 27-30 header note
    ws["AA36"] = "ρ²"
    ws["AB36"] = "ρ⁴"
    ws["AC36"] = "ρ⁶"
    ws["AD36"] = "δ"
    for col in range(27, 31):
        ws.cell(36, col).font = font_small

    ws["AA46"] = '=SUMPRODUCT(AA37:AA44,AA37:AA44)'
    ws["AB46"] = '=SUMPRODUCT(AA37:AA44,AB37:AB44)'
    ws["AC46"] = '=SUMPRODUCT(AA37:AA44,AC37:AC44)'
    ws["AA47"] = '=SUMPRODUCT(AB37:AB44,AB37:AB44)'
    ws["AB47"] = '=SUMPRODUCT(AB37:AB44,AC37:AC44)'
    ws["AC47"] = '=SUMPRODUCT(AC37:AC44,AC37:AC44)'
    ws["AA48"] = '=SUMPRODUCT(AA37:AA44,AD37:AD44)'
    ws["AB48"] = '=SUMPRODUCT(AB37:AB44,AD37:AD44)'
    ws["AC48"] = '=SUMPRODUCT(AC37:AC44,AD37:AD44)'
    # det and Cramer, using the sums above
    # Saa AA46, Sab AB46, Sac AC46, Sbb AA47, Sbc AB47, Scc AC47, Say AA48, Sby AB48, Scy AC48
    ws["AA50"] = (
        "=AA46*(AA47*AC47-AB47*AB47)"
        "-AB46*(AB46*AC47-AC46*AB47)"
        "+AC46*(AB46*AB47-AA47*AC46)"
    )
    ws["AA51"] = (
        '=IF(ABS(AA50)<0.000000000000000001,0,(AA48*(AA47*AC47-AB47*AB47)'
        '-AB46*(AB48*AC47-AB47*AC48)+AC46*(AB48*AB47-AA47*AC48))/AA50)'
    )
    ws["AB51"] = (
        '=IF(ABS(AA50)<0.000000000000000001,0,(AA46*(AB48*AC47-AB47*AC48)'
        '-AA48*(AB46*AC47-AB47*AC46)+AC46*(AB46*AC48-AB48*AC46))/AA50)'
    )
    ws["AC51"] = (
        '=IF(ABS(AA50)<0.000000000000000001,0,(AA46*(AA47*AC48-AB48*AB47)'
        '-AB46*(AB46*AC48-AB48*AC46)+AA48*(AB46*AB47-AA47*AC46))/AA50)'
    )
    add_name(wb, "FitD2", "'參數'!$AA$51")
    add_name(wb, "FitD4", "'參數'!$AB$51")
    add_name(wb, "FitD6", "'參數'!$AC$51")

    section(ws, 46, "四、中望 CAD")
    label(ws, 47, "擬合公差", "mm", "取樣點到直線或圓弧的最大允許距離")
    ws["B47"] = 0.02
    apply_input(ws["B47"], "小於此值就用一條 LINE 或 ARC。超過就拆成更多 ARC，最後才用折線。")
    ws["B47"].number_format = "0.000"
    add_name(wb, "CadTol", "'參數'!$B$47")

    label(ws, 48, "座標縮放", "", "1 = 公厘。圖紙若用公尺，填 0.001")
    ws["B48"] = 1
    apply_input(ws["B48"])
    ws["B48"].number_format = "0.0000"
    add_name(wb, "CadScale", "'參數'!$B$48")

    # Derived values in column I/J
    derived = [
        (5, "Sensor 寬", "SensW", "=PixW*PixUm/1000", "0.000", "mm"),
        (6, "Sensor 高", "SensH", "=PixH*PixUm/1000", "0.000", "mm"),
        (7, "使用中的焦距", "FocalUse",
         '=IF(FocalSrc="由水平視場角",IF(HFovDeg<=0,NA(),(SensW/2)/TAN(RADIANS(HFovDeg/2))),FocalMm)',
         "0.000", "mm"),
        (8, "圖卡/sensor 倍率", "ObjScale",
         '=IF(OR(FocalUse<=0,TestDist<=0),NA(),IF(AND(ProjModel="薄透鏡",TestDist<=FocalUse),NA(),IF(ProjModel="遠距近似",TestDist/FocalUse,(TestDist-FocalUse)/FocalUse)))',
         "0.000", "mm/mm"),
        (9, "半對角", "HalfDiag", "=SQRT((SensW/2)^2+(SensH/2)^2)", "0.000", "mm"),
        (10, "1.0 視場長度", "FieldR",
         '=IF(FieldRef="水平半寬",SensW/2,IF(FieldRef="垂直半高",SensH/2,HalfDiag))',
         "0.000", "mm"),
        (11, "主點 X", "PrinX", "=PrinPx*PixUm/1000", "0.000", "mm"),
        (12, "主點 Y", "PrinY", "=PrinPy*PixUm/1000", "0.000", "mm"),
        (13, "方塊中心 X", "CenterX", "=PrinX+FieldPos*FieldR*COS(RADIANS(AzimuthDeg))", "0.000", "mm"),
        (14, "方塊中心 Y", "CenterY", "=PrinY+FieldPos*FieldR*SIN(RADIANS(AzimuthDeg))", "0.000", "mm"),
        (15, "方塊邊長", "SideMm", "=EdgePx*PixUm/1000", "0.0000", "mm"),
        (16, "cos(傾斜)", "CosT", "=COS(RADIANS(TiltDeg))", "0.000000", ""),
        (17, "sin(傾斜)", "SinT", "=SIN(RADIANS(TiltDeg))", "0.000000", ""),
        (18, "半邊長", "HalfSide", "=SideMm/2", "0.0000", "mm"),
        (19, "外接半寬", "AabbHalf", "=HalfSide*(ABS(CosT)+ABS(SinT))", "0.0000", "mm"),
        (20, "離水平/垂直", "BetaDeg",
         "=MIN(MOD(ABS(TiltDeg),90),90-MOD(ABS(TiltDeg),90))", "0.00", "度"),
        (21, "像素尺寸", "PixMm", "=PixUm/1000", "0.000000", "mm"),
        (22, "邊到畫面邊緣", "ClearPx",
         "=(MIN(SensW/2-ABS(CenterX)-AabbHalf,SensH/2-ABS(CenterY)-AabbHalf))/PixMm",
         "0.0", "px"),
        (29, "有效 k1", "EffK1",
         '=IF(DistModel="Brown-Conrady",RadK1,UseD2/RcNorm^2)', "0.000000", ""),
        (30, "有效 k2", "EffK2",
         '=IF(DistModel="Brown-Conrady",RadK2,UseD4/RcNorm^4)', "0.000000", ""),
        (31, "有效 k3", "EffK3",
         '=IF(DistModel="Brown-Conrady",RadK3,UseD6/RcNorm^6)', "0.000000", ""),
        (32, "有效 p1", "EffP1", '=IF(DistModel="Brown-Conrady",TanP1,0)', "0.000000", ""),
        (33, "有效 p2", "EffP2", '=IF(DistModel="Brown-Conrady",TanP2,0)', "0.000000", ""),
        (34, "半對角/焦距", "RcNorm", '=IF(FocalUse<=0,NA(),HalfDiag/FocalUse)', "0.000000", ""),
        (35, "使用中的 D2", "UseD2", '=IF(DistModel="視場畸變表",FitD2,PolyD2)', "0.000000", ""),
        (36, "使用中的 D4", "UseD4", '=IF(DistModel="視場畸變表",FitD4,PolyD4)', "0.000000", ""),
        (37, "使用中的 D6", "UseD6", '=IF(DistModel="視場畸變表",FitD6,PolyD6)', "0.000000", ""),
    ]
    ws["I4"] = "算出來的位置與尺寸"
    ws["I4"].font = font(bold=True, color=NAVY)
    ws.merge_cells("I4:L4")
    for row, text, name, formula, fmt, unit in derived:
        ws.cell(row, 9, text).font = font_label
        ws.cell(row, 9).alignment = left_align
        cell = ws.cell(row, 10, formula)
        apply_output(cell, fmt)
        ws.cell(row, 11, unit).font = font_small
        add_name(wb, name, f"'參數'!$J${row}")

    # Vertices of the straight square on the sensor. Order is counterclockwise from lower left.
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
    # limX / limY and tMax
    ws["J48"] = (
        '=LET_PLACEHOLDER'
    )
    # Avoid LET. Compute with nested IF in one formula.
    # tx = if abs(rx)<1e-12 then if abs(PrinX)<=limX then 1 else -1 else if rx>0 then (limX-PrinX)/rx else (-limX-PrinX)/rx
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
    ws["J48"] = f'=MAX(0,MIN(1,{tx},{ty}))'
    apply_output(ws["J48"], "0.000")
    add_name(wb, "FieldMax", "'參數'!$J$48")
    ws["K48"] = "0–1"
    ws["K48"].font = font_small

    # Placeholders filled after iteration/fit exist: chart center, errors, rule, modes.
    for row, text, name in [
        (24, "圖卡中心 X", "ChartCx"),
        (25, "圖卡中心 Y", "ChartCy"),
        (26, "未變形圖卡中心 X", "IdealCx"),
        (27, "未變形圖卡中心 Y", "IdealCy"),
        (28, "預變形最大位移", "MaxDisp"),
    ]:
        ws.cell(row, 9, text).font = font_label

    ws["I23"] = "規則總判（詳見「規則」）"
    ws["I23"].font = font_label

    # dropdowns
    dv_ref = DataValidation(type="list", formula1='"對角,水平半寬,垂直半高"', allow_blank=False)
    dv_src = DataValidation(type="list", formula1='"直接輸入焦距,由水平視場角"', allow_blank=False)
    dv_proj = DataValidation(type="list", formula1='"薄透鏡,遠距近似"', allow_blank=False)
    dv_dist = DataValidation(type="list", formula1='"Brown-Conrady,百分比多項式,視場畸變表"', allow_blank=False)
    dv_field = DataValidation(type="decimal", operator="between", formula1="0", formula2="1", allow_blank=False)
    dv_field.error = "視場要在 0 到 1"
    dv_field.errorTitle = "視場"
    for dv in (dv_ref, dv_src, dv_proj, dv_dist, dv_field):
        dv.add(ws["B10"] if dv is dv_ref else ws["B12"] if dv is dv_src else ws["B15"] if dv is dv_proj else ws["B25"] if dv is dv_dist else ws["B8"])
        ws.add_data_validation(dv)

    ws.conditional_formatting.add("I1:K2", CellIsRule(operator="equal", formula=['"通過"'], fill=PatternFill("solid", fgColor="D5F5E3"), font=font(size=22, bold=True, color=GREEN)))
    ws.conditional_formatting.add("I1:K2", CellIsRule(operator="equal", formula=['"有警告"'], fill=PatternFill("solid", fgColor="FDEBD0"), font=font(size=22, bold=True, color=AMBER)))
    ws.conditional_formatting.add("I1:K2", CellIsRule(operator="equal", formula=['"不符合"'], fill=PatternFill("solid", fgColor="FADBD8"), font=font(size=22, bold=True, color=RED)))

    widths = {"A": 24, "B": 22, "C": 14, "D": 62, "E": 3, "F": 3, "G": 3, "H": 3, "I": 28, "J": 18, "K": 16, "L": 16}
    for col, width in widths.items():
        ws.column_dimensions[col].width = width
    ws.auto_filter.ref = None
    ws.sheet_view.zoomScale = 110
    ws.oddHeader.left.text = "Imatest SFR pattern"
    ws.print_title_rows = "1:2"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.sheet_properties.pageSetUpPr.fitToPage = True


def link_param_outputs(ws):
    xcol = iter_letter(N_ITER, OFFSETS["x"])
    ycol = iter_letter(N_ITER, OFFSETS["y"])
    ws["J23"] = "=RuleAll"
    apply_output(ws["J23"])
    ws["J24"] = f"={xcol_ref(xcol)}*FocalUse*ObjScale"
    ws["J25"] = f"={ycol_ref(ycol)}*FocalUse*ObjScale"
    # fix properly below
    ws["J24"] = f"=迭代_勿改!{xcol}{CENTER_ROW}*FocalUse*ObjScale"
    ws["J25"] = f"=迭代_勿改!{ycol}{CENTER_ROW}*FocalUse*ObjScale"
    ws["J26"] = "=CenterX*ObjScale"
    ws["J27"] = "=CenterY*ObjScale"
    ws["J28"] = f"=MAX(取樣!Q{SAMPLE_FIRST}:Q{SAMPLE_LAST})"
    for row, fmt in ((24, "0.000"), (25, "0.000"), (26, "0.000"), (27, "0.000"), (28, "0.000")):
        apply_output(ws.cell(row, 10), fmt)
    ws["K24"] = "mm"
    ws["K25"] = "mm"
    ws["K26"] = "mm"
    ws["K27"] = "mm"
    ws["K28"] = "mm"
    for row in range(24, 29):
        ws.cell(row, 11).font = font_small
    add_name(ws.parent, "ChartCx", "'參數'!$J$24")
    add_name(ws.parent, "ChartCy", "'參數'!$J$25")
    add_name(ws.parent, "IdealCx", "'參數'!$J$26")
    add_name(ws.parent, "IdealCy", "'參數'!$J$27")
    add_name(ws.parent, "MaxDisp", "'參數'!$J$28")
    ws["I50"] = "四邊 CAD 模式"
    ws["J50"] = '=擬合!B2&" / "&擬合!B3&" / "&擬合!B4&" / "&擬合!B5'
    apply_output(ws["J50"])
    ws["I51"] = "反算最大誤差"
    ws["J51"] = f"=MAX(取樣!P{SAMPLE_FIRST}:P{SAMPLE_LAST})"
    apply_output(ws["J51"], "0.000000")
    ws["K51"] = "mm"
    ws["K51"].font = font_small
    add_name(ws.parent, "MaxErr", "'參數'!$J$51")
    ws["I52"] = "中心像素（左下為原點，Y 向上）"
    ws["J52"] = '=CenterX/PixMm+PixW/2'
    ws["K52"] = '=CenterY/PixMm+PixH/2'
    apply_output(ws["J52"], "0.0")
    apply_output(ws["K52"], "0.0")
    ws["L52"] = "X , Y"
    ws["L52"].font = font_small
    ws["I53"] = "中心影像列（上為 0）"
    ws["J53"] = "=PixH-K52"
    apply_output(ws["J53"], "0.0")


def xcol_ref(xcol):
    return xcol


def ycol_ref(ycol):
    return ycol


def build_iteration(ws):
    ws.sheet_properties.tabColor = "AEB6BF"
    ws["A1"] = "xd"
    ws["B1"] = "yd"
    write_newton_row(ws, CENTER_ROW, "=CenterX/FocalUse", "=CenterY/FocalUse")
    for edge in range(1, N_EDGE + 1):
        for i in range(N_SAMP):
            row = sample_row(edge, i)
            write_newton_row(ws, row, f"=取樣!F{row}", f"=取樣!G{row}")
    ws.sheet_view.zoomScale = 80


def build_samples(ws):
    ws.sheet_properties.tabColor = "5D6D7E"
    headers = [
        "邊", "點", "t", "sensor X mm", "sensor Y mm", "xd", "yd", "xu", "yu",
        "圖卡 X mm", "圖卡 Y mm", "未變形 X", "未變形 Y", "正向 xd", "正向 yd",
        "反算誤差 mm", "預變形位移 mm", "整邊弦高", "單弧誤差", "四段弧誤差",
        "八段弧誤差", "四段弦高", "八段弦高", "折線拱高估計",
    ]
    for c, h in enumerate(headers, 1):
        cell = ws.cell(1, c, h)
        cell.font = font(bold=True, size=9, color=WHITE)
        cell.fill = fill_navy
        cell.alignment = center
    ws.auto_filter.ref = f"A1:X{SAMPLE_LAST}"
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:X{SAMPLE_LAST}"
    xfin = f"迭代_勿改!{iter_letter(N_ITER, OFFSETS['x'])}"
    yfin = f"迭代_勿改!{iter_letter(N_ITER, OFFSETS['y'])}"
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
            ws.cell(row, 6, f"=D{row}/FocalUse")
            ws.cell(row, 7, f"=E{row}/FocalUse")
            ws.cell(row, 8, f"={xfin}{row}")
            ws.cell(row, 9, f"={yfin}{row}")
            ws.cell(row, 10, f"=H{row}*FocalUse*ObjScale")
            ws.cell(row, 11, f"=I{row}*FocalUse*ObjScale")
            ws.cell(row, 12, f"=D{row}*ObjScale")
            ws.cell(row, 13, f"=E{row}*ObjScale")
            # forward distort of xu,yu
            ws.cell(row, 14,
                    f"=H{row}*(1+EffK1*(H{row}^2+I{row}^2)+EffK2*(H{row}^2+I{row}^2)^2+EffK3*(H{row}^2+I{row}^2)^3)"
                    f"+2*EffP1*H{row}*I{row}+EffP2*((H{row}^2+I{row}^2)+2*H{row}^2)")
            ws.cell(row, 15,
                    f"=I{row}*(1+EffK1*(H{row}^2+I{row}^2)+EffK2*(H{row}^2+I{row}^2)^2+EffK3*(H{row}^2+I{row}^2)^3)"
                    f"+EffP1*((H{row}^2+I{row}^2)+2*I{row}^2)+2*EffP2*H{row}*I{row}")
            ws.cell(row, 16, f"=SQRT((N{row}-F{row})^2+(O{row}-G{row})^2)*FocalUse")
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
        (6, "測試距離與焦距",
         '=TEXT(TestDist,"0.00")&" mm，焦距 "&TEXT(FocalUse,"0.000")&" mm"',
         '=IF(AND(ISNUMBER(FocalUse),ISNUMBER(ObjScale),TestDist>FocalUse,FocalUse>0),"符合","不符合")',
         "圖卡要在前焦點之外。實體尺寸 = sensor 尺寸 × (距離−焦距)/焦距。"),
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
        (13, "畸變反算有沒有收斂",
         '=TEXT(MaxErr*1000,"0.000")&" μm"',
         '=IF(MaxErr<=0.01*PixMm,"符合",IF(MaxErr<=0.25*PixMm,"警告","不符合"))',
         "把圖卡點再正向畸變一次，要回到原本的直邊。誤差應遠小於 0.01 像素。"),
        (14, "圖卡座標是有限數",
         '=ObjScale',
         '=IF(AND(ISNUMBER(ObjScale),COUNT(取樣!J2:J133)=132,COUNT(取樣!K2:K133)=132),"符合","不符合")',
         "距離必須大於焦距，k 也不能讓反算發散。"),
        (15, "折線剩餘拱高",
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
    ws["H4"] = '=COUNTIF(C5:C15,"不符合")'
    ws["G5"] = "警告"
    ws["H5"] = '=COUNTIF(C5:C15,"警告")'
    ws["G6"] = "總結果"
    ws["H6"] = '=IF(H4>0,"不符合",IF(H5>0,"有警告","通過"))'
    add_name(ws.parent, "RuleAll", "'規則'!$H$6")
    for row in range(4, 7):
        ws.cell(row, 7).font = font_small
        apply_output(ws.cell(row, 8))

    ws.conditional_formatting.add("C5:C15", CellIsRule(operator="equal", formula=['"不符合"'], fill=PatternFill("solid", fgColor="FADBD8"), font=font(bold=True, color=RED)))
    ws.conditional_formatting.add("C5:C15", CellIsRule(operator="equal", formula=['"警告"'], fill=PatternFill("solid", fgColor="FDEBD0"), font=font(bold=True, color=AMBER)))
    ws.conditional_formatting.add("C5:C15", FormulaRule(formula=['LEFT(C5,2)="符合"'], fill=PatternFill("solid", fgColor="D5F5E3"), font=font(bold=True, color=GREEN)))
    ws.conditional_formatting.add("H1:I2", CellIsRule(operator="equal", formula=['"通過"'], fill=PatternFill("solid", fgColor="D5F5E3"), font=font(size=22, bold=True, color=GREEN)))
    ws.conditional_formatting.add("H1:I2", CellIsRule(operator="equal", formula=['"有警告"'], fill=PatternFill("solid", fgColor="FDEBD0"), font=font(size=22, bold=True, color=AMBER)))
    ws.conditional_formatting.add("H1:I2", CellIsRule(operator="equal", formula=['"不符合"'], fill=PatternFill("solid", fgColor="FADBD8"), font=font(size=22, bold=True, color=RED)))

    ws.merge_cells("A19:D21")
    ws["A19"] = (
        "方塊四邊就是 SFR 的斜邊：兩條接近垂直、兩條接近水平，和 SFRplus / eSFR 的斜方塊相同。"
        "傾斜 5° 時，四邊都會離開水平、垂直和 45°。"
        "預變形只發生在圖卡上。拍進 sensor 之後，這四邊應是直的，角度就是你填的傾斜角。"
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
        "7. 改了黃底參數後，這個儲存格會重算，請重新複製。"
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
        f'="; focal_mm="&{num("FocalUse",4)}&" distance_mm="&{num("TestDist",2)}&" edge_px="&{num("EdgePx",2)}',
        f'="; model="&DistModel&" k1="&{num("EffK1",6)}&" k2="&{num("EffK2",6)}&" k3="&{num("EffK3",6)}',
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

    def join_range(a, b):
        return f"TEXTJOIN(CHAR(10),FALSE,AA{a}:AA{b})"

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
    ws["A3"] = '="模式 "&擬合!B2&" / "&擬合!B3&" / "&擬合!B4&" / "&擬合!B5&"    預變形最大位移 "&TEXT(MaxDisp,"0.00")&" mm    反算誤差 "&TEXT(MaxErr*1000,"0.000")&" μm"'
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
        ("2. 預變形", True, 16),
        ("先把想出現在 sensor 上的直邊寫下來，再用畸變模型反算「什麼樣的入射方向，經過這個鏡頭之後會落在這條直邊上」，最後用測試距離投影到圖卡。Brown-Conrady 與 OpenCV 相同：xd = xu·(1+k1 r²+k2 r⁴+k3 r⁶)+切向，r = 像高/焦距。k1<0 是桶形，圖卡會預彎成枕形。百分比多項式與視場表的畸變%和 Zemax 同號，負值是桶形。三種模型不要同時當成兩套畸變疊加；切換模型即可。", False, 12),
        ("", False, 8),
        ("3. 大小與位置", True, 16),
        ("視場 0 在主點，1 在基準邊緣。基準選「對角」時，1 就是 sensor 角落，方位角 45° / 135° / 225° / 315° 對應四個角。邊長是這條邊在 sensor 上要佔的像素。像素尺寸和測試距離、焦距一起把它換成圖卡上的公厘。沒有焦距就選「由水平視場角」，但那個焦距不要再和很大的 k 重複計算。薄透鏡倍率是 (距離−焦距)/焦距。", False, 12),
        ("", False, 8),
        ("4. Imatest 規則（這張表會擋）", True, 16),
        ("只看邊線。傾斜角要離開 0°、90°、45°，建議 3°–7°。邊長建議 80–300 px。四條邊要落在 sensor 裡面。不檢查亮暗或對比，因為這裡沒有填色。", False, 12),
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
        ws.row_dimensions[i].height = 28 if title else (48 if len(text) > 80 else 18)
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
