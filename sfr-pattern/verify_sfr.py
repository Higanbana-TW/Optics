#!/usr/bin/env python3
"""Recalculate the workbook and check it against the independent geometry model."""

from __future__ import annotations

import math
import os
import shutil
from pathlib import Path

import formulas
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

from sfr_geometry import (
    Pattern,
    choose_mode,
    distort,
    fit_radial_polynomial,
    inverse_analytic,
    inverse_numeric,
    piece_stats,
)

XLSX = Path("/workspace/sfr-pattern/Imatest_SFR_pattern_ZWCAD.xlsx")
ART = Path("/opt/cursor/artifacts")
FILE = XLSX.name


def cell_id(sheet, addr):
    return f"'[{FILE}]{sheet}'!{addr}"


def unwrap(value):
    if hasattr(value, "value"):
        value = value.value
    if hasattr(value, "shape"):
        if value.shape == () or value.size == 1:
            item = value.reshape(-1)[0]
            if hasattr(item, "item"):
                return item.item()
            return item
        return value
    return value


class Book:
    def __init__(self):
        self.model = formulas.ExcelModel().loads(str(XLSX)).finish()
        self.sol = None

    def calc(self, overrides=None):
        overrides = overrides or {}
        inputs = {cell_id(sheet, addr): value for (sheet, addr), value in overrides.items()}
        self.sol = self.model.calculate(inputs or None)
        return self

    def get(self, sheet, addr):
        key = cell_id(sheet, addr)
        if key not in self.sol:
            raise KeyError(key)
        return unwrap(self.sol[key])


def default_pattern():
    sw = 4000 * 1.55 / 1000
    sh = 3000 * 1.55 / 1000
    radius = 0.5 * math.hypot(sw, sh)
    center = 0.7 * radius * math.cos(math.radians(45))
    side = 200 * 1.55 / 1000
    focal = 6.0
    scale = (500.0 - focal) / focal
    return Pattern(sw, sh, center, center, side, 5.0, focal, scale, -0.3, 0.05, 0.0, 0.0, 0.0)


def parse_scr(text):
    lines = text.split("\n")
    cmds = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line == "_.LINE":
            p1 = tuple(float(v) for v in lines[i + 1].split(","))
            p2 = tuple(float(v) for v in lines[i + 2].split(","))
            if i + 3 >= len(lines) or lines[i + 3].strip() != "":
                raise AssertionError(f"LINE at {i} is not terminated by a blank line: {lines[i:i+5]}")
            cmds.append(("LINE", p1, p2))
            i += 4
        elif line == "_.ARC":
            pts = [tuple(float(v) for v in lines[i + 1 + k].split(",")) for k in range(3)]
            cmds.append(("ARC", *pts))
            i += 4
        else:
            i += 1
    return cmds


def assert_close(a, b, tol, msg):
    if abs(a - b) > tol:
        raise AssertionError(f"{msg}: {a} vs {b}, tol {tol}")


