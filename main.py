"""Run XML extraction and OpenVSP geometry generation in sequence."""
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

import os

os.system('cls')

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('wing-tail', 'all'), default='all',
                        help='wing-tail: wing, HTP and VTP; all: include fuselage (default)')
    parser.add_argument('--xml', type=Path, default=ROOT / 'inputs' / 'toolOutput.xml')
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'geometry_data')
    parser.add_argument('--output', type=Path, help='Optional output path; defaults depend on --mode')
    parser.add_argument('--api-dir', type=Path, help='Optional directory containing the OpenVSP binding')
    parser.add_argument('--validate-only', action='store_true', help='Run parser and CSV validation, without OpenVSP')
    parser.add_argument('--chordwise', type=int, default=41)
    parser.add_argument('--spanwise', type=int, default=16)
    args = parser.parse_args()
    if not args.xml.is_file():
        parser.error(f'XML does not exist: {args.xml}')
    if min(args.chordwise, args.spanwise) < 2:
        parser.error('Tessellation must be at least 2')
    xml = args.xml.resolve()
    data = args.data_dir.resolve()
    builder = ROOT / ('build_wing_tail.py' if args.mode == 'wing-tail' else 'build_openvsp.py')
    if not builder.is_file():
        parser.error(f'Builder script does not exist: {builder}')
    filename = 'Lab2_wing_tail.vsp3' if args.mode == 'wing-tail' else 'Lab2_aircraft.vsp3'
    output = (args.output or ROOT / 'output' / filename).resolve()
    print(f'Python: {sys.executable}', flush=True)
    print(f'Mode: {args.mode} | Builder: {builder.name}', flush=True)
    steps = [
        ('1/2: Parse CPACS XML', [sys.executable, str(ROOT / 'parse_cpacs_geometry.py'),
                                str(xml), '--out', str(data)]),
        ('2/2: Validate CSV' if args.validate_only else '2/2: Build OpenVSP model',
         [sys.executable, str(builder), str(data / 'openvsp_input.csv'),
          '--output', str(output), '--chordwise', str(args.chordwise),
          '--spanwise', str(args.spanwise)]),
    ]
    if args.api_dir:
        steps[1][1].extend(['--api-dir', str(args.api_dir.resolve())])
    if args.validate_only:
        steps[1][1].append('--validate-only')
    for label, command in steps:
        print(f'\n{label}', flush=True)
        try:
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError as exc:
            print(f'\nStopped: {label} failed (exit {exc.returncode}).', file=sys.stderr)
            return exc.returncode if exc.returncode > 0 else 1
    print('\nParser and CSV validation complete.' if args.validate_only else f'\nModel created: {output}', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
