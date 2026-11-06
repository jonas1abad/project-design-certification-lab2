"""Extract this lab's VAMPzero CPACS geometry without OpenVSP or TiGL.

Python 3.10+, numpy. Usage:
  python -m lab2.geometry.parse_cpacs_geometry inputs/toolOutput.xml --out geometry_data

This is a deliberately constrained VAMPzero reader, not a full CPACS engine.
It preserves transforms and exports section contours, not a TiGL loft.
"""
import argparse
import csv
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np

from .airfoil import selig_coordinates


def vector(node, path, default=0):
    return np.array([float(node.findtext(f'{path}/{a}', str(default))) for a in 'xyz'])


def transform(node):
    """Scale, then rotate about x/y/z, then translate; column vectors."""
    t = node.find('transformation')
    if t is None:
        return np.eye(4)
    ref = t.find('translation')
    if ref is not None and ref.get('refType', 'absGlobal') != 'absGlobal':
        raise ValueError('Only the supplied absGlobal transformation convention is supported')
    x, y, z = np.radians(vector(t, 'rotation'))
    cx, cy, cz = np.cos([x, y, z]); sx, sy, sz = np.sin([x, y, z])
    rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    out = np.eye(4)
    out[:3, :3] = rz @ ry @ rx @ np.diag(vector(t, 'scaling', 1))
    out[:3, 3] = vector(t, 'translation')
    return out


def apply(matrix, points):
    return np.asarray(points) @ matrix[:3, :3].T + matrix[:3, 3]


def positionings(component):
    """Resolve the UID graph independently of XML order; translations do not propagate."""
    pending = {}
    for p in component.findall('./positionings/positioning'):
        target = p.findtext('toSectionUID')
        if target in pending:
            raise ValueError(f'Duplicate positioning for {target}')
        pending[target] = p
    out = {}
    while pending:
        progressed = False
        for target, p in list(pending.items()):
            source = p.findtext('fromSectionUID')
            if source and source not in out:
                continue
            length = float(p.findtext('length', '0'))
            sweep, dihedral = np.radians([float(p.findtext(k, '0')) for k in ('sweepAngle', 'dihedralAngle')])
            offset = length * np.array([np.sin(sweep), np.cos(sweep)*np.cos(dihedral), np.cos(sweep)*np.sin(dihedral)])
            out[target] = out.get(source, np.zeros(3)) + offset
            del pending[target]; progressed = True
        if not progressed:
            raise ValueError(f'Cyclic or unresolved positioning links: {list(pending)}')
    return out


