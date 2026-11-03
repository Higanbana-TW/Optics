"""Reference geometry for an Imatest slanted-square SFR edge pattern.

The square is defined straight on the sensor. Chart coordinates are the
inverse-distorted object points, so a lens with the entered distortion
records those edges as straight.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


def distort(x, y, k1, k2, k3, p1, p2):
    r2 = x * x + y * y
    r4 = r2 * r2
    r6 = r4 * r2
    rad = 1.0 + k1 * r2 + k2 * r4 + k3 * r6
    xd = x * rad + 2.0 * p1 * x * y + p2 * (r2 + 2.0 * x * x)
    yd = y * rad + p1 * (r2 + 2.0 * y * y) + 2.0 * p2 * x * y
    return xd, yd


def inverse_analytic(xd, yd, k1, k2, k3, p1, p2, n=8):
    """Invert Brown-Conrady with analytic Newton steps. xd, yd are distorted."""
    x = float(xd)
    y = float(yd)
    for _ in range(n):
        r2 = x * x + y * y
        r4 = r2 * r2
        r6 = r4 * r2
        rad = 1.0 + k1 * r2 + k2 * r4 + k3 * r6
        q = k1 + 2.0 * k2 * r2 + 3.0 * k3 * r4
        tx = 2.0 * p1 * x * y + p2 * (r2 + 2.0 * x * x)
        ty = p1 * (r2 + 2.0 * y * y) + 2.0 * p2 * x * y
        fx = x * rad + tx - xd
        fy = y * rad + ty - yd
        jxx = rad + 2.0 * q * x * x + (2.0 * p1 * y + 6.0 * p2 * x)
        jxy = 2.0 * q * x * y + (2.0 * p1 * x + 2.0 * p2 * y)
        jyx = 2.0 * q * x * y + (2.0 * p1 * x + 2.0 * p2 * y)
        jyy = rad + 2.0 * q * y * y + (6.0 * p1 * y + 2.0 * p2 * x)
        det = jxx * jyy - jxy * jyx
        if abs(det) < 1e-14:
            break
        x += (-jyy * fx + jxy * fy) / det
        y += (jyx * fx - jxx * fy) / det
    return x, y


def inverse_numeric(xd, yd, k1, k2, k3, p1, p2, n=12):
    """Same inverse, but the Jacobian is finite-difference only."""
    x = float(xd)
    y = float(yd)
    eps = 1e-7

    def residual(px, py):
        fx, fy = distort(px, py, k1, k2, k3, p1, p2)
        return fx - xd, fy - yd

    for _ in range(n):
        fx, fy = residual(x, y)
        fx1, fy1 = residual(x + eps, y)
        fx2, fy2 = residual(x, y + eps)
        jxx = (fx1 - fx) / eps
        jyx = (fy1 - fy) / eps
        jxy = (fx2 - fx) / eps
        jyy = (fy2 - fy) / eps
        det = jxx * jyy - jxy * jyx
        if abs(det) < 1e-18:
            break
        x += (-jyy * fx + jxy * fy) / det
        y += (jyx * fx - jxx * fy) / det
    return x, y


def beta_from_tilt(tilt_deg):
    """Smallest angle from the nearest horizontal or vertical axis, 0..45."""
    a = abs(tilt_deg) % 90.0
    return min(a, 90.0 - a)


def fit_radial_polynomial(rho_delta):
    """Least squares δ = D2 ρ^2 + D4 ρ^4 + D6 ρ^6. rho_delta is (ρ, δ) pairs."""
    saa = sab = sac = sbb = sbc = scc = 0.0
    say = sby = scy = 0.0
    for rho, delta in rho_delta:
        a = rho ** 2
        b = rho ** 4
        c = rho ** 6
        saa += a * a
        sab += a * b
        sac += a * c
        sbb += b * b
        sbc += b * c
        scc += c * c
        say += a * delta
        sby += b * delta
        scy += c * delta
    det = (
        saa * (sbb * scc - sbc * sbc)
        - sab * (sab * scc - sac * sbc)
        + sac * (sab * sbc - sbb * sac)
    )
    if abs(det) < 1e-18:
        return 0.0, 0.0, 0.0

    def det3(a11, a12, a13, a21, a22, a23, a31, a32, a33):
        return (
            a11 * (a22 * a33 - a23 * a32)
            - a12 * (a21 * a33 - a23 * a31)
            + a13 * (a21 * a32 - a22 * a31)
        )

    d2 = det3(say, sab, sac, sby, sbb, sbc, scy, sbc, scc) / det
    d4 = det3(saa, say, sac, sab, sby, sbc, sac, scy, scc) / det
    d6 = det3(saa, sab, say, sab, sbb, sby, sac, sbc, scy) / det
    return d2, d4, d6


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
    focal: float
    obj_scale: float
    k1: float
    k2: float
    k3: float
    p1: float
    p2: float
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

    def chart_edges(self):
        _, edges = self.sensor_points()
        out = []
        for edge in edges:
            pts = []
            for xs, ys in edge:
                xu, yu = inverse_analytic(xs / self.focal, ys / self.focal, self.k1, self.k2, self.k3, self.p1, self.p2)
                pts.append((xu * self.focal * self.obj_scale, yu * self.focal * self.obj_scale))
            out.append(pts)
        return out

    def chart_center(self):
        xu, yu = inverse_analytic(
            self.center_x / self.focal,
            self.center_y / self.focal,
            self.k1,
            self.k2,
            self.k3,
            self.p1,
            self.p2,
        )
        return xu * self.focal * self.obj_scale, yu * self.focal * self.obj_scale


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
