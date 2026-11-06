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

## 3. Run the geometry workflow

```powershell
python main_geom_builder.py
```

The two stages parse `inputs/toolOutput.xml` into `geometry_data`, then build `output/Lab2_aircraft.vsp3`. Both use the selected Python interpreter. Paths default to the repository root, so they work when launched from VS Code as well.

For another source or output:

```powershell
python main_geom_builder.py --xml "C:/MyProject/toolOutput.xml" --output "C:/MyProject/aircraft.vsp3"
```

To extract and validate without the native OpenVSP API:

```powershell
python main_geom_builder.py --validate-only
```

Use `--mode wing-tail` for the lifting surfaces only. `--api-dir "C:/path/to/binding-parent"` is available for a compatible binding not installed in the environment. Edit the top-of-file settings for VS Code runs without command-line arguments. Failed stages raise immediately; existing generated exports and the chosen output file are overwritten.
