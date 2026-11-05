"""Build only the Lab 2 wing, HTP and VTP from the parser CSV.
No fuselage is generated. Add it manually in OpenVSP after inspecting the model.
Adapted from the station/airfoil builder in the supplied VSPAERO_module.py.
"""
from __future__ import annotations
import argparse
import csv
import importlib
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

from lab2.paths import PROJECT_ROOT

try:
    from tqdm import tqdm
except ImportError:
    raise SystemExit("Install progress-bar support: python -m pip install tqdm")


def number(row, key):
    value = float(row[key])
    if not math.isfinite(value):
        raise ValueError(f'Nonfinite {key}')
    return value


def load_geometry(path):
    groups = defaultdict(list)
    with path.open(newline='', encoding='utf-8-sig') as stream:
        for row in csv.DictReader(stream):
            if row['schema_version'] != '1':
                raise ValueError('Expected CSV schema_version 1')
            groups[row['component_uid']].append(row)
    if not groups:
        raise ValueError('Empty geometry CSV')
    for uid, rows in groups.items():
        rows.sort(key=lambda r: int(r['station_index']))
        if [int(r['station_index']) for r in rows] != list(range(len(rows))):
            raise ValueError(f'{uid}: station indices must be contiguous')
        if len(rows) < 2:
            raise ValueError(f'{uid}: at least two stations required')
        for r in rows:
            for key in ('component_x_m','component_y_m','component_z_m',
                        'component_rx_deg','component_ry_deg','component_rz_deg'):
                if r[key] != rows[0][key]:
                    raise ValueError(f'{uid}: inconsistent component placement')
            if r['geometry_type'] == 'wing':
                if number(r, 'chord_m') <= 0:
                    raise ValueError(f'{uid}: nonpositive chord')
                if not (path.parent / r['airfoil_file']).is_file():
                    raise FileNotFoundError(r['airfoil_file'])
                if abs(number(r, 'twist_pivot_chord_fraction')) > 1e-10:
                    raise ValueError('Only leading-edge CPACS twist pivots supported')
            elif r['geometry_type'] != 'fuselage':
                raise ValueError('Unsupported geometry type')
        # This adapter deliberately supports the supplied root-at-origin layout.
        if rows[0]['geometry_type'] == 'wing':
            if any(abs(number(rows[0], f'station_{a}_local_m')) > 1e-8 for a in 'xyz'):
                raise ValueError(f'{uid}: wing root must be at component origin')
            for previous, row in zip(rows, rows[1:]):
                if row['previous_element_uid'] != previous['element_uid']:
                    raise ValueError(f'{uid}: broken station chain')
                delta = [number(row, f'station_{a}_local_m') - number(previous, f'station_{a}_local_m') for a in 'xyz']
                if delta[1] <= 0:
                    raise ValueError(f'{uid}: positive local y span required')
                for a, d in zip('xyz', delta):
                    if not math.isclose(d, number(row, f'bay_d{a}_m'), abs_tol=1e-8):
                        raise ValueError(f'{uid}: bay displacement mismatch')
    return groups


