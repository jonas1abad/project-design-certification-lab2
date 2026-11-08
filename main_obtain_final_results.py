"""Run the selected VLM and PANEL configurations for the final stability derivatives."""
from pathlib import Path

from lab2.aero.study import execute_tasks, load_config, make_plan

ROOT = Path(__file__).resolve().parent
CONFIG_FILE = ROOT / 'configs' / 'grid_study.json'
OUTPUT_ROOT = ROOT / 'output' / 'final'

# Edit these settings and run this file with the OpenVSP Python environment.
METHODS = ('VLM', 'PANEL')
CONFIGURATIONS = ('WB', 'WBH', 'WBV', 'WBHV')
SELECTED_MESH = 'fine'
WAKE_ITERATIONS = 12
WAKE_NODES = 128
THREADS = 4
ALPHA_DEG = 0.0
BETA_DEG = 0.0
RESUME_STUDY = None  # Existing final study directory name when resuming
START_CASE = 1       # First case to rerun when resuming, using the saved settings


def main():
    cfg = load_config(CONFIG_FILE)
    cfg['methods'] = list(METHODS)
    cfg['configurations'] = list(CONFIGURATIONS)
    cfg['cases'] = [{'name': 'reference', 'alpha_deg': ALPHA_DEG, 'beta_deg': BETA_DEG}]
    cfg['threads'] = THREADS
    cfg['stability'] = True
    cfg['wake'] = {'fixed': False, 'nodes': WAKE_NODES, 'iterations': WAKE_ITERATIONS}
    tasks = make_plan(cfg, stage='final', mesh=SELECTED_MESH)
    if not tasks:
        raise ValueError('Select at least one method and geometry set')

    flow, ref = cfg['flow'], cfg['reference']
    if not RESUME_STUDY:
        print(f'{len(tasks)} stability runs with {THREADS} threads per run on the {SELECTED_MESH} mesh.', flush=True)
        print(f'Free wake with {WAKE_ITERATIONS} iterations and {WAKE_NODES} nodes.', flush=True)
        print(f'Mach {flow["mach"]:.3f}, Re {flow["reynolds"]:.7g}, '
              f'alpha {ALPHA_DEG:g} deg, beta {BETA_DEG:g} deg.', flush=True)
        print(f'Sref {ref["Sref"]:.6g} m2, bref {ref["bref"]:.6g} m, cref {ref["cref"]:.6g} m, '
              f'moment reference ({ref["Xcg"]:.6g}, {ref["Ycg"]:.6g}, {ref["Zcg"]:.6g}) m.', flush=True)
    folder = execute_tasks(tasks, OUTPUT_ROOT, prefix='final',
                           resume_name=RESUME_STUDY, start_case=START_CASE)
    print(f'Final stability results and native .stab files: {folder}', flush=True)


if __name__ == '__main__':
    main()
