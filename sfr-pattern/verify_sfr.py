#!/usr/bin/env python3
"""Recalculate the workbook and check it against the half-angle curve model."""

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
    N_CURVE,
    Pattern,
    choose_mode,
    example_curve,
    fit_half_angle,
    piece_stats,
    rule_point_count,
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
    heights, angles = example_curve()
    fit = fit_half_angle(heights, angles)
    return Pattern(sw, sh, center, center, side, 5.0, 500.0, fit)


def parse_librecad(text):
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    cmds = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line == "li":
            p1 = tuple(float(v) for v in lines[i + 1].split(","))
            p2 = tuple(float(v) for v in lines[i + 2].split(","))
            if lines[i + 3] != "k":
                raise AssertionError(f"li at {i} is not followed by k: {lines[i:i+4]}")
            cmds.append(("LINE", p1, p2))
            i += 4
        elif line == "a3":
            pts = [tuple(float(v) for v in lines[i + 1 + k].split(",")) for k in range(3)]
            if lines[i + 4] != "k":
                raise AssertionError(f"a3 at {i} is not followed by k: {lines[i:i+5]}")
            cmds.append(("ARC", *pts))
            i += 5
        else:
            raise AssertionError(f"unexpected LibreCAD token {line!r}")
    return cmds


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

    assert rule_point_count(999) == "不符合"
    assert rule_point_count(1000) == "警告"
    assert rule_point_count(9999) == "警告"
    assert rule_point_count(10000) == "符合建議"
    say("point-count rule: <1000 fail, <10000 warn, 10000 meets the recommendation")

    focal = 6.0
    linear_h = [4.2 * i / (N_CURVE - 1) for i in range(N_CURVE)]
    linear_ang = [math.degrees(math.atan(h / focal)) for h in linear_h]
    linear = fit_half_angle(linear_h, linear_ang)
    assert linear.rmse_deg < 1e-8
    assert_close(linear.focal, focal, 1e-8, "linear paraxial f")
    cx, cy = linear.chart_xy(1.2, -0.4, 500.0)
    ix, iy = linear.ideal_xy(1.2, -0.4, 500.0)
    assert math.hypot(cx - ix, cy - iy) < 1e-6
    say(f"linear h = f·tanθ collapses to a straight chart, f={linear.focal:.6f}")

    pat = default_pattern()
    say(
        f"example fit f={pat.fit.focal:.5f} mm, HFOV={pat.fit.fov_deg(pat.sensor_w / 2):.4f}°, "
        f"angle RMSE={pat.fit.rmse_deg:.6f}°, points={pat.fit.count}"
    )
    assert pat.fit.count == 10000
    assert pat.fit.h_scale >= 0.5 * math.hypot(pat.sensor_w, pat.sensor_h)
    assert 50 < pat.fit.fov_deg(pat.sensor_w / 2) < 70

    book = Book()
    book.calc()
    corners, sensor_edges = pat.sensor_points()
    chart_edges = pat.chart_edges()
    ideal_edges = pat.ideal_edges()

    assert book.get("規則", "H6") == "通過"
    assert book.get("參數", "J7") == 10000
    assert book.get("規則", "C13") == "符合建議"
    assert_close(book.get("參數", "J5"), pat.sensor_w, 1e-9, "sensor width")
    assert_close(book.get("參數", "J8"), pat.fit.h_scale, 1e-9, "h scale")
    assert_close(book.get("參數", "J9"), pat.fit.focal, 1e-6, "paraxial f")
    assert_close(book.get("參數", "J10"), pat.fit.fov_deg(pat.sensor_w / 2), 1e-4, "HFOV")
    assert_close(book.get("參數", "J11"), pat.fit.fov_deg(pat.sensor_h / 2), 1e-4, "VFOV")
    assert_close(book.get("參數", "J12"), pat.fit.fov_deg(0.5 * math.hypot(pat.sensor_w, pat.sensor_h)), 1e-4, "DFOV")
    assert book.get("參數", "J13") < 0.01
    assert_close(book.get("參數", "J18"), pat.center_x, 1e-9, "center x")
    for index, coef in enumerate(pat.fit.coef):
        assert_close(book.get("參數", f"J{53 + index}"), coef, 1e-8, f"d{index}")
    say(
        f"rules pass, HFOV {book.get('參數', 'J10'):.4f}°, "
        f"RMSE {book.get('參數', 'J13'):.6f}°, max shift {book.get('參數', 'J27'):.3f} mm"
    )

    for i, (sx, sy) in enumerate(corners):
        assert_close(book.get("參數", f"J{41 + i}"), sx, 1e-9, f"corner {i} x")
        assert_close(book.get("參數", f"K{41 + i}"), sy, 1e-9, f"corner {i} y")

    max_chart_err = 0.0
    max_ideal_err = 0.0
    max_sensor_err = 0.0
    for e in range(4):
        for i in range(33):
            row = 2 + e * 33 + i
            sx = book.get("取樣", f"D{row}")
            sy = book.get("取樣", f"E{row}")
            cx = book.get("取樣", f"J{row}")
            cy = book.get("取樣", f"K{row}")
            ix = book.get("取樣", f"L{row}")
            iy = book.get("取樣", f"M{row}")
            max_sensor_err = max(max_sensor_err, math.hypot(sx - sensor_edges[e][i][0], sy - sensor_edges[e][i][1]))
            max_chart_err = max(max_chart_err, math.hypot(cx - chart_edges[e][i][0], cy - chart_edges[e][i][1]))
            max_ideal_err = max(max_ideal_err, math.hypot(ix - ideal_edges[e][i][0], iy - ideal_edges[e][i][1]))
    say(
        f"chart matches the curve within {max_chart_err:.3e} mm; "
        f"ideal within {max_ideal_err:.3e} mm; sensor {max_sensor_err:.3e} mm"
    )
    assert max_chart_err < 1e-4
    assert max_ideal_err < 1e-4
    assert max_sensor_err < 1e-9

    modes = [book.get("擬合", f"B{2 + e}") for e in range(4)]
    chords = [book.get("擬合", f"E{2 + e}") for e in range(4)]
    arcs = [book.get("擬合", f"F{2 + e}") for e in range(4)]
    say("modes " + " / ".join(str(m) for m in modes))
    say("chord mm " + ", ".join(f"{v:.4f}" for v in chords))
    say("arc error mm " + ", ".join(f"{v:.6f}" for v in arcs))
    assert modes == ["ARC", "ARC", "ARC", "ARC"]
    assert all(c > 0.02 for c in chords)
    assert all(a <= 0.02 for a in arcs)

    for e, edge in enumerate(chart_edges):
        assert choose_mode(edge, 0.02)[0] == "ARC"
        _chord, arc_err, _ok = piece_stats(edge, 0, 32)
        assert_close(arcs[e], arc_err, 1e-5, f"excel arc error edge {e}")
        ax, ay = edge[0]
        bx, by = edge[-1]
        mx, my = edge[16]
        cmx, cmy = (ax + bx) / 2, (ay + by) / 2
        toward_origin = (mx - cmx) * (-cmx) + (my - cmy) * (-cmy)
        assert toward_origin > 1.0
    say("arc residuals match the curve; edge midpoints bow toward the optical axis")

    script = book.get("指令", "B2")
    (ART / "sfr_pattern_default.scr").write_text(script + ("\n" if not script.endswith("\n") else ""), encoding="utf-8")
    cmds = parse_scr(script)
    assert len(cmds) == 4 and all(c[0] == "ARC" for c in cmds)
    for e, cmd in enumerate(cmds):
        _, p0, pm, p1 = cmd
        for got, idx in ((p0, 0), (pm, 16), (p1, 32)):
            exp = chart_edges[e][idx]
            assert_close(got[0], exp[0], 5e-5, f"arc {e} x{idx}")
            assert_close(got[1], exp[1], 5e-5, f"arc {e} y{idx}")
        if e:
            prev = cmds[e - 1][3]
            assert_close(prev[0], p0[0], 1e-6, "join x")
            assert_close(prev[1], p0[1], 1e-6, "join y")
    assert_close(cmds[-1][3][0], cmds[0][1][0], 1e-6, "close x")
    assert_close(cmds[-1][3][1], cmds[0][1][1], 1e-6, "close y")
    assert "hfov_deg=" in script
    assert script.endswith("\n")
    closing = script.strip().splitlines()[-1]
    assert closing == f"{cmds[0][1][0]:.6f},{cmds[0][1][1]:.6f}"
    say(f"SCR has 4 terminated ARC commands, {len(script.splitlines())} lines, and ends on the return to the first corner")

    librecad = book.get("指令", "E2")
    (ART / "sfr_pattern_librecad.txt").write_text(
        librecad + ("\n" if not librecad.endswith("\n") else ""),
        encoding="utf-8",
    )
    lc_cmds = parse_librecad(librecad)
    assert len(lc_cmds) == 4 and all(c[0] == "ARC" for c in lc_cmds)
    for e, cmd in enumerate(lc_cmds):
        _, p0, pm, p1 = cmd
        for got, idx in ((p0, 0), (pm, 16), (p1, 32)):
            exp = chart_edges[e][idx]
            assert_close(got[0], exp[0], 5e-5, f"librecad arc {e} x{idx}")
            assert_close(got[1], exp[1], 5e-5, f"librecad arc {e} y{idx}")
        if e:
            prev = lc_cmds[e - 1][3]
            assert_close(prev[0], p0[0], 1e-6, "librecad join x")
            assert_close(prev[1], p0[1], 1e-6, "librecad join y")
    assert_close(lc_cmds[-1][3][0], lc_cmds[0][1][0], 1e-6, "librecad close x")
    assert_close(lc_cmds[-1][3][1], lc_cmds[0][1][1], 1e-6, "librecad close y")
    assert librecad.endswith("\n")
    assert librecad.strip().splitlines()[-1] == "k"
    say(f"LibreCAD file has 4 a3 arcs, each ended by k, {len(librecad.splitlines())} lines")

    judgements = [(book.get("規則", f"A{r}"), book.get("規則", f"C{r}")) for r in range(5, 19)]
    for name, judge in judgements:
        say(f"  {judge}  {name}")
    assert all(j != "不符合" for _, j in judgements)
    joined = "".join(name or "" for name, _ in judgements)
    assert "對比" not in joined
    assert "暗區" not in joined

    # A loose tolerance turns the same bowed edges into LINE commands.
    book.calc({("參數", "B24"): 1})
    assert [book.get("擬合", f"B{2 + e}") for e in range(4)] == ["LINE"] * 4
    straight = parse_scr(book.get("指令", "B2"))
    assert len(straight) == 4 and all(c[0] == "LINE" for c in straight)
    lc_straight = parse_librecad(book.get("指令", "E2"))
    assert len(lc_straight) == 4 and all(c[0] == "LINE" for c in lc_straight)
    assert_close(lc_straight[-1][2][0], lc_straight[0][1][0], 1e-6, "librecad line close x")
    assert_close(lc_straight[-1][2][1], lc_straight[0][1][1], 1e-6, "librecad line close y")
    say("tolerance 1 mm -> four LINE commands in ZWCAD and LibreCAD")

    book.calc({("參數", "B16"): 0})
    assert book.get("規則", "H6") == "不符合"
    assert book.get("規則", "C8") == "不符合"
    say("tilt 0° is rejected")

    book.calc({("參數", "B8"): 1})
    assert book.get("規則", "H6") == "不符合"
    assert book.get("規則", "C12") == "不符合"
    say("field 1.0 at 45° is rejected because the edges leave the sensor")

    book.calc({("參數", "B11"): 0})
    assert book.get("規則", "C6") == "不符合"
    say("zero test distance is rejected")

    # Sensor larger than the example curve: horizontal FOV would extrapolate.
    book.calc({("參數", "B5"): 8000, ("參數", "B6"): 8000})
    assert book.get("規則", "C14") == "不符合"
    say("curve that stops inside the sensor half-diagonal is rejected")

    plot(pat, sensor_edges, chart_edges, ideal_edges, arcs)
    (ART / "verify_log.txt").write_text("\n".join(log) + "\n", encoding="utf-8")
    shutil.copy(XLSX, ART / XLSX.name)
    say("artifacts written")


def plot(pat, sensor_edges, chart_edges, ideal_edges, arcs):
    font_path = "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"
    if os.path.exists(font_path):
        font_manager.fontManager.addfont(font_path)
        plt.rcParams["font.family"] = "WenQuanYi Micro Hei"
    plt.rcParams["axes.unicode_minus"] = False
    hfov = pat.fit.fov_deg(pat.sensor_w / 2)

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
    for e, (ideal, pre) in enumerate(zip(ideal_edges, chart_edges)):
        ax.plot([p[0] for p in ideal], [p[1] for p in ideal], color="#AEB6BF", lw=1.2, label="未預變形" if e == 0 else None)
        ax.plot([p[0] for p in pre], [p[1] for p in pre], color="#C65911", lw=2, label="要畫的邊" if e == 0 else None)
    ax.set_aspect("equal")
    ax.set_xlabel("圖卡 X mm")
    ax.set_ylabel("圖卡 Y mm")
    ax.set_title(f"圖卡邊線（水平視場 {hfov:.2f}°，由半像高曲線算出）")
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
    ax.set_title(f"四邊相對直線的拱起；單弧誤差 {arcs[0] * 1000:.2f} μm")
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
