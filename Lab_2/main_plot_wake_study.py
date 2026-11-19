"""Plot completed wake-iteration or wake-node sweeps from native histories."""
import json
from pathlib import Path

from lab2.aero.postprocess import read_history_iterations

ROOT = Path(__file__).resolve().parent
PUBLISHED_ROOT = ROOT / 'results' / 'wake'
STUDIES = [
    (ROOT / 'output' / 'wake', 'wake_iterations_VLM_WBHV_fine_nodes128', 'VLM'),
    (ROOT / 'output' / 'wk', 'wake_iterations_PANEL_WBHV_fine_nodes128', 'PANEL'),
]
SHOW_PLOTS = False

METRICS = {
    'CLtot': 'Lift coefficient',
    'CDtot': 'Near-field total drag',
    'CDi': 'Induced drag coefficient',
    'CDtot_t': 'Trefftz-plane total drag',
    'CMytot': 'Pitching moment coefficient',
    'CStot': 'Side-force coefficient',
}


def plot_study(study_root, study_name, output_folder=None):
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MaxNLocator

    plan = study_root / 'input' / study_name / 'plan.json'
    tasks = sorted(json.loads(plan.read_text())['tasks'], key=lambda task: task['sweep_value'])
    first = tasks[0]
    stages = {'wake-iterations': 'iterations', 'wake-nodes': 'nodes'}
    sweep_key = stages[first['stage']]
    label = 'Wake iterations' if sweep_key == 'iterations' else 'Wake nodes'
    runs = []
    comparison = None
    for task in tasks:
        cfg = task['settings']
        wake = {key: value for key, value in task['wake'].items() if key != sweep_key}
        settings = (task['stage'], task['method'], task['configuration'], task['mesh'],
                    task['case'], cfg['model_sha256'], cfg['reference'], cfg['flow'], wake)
        if comparison is not None and settings != comparison:
            raise ValueError('Select a sweep with one configuration, mesh and flow condition')
        comparison = settings
        folder = ROOT / task['output_directory']
        result = json.loads((folder / 'result.json').read_text())
        if result['status'] != 'completed':
            raise ValueError(f'Incomplete wake run: {folder}')
        stem = 'model_DegenGeom' if task['method'] == 'VLM' else 'model_VSPGeom'
        history = read_history_iterations(folder / (stem + '.history'))[1]
        if history[-1]['Iter'] != task['wake']['iterations']:
            raise ValueError(f'Incomplete wake history: {folder}')
        runs.append((task['sweep_value'], history))

    fig, axes = plt.subplots(3, 2, figsize=(11, 9), layout='constrained')
    for ax, (metric, title) in zip(axes.flat, METRICS.items()):
        if sweep_key == 'iterations':
            for value, history in runs:
                ax.plot([row['Iter'] for row in history], [row[metric] for row in history],
                        marker='o', markevery=[-1], label=f'{value} iterations')
        else:
            ax.plot([value for value, _ in runs], [history[-1][metric] for _, history in runs],
                    'o-', label='Final value of each run')
        ax.set(xlabel=label, ylabel=metric, title=title)
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.ticklabel_format(axis='y', useOffset=False)
        if metric == 'CStot':
            ax.axhline(0, color='0.5', linewidth=.8, linestyle=':')
        ax.grid(alpha=.25)
    axes[0, 0].legend()
    fixed_key = 'nodes' if sweep_key == 'iterations' else 'iterations'
    fig.suptitle(f'{first["method"]} {first["configuration"]} | {first["mesh"]["name"]} mesh'
                 f' | {first["wake"][fixed_key]} wake {fixed_key} held fixed')
    output = output_folder or study_root / 'plots' / study_name
    output.mkdir(parents=True, exist_ok=True)
    for extension in ('png', 'pdf'):
        fig.savefig(output / f'wake_convergence.{extension}', dpi=180)
    for value, history in runs:
        print(f'{label} {value}: ' + ', '.join(f'{key}={history[-1][key]:.7g}' for key in METRICS))
    print(f'Saved wake convergence plot in {output}')
    return fig


def main():
    import matplotlib.pyplot as plt

    figures = []
    for working_root, study_name, published_name in STUDIES:
        plan = working_root / 'input' / study_name / 'plan.json'
        study_root, name = (working_root, study_name) if plan.is_file() else (PUBLISHED_ROOT, published_name)
        figures.append(plot_study(study_root, name, output_folder=working_root / 'plots' / study_name))
    if SHOW_PLOTS:
        plt.show()
    for figure in figures:
        plt.close(figure)


if __name__ == '__main__':
    main()
