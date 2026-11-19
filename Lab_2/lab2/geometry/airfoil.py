"""Selig contour ordering: upper trailing edge, leading edge, lower trailing edge."""
from __future__ import annotations

import math
from pathlib import Path


def signed_area(points):
    return .5 * sum(a[0] * b[1] - b[0] * a[1]
                    for a, b in zip(points, points[1:] + points[:1]))


def selig_coordinates(coordinates):
    """Change traversal only; retain every coordinate and its camber/thickness."""
    points = [tuple(map(float, point)) for point in coordinates]
    if len(points) < 4 or any(len(p) != 2 or not all(map(math.isfinite, p)) for p in points):
        raise ValueError('Airfoil requires finite x,z coordinate pairs')
    xmax = max(p[0] for p in points)
    if not all(math.isclose(p[0], xmax, abs_tol=1e-8) for p in (points[0], points[-1])):
        raise ValueError('Supported airfoil contour must start and end at the trailing edge')
    area = signed_area(points)
    if abs(area) < 1e-12:
        raise ValueError('Airfoil contour has zero signed area')
    return points if area > 0 else points[::-1]


def validate_selig_airfoil(path):
    """Reject stale clockwise DAT exports before importing into OpenVSP."""
    lines = Path(path).read_text().splitlines()
    points = [tuple(map(float, line.split())) for line in lines[1:] if line.strip()]
    if points != selig_coordinates(points):
        raise ValueError(f'{path}: reversed airfoil traversal; regenerate DAT files with the XML parser')
