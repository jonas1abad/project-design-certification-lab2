"""Build one OpenVSP 3.43 solver mesh and launch native VSPAERO."""
from __future__ import annotations
import argparse
import importlib
import json
import math
from pathlib import Path
import subprocess
import sys
import time

from .study import MEMBERS, digest, save_json, write_rows, fuselage_tessellation, lifting_surface_tessellation


def api_errors(v, context):
    mgr = v.ErrorMgrSingleton.getInstance()
    errors = []
    while mgr.GetNumTotalErrors():
        errors.append(mgr.PopLastError().GetErrorString())
    if errors:
        raise RuntimeError(context + ': ' + '; '.join(errors))


def set_parameter(v, pid, value, label, expected):
    if not pid:
        raise RuntimeError(f'Missing parameter {label}')
    v.SetParmVal(pid, value)
    expected.append((pid, value, label))


def check_parameters(v, expected):
    v.Update()
    for pid, value, label in expected:
        actual = v.GetParmVal(pid)
        if not math.isclose(actual, value, abs_tol=1e-8, rel_tol=1e-8):
            raise RuntimeError(f'Clamped/changed {label}: requested {value}, got {actual}')
    api_errors(v, 'Parameter readback')


def configure_geometry(v, task):
    """Use a fresh model, whitelist native components and change only meshing."""
    cfg, mesh = task['settings'], task['mesh']
    v.ClearVSPModel()
    v.ReadVSPFile(cfg['model'])
    v.Update()
    api_errors(v, 'Read model')
    ids = {}
    excluded = []
    reference_meshes = []
    for gid in v.FindGeoms():
        name, kind = v.GetGeomName(gid), v.GetGeomTypeName(gid).lower()
        if name in ('wing', 'htp', 'vtp', 'fuselage'):
            if name in ids or kind != ('fuselage' if name == 'fuselage' else 'wing'):
                raise ValueError(f'Duplicate or unexpected native geometry: {name} ({kind})')
            ids[name] = gid
        else:
            excluded.append(name)
            if kind == 'mesh':
                reference_meshes.append(gid)
    # In 3.43 PANEL export uses SET_SHOWN after CompGeom. A shown STL can
    # therefore leak into the export even when excluded from GeomSet, yielding
    # multiple mesh/wake blocks. Remove overlays from this in-memory copy.
    if reference_meshes:
        v.DeleteGeomVec(reference_meshes)
        v.Update()
    required = set(MEMBERS[task['configuration']])
    if not required <= ids.keys():
        raise ValueError(f'Missing components: {required - ids.keys()}')
    set_index = 6
    v.SetSetName(set_index, task['configuration'])
    for gid in v.FindGeoms():
        v.SetSetFlag(gid, set_index, gid in {ids[name] for name in required})
    actual = {v.GetGeomName(gid) for gid in v.GetGeomSetAtIndex(set_index)}
    if actual != required:
        raise RuntimeError(f'Wrong solver set: {actual}, expected {required}')
    expected = []
    fuselage_rows = []
    lifting_rows = []
    for name in sorted(required):
        gid = ids[name]
        set_parameter(v, v.FindParm(gid, 'Wake', 'Shape'), int(name != 'fuselage'),
                      name + '/Wake', expected)
        for pname, value in [('Tess_W', mesh['fuselage_w'] if name == 'fuselage' else mesh['chordwise'])]:
            set_parameter(v, v.FindParm(gid, pname, 'Shape'), value, name + '/' + pname, expected)
        if name == 'fuselage':
            surf = v.GetXSecSurf(gid, 0)
            length = v.GetParmVal(v.FindParm(gid, 'Length', 'Design'))
            stations = []
            for i in range(v.GetNumXSec(surf)):
                xs = v.GetXSec(surf, i)
                station = {axis: length*v.GetParmVal(v.GetXSecParm(xs, axis.upper()+'LocPercent'))
                           for axis in ('x', 'y', 'z')}
                station.update(width=v.GetXSecWidth(xs), height=v.GetXSecHeight(xs))
                stations.append(station)
            fuselage_rows = fuselage_tessellation(stations, mesh['fuselage_spacing_m'])
            for row in fuselage_rows:
                i = row['section_index']
                xs = v.GetXSec(surf, i)
                for parameter, value in (('SectTess_U', row['SectTess_U']),
                                         ('FwdCluster', 1.0), ('AftCluster', 1.0)):
                    set_parameter(v, v.GetXSecParm(xs, parameter), value,
                                  f'fuselage/section_{i}/{parameter}', expected)
        else:
            surf = v.GetXSecSurf(gid, 0)
            bays = []
            for i in range(1, v.GetNumXSec(surf)):
                xs = v.GetXSec(surf, i)
                bays.append({key: v.GetParmVal(v.GetXSecParm(xs, parameter))
                             for key, parameter in (('span', 'Span'), ('root_chord', 'Root_Chord'),
                                                    ('tip_chord', 'Tip_Chord'), ('sweep', 'Sweep'),
                                                    ('sweep_location', 'Sweep_Location'))})
            for row in lifting_surface_tessellation(bays, mesh['lifting_spacing_m']):
                i = row['section_index']
                lifting_rows.append(dict(component=name, **row))
                xs = v.GetXSec(surf, i)
                for parameter, value in (('SectTess_U', row['SectTess_U']),
                                         ('InCluster', 1.0), ('OutCluster', 1.0)):
                    set_parameter(v, v.GetXSecParm(xs, parameter), value,
                                  f'{name}/bay_{i}/{parameter}', expected)
            set_parameter(v, v.FindParm(gid, 'CapUMinTess', 'EndCap'), cfg['cap_tessellation'], name + '/CapUMinTess', expected)
            # Do not hide open wings by silently altering their geometry.
            if task['method'] == 'PANEL':
                for pname in ('CapUMinOption', 'CapUMaxOption'):
                    pid = v.FindParm(gid, pname, 'EndCap')
                    if not pid or v.GetParmVal(pid) == v.NO_END_CAP:
                        raise ValueError(f'{name} has an open end; inspect caps before PANEL analysis')
    check_parameters(v, expected)
    return set_index, expected, {'included': sorted(required), 'excluded': sorted(excluded),
                                 'fuselage_tessellation': fuselage_rows,
                                 'lifting_surface_tessellation': lifting_rows,
                                 'set_index': set_index, 'note': 'Only whitelisted native components enter the solver set.'}


