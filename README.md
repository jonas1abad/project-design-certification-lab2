# UC3M Aircraft Design & Certification

Use the `main` branch for both labs.

| Lab | Start here | Scope |
| --- | --- | --- |
| Lab 2 | [Workflow](Lab_2/README.md) · [Published results](Lab_2/results/README.md) | CPACS geometry, Section A extraction, mesh and wake studies, and VLM/PANEL stability runs |
| Lab 3 | [Workflow](Lab_3/README.md) · [Baseline inputs](Lab_3/inputs/) | Aileron, elevator and rudder geometry, and VLM control derivative cases |

Run commands from the relevant lab folder. Lab 3 includes its own copy of the baseline aircraft. Both workflows use the official OpenVSP 3.43.0 Python API on Windows x64 with Python 3.11.

Open the repository root in Codex or Claude Code and specify which lab you want to work on. The [agent guide](AGENTS.md) describes the boundaries between labs. For native VSPAERO runs, use a short checkout path on Windows because the solver generates long case filenames.
