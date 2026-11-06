# Grid refinement and wake convergence

Edit `main_grid_study.py` at the repository root and run it in the OpenVSP-compatible environment. Shared implementation lives in `lab2/aero`; the level definitions and default flight condition live in `configs/grid_study.json`. Config-file paths resolve relative to the config file.

## Editable settings

| Setting in main_grid_study.py | Meaning |
|---|---|
| `STAGE` | `surface`, `wake-iterations`, or `wake-nodes` |
| `SELECTED_MESH` | Required for wake stages; ignored by the surface sweep |
| `METHOD` | `None` for both methods, or `VLM` / `PANEL` |
| `CONFIGURATION` | `None` for all four sets, or `WB`, `WBH`, `WBV`, `WBHV` |
| `WAKE_NODES` | Override the node count held fixed in surface/iteration studies |
| `WAKE_ITERATIONS` | Override the iteration count held fixed in surface/node studies |
| `OUTPUT_ROOT` | Optional output location; otherwise use the config |

An override does not replace the variable being swept. The surface default is 3 wake iterations and 128 nodes. The iteration sweep varies 6/12/18 iterations at 128 nodes unless overridden. The node sweep varies 32/64/128 nodes at `wake_node_iterations` (12 by default) unless `WAKE_ITERATIONS` is set.

For example, after inspecting the surface study:

```python
STAGE = 'wake-iterations'
SELECTED_MESH = 'fine'
METHOD = 'VLM'
WAKE_NODES = 128
WAKE_ITERATIONS = None
```

For the subsequent node study, choose `STAGE = 'wake-nodes'`, retain the selected mesh/method, and set `WAKE_ITERATIONS` to the selected count. Repeat for PANEL, which can use a different selected surface level.

## Refinement levels

| Level | Lifting-surface spacing (m) | Chordwise Tess_W | Fuselage body spacing (m) | Fuselage Tess_W |
|---|---:|---:|---:|---:|
| coarse | 0.50 | 17 | 0.65 | 17 |
| medium | 0.35 | 25 | 0.65 | 25 |
| fine | 0.25 | 33 | 0.40 | 33 |
| finest | 0.175 | 49 | 0.28 | 49 |

For each wing/HTP/VTP bay, spanwise intervals are `ceil(longest_LE_or_TE_edge / lifting_spacing_m)`, at least one. The estimate includes span, sweep, sweep-reference location and taper from the loaded model. OpenVSP's `SectTess_U` counts curves, so it receives `intervals + 1`. Spanwise clustering is set to 1. Chordwise tessellation remains a component-wide setting; taper makes chordwise cells narrower near the tip.

For each fuselage bay, the estimate is the longest of four longitudinal meridian chords, including changes in section position and width/height. Target spacing decreases smoothly by up to 25% over the first and last 20% of body length. Existing CPACS station boundaries are retained, so very short bays remain finer than the target. Forward/aft clustering is set to 1.

These are estimates of physical spacing. Loft curvature, twist, caps and PANEL intersections affect actual cell sizes. The calculations are saved as `lifting_surface_tessellation.csv` and `fuselage_tessellation.csv` in each input model folder.

## Matched input and output folders

Each launch receives a descriptive name. Input and output directory names match:

```text
output/grid_study/
  input/surface_VLM_PANEL_all_configs/
    plan.json
    model_001_VLM_WB_coarse_reference/
      model.vsp3
      task.json
      inputs.json
      fuselage_tessellation.csv
      lifting_surface_tessellation.csv
  outputs/surface_VLM_PANEL_all_configs/
    model_001_VLM_WB_coarse_reference/
      model_DegenGeom.csv
      model_DegenGeom.vspaero
      model_DegenGeom.history
      model_DegenGeom.lod
      model_DegenGeom.stab
      solver.log
      result.json
```

PANEL uses the `model_VSPGeom` basename and a `.vspgeom` geometry file. Stability-enabled runs request `.stab`; other native files are retained as emitted by the solver. `result.json` stores run metadata and timing, not parsed aerodynamic coefficients.

Wake directory names include the selected mesh and held wake setting, such as `wake_iterations_VLM_WB_fine_nodes128` or `wake_nodes_PANEL_WB_fine_iterations12`. Repeated launches append `_02`, `_03`, etc. Earlier results are preserved. `plan.json` and each `task.json` record the corresponding input/output paths.

## References and cruise condition

The study uses the CPACS reference wing area, reference MAC and quarter-MAC point. `bref` is the full mirrored wing span. References stay identical across component configurations for coefficient differences.

With `flow.source = section_a`, Mach, TAS, density, viscosity, temperature and altitude come from the matched VAMPzero cruise data. Reynolds is computed as `rho * TAS * cref / mu`. Mach is cross-checked using `TAS / sqrt(1.4 * 287.05 * T)`. The startup summary prints these values before launching any case.

