# Windows venv and sequential launcher

Use a Python version and architecture matching your OpenVSP binary. Read the README and environment.yml supplied in its `python` directory before creating the venv. The installed Python used for earlier work is not automatically compatible. If the distribution specifies NumPy constraints, use them too.

## 1. Create the venv

Open CMD in the project folder containing `main.py`. First check installed Python versions:

```bat
py -0p
```

Select the matching interpreter in VS Code (or use its full path). Once `python` resolves to that compatible interpreter:

```bat
python --version
python -c "import struct; print(struct.calcsize('P') * 8)"
python -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

To select a specific installed version via the Windows launcher, use `py -3.X -m venv .venv`, replacing `3.X` with the version required by your OpenVSP distribution. In PowerShell activation is `.\.venv\Scripts\Activate.ps1`. If activation is blocked, use `.\.venv\Scripts\python.exe` instead of `python`; activation is optional.

## 2. Install the official API into this venv

For the verified Python 3.11.9 / OpenVSP 3.43.0 x64 setup, install the companion packages from the distribution's `python` directory, then install the binding in editable mode. In PowerShell with the project venv activated:

```powershell
$vspPython = "$env:USERPROFILE\Documents\OpenVSP-3.43.0-win64\python"
Push-Location $vspPython
python -m pip install -r requirements.txt
Pop-Location
python -m pip install --no-deps -e "$vspPython\openvsp"
python -c "import openvsp as vsp; print(vsp.GetVSPVersion())"
```

If a non-editable `openvsp` package is already installed and cannot find `_vsp.pyd`, uninstall that package before the editable installation. Keep the extracted distribution in place. Do not install `vsp` from PyPI. See [README.md](../README.md) for the complete setup and troubleshooting instructions.

The builder also accepts `--api-dir` for an existing compatible binding. Adding a path does not resolve a Python binary-version or DLL mismatch.

## 3. Run the workflow

```bat
python main.py
```

Defaults resolve relative to main.py:

1. Parse `inputs/toolOutput.xml` into `geometry_data`.
2. Extract Section A to `geometry_data/section_a.csv`, including operating values when a matching VAMPzero run is found (see README).
3. Build `output/Lab2_aircraft.vsp3` from `geometry_data/openvsp_input.csv`.

All three children use `sys.executable`, so they run with the same venv Python. If geometry or Section A extraction fails, the builder does not run. A builder failure is propagated; successful CSV parsing does not imply model generation succeeded. Existing exports and the selected model output are overwritten.

Custom paths:

```bat
python main.py --xml "C:\MyProject\toolOutput.xml" --output "C:\MyProject\output\aircraft.vsp3"
```

CSV-only check (does not need the OpenVSP API):

```bat
python main.py --validate-only
```

If the API is imported through a directory instead of installed:

```bat
python main.py --api-dir "C:\path\to\binding-parent"
```

In VS Code select `.venv\Scripts\python.exe` with **Python: Select Interpreter**.

## 4. Run the separate mesh study

After `output/Lab2_aircraft.vsp3` and `geometry_data/section_a.csv` exist, set `STAGE = 'surface'` in the **USER SETTINGS** block at the top of `main_grid_study.py`, then run:

```bat
python main_grid_study.py
```

Runs execute in the main Python process. If one raises an error, the traceback appears in the debugger and later runs do not start. Models and settings are saved under `output/grid_study/input/<study_name>/model_XXX_...`; matching solver files are retained under `output/grid_study/outputs/<study_name>/model_XXX_...`. To run a wake sweep, edit `STAGE` to `'wake-nodes'` or `'wake-iterations'` and set `SELECTED_MESH` to the chosen level. Set `WAKE_NODES` to the selected count before the iteration sweep. Then run the same file again:

```bat
python main_grid_study.py
```

Set `METHOD` to `'VLM'` or `'PANEL'` to run just one solver method, and `CONFIGURATION` to `'WBHV'` to run just one component set. The launch script does not generate plots and does not parse `.adb` files.

Official instructions: https://openvsp.org/pyapi_docs/latest/ (Python API Instructions). Read the release-specific README included in the download for exact compatibility.
