# Archived plotting prototype

`plot_grid_study_legacy.py` is a development reference for the former API-result JSON and ADB-count layout. It does not support the current native-file study outputs and is not called by either launcher.

The next plotter will read `.history`, `.lod` and `.stab` files from the paired input/output study directories. Keep that work separate from the solver launcher. Matplotlib is optional and listed in this folder's `requirements.txt`.
