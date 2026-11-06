"""Run one sequential VLM/PANEL surface-mesh or wake-refinement stage."""
from __future__ import annotations

from pathlib import Path

from lab2.aero.study import execute_tasks, load_config, make_plan

ROOT = Path(__file__).resolve().parent

# Edit these values, then run this file directly from VS Code or a terminal.
CONFIG_FILE = ROOT / 'configs' / 'grid_study.json'
STAGE = 'surface'             # 'surface', 'wake-nodes', or 'wake-iterations'
SELECTED_MESH = 'coarse'      # For wake stages: 'coarse', 'medium', 'fine', or 'finest'
METHOD = None                # None runs both, or choose 'VLM' / 'PANEL'
CONFIGURATION = None          # None runs all, or choose 'WB', 'WBH', 'WBV', 'WBHV'
WAKE_NODES = None             # Base count when nodes are not being swept; e.g. 64
WAKE_ITERATIONS = None        # Base count when iterations are not being swept
OUTPUT_ROOT = None            # None uses output_root from CONFIG_FILE
RESUME_STUDY = None           # Existing study name; None starts a new study
START_CASE = 1                # One-based case number when resuming; reruns this case

def main():
    if STAGE not in ('surface', 'wake-nodes', 'wake-iterations'):
        raise ValueError('STAGE must be surface, wake-nodes, or wake-iterations')
    if STAGE != 'surface' and not SELECTED_MESH:
        raise ValueError('Choose SELECTED_MESH after visually inspecting the surface-run models')
    if METHOD not in (None, 'VLM', 'PANEL'):
        raise ValueError('METHOD must be None, VLM, or PANEL')
    if CONFIGURATION not in (None, 'WB', 'WBH', 'WBV', 'WBHV'):
        raise ValueError('CONFIGURATION must be None, WB, WBH, WBV, or WBHV')

    cfg = load_config(CONFIG_FILE)
    ref, flow = cfg['reference'], cfg['flow']
    print(f'References: Sref={ref["Sref"]:.6g} m2, bref={ref["bref"]:.6f} m, cref={ref["cref"]:.6g} m', flush=True)
    print(f'Moment reference: ({ref["Xcg"]:.6f}, {ref["Ycg"]:.6f}, {ref["Zcg"]:.6f}) m; {cfg["moment_reference"]}', flush=True)
    print(f'Flow: Mach={flow["mach"]:.6g}, V={flow["speed_m_s"]:.6f} m/s, rho={flow["density_kg_m3"]:.8g} kg/m3, mu={flow["viscosity_kg_ms"]:.8g} kg/(m s)', flush=True)
    print(f'ReCref = rho * V * cref / mu = {flow["reynolds"]:.8g}', flush=True)
    if 'mach_from_speed' in flow:
        print(f'Mach cross-check from V / sqrt(gamma*R*T): {flow["mach_from_speed"]:.6f}; T={flow["temperature_K"]:.2f} K, altitude={flow["altitude_m"]:.0f} m', flush=True)
    if WAKE_NODES is not None:
        if not isinstance(WAKE_NODES, int) or WAKE_NODES < 8 or WAKE_NODES & (WAKE_NODES - 1):
            raise ValueError('WAKE_NODES must be a power of two >= 8')
        cfg['wake']['nodes'] = WAKE_NODES
    if WAKE_ITERATIONS is not None:
        if not isinstance(WAKE_ITERATIONS, int) or not 3 <= WAKE_ITERATIONS <= 255:
            raise ValueError('WAKE_ITERATIONS must be from 3 through 255')
        cfg['wake']['iterations'] = WAKE_ITERATIONS
        cfg['wake_node_iterations'] = WAKE_ITERATIONS
    # A leftover mesh choice is ignored while running the surface sweep.
    mesh = None if STAGE == 'surface' else SELECTED_MESH
    tasks = make_plan(cfg, STAGE, mesh)
    if METHOD:
        tasks = [task for task in tasks if task['method'] == METHOD]
    if CONFIGURATION:
        tasks = [task for task in tasks if task['configuration'] == CONFIGURATION]
    if not tasks:
        raise ValueError('No solver runs selected')
    output_root = Path(OUTPUT_ROOT).resolve() if OUTPUT_ROOT else Path(cfg['output_root'])
    print(f'Solver CPU threads per run: {cfg["threads"]}', flush=True)
    folder = execute_tasks(tasks, output_root, prefix=STAGE.replace('-', '_'),
                           resume_name=RESUME_STUDY, start_case=START_CASE)
    print(f'Study folder: {folder}', flush=True)
    print('All requested runs completed. Inspect their .vsp3 models and solver outputs before choosing a mesh.', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