def csv_write(path, rows):
    if rows:
        with path.open('w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)


def write_openvsp_input(data, output):
    """One row per station; incoming bay belongs to its outer station.

    Local station data and component placement are separate. Angle columns
    describe CPACS geometry, not yet version-specific OpenVSP API parameters.
    """
    rows = []
    for component in data['components']:
        comp_node = ET.fromstring(component['transformation_xml'])
        origin = vector(comp_node, 'translation')
        rotation = vector(comp_node, 'rotation')
        if not np.allclose(vector(comp_node, 'scaling', 1), 1):
            raise ValueError('CSV adapter currently requires unit component scales')
        elements = {s['element_uid']: s for s in component['sections']}
        incoming, outgoing = {}, {}
        for seg in component['segments']:
            a, b = seg['from_element_uid'], seg['to_element_uid']
            if a in outgoing or b in incoming:
                raise ValueError('CSV adapter requires an unbranched station chain')
            outgoing[a] = b; incoming[b] = a
        starts = set(elements) - set(incoming)
        if len(starts) != 1:
            raise ValueError('Expected one root station per component')
        order, current = [], starts.pop()
        while current is not None:
            if current in order:
                raise ValueError('Cyclic component segment chain')
            order.append(current); current = outgoing.get(current)
        if set(order) != set(elements):
            raise ValueError('Disconnected component segment chain')
        inverse = np.linalg.inv(np.array(component['matrix_global']))
        for index, eid in enumerate(order):
            item = elements[eid]
            local_matrix = inverse @ np.array(item['matrix_global'])
            local_origin = apply(local_matrix, [[0, 0, 0]])[0]
            row = dict(schema_version=1, component_uid=component['uid'],
                       geometry_type='wing' if component['kind'] == 'wing' else 'fuselage',
                       symmetry=component['symmetry'] or 'none', station_index=index,
                       section_uid=item['section_uid'], element_uid=eid,
                       previous_element_uid=incoming.get(eid, ''),
                       component_x_m=float(origin[0]), component_y_m=float(origin[1]), component_z_m=float(origin[2]),
                       component_rx_deg=float(rotation[0]), component_ry_deg=float(rotation[1]), component_rz_deg=float(rotation[2]),
                       station_x_local_m=float(local_origin[0]), station_y_local_m=float(local_origin[1]), station_z_local_m=float(local_origin[2]),
                       chord_m='', cpacs_twist_y_deg='', twist_pivot_chord_fraction='',
                       airfoil_file='', width_m='', height_m='', profile_uid=item['profile_uid'],
                       bay_dx_m='', bay_dy_m='', bay_dz_m='', bay_yz_length_m='',
                       bay_sweep_le_deg='', bay_dihedral_deg='',
                       reference_area_m2=data['reference']['area_m2'], reference_length_m=data['reference']['length_m'],
                       reference_x_m=data['reference']['point_m'][0], reference_y_m=data['reference']['point_m'][1],
                       reference_z_m=data['reference']['point_m'][2])
            if component['kind'] == 'wing':
                sm = np.array(item['section_matrix'])
                row.update(chord_m=item['chord_m'],
                           cpacs_twist_y_deg=float(np.degrees(np.arctan2(-sm[2, 0], sm[0, 0]))),
                           twist_pivot_chord_fraction=0, airfoil_file=f'{eid}.dat')
                if eid in incoming:
                    previous = elements[incoming[eid]]
                    delta = np.array(item['positioning_m']) - previous['positioning_m']
                    dx, dy, dz = map(float, delta)
                    if dy <= 0:
                        raise ValueError('Expected positive local wing span progression')
                    row.update(bay_dx_m=dx, bay_dy_m=dy, bay_dz_m=dz,
                               bay_yz_length_m=float(np.hypot(dy, dz)),
                               bay_sweep_le_deg=float(np.degrees(np.arctan2(dx, dy))),
                               bay_dihedral_deg=float(np.degrees(np.arctan2(dz, dy))))
            else:
                if item['profile_uid'] != 'Circle' or not np.allclose(local_matrix[:3, :3], np.diag(np.diag(local_matrix[:3, :3]))):
                    raise ValueError('Fuselage CSV supports the supplied unrotated Circle sections only')
                local_contour = apply(inverse, item['contour_global_m'])
                row.update(width_m=float(np.ptp(local_contour[:, 1])), height_m=float(np.ptp(local_contour[:, 2])))
            rows.append(row)
    csv_write(output/'openvsp_input.csv', rows)


def parse_geometry(xml_path, out_path):
    root = ET.parse(xml_path).getroot()
    model = root.find('./vehicles/aircraft/model')
    if model is None:
        raise ValueError('Expected an unnamespaced CPACS aircraft model')
    output = Path(out_path); output.mkdir(parents=True, exist_ok=True)
    profiles = {}
    for profile in root.findall('./vehicles/profiles/*/*'):
        pts = []
        for axis in 'xyz':
            text = profile.findtext('pointList/' + axis)
            if text is None:
                raise ValueError(f'Missing point list: {profile.get("uID")}')
            pts.append([float(s) for s in text.split(';') if s.strip()])
        if len(set(map(len, pts))) != 1:
            raise ValueError('Unequal profile coordinate counts')
        profiles[profile.get('uID')] = np.array(pts).T
    components = model.findall('./wings/wing') + model.findall('./fuselages/fuselage')
    component_index = {c.get('uID'): c for c in components}
    data = {'source': Path(xml_path).name, 'cpacs_version': root.findtext('./header/cpacsVersion'),
            'scope': 'VAMPzero geometry extraction; transforms retained; no TiGL loft or OpenVSP model generated',
            'reference': {'area_m2': float(model.findtext('reference/area')),
                          'length_m': float(model.findtext('reference/length')),
                          'point_m': vector(model, 'reference/point').tolist()}, 'components': []}
    stations, bays, fuselage_rows = [], [], []
    for comp in components:
        uid = comp.get('uID'); parent = comp.findtext('parentUID')
        # In this file the parent fuselage transform is identity. Reject other
        # cases instead of silently applying an incorrect hierarchy/refType rule.
        if parent and (parent not in component_index or not np.allclose(transform(component_index[parent]), np.eye(4))):
            raise ValueError(f'{uid}: nonidentity/missing parent requires a full CPACS hierarchy resolver')
        cm = transform(comp); pos = positionings(comp)
        entry = {'uid': uid, 'kind': comp.tag, 'parent_uid': parent, 'symmetry': comp.get('symmetry'),
                 'transformation_xml': ET.tostring(comp.find('transformation'), encoding='unicode'),
                 'matrix_global': cm.tolist(), 'sections': [], 'segments': []}
        by_element = {}
        for section in comp.findall('./sections/section'):
            sid = section.get('uID'); sm = transform(section)
            pm = np.eye(4); pm[:3, 3] = pos.get(sid, np.zeros(3))
            for element in section.findall('./elements/element'):
                eid = element.get('uID'); em = transform(element)
                profile_uid = element.findtext('airfoilUID') or element.findtext('profileUID')
                profile = profiles[profile_uid]
                matrix = cm @ pm @ sm @ em
                contour = apply(matrix, profile)
                item = {'section_uid': sid, 'element_uid': eid, 'profile_uid': profile_uid,
                        'positioning_m': pm[:3, 3].tolist(), 'section_matrix': sm.tolist(),
                        'element_matrix': em.tolist(), 'matrix_global': matrix.tolist(),
                        'contour_global_m': contour.tolist()}
                if comp.tag == 'wing':
                    # Supplied airfoils have LE=(0,0,0), TE x=1, and zero y.
                    if not np.allclose(profile[:, 1], 0) or not np.isclose(np.ptp(profile[:, 0]), 1):
                        raise ValueError('Expected a unit-chord x-z airfoil')
                    chord = float(np.linalg.norm(matrix[:3, 0]))
                    le = apply(matrix, [[0, 0, 0]])[0]
                    local = apply(sm @ em, profile)
                    if not np.allclose(em[:3, :3], np.diag(np.diag(em[:3, :3]))) or not np.allclose(em[:3, 3], 0):
                        raise ValueError('Airfoil .dat export expects diagonal element scaling')
                    if not np.allclose(sm[:3, 3], 0) or not np.allclose(vector(section, 'transformation/rotation')[[0, 2]], 0):
                        raise ValueError('Station summary expects section twist only about y')
                    scale = vector(section, 'transformation/scaling', 1) * vector(element, 'transformation/scaling', 1)
                    normalized = np.array(selig_coordinates(profile[:, [0, 2]] * [1, scale[2]/scale[0]]))
                    np.savetxt(output/f'{eid}.dat', normalized, fmt='%.12g', header=eid, comments='')
                    item.update(chord_m=chord, leading_edge_global_m=le.tolist(),
                                normalized_profile_xz=normalized.tolist())
                    row = {'component': uid, 'section': sid, 'element': eid, 'profile': profile_uid,
                           'chord_m': chord, 'local_twist_y_deg': float(vector(section, 'transformation/rotation')[1]),
                           'profile_z_scale': float(scale[2]/scale[0]),
                           'position_x_m': float(pm[0, 3]), 'position_y_m': float(pm[1, 3]), 'position_z_m': float(pm[2, 3]),
                           'global_le_x_m': float(le[0]), 'global_le_y_m': float(le[1]), 'global_le_z_m': float(le[2])}
                    stations.append(row)
                else:
                    center = apply(matrix, [[0, 0, 0]])[0]
                    fuselage_rows.append({'component': uid, 'section': sid, 'profile': profile_uid,
                        'x_m': float(center[0]), 'y_m': float(center[1]), 'z_m': float(center[2]),
                        'width_m': float(np.ptp(contour[:, 1])), 'height_m': float(np.ptp(contour[:, 2]))})
                entry['sections'].append(item); by_element[eid] = item
        for segment in comp.findall('./segments/segment'):
            a, b = (segment.findtext(k) for k in ('fromElementUID', 'toElementUID'))
            if a not in by_element or b not in by_element:
                raise ValueError(f'Unresolved segment {a} -> {b}')
            seg = {'uid': segment.get('uID'), 'from_element_uid': a, 'to_element_uid': b}
            entry['segments'].append(seg)
            if comp.tag == 'wing':
                delta = np.array(by_element[b]['positioning_m']) - by_element[a]['positioning_m']
                bays.append({'component': uid, **seg, 'dy_local_m': float(delta[1]),
                             'dx_local_m': float(delta[0]), 'dz_local_m': float(delta[2]),
                             'sweep_le_deg': float(np.degrees(np.arctan2(delta[0], delta[1]))),
                             'dihedral_deg': float(np.degrees(np.arctan2(delta[2], delta[1])))})
        data['components'].append(entry)
    (output/'geometry.json').write_text(json.dumps(data, indent=2), encoding='utf-8')
    csv_write(output/'wing_stations.csv', stations)
    csv_write(output/'wing_bays.csv', bays)
    csv_write(output/'fuselage_sections.csv', fuselage_rows)
    write_openvsp_input(data, output)
    print(f'Extracted {len(stations)} lifting-surface stations, {len(bays)} bays, {len(fuselage_rows)} fuselage stations to {output}')
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('xml', type=Path)
    parser.add_argument('--out', type=Path, default=Path('geometry_data'))
    args = parser.parse_args()
    parse_geometry(args.xml, args.out)
