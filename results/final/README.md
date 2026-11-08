# Final VSPAERO runs

This snapshot contains all eight final stability runs for the example aircraft. VLM and PANEL each cover WB (wing and body), WBH (horizontal tail added), WBV (vertical tail added) and WBHV (full aircraft).

- `Lab2_aircraft.vsp3` is the source aircraft with all four geometry sets.
- `reference_data/` contains the geometry inputs, airfoils and Section A data used to derive the reference and cruise conditions.
- `input/final_VLM_PANEL_all_configs/` contains the batch plan and the configured OpenVSP model, settings and mesh records for each job.
- `outputs/final_VLM_PANEL_all_configs/` contains the matching solver directories with `.stab` derivative tables, `.history` coefficient histories, `.lod` span loads, viewer databases, mesh files and solver logs.

The JSON paths refer to locations relative to the repository root. The native solver files retain the original run records. To inspect a result in OpenVSP, copy its configured `model.vsp3` from the matching input directory alongside the solver files.

Every run used OpenVSP 3.43.0, the fine mesh, 12 free-wake iterations, 128 wake nodes and four threads. The reference condition was Mach 0.78, a Reynolds number of approximately 21.45 million, and zero angle of attack and sideslip. Each history contains the base case and six stability perturbations with finite output through iteration 12.

Use the `.stab` tables for the wing–body baseline and full-aircraft derivatives. Within each method, subtract WB from WBH or WBV to estimate the corresponding installed tail increment. PANEL values are provisional. The wake study showed large oscillations, and the final full-aircraft PANEL case still returned negative near-field total drag.