def set_inputs(v, analysis, ints, doubles=None, strings=None):
    v.SetAnalysisInputDefaults(analysis)
    available = set(v.GetAnalysisInputNames(analysis))
    snapshot = {}
    for values, setter, getter in [(ints, v.SetIntAnalysisInput, v.GetIntAnalysisInput),
                                  (doubles or {}, v.SetDoubleAnalysisInput, v.GetDoubleAnalysisInput),
                                  (strings or {}, v.SetStringAnalysisInput, v.GetStringAnalysisInput)]:
        for name, value in values.items():
            if name not in available:
                raise RuntimeError(f'{analysis}: missing input {name}; API version mismatch')
            setter(analysis, name, [value])
            actual = list(getter(analysis, name))
            if len(actual) != 1 or (not math.isclose(actual[0], value, rel_tol=1e-9, abs_tol=1e-9)
                                    if isinstance(value, (int, float)) else actual[0] != value):
                raise RuntimeError(f'{analysis}/{name} readback mismatch: {actual}, expected {value}')
            snapshot[name] = value
    api_errors(v, f'{analysis} inputs')
    return snapshot


def write_solver_case(path, task):
    """Write the rigid, no-propeller case file used by the TFG launch pattern."""
    cfg = task['settings']
    ref, flow, wake = cfg['reference'], cfg['flow'], task['wake']
    values = dict(Sref=ref['Sref'], Cref=ref['cref'], Bref=ref['bref'],
                  X_cg=ref['Xcg'], Y_cg=ref['Ycg'], Z_cg=ref['Zcg'],
                  Mach=flow['mach'], AoA=task['case']['alpha_deg'], Beta=task['case']['beta_deg'],
                  Vinf=flow['speed_m_s'], Rho=flow['density_kg_m3'], ReCref=flow['reynolds'],
                  ClMax=-1, MaxTurningAngle=-1, Symmetry='NO', FarDist=-1,
                  NumWakeNodes=wake['nodes'], WakeIters=0 if wake['fixed'] else wake['iterations'],
                  NumberOfControlGroups=0, Preconditioner='Matrix')
    values['Karman-Tsien Correction'] = 'N'
    values['Stability Type'] = int(cfg['stability'])
    Path(path).write_text(''.join(f'{key} = {value}\n' for key, value in values.items()), encoding='utf-8')


