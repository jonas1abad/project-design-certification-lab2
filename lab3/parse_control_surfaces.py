"""Read elevator, aileron and rudder dimensions from CPACS."""

import argparse
import csv
from pathlib import Path
import xml.etree.ElementTree as ET


CONTROL_NAMES = {"aileron", "elevator", "rudder"}
DEFAULT_XML = Path(__file__).resolve().parent / "inputs" / "toolOutput.xml"
DEFAULT_CSV = Path(__file__).resolve().parent / "output" / "control_surfaces.csv"


def read_border(device, border_name, uid):
    path = f"outerShape/{border_name}"
    values = {}
    for field in ("etaLE", "xsiLE"):
        location = f"{path}/{field}"
        try:
            value = float(device.findtext(location, default=""))
        except ValueError as exc:
            raise ValueError(f"{uid}: expected a number at {location}") from exc
        if not 0 <= value <= 1:
            raise ValueError(f"{uid}: {location} must be between 0 and 1")
        values[field] = value

    return {
        "eta_le": values["etaLE"],
        "xsi_le": values["xsiLE"],
        "length_over_chord": 1 - values["xsiLE"],
    }


def parse_control_surfaces(xml_path):
    """Return normalized CPACS stations and trailing-edge Length/C values."""
    root = ET.parse(xml_path).getroot()
    # ElementTree includes the namespace in each tag when CPACS declares one.
    for element in root.iter():
        element.tag = element.tag.rsplit("}", 1)[-1]

    models = root.findall("./vehicles/aircraft/model")
    if len(models) != 1:
        raise ValueError("Expected exactly one CPACS aircraft model")

    surfaces = []
    for wing in models[0].findall("wings/wing"):
        for segment in wing.findall("componentSegments/componentSegment"):
            for device in segment.findall(
                "controlSurfaces/trailingEdgeDevices/trailingEdgeDevice"
            ):
                name = device.findtext("name", default="").strip().casefold()
                if name not in CONTROL_NAMES:
                    continue
                uid = device.get("uID") or name
                inboard = read_border(device, "innerBorder", uid)
                outboard = read_border(device, "outerBorder", uid)
                if inboard["eta_le"] >= outboard["eta_le"]:
                    raise ValueError(f"{uid}: etaLE must increase from inner to outer border")
                surfaces.append({
                    "name": name,
                    "surface_uid": uid,
                    "wing_uid": wing.get("uID"),
                    "wing_symmetry": wing.get("symmetry"),
                    "component_segment_uid": segment.get("uID"),
                    "inboard": inboard,
                    "outboard": outboard,
                })

    missing = CONTROL_NAMES - {surface["name"] for surface in surfaces}
    if missing:
        raise ValueError(f"Missing CPACS control surfaces: {', '.join(sorted(missing))}")
    return sorted(surfaces, key=lambda surface: (surface["name"], surface["surface_uid"]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xml", nargs="?", type=Path, default=DEFAULT_XML)
    parser.add_argument("--output", type=Path, default=DEFAULT_CSV)
    args = parser.parse_args()
    try:
        surfaces = parse_control_surfaces(args.xml)
        rows = []
        for surface in surfaces:
            row = {key: value for key, value in surface.items() if key not in ("inboard", "outboard")}
            for border in ("inboard", "outboard"):
                row.update({f"{border}_{key}": value for key, value in surface[border].items()})
            rows.append(row)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    except (OSError, ET.ParseError, ValueError) as exc:
        parser.exit(1, f"{parser.prog}: {exc}\n")
    print(args.output.resolve())


if __name__ == "__main__":
    main()
