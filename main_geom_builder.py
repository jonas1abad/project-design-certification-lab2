"""Run geometry extraction, Section A extraction and OpenVSP generation."""
from __future__ import annotations
import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def find_section_a_sources(xml):
    """Find a local VAMPzero run only when its companion XML matches exactly."""
    baseline = ROOT.parent.parent / 'UC3M2.1_baseline_case' / 'UC3MX.Y_template'
    candidates = [(xml.parent / 'VAMPzero.m', xml)]
    if xml.parent.name.lower() == 'tooloutput':
        candidates.append((xml.parent.parent / 'ReturnDirectory' / 'VAMPzero.m', xml))
    candidates.append((baseline / 'ReturnDirectory' / 'VAMPzero.m',
                       baseline / 'ToolOutput' / 'toolOutput.xml'))
    digest = hashlib.sha256(xml.read_bytes()).digest()
    for matlab, companion in candidates:
        if (matlab.is_file() and companion.is_file() and
                hashlib.sha256(companion.read_bytes()).digest() == digest):
            return matlab.resolve(), companion.resolve()
    return None, None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('wing-tail', 'all'), default='all',
                        help='wing-tail: wing, HTP and VTP; all: include fuselage (default)')
    parser.add_argument('--xml', type=Path, default=ROOT / 'inputs' / 'toolOutput.xml')
    parser.add_argument('--data-dir', type=Path, default=ROOT / 'geometry_data')
    parser.add_argument('--output', type=Path, help='Optional output path; defaults depend on --mode')
    parser.add_argument('--api-dir', type=Path, help='Optional directory containing the OpenVSP binding')
    parser.add_argument('--vampzero', type=Path, help='Section A VAMPzero.m; otherwise look for a matching local run')
    parser.add_argument('--companion-xml', type=Path, help='XML from the --vampzero run; defaults to its sibling ToolOutput/toolOutput.xml')
    parser.add_argument('--validate-only', action='store_true', help='Extract geometry and Section A, then validate CSV without OpenVSP')
    parser.add_argument('--chordwise', type=int, default=41)
    parser.add_argument('--spanwise', type=int, default=16)
    args = parser.parse_args()
    if not args.xml.is_file():
        parser.error(f'XML does not exist: {args.xml}')
    if min(args.chordwise, args.spanwise) < 2:
        parser.error('Tessellation must be at least 2')
    xml = args.xml.resolve()
    data = args.data_dir.resolve()
    if args.companion_xml and not args.vampzero:
        parser.error('--companion-xml requires --vampzero')
    if args.vampzero:
        matlab = args.vampzero.resolve()
        companion = (args.companion_xml or matlab.parent.parent / 'ToolOutput' / 'toolOutput.xml').resolve()
        if not matlab.is_file():
            parser.error(f'VAMPzero source does not exist: {matlab}')
        if not companion.is_file():
            parser.error(f'Companion XML does not exist: {companion}; provide --companion-xml')
        if hashlib.sha256(xml.read_bytes()).digest() != hashlib.sha256(companion.read_bytes()).digest():
            parser.error('Companion XML differs from geometry XML; refusing to combine aircraft data')
    else:
        matlab, companion = find_section_a_sources(xml)
    builder = 'lab2.geometry.' + ('build_wing_tail' if args.mode == 'wing-tail' else 'build_openvsp')
    filename = 'Lab2_wing_tail.vsp3' if args.mode == 'wing-tail' else 'Lab2_aircraft.vsp3'
    output = (args.output or ROOT / 'output' / filename).resolve()
    print(f'Python: {sys.executable}', flush=True)
    print(f'Mode: {args.mode} | Builder: {builder}', flush=True)
    if matlab:
        print(f'Section A operating source: {matlab}', flush=True)
    else:
        print('Section A: no matching VAMPzero.m found; operating values will be omitted. '
              'Provide --vampzero and --companion-xml to include them.', flush=True)
    section_a_command = [sys.executable, '-m', 'lab2.section_a',
                         '--xml', str(xml), '--out', str(data / 'section_a.csv')]
    if matlab:
        section_a_command.extend(['--vampzero', str(matlab), '--companion-xml', str(companion)])
    steps = [
        ('1/3: Parse CPACS geometry', [sys.executable, '-m', 'lab2.geometry.parse_cpacs_geometry',
                                str(xml), '--out', str(data)]),
        ('2/3: Extract Section A data', section_a_command),
        ('3/3: Validate CSV' if args.validate_only else '3/3: Build OpenVSP model',
         [sys.executable, '-m', builder, str(data / 'openvsp_input.csv'),
          '--output', str(output), '--chordwise', str(args.chordwise),
          '--spanwise', str(args.spanwise)]),
    ]
    if args.api_dir:
        steps[2][1].extend(['--api-dir', str(args.api_dir.resolve())])
    if args.validate_only:
        steps[2][1].append('--validate-only')
    for label, command in steps:
        print(f'\n{label}', flush=True)
        try:
            subprocess.run(command, check=True, cwd=ROOT)
        except subprocess.CalledProcessError as exc:
            print(f'\nStopped: {label} failed (exit {exc.returncode}).', file=sys.stderr)
            return exc.returncode if exc.returncode > 0 else 1
    print(f'\nSection A CSV: {data / "section_a.csv"}', flush=True)
    print('Geometry extraction and CSV validation complete.' if args.validate_only else f'Model created: {output}', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
