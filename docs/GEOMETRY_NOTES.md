# Geometry interpretation

The XML declares CPACS 2.0, although the lab recommends the CPACS 2.3 guide.
This reader targets the supplied VAMPzero layout, not all CPACS versions.
Lengths are interpreted as metres and angles as degrees for this lab.

For a CPACS positioning of length L, sweep s and dihedral d:

    dx = L sin(s)
    dy = L cos(s) cos(d)
    dz = L cos(s) sin(d)

Positionings accumulate through fromSectionUID/toSectionUID. They translate a
section without rotating its coordinate axes. A section's own translation is
not added to downstream positioning vectors.

Using column-vector homogeneous matrices:

    p_global = T_component T_positioning T_section T_element p_profile

Transforms scale first, rotate about x then y then z, and translate last.
The supplied file has an identity parent fuselage transform, unit component
scales, one element per section, no element translations or rotations, and wing
section rotations only about y. Nonidentity parent transforms are rejected;
this is not a general parent/refType implementation. Original component
transformation XML and the numeric matrices are retained.

The section x scale supplies chord here. Element z scaling changes the supplied
airfoil ordinate, including camber as well as thickness. Import the exported
coordinate airfoils into OpenVSP instead of replacing them with unmodified NACA
names. Contour thickness extrema alone do not equal max airfoil thickness for a
cambered profile: compare upper/lower ordinates at the same x if measuring t/c.

## Values recovered

- Reference area: 122.6 m2; reference length: 4.19 m.
- Reference point: (20.7527214782, 0, 0) m; this is distinct from an aircraft CG.
- Wing origin: (17.877223058, 0, -2.47318892394) m; rotation y = +4 deg.
- Wing chords: 5.73117035423, 5.73117035423, 3.90434561597, 1.00041111849 m.
- Wing local station twists: 0, 0, -2.1, -6 deg.
- Wing local y stations: 0, 2.84, 6.26385115165, 17.8967175761 m.
- HTP origin: (44.9160666759, 0, 1.42) m; two stations, mirrored.
- VTP origin: (43.7044914522, 0, 1.704) m; rotation x = +90 deg, no symmetry.
- Fuselage: 60 sections; first x = 0 m, last x = 49.613 m.
- Fuselage profile Circle uses unit radius; element y/z scales are radii here,
  so widths/heights are twice those scales when section transforms are identity.

## Verification performed

The parser successfully resolved every profile and segment link, with 8 wing /
tail stations, 5 bays and 60 fuselage stations. The reconstructed wing's full
local x-y trapezoidal projected area is 122.59999999985 m2, matching the XML
reference area. The VTP tip LE is (49.6351431473, 0, 8.65019216753) m after the
90-degree component rotation. The 0 and 49.613 m fuselage endpoints were checked.
These are internal consistency checks, not TiGL/OpenVSP shape validation.

## Geometry builder notes and remaining work

The adapter derives OpenVSP bay span from sqrt(dy² + dz²), sweep from atan2(dx, span), and dihedral from atan2(dz, dy). Component transforms are applied once. Absolute section twist/dihedral and leading-edge twist pivots are used, with automatic airfoil dihedral rotation and thickness correction disabled. Station DAT scaling must not be applied a second time.

The supplied VSPAERO_module.py provided the station/airfoil construction pattern. These rigid-geometry builders do not import its ADB, deformation, trim or load-processing dependencies.

The verification above concerns parser consistency. API import has been confirmed, but final surface shape, fuselage loft, intersections and aerodynamic meshing still require validation in the installed OpenVSP version. Section A extraction and the aerodynamic grid-study workflow are now implemented; full stability-result postprocessing is still pending.
