"""Configuration, physical-spacing refinement and sequential VSPAERO studies."""
from __future__ import annotations

import copy
import csv
import hashlib
import itertools
import json
import math
from pathlib import Path
import re

MEMBERS = {'W': ['wing'], 'WH': ['wing', 'htp'], 'WV': ['wing', 'vtp'],
           'WHV': ['wing', 'htp', 'vtp'], 'WB': ['wing', 'fuselage'],
           'WBH': ['wing', 'fuselage', 'htp'], 'WBV': ['wing', 'fuselage', 'vtp'],
           'WBHV': ['wing', 'fuselage', 'htp', 'vtp']}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, allow_nan=False), encoding='utf-8')


def csv_rows(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def write_rows(path, rows, columns=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = columns or list(dict.fromkeys(key for row in rows for key in row))
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def identifier(value):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+', value) or value in ('.', '..'):
        raise ValueError(f'Use letters, digits, underscore or hyphen for names: {value!r}')
    return value


def positive(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError(f'{name} must be finite and positive')


def lifting_surface_tessellation(bays, spacing):
    """Allocate spanwise curves using the longest LE/TE edge of each bay."""
    rows = []
    for i, bay in enumerate(bays, 1):
        span = bay['span']
        taper_change = bay['tip_chord'] - bay['root_chord']
        dx_le = span*math.tan(math.radians(bay['sweep'])) - bay['sweep_location']*taper_change
        edge_length = math.hypot(span, max(abs(dx_le), abs(dx_le+taper_change)))
        intervals = max(1, math.ceil(edge_length/spacing))
        rows.append(dict(section_index=i, span_m=span, estimated_edge_length_m=edge_length,
                         target_spacing_m=spacing, panel_intervals=intervals,
                         SectTess_U=intervals+1, estimated_spacing_m=edge_length/intervals))
    return rows


def fuselage_tessellation(stations, spacing, end_factor=0.75, end_fraction=0.2):
    """Approximate surface spacing from four longitudinal meridian chords.

    SectTess_U counts curves: n panel intervals require n+1 curves.
    Existing CPACS stations are retained, even where closer than the target.
    """
    length = stations[-1]['x'] - stations[0]['x']
    rows = []
    for i, (a, b) in enumerate(zip(stations, stations[1:]), 1):
        dx, dy, dz = (b[k] - a[k] for k in ('x', 'y', 'z'))
        dw = (b['width'] - a['width']) / 2
        dh = (b['height'] - a['height']) / 2
        surface_length = max(math.sqrt(dx*dx + (dy+s*dw)**2 + dz*dz) for s in (-1, 1))
        surface_length = max(surface_length, *(math.sqrt(dx*dx + dy*dy + (dz+s*dh)**2) for s in (-1, 1)))
        midpoint = (a['x'] + b['x']) / 2
        end_distance = min(midpoint-stations[0]['x'], stations[-1]['x']-midpoint)
        t = min(1.0, max(0.0, end_distance / (end_fraction*length)))
        end_weight = 1 - 3*t*t + 2*t*t*t
        target = spacing * (1 - (1-end_factor)*end_weight)
        intervals = max(1, math.ceil(surface_length / target))
        rows.append(dict(section_index=i, x_start_m=a['x'], x_end_m=b['x'],
                         axial_length_m=dx, estimated_surface_length_m=surface_length,
                         target_spacing_m=target, panel_intervals=intervals,
                         SectTess_U=intervals+1, estimated_spacing_m=surface_length/intervals))
    return rows


def load_config(path):
    path = Path(path).resolve()
    cfg = json.loads(path.read_text(encoding='utf-8'))
    for name in ('model', 'geometry_csv', 'section_a_csv', 'output_root', 'api_dir', 'vspaero_dir'):
        if cfg.get(name):
            cfg[name] = str((path.parent / cfg[name]).resolve())
    for name in ('model', 'geometry_csv'):
        if not Path(cfg[name]).is_file():
            raise FileNotFoundError(cfg[name])
    geo = csv_rows(cfg['geometry_csv'])
    wing = [r for r in geo if r['component_uid'] == 'wing']
    if not wing or wing[0]['symmetry'] != 'x-z-plane':
        raise ValueError('Reference span extraction expects the supplied mirrored wing')
    first = wing[0]
    cfg['reference'] = {'Sref': float(first['reference_area_m2']),
                        'cref': float(first['reference_length_m']),
                        'bref': 2 * max(float(r['station_y_local_m']) for r in wing)}
    point = cfg['moment_reference']
    if point == 'cpacs_reference':
        point = [float(first[f'reference_{axis}_m']) for axis in 'xyz']
    if not isinstance(point, list) or len(point) != 3 or any(not math.isfinite(float(x)) for x in point):
        raise ValueError('moment_reference must be cpacs_reference or [x,y,z] in metres')
    cfg['reference'].update(dict(zip(('Xcg', 'Ycg', 'Zcg'), map(float, point))))
    for key in ('Sref', 'cref', 'bref'):
        positive(cfg['reference'][key], key)
    if cfg['flow'].get('source') == 'section_a':
        data = csv_rows(cfg['section_a_csv'])
        def value(quantity):
            matched = [float(r['value']) for r in data if r['category'] == 'operating' and r['item'] == 'cruise' and r['quantity'] == quantity]
            if len(matched) != 1:
                raise ValueError(f'Section A must contain one cruise {quantity}; regenerate it with matching VAMPzero data or set explicit flow values')
            return matched[0]
        cfg['flow'] = {'mach': value('mach'), 'speed_m_s': value('true_airspeed'),
                       'density_kg_m3': value('density'), 'viscosity_kg_ms': value('dynamic_viscosity'),
                       'temperature_K': value('temperature'), 'altitude_m': value('altitude'),
                       'source': cfg['section_a_csv']}
    for key in ('mach', 'speed_m_s', 'density_kg_m3', 'viscosity_kg_ms'):
        positive(cfg['flow'][key], key)
    if cfg['flow']['mach'] >= 1:
        raise ValueError('This lab workflow is configured for subsonic cases only')
    cfg['flow']['reynolds'] = (cfg['flow']['density_kg_m3'] * cfg['flow']['speed_m_s'] *
                               cfg['reference']['cref'] / cfg['flow']['viscosity_kg_ms'])
    if 'temperature_K' in cfg['flow']:
        cfg['flow']['speed_of_sound_m_s'] = math.sqrt(1.4 * 287.05 * cfg['flow']['temperature_K'])
        cfg['flow']['mach_from_speed'] = cfg['flow']['speed_m_s'] / cfg['flow']['speed_of_sound_m_s']
    if not cfg['methods'] or not set(cfg['methods']) <= {'VLM', 'PANEL'}:
        raise ValueError('methods must contain VLM and/or PANEL')
    if not cfg['configurations'] or not set(cfg['configurations']) <= MEMBERS.keys():
        raise ValueError('Unknown/empty configuration list')
    if len(set(cfg['methods'])) != len(cfg['methods']) or len(set(cfg['configurations'])) != len(cfg['configurations']):
        raise ValueError('Duplicate methods/configurations')
    for case in cfg['cases']:
        identifier(case['name'])
        if not all(math.isfinite(case[key]) for key in ('alpha_deg', 'beta_deg')):
            raise ValueError('Angles must be finite')
    if not cfg['cases'] or len({c['name'] for c in cfg['cases']}) != len(cfg['cases']):
        raise ValueError('Cases must have unique names')
    if not isinstance(cfg['stability'], bool) or not isinstance(cfg['wake']['fixed'], bool):
        raise ValueError('stability and wake.fixed must be true or false')
    for key in ('threads', 'cap_tessellation'):
        positive(cfg[key], key)
    if not isinstance(cfg['threads'], int) or cfg['threads'] > 255:
        raise ValueError('threads must be an integer from 1 to 255')
    for n in [cfg['wake']['nodes'], *cfg['wake_node_levels']]:
        if not isinstance(n, int) or n < 8 or n & (n - 1):
            raise ValueError('Wake nodes must be powers of two >= 8')
    for n in [cfg['wake']['iterations'], cfg['wake_node_iterations'], *cfg['wake_iteration_levels']]:
        if not isinstance(n, int) or not 3 <= n <= 255:
            raise ValueError('Wake iterations must be integers from 3 to 255')
    names = set()
    for level in cfg['mesh_levels']:
        identifier(level['name'])
        if level['name'] in names:
            raise ValueError('Duplicate mesh level')
        names.add(level['name'])
        for n in [level['chordwise'], level['fuselage_w']]:
            if not isinstance(n, int) or n < 3:
                raise ValueError('Mesh tessellation values must be integers >= 3')
        positive(level['fuselage_spacing_m'], 'fuselage_spacing_m')
        positive(level['lifting_spacing_m'], 'lifting_spacing_m')
        if (level['chordwise'] - 1) % 4 or (level['fuselage_w'] - 1) % 4:
            raise ValueError('Chordwise and fuselage circumferential counts must have form 4n+1 to avoid API rounding')
    cfg['model_sha256'] = digest(cfg['model'])
    cfg['config_file'] = str(path)
    return cfg


def make_plan(cfg, stage='surface', mesh=None):
    if stage not in ('surface', 'final', 'wake-nodes', 'wake-iterations'):
        raise ValueError('Unknown study stage')
    levels = cfg['mesh_levels']
    if stage != 'surface':
        levels = [level for level in levels if level['name'] == mesh]
        if len(levels) != 1:
            raise ValueError(f'{stage} requires one selected surface mesh level')
    if stage in ('surface', 'final'):
        variants = [(level['name'], i, level, cfg['wake']) for i, level in enumerate(levels)]
    else:
        key = 'nodes' if stage == 'wake-nodes' else 'iterations'
        values = cfg['wake_node_levels'] if key == 'nodes' else cfg['wake_iteration_levels']
        variants = []
        for value in values:
            wake = dict(cfg['wake'], **{key: value})
            if stage == 'wake-nodes':
                wake['iterations'] = cfg['wake_node_iterations']
            # Both appendix wake sweeps are free-wake runs: node-count cases
            # use the selected iteration count, while iteration cases vary it.
            wake['fixed'] = False
            variants.append((f'{key}_{value}', value, levels[0], wake))
    tasks = []
    for method, configuration, case, (variant, order, level, wake) in itertools.product(
            cfg['methods'], cfg['configurations'], cfg['cases'], variants):
        tasks.append(dict(run_id=f'{method}_{configuration}_{variant}_{case["name"]}',
                          stage=stage, method=method, configuration=configuration,
                          case=copy.deepcopy(case), variant=variant, sweep_value=order,
                          mesh=copy.deepcopy(level), wake=copy.deepcopy(wake), settings=copy.deepcopy(cfg)))
    return tasks


def study_directory_name(tasks):
    stage = tasks[0]['stage']
    methods = '_'.join(sorted({t['method'] for t in tasks}, reverse=True))
    configurations = sorted({t['configuration'] for t in tasks})
    config_name = configurations[0] if len(configurations) == 1 else 'all_configs'
    name = f'{stage.replace("-", "_")}_{methods}_{config_name}'
    if stage in ('wake-nodes', 'wake-iterations'):
        meshes = sorted({t['mesh']['name'] for t in tasks})
        name += '_' + '_'.join(meshes)
        fixed_key = 'nodes' if stage == 'wake-iterations' else 'iterations'
        values = sorted({t['wake'][fixed_key] for t in tasks})
        name += '_' + fixed_key + '_'.join(map(str, values))
    return identifier(name)


def execute_tasks(tasks, output_root, prefix='study', resume_name=None, start_case=1):
    folder = Path(output_root).resolve()
    base_name = identifier(resume_name) if resume_name else study_directory_name(tasks)
    run_name = base_name
    repeat = 2
    while not resume_name and any((folder / branch / run_name).exists() for branch in ('input', 'outputs')):
        run_name = f'{base_name}_{repeat:02d}'
        repeat += 1
    input_run = folder / 'input' / run_name
    output_run = folder / 'outputs' / run_name
    if resume_name:
        threads = tasks[0]['settings']['threads']
        planned_ids = [task['run_id'] for task in tasks]
        tasks = json.loads((input_run / 'plan.json').read_text())['tasks']
        if [task['run_id'] for task in tasks] != planned_ids:
            raise ValueError('Resume selection differs from the saved plan; match stage/method/configuration first')
        if not 1 <= start_case <= len(tasks):
            raise ValueError('START_CASE is outside the saved plan')
        for task in tasks[start_case - 1:]:
            task['settings']['threads'] = threads
        print(f'Resuming case {start_case}/{len(tasks)} with {threads} CPU threads; saved geometry/flow/wake settings retained.', flush=True)
    else:
        start_case = 1
        input_run.mkdir(parents=True)
        output_run.mkdir(parents=True)
        for i, task in enumerate(tasks, 1):
            model_name = f'model_{i:03d}_{identifier(task["run_id"])}'
            task['input_directory'] = str(input_run / model_name)
            task['output_directory'] = str(output_run / model_name)
    save_json(input_run / 'plan.json', {'stage': prefix, 'tasks': tasks})
    print(f'{len(tasks)} sequential solver runs. Inputs: {input_run}', flush=True)
    print(f'Solver outputs: {output_run}', flush=True)
    from .runner import run_task

    for i, task in enumerate(tasks, 1):
        if i < start_case:
            continue
        target = Path(task['input_directory'])
        target.mkdir(parents=True, exist_ok=bool(resume_name))
        Path(task['output_directory']).mkdir(parents=True, exist_ok=bool(resume_name))
        save_json(target / 'task.json', task)
        print(f'[{i}/{len(tasks)}] {task["run_id"]}', flush=True)
        run_task(target / 'task.json')
        print('  Completed; saved the model and native solver outputs.', flush=True)
    print(f'Saved models: {input_run}', flush=True)
    print(f'Native solver files: {output_run}', flush=True)
    print('Plot generation is intentionally a separate later step.', flush=True)
    return output_run
