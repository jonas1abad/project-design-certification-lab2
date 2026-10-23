# Windows venv and sequential launcher

Use a Python version and architecture matching your OpenVSP binary. Read the README and environment.yml supplied in its `python` directory before creating the venv. The installed Python used for earlier work is not automatically compatible. If the distribution specifies NumPy constraints, use them too.

## 1. Create the venv

Open CMD in this project's extracted `lab2_geometry` folder. First check installed Python versions:

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

Keep the full extracted OpenVSP distribution on your PC. If its Python API has the standard `python/openvsp/setup.py` package layout, use the following command with your real path:

```bat
python -m pip install "C:\Tools\OpenVSP-VERSION-win64\python\openvsp"
python -c "import openvsp as vsp; print(vsp.GetVSPVersion())"
```

`VERSION` and the installation directory are placeholders. Install from the folder containing setup.py (or pyproject.toml), not the nested folder containing only Python modules. If the distribution includes a compatible wheel instead, install that wheel by path. Follow that release's README for required dependencies/native DLL setup. Do not use `pip install vsp` to obtain this API.

If using an older `vsp` binding rather than an installed `openvsp` package, verify with:

```bat
python -c "import vsp; print(vsp.GetVSPVersion())"
```

The builder also accepts `--api-dir` for an existing compatible binding. Adding a path does not resolve a Python binary-version or DLL mismatch.

## 3. Run both steps

```bat
python main.py
```

Defaults resolve relative to main.py:

1. Parse `toolOutput.xml` into `geometry_data`.
2. Build `output/Lab2_aircraft.vsp3` from `geometry_data/openvsp_input.csv`.

Both children use `sys.executable`, so they run with the same venv Python. If the parser fails, the builder does not run. A builder failure is propagated; successful CSV parsing does not imply model generation succeeded. Existing parser exports and the selected model output are overwritten.

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

Official instructions: https://openvsp.org/pyapi_docs/latest/ (Python API Instructions). Read the release-specific README included in the download for exact compatibility.
