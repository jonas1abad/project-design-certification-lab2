# Working in this repository

- Read the relevant lab README before changing files. Run commands and tests from that lab's folder.
- `Lab_2/` contains the aircraft builder, stability workflow and published results. The Python package inside it is `lab2`. Run `python -m unittest discover -s tests` from `Lab_2/`.
- `Lab_3/` contains the control surfaces workflow. Use its checked-in baseline. Treat raw CPACS control geometry, especially the rudder, as a setup case until reviewed.
- Each lab writes to its own ignored `output/` folder. Keep machine-specific paths, environments and scratch files out of Git. Treat `Lab_2/results/` as published run records.
- Keep both labs independent at runtime. Update the Lab 3 baseline only when asked and record which model was used.
- Check the model, flow, reference values, geometry set and output paths before a solver batch. Use a fresh run directory for new cases.