class Builder:
    def __init__(self, api, csv_path, chordwise=41, spanwise=16):
        self.v = api
        self.csv_path = csv_path
        self.chordwise, self.spanwise = chordwise, spanwise
        self.expected = []
        self.dimensions = []

    def set(self, gid, name, group, value):
        pid = self.v.FindParm(gid, name, group)
        if not pid:
            raise RuntimeError(f'Missing OpenVSP parameter: {name} / {group}')
        self.v.SetParmVal(pid, float(value))
        self.expected.append((pid, float(value), name, group))

    def xparm(self, xsec, name, value):
        pid = self.v.GetXSecParm(xsec, name)
        if not pid:
            raise RuntimeError(f'Missing XSec parameter {name}')
        self.v.SetParmVal(pid, float(value))
        self.expected.append((pid, float(value), name, 'XSec'))

    def placement(self, gid, row):
        # Standalone components, rotation about their local origin.
        self.set(gid, 'Origin', 'XForm', 0)
        for axis in 'XYZ':
            self.set(gid, f'{axis}_Rel_Location', 'XForm', number(row, f'component_{axis.lower()}_m'))
            self.set(gid, f'{axis}_Rel_Rotation', 'XForm', number(row, f'component_r{axis.lower()}_deg'))
        self.set(gid, 'Sym_Planar_Flag', 'Sym', self.v.SYM_XZ if row['symmetry'] == 'x-z-plane' else 0)

    def resize_sections(self, gid, target, shape, uid, wing=False):
        v = self.v
        v.Update()
        surf = v.GetXSecSurf(gid, 0)
        count = v.GetNumXSec(surf)
        with tqdm(total=abs(target-count), desc=f'{uid}: resize sections', unit='section',
                  position=1, leave=False, dynamic_ncols=True) as progress:
            # Fixed number of operations; a rejected API call stops immediately.
            for _ in range(abs(target-count)):
                before = count
                if count < target:
                    # A wing's root (index 0) is not a valid insertion section.
                    index = count-1 if wing else count-2
                    v.InsertXSec(gid, index, shape)
                    expected = before+1
                else:
                    v.CutXSec(gid, 1)
                    expected = before-1
                v.Update()
                surf = v.GetXSecSurf(gid, 0)
                count = v.GetNumXSec(surf)
                if count != expected:
                    mgr = v.ErrorMgrSingleton.getInstance()
                    errors = []
                    while mgr.GetNumTotalErrors():
                        errors.append(mgr.PopLastError().GetErrorString())
                    detail = '; '.join(errors) or 'API did not change the section count'
                    raise RuntimeError(f'{uid}: expected {expected} sections, got {count}. {detail}')
                progress.update(1)
        if count != target:
            raise RuntimeError(f'{uid}: expected {target} sections, got {count}')
        return surf

    def wing(self, uid, rows):
        v = self.v
        gid = v.AddGeom('WING')
        v.SetGeomName(gid, uid)
        surf = self.resize_sections(gid, len(rows), v.XS_FILE_AIRFOIL, uid, wing=True)
        for flag in ('RelativeTwistFlag', 'RelativeDihedralFlag',
                     'RotateAirfoilMatchDideralFlag', 'CorrectAirfoilthicknessFlag'):
            self.set(gid, flag, 'WingGeom', 0)
        for i, row in tqdm(enumerate(rows), total=len(rows), desc=f'{uid}: set stations', unit='station', position=1, leave=False, dynamic_ncols=True):
            v.ChangeXSecShape(surf, i, v.XS_FILE_AIRFOIL)
            v.ReadFileAirfoil(v.GetXSec(surf, i), str((self.csv_path.parent / row['airfoil_file']).resolve()))
            xs = v.GetXSec(surf, i)
            # Resolve parameters on the actual station container, not the
            # geometry's display-group names (root XSec_0 is not reliable).
            self.xparm(xs, 'Twist', number(row, 'cpacs_twist_y_deg'))
            self.xparm(xs, 'Twist_Location', 0)
            self.xparm(xs, 'RotateMatchDideralFlag', 0)
            if i:
                # OpenVSP section index is 1-based, including in SetDriverGroup.
                v.SetDriverGroup(gid, i, v.SPAN_WSECT_DRIVER, v.ROOTC_WSECT_DRIVER, v.TIPC_WSECT_DRIVER)
                dx, dy, dz = [number(row, f'bay_d{a}_m') for a in 'xyz']
                span = math.hypot(dy, dz)
                for name, value in [('Span', span), ('Root_Chord', number(rows[i-1], 'chord_m')),
                                    ('Tip_Chord', number(row, 'chord_m')), ('Sweep_Location', 0),
                                    ('Sweep', math.degrees(math.atan2(dx, span))),
                                    ('Dihedral', math.degrees(math.atan2(dz, dy))),
                                    ('SectTess_U', self.spanwise)]:
                    self.xparm(xs, name, value)
                v.Update()
        self.set(gid, 'Tess_W', 'Shape', self.chordwise)
        self.placement(gid, rows[0])
        self.set(gid, 'Wake', 'Shape', 1)
        v.Update()
        return gid

    def check(self):
        self.v.Update()
        for pid, expected, name, group in self.expected:
            actual = self.v.GetParmVal(pid)
            if not math.isclose(actual, expected, rel_tol=1e-7, abs_tol=1e-7):
                raise RuntimeError(f'OpenVSP changed {name}/{group}: requested {expected}, got {actual}')
        for xs, width, height in self.dimensions:
            if not (math.isclose(self.v.GetXSecWidth(xs), width, abs_tol=1e-7) and
                    math.isclose(self.v.GetXSecHeight(xs), height, abs_tol=1e-7)):
                raise RuntimeError('Fuselage width/height readback failed')
        mgr = self.v.ErrorMgrSingleton.getInstance()
        errors = []
        while mgr.GetNumTotalErrors():
            errors.append(mgr.PopLastError().GetErrorString())
        if errors:
            raise RuntimeError('\n'.join(errors))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('csv', nargs='?', type=Path, default=PROJECT_ROOT/'geometry_data/openvsp_input.csv')
    p.add_argument('--output', type=Path, default=PROJECT_ROOT/'output'/'Lab2_wing_tail.vsp3')
    p.add_argument('--api-dir', type=Path, help='Directory containing the official openvsp or vsp binding')
    p.add_argument('--validate-only', action='store_true', help='Validate CSV without importing OpenVSP')
    p.add_argument('--chordwise', type=int, default=41)
    p.add_argument('--spanwise', type=int, default=16)
    args = p.parse_args()
    groups = {uid: rows for uid, rows in load_geometry(args.csv.resolve()).items()
              if rows[0]['geometry_type'] == 'wing'}
    if set(groups) != {'wing', 'htp', 'vtp'}:
        p.error('Expected wing, htp and vtp component UIDs in the CSV')
    summary = {uid: len(rows) for uid, rows in groups.items()}
    print('Validated stations:', summary)
    if args.validate_only:
        return
    if min(args.chordwise, args.spanwise) < 2:
        p.error('Tessellation must be at least 2')
    if args.api_dir:
        sys.path.insert(0, str(args.api_dir.resolve()))
    try:
        v = importlib.import_module('openvsp')
    except ModuleNotFoundError as exc:
        if exc.name != 'openvsp':
            raise
        try:
            v = importlib.import_module('vsp')
        except ModuleNotFoundError as fallback:
            raise SystemExit('OpenVSP API unavailable. Use its compatible Python and --api-dir.') from fallback
    v.ClearVSPModel()
    b = Builder(v, args.csv.resolve(), args.chordwise, args.spanwise)
    ids = {}
    with tqdm(total=len(groups), desc='Components', unit='component', position=0, dynamic_ncols=True) as progress:
        for uid, rows in groups.items():
            progress.set_postfix_str(uid, refresh=True)
            ids[uid] = b.wing(uid, rows)
            progress.update(1)
    tqdm.write('Creating analysis sets...')
    # Use honest labels: these sets do not contain a body.
    memberships = {'W': ['wing'], 'WH': ['wing','htp'],
                   'WV': ['wing','vtp'], 'WHV': ['wing','htp','vtp']}
    for index, (name, members) in enumerate(memberships.items(), 3):
        if not set(members) <= ids.keys():
            raise ValueError(f'{name} requires component UIDs {members}')
        v.SetSetName(index, name)
        for uid, gid in ids.items():
            v.SetSetFlag(gid, index, uid in members)
    tqdm.write('Updating model and checking parameter values...')
    b.check()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    tqdm.write(f'Saving model: {args.output.resolve()}')
    v.WriteVSPFile(str(args.output.resolve()), v.SET_ALL)
    b.check()
    if not args.output.is_file() or args.output.stat().st_size == 0:
        raise RuntimeError('OpenVSP did not write the model')
    report = {'api_version': v.GetVSPVersion(), 'station_counts': summary,
              'sets': {name: i for i, name in enumerate(memberships, 3)},
              'reference': {k: val for k, val in next(iter(groups.values()))[0].items() if k.startswith('reference_')},
              'validation': 'Parameter readback passed; visual comparison with TiGL still required.'}
    args.output.with_suffix('.build.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('Wrote', args.output.resolve())


if __name__ == '__main__':
    main()