def main():
    ART.mkdir(parents=True, exist_ok=True)
    log = []

    def say(msg):
        print(msg, flush=True)
        log.append(msg)

    d2, d4, d6 = fit_radial_polynomial(
        [(rho, -0.02 * rho ** 2 + 0.01 * rho ** 4) for rho in (0, 0.2, 0.4, 0.5, 0.6, 0.7, 0.85, 1)]
    )
    assert_close(d2, -0.02, 1e-12, "poly D2")
    assert_close(d4, 0.01, 1e-12, "poly D4")
    assert_close(d6, 0.0, 1e-12, "poly D6")
    say("polynomial fit recovers D2=-0.02 D4=0.01 D6=0")

    # Jacobian cross-check
    worst = 0.0
    for xd, yd in ((0.2, 0.05), (0.45, 0.3), (0.1, -0.22), (0.0, 0.0)):
        a = inverse_analytic(xd, yd, -0.3, 0.05, 0.0, 0.0, 0.0)
        b = inverse_numeric(xd, yd, -0.3, 0.05, 0.0, 0.0, 0.0)
        worst = max(worst, math.hypot(a[0] - b[0], a[1] - b[1]))
        fx, fy = distort(*a, -0.3, 0.05, 0.0, 0.0, 0.0)
        assert math.hypot(fx - xd, fy - yd) < 1e-12
    say(f"analytic Newton matches finite-difference Newton within {worst:.3e}")

    book = Book()
    book.calc()
    pat = default_pattern()
    corners, sensor_edges = pat.sensor_points()
    chart_edges = pat.chart_edges()

    assert book.get("規則", "H6") == "通過"
    assert book.get("參數", "J20") == 5
    assert_close(book.get("參數", "J5"), pat.sensor_w, 1e-9, "sensor width")
    assert_close(book.get("參數", "J8"), pat.obj_scale, 1e-9, "scale")
    assert_close(book.get("參數", "J13"), pat.center_x, 1e-9, "center x")
    assert_close(book.get("參數", "J51"), 0.0, 1e-9, "inverse error mm")
    say(f"rules pass, inverse error {book.get('參數', 'J51'):.3e} mm, max shift {book.get('參數', 'J28'):.3f} mm")

    for i, (sx, sy) in enumerate(corners):
        assert_close(book.get("參數", f"J{41+i}"), sx, 1e-9, f"corner {i} x")
        assert_close(book.get("參數", f"K{41+i}"), sy, 1e-9, f"corner {i} y")

    max_chart_err = 0.0
    max_sensor_err = 0.0
    for e in range(4):
        for i in range(33):
            row = 2 + e * 33 + i
            sx = book.get("取樣", f"D{row}")
            sy = book.get("取樣", f"E{row}")
            cx = book.get("取樣", f"J{row}")
            cy = book.get("取樣", f"K{row}")
            max_sensor_err = max(max_sensor_err, math.hypot(sx - sensor_edges[e][i][0], sy - sensor_edges[e][i][1]))
            max_chart_err = max(max_chart_err, math.hypot(cx - chart_edges[e][i][0], cy - chart_edges[e][i][1]))
            # Land back on the straight sensor edge after forward distortion.
            xu = cx / (pat.focal * pat.obj_scale)
            yu = cy / (pat.focal * pat.obj_scale)
            xd, yd = distort(xu, yu, pat.k1, pat.k2, pat.k3, pat.p1, pat.p2)
            max_sensor_err = max(max_sensor_err, math.hypot(xd * pat.focal - sx, yd * pat.focal - sy))
    say(f"chart matches independent model within {max_chart_err:.3e} mm; sensor closure {max_sensor_err:.3e} mm")
    assert max_chart_err < 1e-8
    assert max_sensor_err < 1e-8

    modes = [book.get("擬合", f"B{2+e}") for e in range(4)]
    chords = [book.get("擬合", f"E{2+e}") for e in range(4)]
    arcs = [book.get("擬合", f"F{2+e}") for e in range(4)]
    say("modes " + " / ".join(modes))
    say("chord mm " + ", ".join(f"{v:.4f}" for v in chords))
    say("arc error mm " + ", ".join(f"{v:.5f}" for v in arcs))
    assert modes == ["ARC", "ARC", "ARC", "ARC"]
    assert all(c > 0.02 for c in chords)
    assert all(a <= 0.02 for a in arcs)

    for e, edge in enumerate(chart_edges):
        assert choose_mode(edge, 0.02)[0] == "ARC"
        _chord, arc_err, _ok = piece_stats(edge, 0, 32)
        assert_close(arcs[e], arc_err, 1e-8, f"excel arc error edge {e}")
        ax, ay = edge[0]
        bx, by = edge[-1]
        mx, my = edge[16]
        cmx, cmy = (ax + bx) / 2, (ay + by) / 2
        toward_origin = (mx - cmx) * (-cmx) + (my - cmy) * (-cmy)
        assert toward_origin > 1.0
    say("arc residuals match the geometry model; edges bow toward the optical axis")

    script = book.get("指令", "B2")
    (ART / "sfr_pattern_default.scr").write_text(script + ("\n" if not script.endswith("\n") else ""), encoding="utf-8")
    cmds = parse_scr(script)
    assert len(cmds) == 4 and all(c[0] == "ARC" for c in cmds)
    for e, cmd in enumerate(cmds):
        _, p0, pm, p1 = cmd
        for got, idx in ((p0, 0), (pm, 16), (p1, 32)):
            exp = chart_edges[e][idx]
            assert_close(got[0], exp[0], 5e-7, f"arc {e} x{idx}")
            assert_close(got[1], exp[1], 5e-7, f"arc {e} y{idx}")
        # Shared vertices close the loop.
        if e:
            prev = cmds[e - 1][3]
            assert_close(prev[0], p0[0], 1e-6, "join x")
            assert_close(prev[1], p0[1], 1e-6, "join y")
    assert_close(cmds[-1][3][0], cmds[0][1][0], 1e-6, "close x")
    assert_close(cmds[-1][3][1], cmds[0][1][1], 1e-6, "close y")
    say(f"SCR has 4 terminated ARC commands, {len(script.splitlines())} lines")

    judgements = [(book.get("規則", f"A{r}"), book.get("規則", f"C{r}")) for r in range(5, 16)]
    for name, judge in judgements:
        say(f"  {judge}  {name}")
    assert all(j != "不符合" for _, j in judgements)
    assert "對比" not in "".join(name or "" for name, _ in judgements)
    assert "暗區" not in "".join(name or "" for name, _ in judgements)

    # Zero distortion collapses to straight LINE commands.
    book.calc({("參數", "B26"): 0, ("參數", "B27"): 0})
    assert [book.get("擬合", f"B{2+e}") for e in range(4)] == ["LINE"] * 4
    assert book.get("參數", "J28") < 1e-9
    straight = parse_scr(book.get("指令", "B2"))
    assert len(straight) == 4 and all(c[0] == "LINE" for c in straight)
    say("k=0 -> four LINE commands, displacement ~ 0")

    book.calc({("參數", "B20"): 0})
    assert book.get("規則", "H6") == "不符合"
    assert book.get("規則", "C8") == "不符合"
    say("tilt 0° is rejected")

    book.calc({("參數", "B8"): 1})
    assert book.get("規則", "H6") == "不符合"
    assert book.get("規則", "C12") == "不符合"
    say("field 1.0 at 45° is rejected because the edges leave the sensor")

    book.calc({("參數", "B25"): "百分比多項式", ("參數", "B31"): -0.04})
    assert book.get("規則", "H6") == "通過"
    assert book.get("參數", "J51") < 1e-9
    assert book.get("參數", "J28") > 1.0
    say(f"percent polynomial still converges, shift {book.get('參數', 'J28'):.3f} mm, rules pass")

    rhos = [0, 0.2, 0.4, 0.5, 0.6, 0.7, 0.85, 1]
    overrides = {("參數", "B25"): "視場畸變表"}
    for i, rho in enumerate(rhos):
        overrides[("參數", f"C{37+i}")] = 100 * (-0.02 * rho ** 2 + 0.01 * rho ** 4)
    book.calc(overrides)
    assert_close(book.get("參數", "AA51"), -0.02, 1e-10, "table D2")
    assert_close(book.get("參數", "AB51"), 0.01, 1e-10, "table D4")
    assert_close(book.get("參數", "AC51"), 0.0, 1e-10, "table D6")
    assert book.get("規則", "C13") == "符合"
    say("distortion table refits to D2=-0.02, D4=0.01, D6=0")

    # Plots use the default solution again.
    plot(pat, sensor_edges, chart_edges, arcs[0])
    (ART / "verify_log.txt").write_text("\n".join(log) + "\n", encoding="utf-8")
    shutil.copy(XLSX, ART / XLSX.name)
    say("artifacts written")