def launch_solver(executable, folder, basename, threads, stability):
    """Stream merged solver stdout/stderr to the terminal and the case log."""
    command = [str(executable), '-omp', str(threads)]
    if stability:
        command.append('-stab')
    command.append(basename)
    display = subprocess.list2cmdline(command)
    print(display, flush=True)
    with (Path(folder) / 'solver.log').open('w', encoding='utf-8') as log:
        log.write(display + '\n')
        log.flush()
        process = subprocess.Popen(command, cwd=folder, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, errors='replace', bufsize=1)
        for line in process.stdout:
            print(line, end='', flush=True)
            log.write(line)
            log.flush()
        returncode = process.wait()
    if returncode:
        raise subprocess.CalledProcessError(returncode, command)


def run_task(task_file):
    task_file = Path(task_file).resolve()
    task = json.loads(task_file.read_text())
    cfg, input_folder = task['settings'], task_file.parent
    folder = Path(task.get('output_directory', str(input_folder))).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    if digest(cfg['model']) != cfg['model_sha256']:
        raise ValueError('Source model changed since planning; create a new study')
    if cfg.get('api_dir'):
        sys.path.insert(0, cfg['api_dir'])
    v = importlib.import_module('openvsp')
    version = v.GetVSPVersion()
    if version != 'OpenVSP ' + cfg['api_version']:
        raise RuntimeError(f'Expected OpenVSP {cfg["api_version"]}, got {version}; verify API inputs before changing versions')
    exe_dir = Path(cfg['vspaero_dir']) if cfg.get('vspaero_dir') else next(
        (p for p in Path(v.__file__).resolve().parents if (p / 'vspaero.exe').is_file()), None)
    if exe_dir is None or not (exe_dir / 'vspaero.exe').is_file():
        raise FileNotFoundError('Set vspaero_dir to the distribution directory containing vspaero.exe')
    v.SetVSPAEROPath(str(exe_dir))
    v.ClearAllResults() if hasattr(v, 'ClearAllResults') else None
    set_index, expected, membership = configure_geometry(v, task)
    if membership['fuselage_tessellation']:
        write_rows(input_folder / 'fuselage_tessellation.csv', membership['fuselage_tessellation'])
    write_rows(input_folder / 'lifting_surface_tessellation.csv', membership['lifting_surface_tessellation'])
    method = v.VORTEX_LATTICE if task['method'] == 'VLM' else v.PANEL
    common = {'AnalysisMethod': method, 'GeomSet': set_index, 'Symmetry': 0,
              'UseModeFlag': 0, 'AlternateInputFormatFlag': 0}
    inputs = {'geometry': set_inputs(v, 'VSPAEROComputeGeometry', common)}
    ints = dict(common, RefFlag=v.MANUAL_REF, AlphaNpts=1, BetaNpts=1, MachNpts=1, ReCrefNpts=1,
                NCPU=cfg['threads'], FixedWakeFlag=int(task['wake']['fixed']),
                WakeNumIter=task['wake']['iterations'], NumWakeNodes=task['wake']['nodes'],
                UnsteadyType=v.STABILITY_DEFAULT if cfg['stability'] else v.STABILITY_OFF,
                CGGeomSet=v.SET_NONE, CGDegenSet=v.SET_NONE, UseCGModeFlag=0,
                ClmaxToggle=0, MaxTurnToggle=0, GroundEffectToggle=0, KTCorrection=0,
                ActuatorDiskFlag=0, RotateBladesFlag=0, NoiseCalcFlag=0)
    doubles = dict(cfg['reference'], AlphaStart=task['case']['alpha_deg'], AlphaEnd=task['case']['alpha_deg'],
                   BetaStart=task['case']['beta_deg'], BetaEnd=task['case']['beta_deg'],
                   MachStart=cfg['flow']['mach'], MachEnd=cfg['flow']['mach'],
                   ReCref=cfg['flow']['reynolds'], ReCrefEnd=cfg['flow']['reynolds'],
                   Rho=cfg['flow']['density_kg_m3'], Vinf=cfg['flow']['speed_m_s'])
    inputs['solver'] = dict(ints, **doubles)
    # AnalysisManager inputs are temporary. Persist the corresponding GUI
    # settings too, so the saved input model shows the setup used for this run.
    container = v.FindContainer('VSPAEROSettings', 0)
    aliases = {'UseModeFlag': 'UseMode', 'CGGeomSet': 'MassSet',
               'CGDegenSet': 'MassDegenSet', 'UseCGModeFlag': 'CGUseMode',
               'NumWakeNodes': 'RootWakeNodes'}
    for name, value in inputs['solver'].items():
        pname = aliases.get(name, name)
        set_parameter(v, v.FindParm(container, pname, 'VSPAERO'), value,
                      'VSPAERO/' + pname, expected)
    check_parameters(v, expected)
    save_json(input_folder / 'inputs.json', {'api_version': version, 'membership': membership, 'inputs': inputs,
                                     'mesh': task['mesh'], 'wake': task['wake']})
    # Save only after both geometry and solver analysis inputs are configured.
    # inputs.json is kept alongside it because some OpenVSP versions do not
    # serialize transient AnalysisManager inputs into a .vsp3 model.
    prepared = input_folder / 'model.vsp3'
    v.SetVSP3FileName(str(prepared))
    v.WriteVSPFile(str(prepared), v.SET_ALL)
    api_errors(v, 'Save configured model')
    # Route generated solver files to the matching output directory while the
    # exact saved input model remains in the input directory.
    for file_type, name in (
            (v.VSPAERO_VSPGEOM_TYPE, 'model_VSPGeom.vspgeom'),
            (v.VSPAERO_PANEL_TRI_TYPE, 'model.tri'),
            (v.DEGEN_GEOM_CSV_TYPE, 'model_DegenGeom.csv'),
            (v.COMP_GEOM_TXT_TYPE, 'model_CompGeom.txt'),
            (v.COMP_GEOM_CSV_TYPE, 'model_CompGeom.csv')):
        v.SetComputationFileName(file_type, str(folder / name))
    v.Update()
    t0 = time.perf_counter()
    geometry_id = v.ExecAnalysis('VSPAEROComputeGeometry')
    api_errors(v, 'Compute solver geometry')
    if not geometry_id:
        raise RuntimeError('Geometry analysis returned no result')
    if task['method'] == 'PANEL':
        from .mesh import check_panel_mesh
        save_json(input_folder / 'panel_mesh_check.json',
                  check_panel_mesh(folder / 'model_VSPGeom.vspgeom'))
    geometry_seconds = time.perf_counter() - t0
    t0 = time.perf_counter()
    basename = 'model_VSPGeom' if task['method'] == 'PANEL' else 'model_DegenGeom'
    write_solver_case(folder / (basename + '.vspaero'), task)
    launch_solver(exe_dir / 'vspaero.exe', folder, basename, cfg['threads'], cfg['stability'])
    solver_seconds = time.perf_counter() - t0
    from .postprocess import read_history, read_stability
    history = read_history(folder / (basename + '.history'))
    if set(history) != set(range(1, 8) if cfg['stability'] else [1]):
        raise RuntimeError('Solver history is missing requested cases')
    if cfg['stability']:
        read_stability(folder / (basename + '.stab'))
    save_json(folder / 'result.json', {'status': 'completed', 'run_id': task['run_id'],
              'api_version': version, 'source_model_sha256': cfg['model_sha256'],
              'membership': membership, 'geometry_seconds': geometry_seconds,
              'solver_seconds': solver_seconds,
              'model_file': str(prepared),
              'mesh_settings': task['mesh'], 'wake_settings': task['wake'],
              'finite_output_check': 'Native history and stability values checked; this is not convergence acceptance.',
              'result_source': 'Native .history, .lod and .stab files; parsing deferred to postprocessing.',
              'convergence': 'Not automatically accepted. Review native solver files.'})
    print('Completed', task['run_id'], flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task', required=True, type=Path)
    arguments = parser.parse_args()
    run_task(arguments.task)
