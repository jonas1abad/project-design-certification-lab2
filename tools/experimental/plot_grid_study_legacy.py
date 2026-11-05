"""Archived prototype for the obsolete API-results layout. See README.md."""
from __future__ import annotations
import argparse
from collections import defaultdict
import json
import math
from pathlib import Path

from lab2.aero.study import csv_rows, write_rows


def collect_results(folder):
    folder = Path(folder)
    plan = json.loads((folder / 'plan.json').read_text())
    summary, metrics, complete = [], [], []
    for task in plan:
        run = folder / 'runs' / task['run_id']
        common = {key: task[key] for key in ('run_id','stage','method','configuration','variant','sweep_value')}
        common.update(case=task['case']['name'], alpha_deg=task['case']['alpha_deg'], beta_deg=task['case']['beta_deg'])
        if (run / 'failure.json').exists() or not (run / 'result.json').exists():
            summary.append(dict(common, status='failed' if (run / 'failure.json').exists() else 'not_run'))
            continue
        result = json.loads((run / 'result.json').read_text())
        if result.get('status') != 'completed':
            summary.append(dict(common, status='failed'))
            continue
        counts = result['mesh_counts']
        common.update(solver_loops=counts['solver_loops'], surface_faces=counts['surface_faces'],
                      nodes=counts['nodes'], solver_seconds=result['solver_seconds'])
        summary.append(dict(common, status='completed', **result['metrics']))
        for name, value in result['metrics'].items():
            if not isinstance(value, (int,float)) or not math.isfinite(value):
                raise ValueError(f'Nonfinite saved metric: {task["run_id"]}/{name}')
            metrics.append(dict(common, metric=name, value=value))
        complete.append((task, result))
    groups = defaultdict(list)
    for row in metrics:
        groups[(row['stage'], row['method'], row['configuration'], row['case'], row['metric'])].append(row)
    changes = []
    for group in groups.values():
        ordered = sorted(group, key=lambda r:r['sweep_value'])
        previous = None
        finest = ordered[-1]['value']
        for row in ordered:
            difference = row['value'] - previous['value'] if previous else None
            percent = 100*difference/abs(previous['value']) if previous and abs(previous['value'])>1e-12 else None
            changes.append(dict(row, previous_variant=previous['variant'] if previous else '',
                                successive_change=difference, successive_change_percent=percent,
                                change_from_last_available=row['value']-finest))
            previous = row
    indexed = {(t['stage'],t['method'],t['variant'],t['case']['name'],t['configuration']):(t,r) for t,r in complete}
    contributions = []
    differences = {'HTP_on_WB': [('WBH',1),('WB',-1)],
                   'VTP_on_WB': [('WBV',1),('WB',-1)],
                   'HTP_with_VTP': [('WBHV',1),('WBV',-1)],
                   'VTP_with_HTP': [('WBHV',1),('WBH',-1)],
                   'tail_interaction': [('WBHV',1),('WBH',-1),('WBV',-1),('WB',1)]}
    for key in sorted({k[:4] for k in indexed}):
        for label, components in differences.items():
            if not all(key+(name,) in indexed for name,_ in components):
                continue
            pairs = [indexed[key+(name,)] for name,_ in components]
            if any((t['settings']['reference'],t['settings']['flow'],t['wake'],t['mesh']) !=
                   (pairs[0][0]['settings']['reference'],pairs[0][0]['settings']['flow'],pairs[0][0]['wake'],pairs[0][0]['mesh'])
                   for t,_ in pairs[1:]):
                raise ValueError('Cannot subtract configurations with different normalization, flow, mesh or wake settings')
            names = set.intersection(*(set(r['metrics']) for _,r in pairs))
            for metric in sorted(names):
                value = sum(sign*pair[1]['metrics'][metric] for pair,(_,sign) in zip(pairs,components))
                contributions.append(dict(stage=key[0],method=key[1],variant=key[2],case=key[3],
                                          sweep_value=pairs[0][0]['sweep_value'],contribution=label,metric=metric,value=value))
    results = folder / 'results'
    write_rows(results / 'summary.csv', summary, None if summary else ['run_id','status'])
    write_rows(results / 'metrics.csv', metrics, None if metrics else ['run_id','metric','value'])
    write_rows(results / 'changes.csv', changes, None if changes else ['run_id','metric','value','successive_change'])
    write_rows(results / 'tail_contributions.csv', contributions, None if contributions else ['contribution','metric','value'])
    (results / 'README.txt').write_text(
        'Acceptance is by visual review. Completed means a solver output was read, not that the mesh converged.\n'
        'N is actual solver vortex-loop count read from the ADB header; input faces and nodes are also recorded.\n'
        'changes.csv compares the same method/configuration/condition/metric only. Missing runs remain explicit in summary.csv.\n'
        'Percent changes are blank when the previous value is numerically zero. The last available level is not an exact solution.\n'
        'Tail contributions are installed increments from configuration subtraction with common references/settings.\n'
        'Native derivative names and solver units are retained. Inspect .stab and raw_results.json before interpreting axes/units.\n', encoding='utf-8')
    return summary, changes, contributions