def plot(pat, sensor_edges, chart_edges, arc_err_mm):
    font_path = "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"
    if os.path.exists(font_path):
        font_manager.fontManager.addfont(font_path)
        plt.rcParams["font.family"] = "WenQuanYi Micro Hei"
    plt.rcParams["axes.unicode_minus"] = False

    fig, ax = plt.subplots(figsize=(7.2, 5.6), dpi=140)
    sw, sh = pat.sensor_w, pat.sensor_h
    ax.plot([-sw / 2, sw / 2, sw / 2, -sw / 2, -sw / 2], [-sh / 2, -sh / 2, sh / 2, sh / 2, -sh / 2], color="#85929E", lw=1)
    for edge in sensor_edges:
        xs, ys = zip(*edge)
        ax.plot(xs, ys, color="#1F4E79", lw=2)
    ax.scatter([pat.center_x], [pat.center_y], color="#C65911", s=18, zorder=3)
    ax.scatter([0], [0], color="#85929E", s=12)
    ax.set_aspect("equal")
    ax.set_xlabel("X mm")
    ax.set_ylabel("Y mm")
    ax.set_title("Sensor 上的直斜方塊（0.7 視場，45°，傾斜 5°）")
    ax.grid(True, color="#E5E8EB", lw=0.6)
    fig.tight_layout()
    fig.savefig(ART / "sensor_straight.png")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.2, 6.2), dpi=140)
    for e, (ideal_src, pre) in enumerate(zip(pat.sensor_points()[1], chart_edges)):
        ideal = [(x * pat.obj_scale, y * pat.obj_scale) for x, y in ideal_src]
        ax.plot([p[0] for p in ideal], [p[1] for p in ideal], color="#AEB6BF", lw=1.2, label="未預變形" if e == 0 else None)
        ax.plot([p[0] for p in pre], [p[1] for p in pre], color="#C65911", lw=2, label="要畫的邊" if e == 0 else None)
    ax.set_aspect("equal")
    ax.set_xlabel("圖卡 X mm")
    ax.set_ylabel("圖卡 Y mm")
    ax.set_title("圖卡邊線：桶形鏡頭要先畫成枕形")
    ax.legend(frameon=False)
    ax.grid(True, color="#E5E8EB", lw=0.6)
    fig.tight_layout()
    fig.savefig(ART / "chart_predistorted.png")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.2, 4.4), dpi=140)
    for e, edge in enumerate(chart_edges):
        ax.plot(*normal_offset(edge), color="#C65911", lw=1.6, label="預變形邊" if e == 0 else None)
    ax.axhline(0, color="#85929E", lw=1, label="直線")
    ax.set_xlabel("沿邊距離 mm")
    ax.set_ylabel("偏離直線 mm")
    ax.set_title(f"四邊相對直線的拱起；單弧誤差 {arc_err_mm*1000:.2f} μm")
    ax.legend(frameon=False)
    ax.grid(True, color="#E5E8EB", lw=0.6)
    fig.tight_layout()
    fig.savefig(ART / "edge_arc_fit.png")
    plt.close(fig)


def normal_offset(edge):
    ax, ay = edge[0]
    bx, by = edge[-1]
    length = math.hypot(bx - ax, by - ay)
    tx, ty = (bx - ax) / length, (by - ay) / length
    nx, ny = -ty, tx
    xs, ys = [], []
    for px, py in edge:
        vx, vy = px - ax, py - ay
        xs.append(vx * tx + vy * ty)
        ys.append(vx * nx + vy * ny)
    return xs, ys


if __name__ == "__main__":
    main()
