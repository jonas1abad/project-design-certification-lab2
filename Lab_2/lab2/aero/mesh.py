"""Topology check for OpenVSP 3.43 thick-surface VSPGeom exports."""
from collections import Counter
from pathlib import Path


def check_panel_mesh(path):
    lines = Path(path).read_text().splitlines()
    nodes = int(lines[0])
    faces = int(lines[nodes + 1])
    edges = Counter()
    for line in lines[nodes + 2:nodes + 2 + faces]:
        count, *vertices = map(int, line.split())
        if count != 3 or len(vertices) != 3 or len(set(vertices)) != 3:
            raise ValueError(f'Invalid triangle in {path}: {line}')
        for a, b in zip(vertices, vertices[1:] + vertices[:1]):
            edges[tuple(sorted((a, b)))] += 1
    invalid = {edge: count for edge, count in edges.items() if count != 2}
    if invalid:
        sample = next(iter(invalid.items()))
        raise ValueError(f'PANEL mesh is not a closed manifold: {path}; '
                         f'{len(invalid)} invalid edges, example {sample}. '
                         'Adjust tessellation or inspect the intersection before solving.')
    return {'nodes': nodes, 'triangles': faces, 'edges': len(edges),
            'edge_face_count': 2, 'validation': 'Closed edge connectivity; not aerodynamic convergence acceptance.'}
