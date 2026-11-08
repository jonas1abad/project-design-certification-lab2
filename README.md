# UC3M Aircraft Design & Certification — Lab 2

Build a parametric OpenVSP aircraft from CPACS, extract the requested Section A data, and run sequential VLM/PANEL mesh and wake studies.

## Project layout

```text
main_geom_builder.py       Geometry + Section A workflow
main_grid_study.py         Edit settings here, then run the study
main_plot_grid_study.py    Plot surface refinement results
main_plot_wake_study.py    Plot wake iteration and node sweeps
main_obtain_final_results.py  Run the final stability cases
main.py                    Compatibility entry point for geometry
lab2/
  geometry/                CPACS parser and OpenVSP builders
  section_a.py             Concise Section A CSV extraction
  aero/study.py            Configuration, refinement calculations and run planning
  aero/runner.py           Solver preparation and live native VSPAERO launch
configs/grid_study.json    Mesh levels, flow source and solver defaults
inputs/toolOutput.xml      Example CPACS input
geometry_data/             Generated geometry CSV/DAT and section_a.csv (ignored)
output/                    Generated models and solver files (ignored)
docs/                      Installation, geometry interface and study notes
results/                   Published surface, wake and final runs, plus figures
```

Working runs, local environments and diagnostic files are ignored. Published snapshots are indexed in [results](results/README.md).

## Setup

The current integration targets **OpenVSP 3.43.0, Python 3.11, Windows x64**. Python's version and architecture must match the compiled OpenVSP API. Install the API and its companion packages from the official distribution rather than an unrelated PyPI package.

See [Windows setup](docs/SETUP_WINDOWS.md) for environment creation and API installation. Project dependencies are `numpy` and `tqdm`; plotting dependencies are optional and separate.

## Build geometry and extract Section A

Run `main_geom_builder.py` in your compatible environment. `main.py` remains an alias for the same workflow.

```powershell
python main_geom_builder.py
```

The sequential steps are:

1. Parse `inputs/toolOutput.xml` into `geometry_data`.
2. Export the requested masses, CG limits, reference quantities and available operating values to `geometry_data/section_a.csv`.
3. Build `output/Lab2_aircraft.vsp3`, with wing, HTP, VTP and fuselage.

For the lifting surfaces only:

```powershell
python main_geom_builder.py --mode wing-tail
```

The full model has sets `WB`, `WBH`, `WBV`, `WBHV`; the lifting-surface model has `W`, `WH`, `WV`, `WHV`. Airfoil DAT files stay alongside `openvsp_input.csv`.

Operating values require a matching VAMPzero run. The launcher searches the local baseline and accepts it only if its companion XML matches the geometry input byte-for-byte. You can specify it explicitly:

```powershell
python main_geom_builder.py --vampzero "C:\MyRun\ReturnDirectory\VAMPzero.m" --companion-xml "C:\MyRun\ToolOutput\toolOutput.xml"
```

If no matching run is found, operating values are omitted and the launcher reports it. MATLAB assignments are read as numeric source data, never executed. The grid study needs the cruise data or explicit flow values in its configuration.

To extract and check the CSVs without importing OpenVSP:

```powershell
python main_geom_builder.py --validate-only
```

Direct module commands are also available from the repository root:

```powershell
python -m lab2.geometry.parse_cpacs_geometry inputs/toolOutput.xml --out geometry_data
python -m lab2.geometry.build_openvsp --validate-only
python -m lab2.section_a
```

## Run a grid study

Edit the settings block at the top of **`main_grid_study.py`**, then run that file from your editor. No command-line options are required. The default selection runs both methods and all four body-containing configurations.

```python
STAGE = 'surface'
METHOD = None                 # Both methods; or 'VLM' / 'PANEL'
CONFIGURATION = None          # All sets; or 'WB', 'WBH', 'WBV', 'WBHV'
WAKE_ITERATIONS = None         # Surface default: 3
```

The workflow runs cases in sequence and stops at the first exception so the debugger can inspect it. Native solver progress appears live in the terminal and is also written to each case's `solver.log`.

Study order:

1. Surface mesh sweep: `coarse`, `medium`, `fine`, `finest`, using three wake iterations.
2. Wake-iteration sweep on a selected surface mesh: 6, 12, 18 iterations.
3. Wake-node sweep using the selected surface mesh and iteration count: 32, 64, 128 nodes.
4. Recheck the selected surface resolution with the selected wake settings.

See [grid-study settings and file layout](docs/GRID_STUDY.md) for editable spacing targets, formulas, references, output naming and wake-study examples.

The saved **study models** receive the analysis references and flow conditions. The original geometry-only model can still show GUI defaults. For the supplied cruise case, the study uses `Sref = 122.6 m²`, `bref = 35.793435 m`, `cref = 4.19 m`, `Mach = 0.78` and `ReCref ≈ 2.145e7`. The moment reference is the CPACS quarter-MAC point, `(20.752721, 0, 0) m`.

## Final stability runs

Run `main_obtain_final_results.py` in the OpenVSP environment. The defaults run VLM and PANEL for WB, WBH, WBV and WBHV on the fine mesh with 12 free-wake iterations, 128 wake nodes and steady stability enabled. New runs are written under `output/final`.

The [published final runs](results/final/README.md) contain the models, native outputs and settings for all eight completed cases. The PANEL values are provisional because the wake study showed substantial oscillations and the final WBHV near-field drag is negative.

Run `main_plot_grid_study.py` for surface comparisons and `main_plot_wake_study.py` for wake histories. They use the working study when available and fall back to the published results on a fresh clone. New figures are saved under `output/`.

The supplied source data retain two Section A discrepancies: component OEM masses exceed the stated OEM by about 896.664 kg, and the take-off CG lies aft of the supplied certification-case envelope. These are recorded in `section_a.csv`; no values are silently corrected.

## Further documentation

- [Windows environment and installation](docs/SETUP_WINDOWS.md)
- [Geometry CSV contract](docs/CSV_INTERFACE.md)
- [OpenVSP builder details](docs/OPENVSP_README.md)
- [Geometry interpretation](docs/GEOMETRY_NOTES.md)
- [Grid studies and solver outputs](docs/GRID_STUDY.md)
- [Historical geometry verification, 1 November 2026](docs/VERIFICATION.md)

## Airfoil orientation correction (6 November 2026)

Earlier exports preserved clockwise CPACS point order in Selig DAT files. This retained the visible outline but inverted the wing/tail surface orientation, producing negative signed volumes in CompGeom and invalid PANEL solutions. The parser now exports upper-TE to LE to lower-TE (positive signed x-z area), and both builders reject stale DAT ordering. Re-extract from XML and rebuild any models made with the earlier version; changing the viewer's normals does not repair the saved solver geometry. Existing aerodynamic results are provisional or invalid and must be rechecked with rebuilt geometry. The geometry-only branch contains the same correction.
