"""Export the remaining Section A data to one concise CSV, without OpenVSP.

Uses only the Python standard library. Never executes MATLAB assignments.
Geometry stays in the existing geometry CSVs. No raw loading-case dump or Excel
workbook is generated. Only supplied values and two paired CG limits are exported.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import math
import re
from collections import Counter
from pathlib import Path
import xml.etree.ElementTree as ET

from lab2.paths import PROJECT_ROOT as ROOT
NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"


def numeric(text):
    if text is None or not text.strip():
        return None
    result = float(text)
    if not math.isfinite(result):
        raise ValueError(f'Nonfinite source value: {text}')
    return result


def paths(node, prefix=''):
    """Unique, usable XPath with 1-based indices for repeated siblings."""
    path = prefix + '/' + node.tag
    yield node, path
    counts = Counter(c.tag for c in node)
    seen = Counter()
    for child in node:
        seen[child.tag] += 1
        suffix = f'[{seen[child.tag]}]' if counts[child.tag] > 1 else ''
        child_prefix = path
        # Include sibling index on this node, without changing recursion rules.
        for descendant, child_path in paths(child, child_prefix):
            start = child_prefix + '/' + child.tag
            yield descendant, start + suffix + child_path[len(start):]


def write_csv(path, rows):
    if not rows:
        return
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def read_matlab(path):
    values = {}
    for line, text in enumerate(path.read_text(encoding='utf-8-sig').splitlines(), 1):
        match = re.fullmatch(r'\s*([A-Za-z]\w*\.[A-Za-z]\w*)\s*=\s*(' + NUMBER + r')\s*;\s*', text)
        if match:
            key, value = match.groups()
            if key in values:
                if values[key][0] != numeric(value):
                    raise ValueError(f'Conflicting duplicate numeric assignment: {key}')
                continue  # Repeated identical airfoil definitions occur in VAMPzero.m.
            values[key] = (numeric(value), line)
    return values


def source_unit(matlab, key):
    file = matlab.parent / 'mindMaps' / (key + '.mm')
    if not file.exists():
        return '', ''
    label = ET.parse(file).getroot().find('node').get('TEXT', '')
    match = re.match(re.escape(key) + r'\s*=\s*' + NUMBER + r'\s*(.*)$', label)
    return (match.group(1).strip() if match else ''), str(file.resolve())


def extract(xml, out, matlab=None, companion_xml=None):
    root = ET.parse(xml).getroot()
    node_paths = {node: path for node, path in paths(root)}
    model = root.find('./vehicles/aircraft/model')
    if model is None:
        raise ValueError('Missing aircraft model')
    analysis = model.find('analyses')
    if analysis is None:
        raise ValueError('Missing model/analyses')
    mb = analysis.find('massBreakdown')
    if mb is None:
        raise ValueError('Missing massBreakdown')
    warnings, checks = [], []

    def check(name, actual, expected, tolerance=1e-7):
        delta = actual - expected
        status = 'PASS' if abs(delta) <= tolerance else 'REVIEW'
        checks.append(dict(check=name, actual=actual, expected=expected,
                           difference=delta, tolerance=tolerance, status=status))
        return status

    masses, designs = [], []
    design_nodes = list(mb.find('designMasses'))
    for node in mb.iter():
        mass = node.find('mass')
        if mass is None:
            continue
        is_design = node in design_nodes
        path = node_paths[node]
        record = dict(category='design_mass' if is_design else 'mass_breakdown',
                      item=node.tag if is_design else path.split('/massBreakdown/', 1)[1].removesuffix('/massDescription'),
                      uid=node.get('uID', ''), component_uid=node.findtext('parentUID', ''),
                      mass_kg=numeric(mass.text),
                      x_m=numeric(node.findtext('location/x')),
                      y_m=numeric(node.findtext('location/y')),
                      z_m=numeric(node.findtext('location/z')),
                      Jxx_kg_m2=numeric(node.findtext('massInertia/Jxx')),
                      Jyy_kg_m2=numeric(node.findtext('massInertia/Jyy')),
                      Jzz_kg_m2=numeric(node.findtext('massInertia/Jzz')),
                      Jxy_kg_m2=numeric(node.findtext('massInertia/Jxy')),
                      Jxz_kg_m2=numeric(node.findtext('massInertia/Jxz')),
                      Jyz_kg_m2=numeric(node.findtext('massInertia/Jyz')),
                      source_file=str(xml.resolve()), source_xpath=path,
                      notes='SI convention: kg, m, kg m^2. Inertia origin/axes not explicit in this XML. Blank means absent.')
        (designs if is_design else masses).append(record)

    references = []
    for key, relative, unit in [('area_m2', 'area', 'm^2'), ('length_m', 'length', 'm'),
                                ('point_x_m', 'point/x', 'm'), ('point_y_m', 'point/y', 'm'),
                                ('point_z_m', 'point/z', 'm')]:
        node = model.find('reference/' + relative)
        if node is None:
            raise ValueError(f'Missing reference/{relative}')
        references.append(dict(quantity=key, value=numeric(node.text), unit=unit,
                               source_file=str(xml.resolve()), source_xpath=node_paths[node]))
    ref = {r['quantity']: r['value'] for r in references}
    if ref['length_m'] <= 0:
        raise ValueError('Reference length must be positive')

    cases = []
    certification = analysis.find('weightAndBalance/certificationCases')
    if certification is None:
        raise ValueError('Missing certificationCases')
    for index, case in enumerate(certification, 1):
        def vector(path):
            text = case.findtext(path)
            if text is None:
                return None
            return [numeric(value) for value in text.split(';') if value.strip()]
        columns = {key: vector(path) for key, path in [('mass_kg', 'mass'), ('x_m', 'coG/point/x'),
                                                     ('y_m', 'coG/point/y'), ('z_m', 'coG/point/z')]}
        count = len(columns['mass_kg'] or [])
        if not count or columns['x_m'] is None or any(len(c) != count for c in columns.values() if c is not None):
            raise ValueError(f'Unequal/missing certification vectors: {case.get("uID")}')
        for i in range(count):
            row = dict(case_uid=case.get('uID', f'case_{index}'), sample_index=i + 1,
                       **{key: column[i] if column is not None else None for key, column in columns.items()})
            row['cg_percent_mac'] = 25 + 100 * (row['x_m'] - ref['point_x_m']) / ref['length_m']
            row.update(source_file=str(xml.resolve()), source_xpath=node_paths[case],
                       notes='Sample index is 1-based and pairs the mass/coG vectors. %MAC assumes reference point is quarter-MAC per lab guide.')
            cases.append(row)
    if any(r['mass_kg'] <= 0 for r in cases):
        raise ValueError('Nonpositive certification mass')

    matlab_values = {}
    operating, supplementary = [], []
    if matlab:
        if companion_xml is None or not companion_xml.is_file():
            raise ValueError('--vampzero requires --companion-xml to verify the source aircraft')
        if hashlib.sha256(xml.read_bytes()).digest() != hashlib.sha256(companion_xml.read_bytes()).digest():
            raise ValueError('Companion XML differs from geometry XML; refusing to combine aircraft data')
        matlab_values = read_matlab(matlab)
        operating_keys = {'aircraft.altCR', 'aircraft.machCR', 'atmosphere.TASCR',
                          'atmosphere.rhoCR', 'atmosphere.myCR', 'atmosphere.TCR'}
        for key, (value, line) in matlab_values.items():
            relevant_op = key in operating_keys
            relevant_mass = key == 'aircraft.posCoGOEM'
            if not (relevant_op or relevant_mass):
                continue
            unit, unit_source = source_unit(matlab, key)
            notes = '' if unit else 'Source does not label a unit; do not assume one.'
            record = dict(parameter=key, value=value, source_unit=unit, source_file=str(matlab.resolve()),
                          source_line=line, unit_source=unit_source, notes=notes)
            (operating if relevant_op else supplementary).append(record)
        aliases = {'mTOM': 'aircraft.mTOM', 'mZFM': 'aircraft.mZFW', 'mMLM': 'aircraft.mLM'}
        for row in designs:
            check(row['item'] + ' XML vs VAMPzero mass', row['mass_kg'], matlab_values[aliases[row['item']]][0], 0.01)
        for row in masses:
            alias = {'wing': 'wing.mWing', 'htp': 'htp.mHtp', 'vtp': 'vtp.mVtp'}.get(row['component_uid'])
            if alias:
                check(alias + ' XML vs VAMPzero', row['mass_kg'], matlab_values[alias][0], 0.01)
        for row in designs:
            for axis in 'XYZ':
                alias = 'aircraft.massI' + axis + {'mTOM': 'mTOM', 'mZFM': 'mZFW', 'mMLM': 'mLM'}[row['item']]
                value = row['J' + axis.lower() * 2 + '_kg_m2']
                if value is not None and alias in matlab_values:
                    check(alias + ' XML vs VAMPzero', value, matlab_values[alias][0], 0.01)
        for key, value in [('aircraft.posCoGMIN', min(r['x_m'] for r in cases)),
                           ('aircraft.posCoGMAX', max(r['x_m'] for r in cases))]:
            if key in matlab_values:
                check(key + ' vs certification extrema', value, matlab_values[key][0], 1e-7)

    by_design = {r['item']: r for r in designs}
    oem = next(r for r in masses if r['item'] == 'mOEM')
    payload = next(r for r in masses if r['item'] == 'payload')
    fuel = next(r for r in masses if r['item'] == 'fuel')
    # Only leaf mass entries: do not sum OEM or payload twice with their children.
    oem_leaves = [r for r in masses if r['item'].startswith('mOEM/')]
    oem_sum = sum(r['mass_kg'] for r in oem_leaves)
    if check('OEM vs component mass sum', oem_sum, oem['mass_kg'], 0.01) == 'REVIEW':
        warnings.append(f'OEM component entries sum to {oem_sum:.11g} kg versus stated OEM {oem["mass_kg"]:.11g} kg (difference {oem_sum - oem["mass_kg"]:.11g} kg). Check landing-gear aggregation before using component sums.')
    check('ZFM vs OEM plus payload', oem['mass_kg'] + payload['mass_kg'], by_design['mZFM']['mass_kg'], 0.01)
    check('TOM vs OEM plus payload plus fuel', oem['mass_kg'] + payload['mass_kg'] + fuel['mass_kg'], by_design['mTOM']['mass_kg'], 0.01)
    cg_min, cg_max = min(r['x_m'] for r in cases), max(r['x_m'] for r in cases)
    tom_cg = by_design['mTOM']['x_m']
    if tom_cg is not None and not cg_min <= tom_cg <= cg_max:
        warnings.append(f'TOM CG x={tom_cg:.11g} m lies outside certification x range [{cg_min:.11g}, {cg_max:.11g}] m. Preserve both; confirm loading definitions before stability work.')
    uids = list(dict.fromkeys(r['case_uid'] for r in cases))
    if len(uids) == 2:
        one, two = ([tuple(r[k] for k in ('mass_kg', 'x_m', 'y_m', 'z_m')) for r in cases if r['case_uid'] == uid] for uid in uids)
        if one == two:
            warnings.append('Forward/rearward-labelled certification vectors are identical. Do not interpret their labels as distinct envelopes.')
    warnings += ['Some component locations and off-diagonal inertias are absent. Unavailable fields are omitted, not assumed zero.',
                 'Inertia values are reported as supplied; origin, axes and parallel-axis convention require confirmation.',
                 'Reference point is quarter-MAC per the lab guide, not aircraft CG. Reference length is MAC, not fuselage length.',
                 'Operating data are VAMPzero source cruise outputs, not a selected or validated VSPAERO analysis condition.']
    tables = {'design_masses': designs, 'mass_breakdown': masses, 'reference_values': references,
              'cg_cases': cases, 'operating_conditions': operating,
              'vampzero_mass_cg': supplementary, 'checks': checks}
    rows = []

    def add(category, item, quantity, value, unit, source, notes=''):
        rows.append(dict(category=category, item=item, quantity=quantity, value=value,
                         unit=unit, source=source, notes=notes))

    labels = {'mTOM': 'maximum_takeoff', 'mZFM': 'zero_fuel', 'mMLM': 'maximum_landing',
              'payload': 'payload_total', 'payload/mPax': 'passengers', 'payload/mCargo': 'cargo',
              'fuel': 'fuel', 'mOEM': 'operating_empty_total'}
    for record in designs + masses:
        item = labels.get(record['item']) or record['component_uid'] or record['item'].split('/')[-1]
        if 'mFuselageStructure' in record['item']:
            item = 'fuselage_structure'
        suffixes = {'mass_kg': ('mass', 'kg', '/mass'),
                    **{a + '_m': ('cg_' + a, 'm', '/location/' + a) for a in 'xyz'},
                    **{'J' + a + '_kg_m2': ('J' + a, 'kg m^2', '/massInertia/J' + a)
                       for a in ('xx', 'yy', 'zz', 'xy', 'xz', 'yz')}}
        for field, (quantity, unit, suffix) in suffixes.items():
            if record[field] is None:
                continue
            notes = ''
            if quantity == 'mass' and item in ('operating_empty_total', 'payload_total'):
                notes = 'Parent total. Do not add to its component entries.'
            if quantity.startswith('J'):
                notes = 'Source inertia origin/axes not explicit; value is untransformed.'
            if quantity == 'mass' and item == 'operating_empty_total':
                notes += f' Component sum exceeds stated OEM by {oem_sum - oem["mass_kg"]:.6f} kg; review landing-gear aggregation.'
            if item == 'maximum_takeoff' and quantity == 'cg_x' and not cg_min <= record[field] <= cg_max:
                notes = 'Outside certification-case CG range; confirm loading definitions.'
            add(record['category'], item, quantity, record[field], unit,
                f'{xml.name}:{record["source_xpath"]}{suffix}', notes)
    for record in references:
        add('reference', 'aircraft', record['quantity'], record['value'], record['unit'],
            f'{xml.name}:{record["source_xpath"]}', 'Reference point is quarter-MAC per lab guide, not aircraft CG.' if 'point' in record['quantity'] else '')
    # Inspect every loading sample internally, but export only the two global CG limits.
    for item, function in [('forward_limit', min), ('aft_limit', max)]:
        case = function(cases, key=lambda r: r['x_m'])
        notes = f'{case["case_uid"]}; vector sample {case["sample_index"]} (1-based). First occurrence if tied.'
        for field, quantity, unit, suffix in [('x_m', 'cg_x', 'm', '/coG/point/x'),
                                             ('mass_kg', 'associated_mass', 'kg', '/mass'),
                                             ('y_m', 'cg_y', 'm', '/coG/point/y'),
                                             ('z_m', 'cg_z', 'm', '/coG/point/z'),
                                             ('cg_percent_mac', 'cg_percent_mac', '% MAC', '/coG/point/x')]:
            if case[field] is None:
                continue
            detail = notes
            if field == 'cg_percent_mac':
                detail += ' Derived: 25 + 100*(x_CG - reference_x)/reference_length.'
            add('cg_limit', item, quantity, case[field], unit, f'{xml.name}:{case["source_xpath"]}{suffix}', detail)
    for record in supplementary:
        add('mass_breakdown', 'operating_empty_total', 'cg_x', record['value'], 'm',
            f'{matlab.name}:{record["parameter"]} (line {record["source_line"]})')
    op_labels = {'aircraft.altCR': ('cruise', 'altitude', 'm'),
                 'aircraft.machCR': ('cruise', 'mach', '1'),
                 'atmosphere.TASCR': ('cruise', 'true_airspeed', 'm/s'),
                 'atmosphere.rhoCR': ('cruise', 'density', 'kg/m^3'),
                 'atmosphere.myCR': ('cruise', 'dynamic_viscosity', 'kg/(m s)'),
                 'atmosphere.TCR': ('cruise', 'temperature', 'K')}
    for record in operating:
        item, quantity, unit = op_labels[record['parameter']]
        add('operating', item, quantity, record['value'], unit,
            f'{matlab.name}:{record["parameter"]} (line {record["source_line"]})',
            'VAMPzero cruise output; no VSPAERO condition selected.')
    if matlab is None:
        warnings.append('No VAMPzero source supplied: operating values and supplementary OEM CG are not exported.')
    out.parent.mkdir(parents=True, exist_ok=True)
    write_csv(out, rows)
    print(f'Wrote {len(rows)} Section A values to {out}')
    print(f'Checked {len(cases)} loading records internally; exported forward/aft limits only.')
    print(f'Checks: {sum(r["status"] == "PASS" for r in checks)} passed, {sum(r["status"] == "REVIEW" for r in checks)} require review.')
    for warning in warnings:
        print('Note:', warning)
    return dict(rows=rows, warnings=warnings, tables=tables)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xml', type=Path, default=ROOT / 'inputs/toolOutput.xml')
    parser.add_argument('--out', type=Path, default=ROOT / 'geometry_data/section_a.csv', help='Single output CSV file')
    parser.add_argument('--vampzero', type=Path, help='Matching ReturnDirectory/VAMPzero.m (numeric assignments only)')
    parser.add_argument('--companion-xml', type=Path, help='XML from the same run as --vampzero; exact hash match required')
    args = parser.parse_args()
    extract(args.xml.resolve(), args.out.resolve(), args.vampzero, args.companion_xml)


if __name__ == '__main__':
    main()
