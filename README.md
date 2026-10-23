# Lab 2: CPACS to OpenVSP

Python tool for extracting aircraft geometry from a VAMPzero `toolOutput.xml` and building an OpenVSP model with either the wing and tails or all four components.

```text
toolOutput.xml -> Python parser -> CSV + airfoil DAT files -> selected builder -> .vsp3
```

## Current status

The parser and both launcher modes pass input validation. Importing the official OpenVSP API has been confirmed on Windows with Python 3.11.9 and OpenVSP 3.43.0. The latest complete geometry build and visual comparison with TiGL remain to be verified. No VSPAERO analysis is launched by these scripts.

## Software and download links

| Software | Project setup | Download / documentation |
|---|---|---|
| Python | CPython 3.11, 64-bit; API import confirmed with 3.11.9 | [Python 3.11.9](https://www.python.org/downloads/release/python-3119/) — select Windows installer (64-bit) |
| OpenVSP | 3.43.0 Windows 64-bit distribution compiled for Python 3.11 | [Archived OpenVSP downloads](https://openvsp.org/download_old.php) |
| OpenVSP Python API | Bundled with the OpenVSP distribution | [Official API documentation](https://openvsp.org/pyapi_docs/latest/) |
| Project packages | NumPy and tqdm | Installed with pip below |
| Git (optional) | Required for cloning and contributing | [Git for Windows](https://gitforwindows.org/) |

Python's major/minor version and architecture must match the downloaded OpenVSP binary. The Python 3.14 environment previously used for this project could not import this distribution's compiled API. Check the downloaded OpenVSP `python/README.md` and `python/environment.yml`; the latter specifies Python 3.11 for the distribution used here. Other OpenVSP releases may require different interpreters or API settings. The lab guide mentions 3.40.1; this project's installation was configured with 3.43.0.

The `latest` API documentation may describe features absent from 3.43.0; check release-specific source or installed examples when a function or enum is unavailable.

## 1. Obtain the project and OpenVSP

Clone the repository, or download and extract its ZIP:

```powershell
git clone https://github.com/jonas1abad/project-design-certification-lab2.git
cd project-design-certification-lab2
```

Open the folder containing `main.py` in VS Code. Keep `parse_cpacs_geometry.py`, `build_openvsp.py`, `build_wing_tail.py` and your example `toolOutput.xml` beside it.

Download and fully extract OpenVSP 3.43.0 for Windows 64-bit / Python 3.11. Keep the installation outside the repository. The API is included; do not obtain it using `pip install vsp`.

## 2. Create the virtual environment

Install Python 3.11 64-bit from the link above. Reopen the terminal after installation. In PowerShell, from the folder containing `main.py`:

```powershell
py -3.11 --version
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python --version
python -c "import sys, struct; print(sys.executable); print('Architecture:', struct.calcsize('P') * 8)"
python -m pip install --upgrade pip
python -m pip install numpy tqdm
```

Expected: Python 3.11.x, an executable under this project's `.venv`, and architecture 64. The repository's `requirements.txt` should contain `numpy` and `tqdm`; once it does, `python -m pip install -r requirements.txt` is equivalent for project dependencies. OpenVSP is installed separately below.

If `py -3.11` reports no suitable runtime, install Python 3.11 first. A venv cannot change the version of its base interpreter. If PowerShell blocks activation, run commands with `.\.venv\Scripts\python.exe` instead of `python`; activation is optional.

In VS Code, use **Python: Select Interpreter** and select `.venv\Scripts\python.exe`.

## 3. Install the OpenVSP Python API in the venv

Set this path to your own extracted OpenVSP `python` directory:

```powershell
$vspPython = "$env:USERPROFILE\Documents\OpenVSP-3.43.0-win64\python"
```

Its contents should include `utilities`, `degen_geom`, `openvsp_config`, `openvsp` and `requirements.txt`.

Install the distribution's companion packages from its `python` directory. Its requirements file uses relative paths, so changing directory matters:

```powershell
Push-Location $vspPython
python -m pip install -r requirements.txt
Pop-Location
```

For this project's Windows installation, a normal package install did not copy `_vsp.pyd` into the venv. Installing `openvsp` in editable mode resolved the import by using the compiled extension in the original distribution directory:

```powershell
python -m pip uninstall -y openvsp
python -m pip install --no-deps -e "$vspPython\openvsp"
```

Run this only after the companion-package installation succeeds. `--no-deps` does not install missing dependencies. Keep the extracted OpenVSP folder in place because editable mode references it directly.

Verify the API before running the tool:

```powershell
python -c "import openvsp as vsp; print(vsp.GetVSPVersion())"
```

Expected for this setup:

```text
OpenVSP 3.43.0
```

## 4. Run the workflow

Both modes parse the XML first, then run the selected builder using the same venv Python. If a stage fails, execution stops.

### Wing and tails only

```powershell
python main.py --mode wing-tail
```

Runs `build_wing_tail.py` after parsing and creates:

```text
output/Lab2_wing_tail.vsp3
```

Contains wing, HTP and VTP, with sets `W`, `WH`, `WV` and `WHV`. These sets contain no fuselage. This is useful for inspecting the lifting surfaces before adding a fuselage manually in OpenVSP.

### All components

```powershell
python main.py --mode all
```

Runs `build_openvsp.py` after parsing and creates:

```text
output/Lab2_aircraft.vsp3
```

Includes the fuselage, wing and tails, with sets `WB`, `WBH`, `WBV` and `WBHV`. The fuselage is lofted from extracted elliptical stations. Its surface must be checked visually against TiGL. The default mode when no option is supplied is `all`.

The lab guide suggests fitting the fuselage manually using aircraft views or TiGL screenshots as backgrounds. It permits skipping CPACS fuselage reconstruction; it does not require manual construction. If adding the fuselage to the wing-tail model, save a separate complete-aircraft file and create the corresponding body-containing analysis sets there.

### Other options

```powershell
# Parse and validate without importing OpenVSP:
python main.py --mode wing-tail --validate-only
python main.py --mode all --validate-only

# Choose input and output paths:
python main.py --mode wing-tail --xml "C:\MyProject\toolOutput.xml" --output "C:\MyProject\output\aircraft.vsp3"

# Set wing tessellation:
python main.py --mode all --chordwise 41 --spanwise 16

# Run only the parser:
python parse_cpacs_geometry.py toolOutput.xml --out geometry_data
```

Default paths resolve relative to `main.py`; explicit relative paths resolve from the terminal's working directory. CSV and DAT files must stay together. Progress bars advance between API calls; a single slow OpenVSP call can pause a bar. The model is saved only after the build and parameter checks pass. Existing exports at the selected paths are overwritten, so save manual edits under a different filename.

Open the generated `.vsp3` in OpenVSP using **File -> Open**. The adjacent `.build.json` records API version, station counts, set indices and reference quantities. Those references are recorded for later analysis, not automatically assigned to VSPAERO.

## Outputs

| File | Contents |
|---|---|
| `geometry_data/openvsp_input.csv` | Main builder input: one row per station, including component placement and relative airfoil paths |
| `geometry_data/geometry.json` | Component transforms, symmetry, UID links, matrices and contours |
| `geometry_data/wing_stations.csv` | Eight lifting-surface stations, local twists and global leading-edge positions |
| `geometry_data/wing_bays.csv` | Five lifting-surface bays |
| `geometry_data/fuselage_sections.csv` | 60 section centres, widths and heights |
| `geometry_data/*.dat` | Eight station-specific airfoil files with thickness/camber scaling already applied |
| `output/*.vsp3` | Generated parametric OpenVSP models |
| `output/*.build.json` | Build metadata and reference quantities |

The parser extracts all source components even when the selected builder only uses the wing and tails. JSON contains the modelled side of symmetric components; symmetry metadata specifies the mirrored side. See `CSV_INTERFACE.md` for the CSV contract.

## Troubleshooting

| Symptom | Check / fix |
|---|---|
| `No suitable Python runtime found` | Install Python 3.11 64-bit before creating this venv |
| `No matching distribution found for degen_geom/openvsp_config` | Install the bundled requirements from OpenVSP's `python` directory, not only the `openvsp` subfolder |
| Cannot import `_vsp` / partially initialised `openvsp` | Check Python version/architecture, presence of the original `_vsp.pyd`, and the editable installation above |
| DLL-load failure | Follow the distribution README for native dependencies; confirm the interpreter matches the binary |
| Missing `tqdm` | Run `python -m pip install tqdm` in the project venv |
| Old errors such as `v.FUSE_FREE` or millions of insertions | Replace outdated builder copies with the corrected scripts; the current full builder uses numeric ordering policies and bounded section insertion |
| No `.vsp3` after a failed check | Expected: validation must pass before the model is saved; inspect the reported parameter mismatch |

## Version control

Keep `.venv`, generated exports and local credentials out of Git. Suggested `.gitignore`:

```gitignore
.venv/
__pycache__/
*.py[cod]
.env
output/
geometry_data/
```

Keep the Python sources, documentation, dependency list and example XML tracked. Do not commit the downloaded OpenVSP distribution. Each collaborator installs the API locally.

## Geometry interpretation

The XML declares CPACS 2.0, although the lab recommends the CPACS 2.3 guide.
This reader targets the supplied VAMPzero layout, not all CPACS versions.
Lengths are interpreted as metres and angles as degrees for this lab.

For a CPACS positioning of length L, sweep s and dihedral d:

    dx = L sin(s)
    dy = L cos(s) cos(d)
    dz = L cos(s) sin(d)

Positionings accumulate through fromSectionUID/toSectionUID. They translate a
section without rotating its coordinate axes. A section's own translation is
not added to downstream positioning vectors.

Using column-vector homogeneous matrices:

    p_global = T_component T_positioning T_section T_element p_profile

Transforms scale first, rotate about x then y then z, and translate last.
The supplied file has an identity parent fuselage transform, unit component
scales, one element per section, no element translations or rotations, and wing
section rotations only about y. Nonidentity parent transforms are rejected;
this is not a general parent/refType implementation. Original component
transformation XML and the numeric matrices are retained.

The section x scale supplies chord here. Element z scaling changes the supplied
airfoil ordinate, including camber as well as thickness. Import the exported
coordinate airfoils into OpenVSP instead of replacing them with unmodified NACA
names. Contour thickness extrema alone do not equal max airfoil thickness for a
cambered profile: compare upper/lower ordinates at the same x if measuring t/c.

## Values recovered

- Reference area: 122.6 m2; reference length: 4.19 m.
- Reference point: (20.7527214782, 0, 0) m; this is distinct from an aircraft CG.
- Wing origin: (17.877223058, 0, -2.47318892394) m; rotation y = +4 deg.
- Wing chords: 5.73117035423, 5.73117035423, 3.90434561597, 1.00041111849 m.
- Wing local station twists: 0, 0, -2.1, -6 deg.
- Wing local y stations: 0, 2.84, 6.26385115165, 17.8967175761 m.
- HTP origin: (44.9160666759, 0, 1.42) m; two stations, mirrored.
- VTP origin: (43.7044914522, 0, 1.704) m; rotation x = +90 deg, no symmetry.
- Fuselage: 60 sections; first x = 0 m, last x = 49.613 m.
- Fuselage profile Circle uses unit radius; element y/z scales are radii here,
  so widths/heights are twice those scales when section transforms are identity.

## Verification performed

The parser successfully resolved every profile and segment link, with 8 wing /
tail stations, 5 bays and 60 fuselage stations. The reconstructed wing's full
local x-y trapezoidal projected area is 122.59999999985 m2, matching the XML
reference area. The VTP tip LE is (49.6351431473, 0, 8.65019216753) m after the
90-degree component rotation. The 0 and 49.613 m fuselage endpoints were checked.
These are internal consistency checks, not TiGL/OpenVSP shape validation.

## Geometry builder notes and remaining work

The adapter derives OpenVSP bay span from sqrt(dy² + dz²), sweep from atan2(dx, span), and dihedral from atan2(dz, dy). Component transforms are applied once. Absolute section twist/dihedral and leading-edge twist pivots are used, with automatic airfoil dihedral rotation and thickness correction disabled. Station DAT scaling must not be applied a second time.

The supplied VSPAERO_module.py provided the station/airfoil construction pattern. These rigid-geometry builders do not import its ADB, deformation, trim or load-processing dependencies.

The verification above concerns parser consistency. API import has been confirmed, but final surface shape, fuselage loft, intersections and aerodynamic meshing still require validation in the installed OpenVSP version. Masses, CG cases, mission/operating data and VSPAERO aerodynamic derivatives remain subsequent Lab 2 tasks.
