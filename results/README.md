# Published run results

| Study | Scope | Where to start |
|---|---|---|
| [Surface grid](grid/) | 32 VLM and PANEL runs across four geometry sets and four mesh levels | [VLM figures](grid/plots/surface_VLM_PANEL_all_configs/VLM/) · [PANEL figures](grid/plots/surface_VLM_PANEL_all_configs/PANEL/) |
| [Wake iterations](wake/) | Six base-condition runs on the fine WBHV mesh at 128 wake nodes | [VLM figure](wake/plots/VLM/wake_convergence.png) · [PANEL figure](wake/plots/PANEL/wake_convergence.png) |
| [Final stability](final/) | Eight runs on the selected fine mesh with 12 wake iterations | [Run settings and limitations](final/README.md) |

Each study pairs a run plan and configured OpenVSP models in `input/` with native VSPAERO files and solver logs in `outputs/`. Match runs by folder name. The archived JSON paths are relative to the repository root. To use OpenVSP’s Results Manager, copy the matching `model.vsp3` into a working copy of the solver folder and open it there.

The [source aircraft](final/Lab2_aircraft.vsp3) and [reference data](final/reference_data/) are shared by all three snapshots. The plotter scripts can regenerate the surface and wake figures from these files. PANEL values remain provisional because the surface and wake sweeps show substantial sensitivity.
