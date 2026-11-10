"""Reference geometry for an Imatest slanted-square SFR edge pattern.

The square is straight on the sensor. Chart coordinates come from a fitted
curve of half image height versus object-space half field angle:

    tan(θ) = d1 u + d3 u^3 + d5 u^5 + d7 u^7 + d9 u^9
    u = h / h_scale,  h_scale = max h in the distortion table

A point at sensor (x, y) with radius h is drawn at chart radius L·tan(θ(h)),
in the same direction. L is the entrance-pupil (nodal) distance to the chart.
The paraxial focal length is h_scale / d1, so the undistorted chart is L·h/f.
Horizontal field of view is twice the half-angle at half the sensor width.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

N_CURVE = 10000
POWERS = (1, 3, 5, 7, 9)
EXAMPLE_F = 6.0
EXAMPLE_K1 = -0.3
EXAMPLE_K2 = 0.05
EXAMPLE_H_MAX = 4.2


def barrel_image_height(tan_theta, focal=EXAMPLE_F, k1=EXAMPLE_K1, k2=EXAMPLE_K2):
    """Synthetic barrel curve used only to fill the example table.

    h = f·t·(1 + k1 t^2 + k2 t^4), t = tan(θ). k1 < 0 pulls image height in.
    """
    t = tan_theta
    return focal * t * (1.0 + k1 * t * t + k2 * t ** 4)


def solve_tan_theta(image_height, focal=EXAMPLE_F, k1=EXAMPLE_K1, k2=EXAMPLE_K2):
    """Invert barrel_image_height. Returns t = tan(θ) for a given h."""
    if image_height <= 0:
        return 0.0
    t = image_height / focal
    for _ in range(40):
        ht = barrel_image_height(t, focal, k1, k2)
        deriv = focal * (
            (1.0 + k1 * t * t + k2 * t ** 4) + t * (2.0 * k1 * t + 4.0 * k2 * t ** 3)
        )
        if abs(deriv) < 1e-18:
            break
        step = (ht - image_height) / deriv
        t -= step
        if abs(step) < 1e-15:
            break
    return t


def example_curve(n=N_CURVE, h_max=EXAMPLE_H_MAX):
    """n samples of (half image height mm, half field angle degrees), including 0."""
    if n < 2:
        raise ValueError("need at least two samples")
    tmax = solve_tan_theta(h_max)
    heights = []
    angles = []
    for i in range(n):
        t = tmax * i / (n - 1)
        heights.append(barrel_image_height(t))
        angles.append(math.degrees(math.atan(t)))
    return heights, angles


@dataclass
class AngleFit:
    coef: tuple
    h_scale: float
    count: int
    rmse_deg: float

    @property
    def focal(self):
        return self.h_scale / self.coef[0]

    def tan_theta(self, image_height):
        if image_height <= 0 or self.h_scale <= 0:
            return 0.0
        u = image_height / self.h_scale
        total = 0.0
        for coef, power in zip(self.coef, POWERS):
            total += coef * u ** power
        return total

    def half_angle_deg(self, image_height):
        return math.degrees(math.atan(self.tan_theta(image_height)))

    def fov_deg(self, half_height):
        return 2.0 * self.half_angle_deg(half_height)

    def chart_xy(self, x, y, distance):
        h = math.hypot(x, y)
        if h < 1e-15:
            return 0.0, 0.0
        radius = distance * self.tan_theta(h)
        return radius * x / h, radius * y / h

    def ideal_xy(self, x, y, distance):
        scale = distance / self.focal
        return x * scale, y * scale


def fit_half_angle(heights, angles_deg):
    """Least squares of tan(θ) on odd powers of u = h / max(h). Drops non-numeric rows."""
    h = np.asarray(heights, dtype=float)
    ang = np.asarray(angles_deg, dtype=float)
    mask = np.isfinite(h) & np.isfinite(ang) & (h >= 0)
    h = h[mask]
    ang = ang[mask]
    if h.size < 5 or float(np.max(h)) <= 0:
        raise ValueError("distortion table needs a positive image-height range")
    h_scale = float(np.max(h))
    u = h / h_scale
    tan_theta = np.tan(np.radians(ang))
    design = np.column_stack([u ** power for power in POWERS])
    coef, *_ = np.linalg.lstsq(design, tan_theta, rcond=None)
    pred = design @ coef
    pred_ang = np.degrees(np.arctan(pred))
    rmse = float(np.sqrt(np.mean((pred_ang - ang) ** 2)))
    return AngleFit(tuple(float(c) for c in coef), h_scale, int(h.size), rmse)


def beta_from_tilt(tilt_deg):
    """Smallest angle from the nearest horizontal or vertical axis, 0..45."""
    a = abs(tilt_deg) % 90.0
    return min(a, 90.0 - a)


def circle_3pt(ax, ay, bx, by, cx, cy):
    d = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-9:
        return None
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) + (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) + (cx * cx + cy * cy) * (bx - ax)) / d
    r = math.hypot(ax - ux, ay - uy)
    if r > 1e6:
        return None
    return ux, uy, r


def dist_point_line(px, py, ax, ay, bx, by):
    length = math.hypot(bx - ax, by - ay)
    if length < 1e-12:
        return 0.0
    return abs((bx - ax) * (py - ay) - (by - ay) * (px - ax)) / length


def dist_point_circle(px, py, circ):
    if circ is None:
        return None
    ux, uy, r = circ
    return abs(math.hypot(px - ux, py - uy) - r)


@dataclass
class Pattern:
    sensor_w: float
    sensor_h: float
    center_x: float
    center_y: float
    side: float
    tilt_deg: float
    distance: float
    fit: AngleFit
    samples: int = 33

    def sensor_points(self):
        half = self.side / 2.0
        c = math.cos(math.radians(self.tilt_deg))
        s = math.sin(math.radians(self.tilt_deg))
        local = [(-half, -half), (half, -half), (half, half), (-half, half)]
        corners = []
        for xl, yl in local:
            corners.append((self.center_x + xl * c - yl * s, self.center_y + xl * s + yl * c))
        edges = []
        n = self.samples
        for e in range(4):
            x1, y1 = corners[e]
            x2, y2 = corners[(e + 1) % 4]
            pts = []
            for i in range(n):
                t = i / (n - 1)
                pts.append((x1 * (1 - t) + x2 * t, y1 * (1 - t) + y2 * t))
            edges.append(pts)
        return corners, edges

    def _map_edges(self, mapper):
        _, edges = self.sensor_points()
        out = []
        for edge in edges:
            out.append([mapper(x, y) for x, y in edge])
        return out

    def chart_edges(self):
        return self._map_edges(lambda x, y: self.fit.chart_xy(x, y, self.distance))

    def ideal_edges(self):
        return self._map_edges(lambda x, y: self.fit.ideal_xy(x, y, self.distance))

    def chart_center(self):
        return self.fit.chart_xy(self.center_x, self.center_y, self.distance)


def max_chord_dev(points):
    ax, ay = points[0]
    bx, by = points[-1]
    return max(dist_point_line(px, py, ax, ay, bx, by) for px, py in points)


def piece_stats(points, i0, i1):
    """Chord and arc deviation of samples i0..i1 inclusive. Midpoint is the arc sample."""
    span = points[i0 : i1 + 1]
    ax, ay = span[0]
    bx, by = span[-1]
    chord = max(dist_point_line(px, py, ax, ay, bx, by) for px, py in span)
    mid = i0 + (i1 - i0) // 2
    circ = circle_3pt(points[i0][0], points[i0][1], points[mid][0], points[mid][1], points[i1][0], points[i1][1])
    if circ is None:
        return chord, None, False
    arc = max(dist_point_circle(px, py, circ) for px, py in span)
    return chord, arc, True


def choose_mode(points, tol):
    """LINE, ARC, ARC4, ARC8, or POLY. Pieces inside ARC4/ARC8 may still be lines."""
    n = len(points)
    assert n == 33
    whole, whole_arc, whole_ok = piece_stats(points, 0, 32)
    if whole <= tol:
        return "LINE", []
    if whole_ok and whole_arc is not None and whole_arc <= tol:
        return "ARC", [True]
    for divisions, name in ((4, "ARC4"), (8, "ARC8")):
        step = 32 // divisions
        flags = []
        ok = True
        for s in range(divisions):
            chord, arc, good = piece_stats(points, s * step, (s + 1) * step)
            use_arc = bool(good and arc is not None and arc <= tol)
            if not (chord <= tol or use_arc):
                ok = False
                break
            flags.append(use_arc)
        if ok:
            return name, flags
    return "POLY", []


def edge_angle_deg(p0, p1):
    return math.degrees(math.atan2(p1[1] - p0[1], p1[0] - p0[0]))


def rule_tilt(tilt_deg):
    beta = beta_from_tilt(tilt_deg)
    if beta < 2.0 or beta > 43.0:
        return "不符合", beta
    if 3.0 <= beta <= 7.0:
        return "符合建議", beta
    return "警告", beta


def rule_edge_px(edge_px):
    if edge_px < 10 or edge_px > 2000:
        return "不符合"
    if edge_px < 80 or edge_px > 500:
        return "警告"
    if edge_px <= 300:
        return "符合建議"
    return "符合"


def rule_point_count(count):
    if count < 1000:
        return "不符合"
    if count < 10000:
        return "警告"
    return "符合建議"
