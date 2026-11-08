"""Read native VSPAERO text files and compare surface mesh levels."""
from __future__ import annotations

import csv
import json
import math
import re
from collections import defaultdict
from pathlib import Path


def read_history_iterations(path):
    """Return the wake history of every explicitly numbered solver case."""
    cases = defaultdict(list)
    case = None
    header = None
    for line in Path(path).read_text().splitlines():
        match = re.match(r'\s*Solver Case:\s*(\d+)', line)
        if match:
            case, header = int(match[1]), None
        fields = line.split()
        if fields[:4] == ['Iter', 'Mach', 'AoA', 'Beta']:
            header = fields
        elif header and len(fields) == len(header):
            try:
                values = [float(re.sub(r'[+-]?nan\(ind\)', 'nan', token, flags=re.I)) for token in fields]
            except ValueError:
                continue
            if case is None:
                raise ValueError(f'Unnumbered history table: {path}')
            if not all(map(math.isfinite, values)):
                raise ValueError(f'Nonfinite solver output: {path}, case {case}, iteration {fields[0]}')
            cases[case].append(dict(zip(header, values)))
    if not cases:
        raise ValueError(f'No solver case in {path}')
    return dict(cases)


def read_history(path):
    """Return the final wake iteration of every explicitly numbered solver case."""
    return {case: iterations[-1] for case, iterations in read_history_iterations(path).items()}


def read_stability(path):
    """Read the derivative table as printed, preserving its coefficient axes."""
    columns = None
    rows = {}
    for line in Path(path).read_text().splitlines():
        fields = line.split()
        if fields[:2] == ['Coef', 'Total']:
            columns = fields[1:]
        elif columns and len(fields) == len(columns) + 1 and not line.lstrip().startswith('#'):
            try:
                values = [float(re.sub(r'[+-]?nan\(ind\)', 'nan', token, flags=re.I)) for token in fields[1:]]
            except ValueError:
                continue
            if not all(map(math.isfinite, values)):
                raise ValueError(f'Nonfinite derivative: {path}, coefficient {fields[0]}')
            rows[fields[0]] = dict(zip(columns, values))
    if not rows:
        raise ValueError(f'No derivative table in {path}')
    return rows


def read_mesh_counts(path):
    text = Path(path).read_text()
    counts = {}
    for key, label in [('surface_loops', 'Loops'), ('surface_nodes', 'Nodes')]:
        match = re.search(r'Total NumberOf' + label + r':\s*(\d+)', text)
        if not match:
            raise ValueError(f'Missing mesh count {label}: {path}')
        counts[key] = int(match[1])
    match = re.search(r'NumberOfEquations_:\s*(\d+)', text)
    counts['solver_equations'] = int(match[1]) if match else ''
    return counts


def write_csv(path, rows):
    keys = list(dict.fromkeys(key for row in rows for key in row))
    with Path(path).open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def collect_surface(plan_path, method):
    tasks = json.loads(Path(plan_path).read_text())['tasks']
    rows, pending = [], []
    for task in tasks:
        if task['method'] != method or task['stage'] != 'surface':
            continue
        output = Path(task['output_directory'])
        if not (output / 'result.json').exists():
            pending.append(task['run_id'])
            continue
        result = json.loads((output / 'result.json').read_text())
        if result['status'] != 'completed':
            raise ValueError(f'Unexpected result status: {output}')
        stem = 'model_DegenGeom' if method == 'VLM' else 'model_VSPGeom'
        history = read_history(output / (stem + '.history'))[1]
        cfg = task['settings']
        for key, expected in [('Mach', cfg['flow']['mach']), ('AoA', task['case']['alpha_deg']),
                              ('Beta', task['case']['beta_deg'])]:
            if not math.isclose(history[key], expected, abs_tol=1e-7):
                raise ValueError(f'Base condition mismatch: {output}/{key}')
        metrics = {key: history[key] for key in ('CLtot', 'CDtot', 'CDi', 'CMytot')}
        if cfg['stability']:
            stability = read_stability(output / (stem + '.stab'))
            for coef, variable in [('CL', 'Alpha'), ('CMm', 'Alpha'), ('CMm', 'q'),
                                   ('CS', 'Beta'), ('CMl', 'Beta'), ('CMn', 'Beta'),
                                   ('CMl', 'p'), ('CMn', 'r')]:
                metrics[f'{coef}_{variable}'] = stability[coef][variable]
        common = dict(run_id=task['run_id'], method=method, configuration=task['configuration'],
                      case=task['case']['name'], mesh=task['variant'], order=task['sweep_value'],
                      **read_mesh_counts(output / 'solver.log'), solver_seconds=result['solver_seconds'],
                      history_file=str(output / (stem + '.history')),
                      stability_file=str(output / (stem + '.stab')),
                      comparison_settings=json.dumps([cfg['reference'], cfg['flow'], task['wake'], task['case']], sort_keys=True))
        for metric, value in metrics.items():
            if not math.isfinite(value):
                raise ValueError(f'Nonfinite {metric}: {output}')
            rows.append(dict(common, metric=metric, value=value))
    if not rows:
        raise ValueError(f'No completed {method} surface runs in {plan_path}')
    return rows, pending


