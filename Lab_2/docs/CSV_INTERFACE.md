# XML -> Python parser -> CSV -> OpenVSP script

Run with Python 3.10+ and NumPy:

    python -m lab2.geometry.parse_cpacs_geometry inputs/toolOutput.xml --out geometry_data

The primary output is `geometry_data/openvsp_input.csv`. Keep the .dat files
alongside it. The OpenVSP builder will read this CSV; it does not need to parse
the XML or geometry.json. Additional CSVs/JSON remain diagnostic exports.

## Row contract (schema_version = 1)

One row per station: 4 wing + 2 HTP + 2 VTP + 60 fuselage = 68 rows.
Group by component_uid and sort each group by station_index (zero-based).
Station order is resolved from the XML segment UID chain, not XML listing order.
Empty fields mean not applicable or no incoming bay; they are not numeric zero.
Units: metres, square metres, degrees. CSV separator: comma; decimal point: dot.

| Columns | Meaning |
|---|---|
| component_uid, geometry_type, symmetry | Component identity; wing/fuselage; x-z-plane/none |
| section_uid, element_uid, previous_element_uid | CPACS identity and connection to previous station |
| component_x/y/z_m | Whole-component translation |
| component_rx/ry/rz_deg | Whole-component CPACS rotations; apply once |
| station_x/y/z_local_m | Station origin before the whole-component transform |
| chord_m | Wing/tail station chord |
| cpacs_twist_y_deg | Local section rotation about CPACS y; preserve sign convention explicitly |
| twist_pivot_chord_fraction | 0 means rotation about the leading edge |
| airfoil_file | Relative path from CSV directory to scaled coordinate airfoil |
| width_m, height_m | Fuselage cross-section full dimensions, including zero-size end points |
| bay_dx/dy/dz_m | Displacement from the previous wing station, in component coordinates |
| bay_yz_length_m | sqrt(dy^2 + dz^2); supplied alongside projected dy to avoid span ambiguity |
| bay_sweep_le_deg | atan2(dx,dy), projected leading-edge sweep |
| bay_dihedral_deg | atan2(dz,dy) |
| reference_area_m2, reference_length_m | Aircraft coefficient normalization, repeated identically on every row |
| reference_x/y/z_m | Aircraft reference point; not necessarily the CG |

The incoming bay is recorded on its OUTER station row. Root station bay fields
are empty. Fuselage rows have no wing/bay/airfoil fields. Wing rows have no
fuselage width/height. Do not mirror the VTP or rotate it a second time.

Airfoil files already contain station-specific ordinate scaling (including
camber). Do not apply the CPACS thickness scale again in the builder.

## Reader pattern for the future OpenVSP script

    import csv
    from pathlib import Path
    from collections import defaultdict

    csv_path = Path('geometry_data/openvsp_input.csv')
    components = defaultdict(list)
    with csv_path.open(newline='', encoding='utf-8') as stream:
        for row in csv.DictReader(stream):
            components[row['component_uid']].append(row)
    for component_uid, stations in components.items():
        stations.sort(key=lambda row: int(row['station_index']))
        # Convert applicable numeric strings to floats.
        # Resolve airfoil files with csv_path.parent / row['airfoil_file'].
        # Build the component and apply its placement once.

CSV values describe the CPACS geometry; they are not promises that identically
named OpenVSP parameters use the same sign, span projection or rotation pivot.
The adapter must verify those settings against the installed binding. Fuselage
rows represent ellipses at the extracted section positions; loft interpolation
still needs visual verification. The parser supports the supplied VAMPzero
layout and deliberately rejects unsupported parent/component transforms and
branched segment chains.

Validation on the supplied XML: all 68 CSV stations, 8 referenced airfoil files,
5 incoming wing bays, and reconstruction of every exported wing contour from
the CSV were checked. Reconstructed wing planform area matches 122.6 m2.
OpenVSP generation is the next stage and has not been run.

## DAT traversal and surface normals

Airfoils are exported in Selig order: upper trailing edge, leading edge, lower trailing edge. The x-z polygon has positive signed area. Source CPACS coordinates remain in the source contour record; reversing their exported traversal changes no coordinate, scale or camber. Builder validation rejects the older clockwise DAT exports, which can look correct but produce inward normals and negative signed wing/tail volumes. Regenerate the DATs with the current parser before building. Parameter readback and visual overlays alone do not validate orientation.
