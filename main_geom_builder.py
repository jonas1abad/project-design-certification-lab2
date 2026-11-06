"""Extract VAMPzero CPACS geometry and build an editable OpenVSP model."""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent

# Edit these settings and run this file from VS Code, or override them via CLI.
XML_FILE = ROOT / 'inputs' / 'toolOutput.xml'
MODE = 'all'                 # 'all' includes fuselage; 'wing-tail' excludes it
DATA_DIR = ROOT / 'geometry_data'
OUTPUT_FILE = None          # None uses output/Lab2_aircraft.vsp3 (or Lab2_wing_tail.vsp3)
API_DIR = None              # Optional directory containing the compatible OpenVSP binding
VALIDATE_ONLY = False      # True extracts and validates without importing OpenVSP
CHORDWISE = 41
SPANWISE = 16


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xml', type=Path, default=XML_FILE)
    parser.add_argument('--mode', choices=('all', 'wing-tail'), default=MODE)
    parser.add_argument('--data-dir', type=Path, default=DATA_DIR)
    parser.add_argument('--output', type=Path, default=OUTPUT_FILE)
    parser.add_argument('--api-dir', type=Path, default=API_DIR)
    parser.add_argument('--validate-only', action='store_true', default=VALIDATE_ONLY)
    parser.add_argument('--chordwise', type=int, default=CHORDWISE)
    parser.add_argument('--spanwise', type=int, default=SPANWISE)
    args = parser.parse_args()
    xml = args.xml.resolve()
    if not xml.is_file():
        raise FileNotFoundError(xml)
    if min(args.chordwise, args.spanwise) < 2:
        raise ValueError('Tessellation must be at least 2')
    data = args.data_dir.resolve()
    name = 'Lab2_aircraft.vsp3' if args.mode == 'all' else 'Lab2_wing_tail.vsp3'
    output = (args.output or ROOT / 'output' / name).resolve()
    builder = 'lab2.geometry.' + ('build_openvsp' if args.mode == 'all' else 'build_wing_tail')
    commands = [
        [sys.executable, '-m', 'lab2.geometry.parse_cpacs_geometry', str(xml), '--out', str(data)],
        [sys.executable, '-m', builder, str(data / 'openvsp_input.csv'), '--output', str(output),
         '--chordwise', str(args.chordwise), '--spanwise', str(args.spanwise)],
    ]
    if args.api_dir:
        commands[1].extend(['--api-dir', str(args.api_dir.resolve())])
    if args.validate_only:
        commands[1].append('--validate-only')
    print(f'Python: {sys.executable}', flush=True)
    for index, command in enumerate(commands, 1):
        print(f'[{index}/2] {command[2]}', flush=True)
        subprocess.run(command, cwd=ROOT, check=True)
    print(f'Geometry data: {data}', flush=True)
    print('CSV validation complete.' if args.validate_only else f'Model: {output}', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