def plot_results(folder):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    folder = Path(folder)
    _, changes, contributions = collect_results(folder)
    output = folder / 'results' / 'plots'
    output.mkdir(parents=True, exist_ok=True)
    groups = defaultdict(list)
    for row in changes:
        groups[(row['stage'],row['method'],row['configuration'],row['case'])].append(row)
    for (stage,method,configuration,case), group in groups.items():
        title = f'{method} {configuration} {case} - {stage}'
        prefix = f'{stage}_{method}_{configuration}_{case}'
        base_names = ['CL','CDi','CDtot','CS','CMx','CMy','CMz']
        derivative_names = sorted({r['metric'] for r in group} - set(base_names))
        for kind,names in [('coefficients',base_names),('derivatives',derivative_names)]:
            for page in range(0,len(names),12):
                selected = names[page:page+12]
                fig, axes = plt.subplots(math.ceil(len(selected)/3),3,figsize=(14,3.5*math.ceil(len(selected)/3)),squeeze=False)
                for ax,metric in zip(axes.flat, selected):
                    rows=sorted((r for r in group if r['metric']==metric),key=lambda r:r['sweep_value'])
                    x=[r['solver_loops'] if stage=='surface' else r['sweep_value'] for r in rows]
                    ax.plot(x,[r['value'] for r in rows],'-o',linewidth=1.4)
                    for xx,row in zip(x,rows): ax.annotate(row['variant'],(xx,row['value']),fontsize=7,xytext=(3,5),textcoords='offset points')
                    ax.set(title=metric,xlabel='Solver vortex loops' if stage=='surface' else stage.replace('-',' '),ylabel='Coefficient / native derivative')
                    ax.ticklabel_format(useOffset=False,axis='y');ax.grid(alpha=.25)
                for ax in list(axes.flat)[len(selected):]: ax.set_visible(False)
                fig.suptitle(title+' - '+kind+' (visual selection)');fig.tight_layout()
                fig.savefig(output/f'{prefix}_{kind}_{page//12+1}.png',dpi=160);plt.close(fig)
        for kind,field,label in [('absolute','successive_change','Absolute change between available levels'),
                                 ('percent','successive_change_percent','Change (%) - undefined near zero')]:
            names=base_names+derivative_names
            for page in range(0,len(names),12):
                selected=names[page:page+12]
                fig,axes=plt.subplots(math.ceil(len(selected)/3),3,figsize=(14,3*math.ceil(len(selected)/3)),squeeze=False)
                for ax,metric in zip(axes.flat,selected):
                    rows=sorted((r for r in group if r['metric']==metric and r[field] is not None),key=lambda r:r['sweep_value'])
                    ax.plot([r['solver_loops'] if stage=='surface' else r['sweep_value'] for r in rows],
                            [abs(r[field]) for r in rows],'-o')
                    ax.set(title=metric,xlabel='Solver vortex loops' if stage=='surface' else stage.replace('-',' '),ylabel=label)
                    ax.grid(alpha=.25)
                for ax in list(axes.flat)[len(selected):]:ax.set_visible(False)
                fig.suptitle(title+' - successive '+kind+' changes');fig.tight_layout()
                fig.savefig(output/f'{prefix}_changes_{kind}_{page//12+1}.png',dpi=160);plt.close(fig)
        unique={r['run_id']:r for r in group}
        rows=sorted(unique.values(),key=lambda r:r['sweep_value'])
        fig,ax=plt.subplots(figsize=(7,4))
        ax.plot([r['solver_loops'] if stage=='surface' else r['sweep_value'] for r in rows],[r['solver_seconds'] for r in rows],'-o')
        ax.set(title=title+' - runtime',xlabel='Solver vortex loops' if stage=='surface' else stage.replace('-',' '),ylabel='Solver wall time (s)')
        ax.grid(alpha=.25);fig.tight_layout();fig.savefig(output/f'{prefix}_runtime.png',dpi=160);plt.close(fig)
    tail_groups=defaultdict(list)
    for row in contributions:
        tail_groups[(row['stage'],row['method'],row['case'],row['contribution'])].append(row)
    for (stage,method,case,label),group in tail_groups.items():
        names=[n for n in ['CL','CMy','CMz','CS','CL_Alpha','CMy_Alpha','CS_Beta','CMz_Beta'] if any(r['metric']==n for r in group)]
        if not names:continue
        fig,axes=plt.subplots(math.ceil(len(names)/3),3,figsize=(14,3*math.ceil(len(names)/3)),squeeze=False)
        for ax,metric in zip(axes.flat,names):
            rows=sorted((r for r in group if r['metric']==metric),key=lambda r:r['sweep_value'])
            ax.plot([r['sweep_value'] for r in rows],[r['value'] for r in rows],'-o')
            ax.set(title=metric,xlabel='Refinement index' if stage=='surface' else stage.replace('-',' '),ylabel='Installed increment');ax.grid(alpha=.25)
        for ax in list(axes.flat)[len(names):]:ax.set_visible(False)
        fig.suptitle(f'{method} {case} {label}');fig.tight_layout();fig.savefig(output/f'{stage}_{method}_{case}_{label}.png',dpi=160);plt.close(fig)
    # Preserve a plot of all solver-case wake histories beside the grid curves.
    for file in (folder/'runs').glob('*/iteration_history.csv'):
        rows=csv_rows(file)
        if not rows:continue
        fields=[n for n in ('CLtot','CDi','CMytot','CL','CMy') if n in rows[0]]
        if not fields:continue
        fig,axes=plt.subplots(len(fields),1,figsize=(8,2.5*len(fields)),squeeze=False)
        for ax,metric in zip(axes.flat,fields):
            for case in sorted({r['solver_case'] for r in rows}):
                sub=[r for r in rows if r['solver_case']==case and r.get(metric) not in ('',None)]
                ax.plot([float(r['wake_iteration']) for r in sub],[float(r[metric]) for r in sub],'-o',label='solver case '+case,markersize=3)
            ax.set(xlabel='Wake iteration',ylabel=metric);ax.grid(alpha=.25);ax.legend(fontsize=7)
        fig.suptitle(file.parent.name+' - iteration history');fig.tight_layout();fig.savefig(output/(file.parent.name+'_iterations.png'),dpi=150);plt.close(fig)
    print(f'Plots: {output} ({len(list(output.glob("*.png")))} PNG files)',flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('study',type=Path)
    args=parser.parse_args()
    plot_results(args.study)
