# Lab 3 · Control surfaces and VSPAERO

This standalone workflow extends the UC3M2.1 Lab 2 aircraft for Parts III and IV. It extracts the aileron, elevator, and rudder from the original CPACS geometry, adds them to the selected Lab 2 OpenVSP model, and prepares a steady VLM stability case for control derivatives.

## Setup

Use Windows x64, Python 3.11, and the Python API from OpenVSP 3.43.0 with its companion packages. The local environment is `.venv`. The requirements snapshot includes machine-specific paths to the OpenVSP distribution. Adjust those paths to match your installation when recreating the environment.

## Run from this folder

```powershell
.\.venv\Scripts\python.exe .\parse_control_surfaces.py
.\.venv\Scripts\python.exe .\build_control_surfaces.py
```

The parser writes `output/control_surfaces.csv` from `inputs/toolOutput.xml`. Each row records the parent geometry and the inboard and outboard CPACS span and leading-edge chord fractions. The builder uses the eta and Length/C columns to create the controls and saves `output/UC3M2.1_controls.vsp3`. Open the generated model in OpenVSP and use the parent wing's **Sub** tab to inspect the outlines.

For revisions, copy the raw CSV, edit the span and Length/C fields, and pass the revised file to the builder with `--csv`. Use `--output` to save the revised model separately.

## Rudder geometry

The raw CPACS rudder spans the full vertical tail, with its hinge at 33.9% of local chord (66.1% Length/C at both ends). The course guide flags this geometry as implausible. Treat the raw model as a setup case. Before using rudder derivatives for the one-engine-inoperative trim check, estimate revised span stations and hinge fractions from a side-on reference and document the source and the resulting dimensions.

## VSPAERO

Edit `MODEL_PATH`, `RUN_DIR`, and `PREPARE_ONLY` at the top of `launch_vspaero.py`. Choose a fresh run directory for each case, then run:

```powershell
.\.venv\Scripts\python.exe .\launch_vspaero.py
```

The launcher groups the differential ailerons, symmetric elevator, and rudder at zero baseline deflection. It prepares a full-aircraft steady VLM case at the Lab 2 reference condition (Mach 0.78, zero angle of attack and sideslip, 12 wake iterations, 128 wake nodes). Prepare-only mode writes the configured model and `inputs.json`. A solver run is expected to also write `model_DegenGeom.stab`. Check the control derivative columns and sign conventions before using results in Parts III and IV.

The input XML declares CPACS 2.0. OpenVSP can inspect the generated model directly. TiGL Creator 3 requires a migrated copy of the XML to inspect the original CPACS geometry.
