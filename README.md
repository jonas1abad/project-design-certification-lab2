# VAMPzero XML to OpenVSP geometry

This geometry-only branch contains the XML parser and editable OpenVSP model builders used for the UC3M Aircraft Design & Certification Lab 2. It includes the original example `inputs/toolOutput.xml` so the workflow can be run immediately after setup.

The parser reads the supplied **VAMPzero CPACS 2.0 layout**, exports station geometry and airfoil files, and builds the wing, horizontal tail, vertical tail and fuselage. This is a constrained translator for this aircraft layout, not a general CPACS importer. Component UIDs `wing`, `htp`, `vtp` and `fuselage` and the supported transformations must match the builder's assumptions. Different XML layouts may require changes; unsupported cases raise errors.

## Get this branch

```powershell
git clone --branch geometry-builder --single-branch https://github.com/jonas1abad/project-design-certification-lab2.git
cd project-design-certification-lab2
```

Alternatively select **geometry-builder** on GitHub and use **Code > Download ZIP**. Repository access is still required if the repository is private.

## Setup

The verified native build uses **OpenVSP 3.43.0 x64 with Python 3.11.9**. Install the official OpenVSP distribution and its matching Python binding; this repository does not bundle OpenVSP. Other versions have not been verified here. See [Windows setup](docs/SETUP_WINDOWS.md) for the environment and API installation commands.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Follow the OpenVSP distribution's NumPy constraints if present. Do not install an unrelated package named `vsp` from PyPI. Select `.venv/Scripts/python.exe` as the VS Code interpreter.

## Run

Open `main_geom_builder.py` and edit the settings at the top, then run it from VS Code. The defaults use the example XML and create the complete aircraft:

```powershell
python main_geom_builder.py
```

`python main.py` is an equivalent shortcut. To use a colleague's XML:

```powershell
python main_geom_builder.py --xml "C:/my-aircraft/toolOutput.xml"
```

To build only the wing and tails, without the fuselage:

```powershell
python main_geom_builder.py --mode wing-tail
```

For extraction and CSV validation without installing OpenVSP:

```powershell
python main_geom_builder.py --validate-only
```

To run the XML parser independently:

```powershell
python -m lab2.geometry.parse_cpacs_geometry inputs/toolOutput.xml --out geometry_data
```

The parser only needs NumPy; builders also need tqdm and the official OpenVSP API. All workflow stages use the same Python interpreter. Errors stop execution. Existing generated data and the chosen model file are overwritten.

## Outputs

- `geometry_data/openvsp_input.csv`: primary station data consumed by the builder.
- `geometry_data/*.dat`: eight station-specific airfoil files for the supplied XML; keep these alongside the CSV.
- `geometry_data/geometry.json`, `wing_stations.csv`, `wing_bays.csv`, `fuselage_sections.csv`: extracted geometry for manual checks.
- `output/Lab2_aircraft.vsp3`: full, parametrically editable aircraft, with WB/WBH/WBV/WBHV sets.
- `output/Lab2_aircraft.build.json`: API version, station counts and reference quantities.
- Wing-tail mode instead writes `output/Lab2_wing_tail.vsp3` and its build report.

Generated files are ignored by Git. Open the `.vsp3` model in OpenVSP to inspect it. This branch contains geometry generation only; no Section A extraction, solver launching, grid study or result plotting. Aerodynamic reference values in the build report are not automatically applied to VSPAERO.

## Geometry checks and limits

For the example XML, extraction gives 68 stations: 4 wing, 2 horizontal-tail, 2 vertical-tail and 60 fuselage. Profiles retain their station-specific scaling, and component transforms are applied once. The fuselage uses elliptical stations and OpenVSP loft interpolation; it is not a TiGL surface import. Inspect the nose, tail, intersections and loft before using a new aircraft for analysis. A visual TiGL overlay comparison was performed for the original lab aircraft; it is not a numerical proof of surface equivalence.

- [CSV schema and units](docs/CSV_INTERFACE.md)
- [CPACS transformations and recovered dimensions](docs/GEOMETRY_NOTES.md)
- [OpenVSP adapter details](docs/OPENVSP_README.md)

The branch shares Git history with the main lab project, but its current checkout is limited to geometry tools.
