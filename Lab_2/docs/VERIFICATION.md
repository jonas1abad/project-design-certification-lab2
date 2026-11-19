# Local geometry verification — 1 November 2026

Environment: project `.venv`, CPython 3.11.9 x64, OpenVSP 3.43.0. Initial working tree was clean at `9058ede`. The repository is nested under `LAB2_PYTHON_TOOL/Lab2_Sequential_Workflow`, rather than the workspace root.

Both `main.py --mode wing-tail` and `main.py --mode all` completed with strict parameter and API-error checks. Verification runs used `--data-dir geometry_data/verification` and distinct outputs under `output/verification`; pre-existing models were preserved. Python compilation and `git diff --check` passed.

Reopened both saved VSP3 files with the installed API. Confirmed 4 wing, 2 HTP, 2 VTP and (full mode only) 60 fuselage sections. Confirmed all four configuration memberships in each model, with no body in W/WH/WV/WHV. Sampled all surfaces using the actual tessellation coordinates, checking finite coordinates and API errors. The lifting-surface bounding boxes agree between modes. The VTP reaches z=8.65019216753 m and the wing extends to y=+/-17.8967175761 m.

Generated top, side and front surface wireframes and inspected the full-model image. Wing/HTP symmetry and upright VTP are visible. The fuselage surface reaches x=49.6639423241 m, approximately 0.051 m beyond the last extracted station at x=49.613 m; strict section readback therefore does not establish loft fidelity. Preserve this discrepancy for TiGL comparison rather than changing source station geometry to hide it.

Generated evidence (ignored by Git):
- `output/verification/Lab2_aircraft.vsp3` and `.build.json`
- `output/verification/Lab2_wing_tail.vsp3` and `.build.json`
- `output/verification/Lab2_aircraft_views.png`
- `output/verification/Lab2_wing_tail_views.png`
- `output/verification/inspection.json` and `inspect_models.py`

Handover discrepancies fixed: `requirements.txt` lacked tqdm; setup notes referenced the old XML location and incomplete API installation steps; launcher cleared terminal output. The XML move was already complete. Shared lifting-surface builder methods have no current drift; duplication remains, without a speculative refactor.

TiGL overlay, station-contour comparison, intersection/cap inspection and aerodynamic mesh validation remain outstanding. These results establish successful generation and saved-model inspection, not complete geometric fidelity. No VSPAERO solve was started. Nothing was committed or pushed.