def compare_levels(rows, relative_tolerance, absolute_tolerance):
    groups = defaultdict(list)
    for row in rows:
        groups[row['configuration'], row['case'], row['metric']].append(row)
    compared = []
    for group in groups.values():
        group.sort(key=lambda row: row['order'])
        if len({r['comparison_settings'] for r in group}) != 1:
            raise ValueError('Reference, flow, wake or case changed within a mesh comparison')
        reference = group[-1]
        previous = None
        for row in group:
            tolerance = absolute_tolerance + relative_tolerance * abs(reference['value'])
            difference = row['value'] - reference['value']
            compared.append(dict(row,
                reference_mesh=reference['mesh'], last_available_difference=difference,
                last_available_difference_percent=100 * difference / abs(reference['value']) if abs(reference['value']) > absolute_tolerance else '',
                successive_difference=row['value'] - previous['value'] if previous else '',
                successive_change_percent=100 * (row['value'] - previous['value']) / abs(previous['value']) if previous and abs(previous['value']) > absolute_tolerance else '',
                within_tolerance_to_last=abs(difference) <= tolerance))
            previous = row
    return compared


def plot_surface(rows, destination, show=False, relative_tolerance=.01, absolute_tolerance=1e-4):
    import matplotlib.pyplot as plt

    configurations = list(dict.fromkeys(row['configuration'] for row in rows))
    cases = list(dict.fromkeys(row['case'] for row in rows))
    figures = []
    for case in cases:
        for name, metrics in [('coefficients', ['CLtot', 'CDtot', 'CDi', 'CMytot']),
                              ('derivatives', ['CL_Alpha', 'CMm_Alpha', 'CMm_q', 'CS_Beta', 'CMl_Beta', 'CMn_Beta', 'CMl_p', 'CMn_r'])]:
            metrics = [m for m in metrics if any(r['metric'] == m for r in rows)]
            if not metrics:
                continue
            fig, axes = plt.subplots(math.ceil(len(metrics) / 2), 2, figsize=(12, 3.2 * math.ceil(len(metrics) / 2)), squeeze=False)
            for ax, metric in zip(axes.flat, metrics):
                for configuration in configurations:
                    group = sorted([r for r in rows if r['configuration'] == configuration and r['metric'] == metric and r['case'] == case], key=lambda r: r['order'])
                    ax.plot([r['surface_loops'] for r in group], [r['value'] for r in group], 'o-', label=configuration)
                    for r in group:
                        ax.annotate(r['mesh'], (r['surface_loops'], r['value']), xytext=(3, 5), textcoords='offset points', fontsize=7)
                ax.set(xlabel='Surface loops before agglomeration', ylabel=metric)
                ax.grid(alpha=.25)
                ax.legend(fontsize=8)
            for ax in list(axes.flat)[len(metrics):]:
                ax.set_visible(False)
            fig.suptitle(f'{rows[0]["method"]} surface refinement — {case}\nFixed wake settings; surface convergence only')
            fig.tight_layout()
            for extension in ('png', 'pdf'):
                fig.savefig(Path(destination) / f'{case}_{name}.{extension}', dpi=180)
            figures.append(fig)
        fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
        for configuration in configurations:
            group = [r for r in rows if r['configuration'] == configuration and r['case'] == case]
            by_metric = defaultdict(list)
            for row in group:
                by_metric[row['metric']].append(row)
            errors = defaultdict(list)
            by_order = {}
            for metric_rows in by_metric.values():
                metric_rows.sort(key=lambda r: r['order'])
                reference = metric_rows[-1]['value']
                scale = absolute_tolerance + relative_tolerance * abs(reference)
                for row in metric_rows:
                    errors[row['order']].append(abs(row['value'] - reference) / scale)
                    by_order[row['order']] = row
            ordered = sorted(by_order)
            counts = [by_order[o]['surface_loops'] for o in ordered]
            axes[0].plot(counts, [max(errors[o]) for o in ordered], 'o-', label=configuration)
            axes[1].plot(counts, [by_order[o]['solver_seconds'] / 60 for o in ordered], 'o-', label=configuration)
        axes[0].axhline(1, color='black', linestyle='--', label='Exploratory tolerance')
        axes[0].set(ylabel='Largest scaled difference across plotted metrics', yscale='symlog', title='Difference from last available mesh')
        axes[1].set(ylabel='Solver time (minutes)', title='Computational cost')
        for ax in axes:
            ax.set_xlabel('Surface loops before agglomeration')
            ax.grid(alpha=.25)
            ax.legend(fontsize=8)
        fig.suptitle(f'{rows[0]["method"]} — {case}; last available mesh is not an exact solution')
        fig.tight_layout()
        for extension in ('png', 'pdf'):
            fig.savefig(Path(destination) / f'{case}_comparison_cost.{extension}', dpi=180)
        figures.append(fig)
    if show:
        plt.show()
    for fig in figures:
        plt.close(fig)
