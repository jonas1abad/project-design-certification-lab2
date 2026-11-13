"""Add trailing-edge controls from a CSV to the Lab 2 OpenVSP model."""

import argparse
import csv
from pathlib import Path

import openvsp as vsp

LAB3 = Path(__file__).resolve().parent
DEFAULT_CSV = LAB3 / "output" / "control_surfaces.csv"
DEFAULT_MODEL = LAB3 / "inputs" / "UC3M2.1.vsp3"
DEFAULT_OUTPUT = LAB3 / "output" / "UC3M2.1_controls.vsp3"


def control_settings(surface):
    return {
        "EtaFlag": 1,
        "EtaStart": float(surface["inboard_eta_le"]),
        "EtaEnd": float(surface["outboard_eta_le"]),
        "Abs_Rel_Flag": 1,
        "SE_Const_Flag": 0,
        "LE_Flag": 0,
        "Length_C_Start": float(surface["inboard_length_over_chord"]),
        "Length_C_End": float(surface["outboard_length_over_chord"]),
    }


def build_controls(csv_path, model_path, output_path):
    if output_path.resolve() in (model_path.resolve(), csv_path.resolve()):
        raise ValueError("Choose an output path separate from the input files")
    if not model_path.is_file():
        raise FileNotFoundError(model_path)
    with csv_path.open(newline="", encoding="utf-8-sig") as stream:
        surfaces = list(csv.DictReader(stream))
    if not surfaces:
        raise ValueError(f"No control surfaces in {csv_path}")

    vsp.ClearVSPModel()
    vsp.ReadVSPFile(str(model_path.resolve()))
    for surface in surfaces:
        wing_uid = surface["wing_uid"]
        parents = vsp.FindGeomsWithName(wing_uid)
        if len(parents) != 1 or vsp.GetGeomTypeName(parents[0]) != "Wing":
            raise ValueError(f"Expected exactly one OpenVSP wing named {wing_uid!r}")
        parent = parents[0]
        name = surface["name"]
        settings = control_settings(surface)
        if not 0 <= settings["EtaStart"] < settings["EtaEnd"] <= 1:
            raise ValueError(f"{name}: expected increasing eta stations between 0 and 1")
        for key in ("Length_C_Start", "Length_C_End"):
            if not 0 < settings[key] <= 1:
                raise ValueError(f"{name}: {key} must be greater than 0 and at most 1")
        for existing in vsp.GetSubSurfIDVec(parent):
            if vsp.GetSubSurfName(existing).casefold() == name:
                raise ValueError(f"{wing_uid} already contains a subsurface named {name}")

        control = vsp.AddSubSurf(parent, vsp.SS_CONTROL, 0)
        if not control:
            raise RuntimeError(f"OpenVSP failed to create {name} on {wing_uid}")
        vsp.SetSubSurfName(control, name)
        parameters = {
            vsp.GetParmName(parm): parm for parm in vsp.GetSubSurfParmIDs(control)
        }
        for parameter, value in settings.items():
            vsp.SetParmVal(parameters[parameter], value)
        vsp.Update()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    vsp.WriteVSPFile(str(output_path.resolve()), vsp.SET_ALL)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        build_controls(args.csv, args.model, args.output)
    except (OSError, ValueError, RuntimeError, KeyError, TypeError, csv.Error) as exc:
        parser.exit(1, f"{parser.prog}: {exc}\n")
    print(args.output.resolve())


if __name__ == "__main__":
    main()
