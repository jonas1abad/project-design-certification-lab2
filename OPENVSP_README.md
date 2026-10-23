# Lab 2: CSV to OpenVSP

Workflow: toolOutput.xml -> parse_cpacs_geometry.py -> geometry_data/openvsp_input.csv -> build_openvsp.py -> Lab2_aircraft.vsp3.

## Run

Use the Python version supported by your official OpenVSP distribution (the lab guide names OpenVSP 3.40.1). Install its Python API following that distribution's instructions. Do not install an unrelated package named vsp. This builder imports `openvsp`, falling back to `vsp` for your older binding style.

From this folder:

```bash
python build_openvsp.py --validate-only
python build_openvsp.py --api-dir "C:/path/to/OpenVSP/python" --output Lab2_aircraft.vsp3
```

`--api-dir` must point to the directory from which `import openvsp` or `import vsp` works; omit it if installed already. Native library/DLL dependencies must also be configured according to your distribution. To use another CSV:

```bash
python build_openvsp.py geometry_data/openvsp_input.csv --output output/Lab2_aircraft.vsp3 --chordwise 41 --spanwise 16
```

Run the existing XML parser if you change the XML (requires NumPy):

```bash
python parse_cpacs_geometry.py path/to/toolOutput.xml --out geometry_data
```

## What it builds

One model containing the wing (4 stations), HTP (2), VTP (2), and elliptical fuselage (60). Profiles are imported from the eight station-specific DAT files. All geometry remains parametrically editable.

| Set index | Set | Members |
|---|---|---|
| 3 | WB | Wing, fuselage |
| 4 | WBH | Wing, fuselage, HTP |
| 5 | WBV | Wing, fuselage, VTP |
| 6 | WBHV | Wing, fuselage, HTP, VTP |

The script writes a `.build.json` beside the model with API version, station counts, set indices, and the CSV reference quantities. These reference quantities are recorded, **not automatically applied to VSPAERO**. No aerodynamic solve is launched.

## Adaptation from your module

Uses the station insertion / file-airfoil / parameter-driver pattern in the supplied VSPAERO_module.py's wing-reconstruction code. It does not import that entire module, so geometry generation does not need scipy, sklearn, plotly, psutil or the ADB parser.

Two details are corrected explicitly:

- The driver section index for XSec_1 is 1, following the official API examples (the supplied helper used i1-1).
- OpenVSP Span is sqrt(dy²+dz²). Leading-edge sweep is atan2(dx, Span), since OpenVSP applies sweep offset using that span. CSV bay_sweep_le_deg is projected sweep atan2(dx,dy) and cannot be copied unchanged for dihedral bays.

Local twist uses the same y-axis rotation sign as the CPACS transformations. Absolute twist/dihedral are selected; airfoil rotation to match dihedral and thickness correction are disabled. The whole-component rotation is applied once, including the wing +4° y rotation and VTP +90° x rotation. Rotation origin is set at the local leading-edge origin. DAT ordinate scaling is not applied a second time.

Fuselage Y/Z offsets are divided by the fuselage length for OpenVSP's percentage-location parameters. Zero-size end sections use POINT; the others use ELLIPSE.

Sources checked: official OpenVSP API Geom and XSec documentation, plus OpenVSP_3.40.1 WingGeom.cpp and XSec.cpp. In 3.40.1 the thickness flag is spelled `CorrectAirfoilthicknessFlag` (lowercase t).

- https://openvsp.org/api_docs/latest/group___geom.html
- https://openvsp.org/api_docs/latest/group___x_sec.html
- https://github.com/OpenVSP/OpenVSP/blob/OpenVSP_3.40.1/src/geom_core/WingGeom.cpp
- https://github.com/OpenVSP/OpenVSP/blob/OpenVSP_3.40.1/src/geom_core/XSec.cpp

## Validation and remaining checks

CSV validation and independent reconstruction of station origins from the adapter's span/sweep/dihedral mapping passed on the supplied data. Python compilation passed. OpenVSP is not installed in the authoring environment, so actual API execution, .vsp3 creation and surface comparison remain untested.

The builder fails on missing parameters, API errors or changed/clamped parameter values; it reads back fuselage widths/heights after update as well. It clears the in-memory OpenVSP model at startup; run as a separate Python process. The output path is overwritten if it exists.

Before analysis, open the generated model and compare station placement, incidence/twist, tail orientation and fuselage loft with TiGL. Ellipse stations and OpenVSP loft interpolation are an approximation of the source fuselage. Inspect wing-body intersections, panel spacing and caps before a VSPAERO solve. The lab separates geometry creation (Section B) from derivative calculations (Section C).

This adapter targets the supplied CSV/component UIDs. It rejects unsupported root offsets, nonzero twist pivots, negative local wing spans and broken station chains. It is not a general CPACS-to-OpenVSP translator.