For the supplied aircraft: Sref = 122.6 mÃ‚Â², cref = 4.19 m, bref = 35.793435 m, reference point = (20.752721, 0, 0) m; cruise Mach = 0.78, TAS = 230.153 m/s, density = 0.316211 kg/mÃ‚Â³, viscosity = 1.42161e-5 Pa s, ReCref = 2.144997e7. Each case currently has one alpha/beta/Mach reference point, with stability derivatives enabled by the configuration.

## Native execution and debugging

To restart an interrupted study, set `RESUME_STUDY` in `main_grid_study.py` to its existing directory name and `START_CASE` to the one-based case to rerun. Keep the stage/method/configuration selection matching that study. Earlier cases are left intact; cases from `START_CASE` onward reuse their folders and saved settings, with the CPU thread count refreshed from `configs/grid_study.json`. For a new study set `RESUME_STUDY = None`. Stop the old batch and its solver before resuming.

OpenVSP prepares the aerodynamic geometry. The launcher writes a rigid, no-propeller `.vspaero` case and runs `vspaero.exe` directly, following the TFG approach. Stdout and stderr are streamed to the terminal and saved in `solver.log`. A nonzero solver exit raises immediately; Python errors propagate to the debugger. The study does not continue after a failed case.

The per-run input VSP3 is saved after applying the geometry and persistent VSPAERO settings. Original source models are left intact. Reference MeshGeoms, including the TiGL STL overlay, are removed from the in-memory solver copy: in OpenVSP 3.43, PANEL export uses shown meshes after CompGeom and can otherwise include a visible overlay despite analysis-set exclusion. Included lifting surfaces have their wake flag enabled.

## Surface comparison plots

Edit `main_plot_grid_study.py`: set `STUDY_NAME` (or `PLAN_FILE`), `METHOD`, the two exploratory tolerances, and `SHOW_PLOTS`. Run the file directly. Matplotlib is included in `requirements.txt`.

Outputs go to `output/grid_study/plots/<study>/<method>/`:

- `reference_coefficients.png/.pdf`: CLtot, CDtot, CDi and CMytot.
- `reference_derivatives.png/.pdf`: CL_Alpha, CMm_Alpha, CMm_q, CS_Beta, CMl_Beta, CMn_Beta, CMl_p and CMn_r, retaining the native coefficient axes and normalization.
- `reference_comparison_cost.png/.pdf`: largest scaled difference across those metrics and solver time against mesh size.
- `mesh_comparison.csv`: values, native-file paths, loop/node/equation counts, successive changes and differences from the last available level.
- `notes.txt`: pending cases and interpretation notes.

The history parser selects the final wake iteration of **Solver Case 1**, checks its Mach/alpha/beta against the plan, and avoids mixing in stability perturbation cases. Derivatives come directly from the `.stab` derivative table, whose Alpha/Beta columns are per radian; no finite-difference reconstruction or sign conversion is applied. Mesh size uses `Total NumberOfLoops` before solver agglomeration; equation counts are recorded separately.

Only cases with completion records are included; missing cases are listed. Comparisons require common reference, flow, case and wake settings. The last available level is clearly labelled and can be an incomplete-study reference. The exploratory criterion is `abs(value - last_value) <= absolute_tolerance + relative_tolerance * abs(last_value)`; near-zero metrics use the absolute term, and percent changes are omitted below that floor. The default 1% plus 1e-4 is editable, not a lab-mandated acceptance rule. The largest scaled difference plot uses the same denominator, with 1 indicating the tolerance boundary.

Inspect trends, derivatives and solver histories before accepting a mesh; the finest tested level is not an exact solution and an apparent match at three wake iterations must be rechecked after the wake study. No mesh is automatically selected. `.lod` distribution parsing and wake plots remain to be added. No aerodynamic-result extraction through the OpenVSP API or `.adb` parsing is performed.

## Corrected study outputs

The active configuration writes to `output/grid_fixed`. Earlier studies directly under `output/grid_study/input` and `outputs` used reversed airfoil traversal and must not be treated as validated convergence results. Both methods are rerun after rebuilding `output/Lab2_aircraft.vsp3`; the plotter defaults to the corrected study root. Existing results and a pre-fix model/data backup are retained. The runner now rejects missing solver cases and nonfinite native history/stability values before recording completion. Finite output and a zero exit code still do not constitute convergence acceptance.

The corrected coarse level uses 0.65 m longitudinal fuselage spacing. At 1.0 m, CompGeom generated a four-face edge at the HTP/body tail joint and the entire WBH solve returned NaNs. Increasing only longitudinal tessellation removed this edge without moving any component. The coarse and medium levels now share the body spacing target but retain different circumferential and lifting-surface counts. PANEL exports are checked for closed edge connectivity before solving; failure raises immediately. Native output must also remain finite.
