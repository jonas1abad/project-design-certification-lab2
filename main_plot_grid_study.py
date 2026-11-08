"""Plot completed native VSPAERO surface runs. Edit settings and run this file."""
from pathlib import Path

from lab2.aero.postprocess import collect_surface, compare_levels, plot_surface, write_csv

ROOT = Path(__file__).resolve().parent
STUDY_NAME = 'surface_VLM_PANEL_all_configs'
STUDY_ROOT = ROOT / 'output/grid_fixed'
PLAN_FILE = STUDY_ROOT / 'input' / STUDY_NAME / 'plan.json'
METHOD = 'PANEL'
OUTPUT_FOLDER = STUDY_ROOT / 'plots' / STUDY_NAME / METHOD
RELATIVE_TOLERANCE = 0.01  # 1%; exploratory comparison, not an acceptance requirement
ABSOLUTE_TOLERANCE = 1e-4  # Avoid percentage-only decisions near zero
SHOW_PLOTS = True


def main():
    rows, pending = collect_surface(PLAN_FILE, METHOD)
    compared = compare_levels(rows, RELATIVE_TOLERANCE, ABSOLUTE_TOLERANCE)
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
    write_csv(OUTPUT_FOLDER / 'mesh_comparison.csv', compared)
    plot_surface(rows, OUTPUT_FOLDER, SHOW_PLOTS, RELATIVE_TOLERANCE, ABSOLUTE_TOLERANCE)
    lines = [f'{METHOD}: {len(set(r["run_id"] for r in rows))} completed surface cases.',
             f'{len(pending)} planned cases are missing completion records.',
             'The last available mesh is a comparison reference, not an exact solution.',
             'Review all configurations and derivatives before choosing a common resolution.',
             'A pass to the last mesh alone does not prove monotonic or asymptotic convergence.',
             'Wake convergence must be studied separately.',
             'Derivatives retain the native .stab table conventions (Alpha/Beta per radian).',
             'Surface loops and solver equations are separate counts; no ADB parsing.',
             f'Exploratory tolerance: {ABSOLUTE_TOLERANCE} + {RELATIVE_TOLERANCE} * abs(last value).',
             'Pending runs:', *pending]
    (OUTPUT_FOLDER / 'notes.txt').write_text('\n'.join(lines), encoding='utf-8')
    print('\n'.join(lines[:9]))
    print(f'Saved plots and comparison CSV: {OUTPUT_FOLDER}')


if __name__ == '__main__':
    main()
