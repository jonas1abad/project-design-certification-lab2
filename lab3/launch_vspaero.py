"""Prepare and optionally run a steady VSPAERO control-derivative case."""

import json
from pathlib import Path

import openvsp as vsp


HERE = Path(__file__).resolve().parent
MODEL_PATH = HERE / "output" / "UC3M2.1_controls.vsp3"
RUN_DIR = HERE / "output" / "controls_steady"  # Choose a new directory for each run.
PREPARE_ONLY = True  # True saves the configured model without running the solver.

# Gains follow the course guide's Surf0/Surf1 convention.
GROUPS = {
    "wing_aileron": ("aileron", {"wing_Surf0_aileron": 1, "wing_Surf1_aileron": 1}),
    "htp_elevator": ("elevator", {"htp_Surf0_elevator": -1, "htp_Surf1_elevator": 1}),
    "vtp_rudder": ("rudder", {"vtp_Surf0_rudder": 1}),
}


def configure_groups(container):
    vsp.AutoGroupVSPAEROControlSurfaces()
    indices = {
        vsp.GetVSPAEROControlGroupName(i): i
        for i in range(vsp.GetNumControlSurfaceGroups())
    }
    if set(indices) != set(GROUPS) or len(indices) != vsp.GetNumControlSurfaceGroups():
        raise ValueError(f"Expected three control groups, found {indices}")
    for original, (name, gains) in GROUPS.items():
        index = indices[original]
        members = vsp.GetActiveCSNameVec(index)
        if set(members) != set(gains):
            raise ValueError(f"Unexpected members in {original}: {members}")
        parent_name = original.rsplit("_", 1)[0]
        parent, = vsp.FindGeomsWithName(parent_name)
        surface, = [s for s in vsp.GetSubSurfIDVec(parent) if vsp.GetSubSurfName(s) == name]
        vsp.SetVSPAEROControlGroupName(name, index)
        settings = {"ActiveFlag": 1, "DeflectionAngle": 0}
        for member, gain in gains.items():
            reflection = member.split("_Surf", 1)[1].split("_", 1)[0]
            settings[f"Surf_{surface}_{reflection}_Gain"] = gain
        for parm, value in settings.items():
            set_parm(container, f"ControlSurfaceGroup_{index}", parm, value)


def set_parm(container, group, name, value):
    parm = vsp.FindParm(container, name, group)
    if not parm:
        raise RuntimeError(f"Missing OpenVSP parameter {group}/{name}")
    vsp.SetParmVal(parm, value)


def set_inputs(analysis, settings):
    vsp.SetAnalysisInputDefaults(analysis)
    for name, value in settings.items():
        setter = vsp.SetIntAnalysisInput if isinstance(value, int) else vsp.SetDoubleAnalysisInput
        setter(analysis, name, [value])


def launch(model, run_dir, prepare_only):
    if not model.is_file():
        raise FileNotFoundError(model)
    run_dir = run_dir.resolve()
    run_dir.mkdir(parents=True, exist_ok=False)
    vsp.ReadVSPFile(str(model.resolve()))
    container = vsp.FindContainer("VSPAEROSettings", 0)
    configure_groups(container)

    # Match the Lab 2 full-aircraft reference condition and wake settings.
    common = dict(AnalysisMethod=vsp.VORTEX_LATTICE, GeomSet=vsp.SET_ALL,
                  Symmetry=0, UseModeFlag=0, AlternateInputFormatFlag=0)
    settings = dict(
        common, RefFlag=vsp.MANUAL_REF, Sref=122.6, cref=4.19, bref=35.7934351522514,
        Xcg=20.7527214782, Ycg=0.0, Zcg=0.0, MachStart=0.78, MachEnd=0.78,
        AlphaStart=0.0, AlphaEnd=0.0, BetaStart=0.0, BetaEnd=0.0,
        ReCref=21449968.069131244, ReCrefEnd=21449968.069131244,
        Rho=0.31621123386, Vinf=230.153054375, AlphaNpts=1, BetaNpts=1,
        MachNpts=1, ReCrefNpts=1, FixedWakeFlag=0, WakeNumIter=12,
        NumWakeNodes=128, UnsteadyType=vsp.STABILITY_DEFAULT, NCPU=4,
        CGGeomSet=vsp.SET_NONE, CGDegenSet=vsp.SET_NONE, UseCGModeFlag=0,
    )
    aliases = {"UseModeFlag": "UseMode", "CGGeomSet": "MassSet",
               "CGDegenSet": "MassDegenSet", "UseCGModeFlag": "CGUseMode",
               "NumWakeNodes": "RootWakeNodes"}
    for name, value in settings.items():
        set_parm(container, "VSPAERO", aliases.get(name, name), value)
    prepared = run_dir / "model.vsp3"
    vsp.SetVSP3FileName(str(prepared))
    vsp.Update()
    vsp.WriteVSPFile(str(prepared), vsp.SET_ALL)
    (run_dir / "inputs.json").write_text(
        json.dumps({"source_model": str(model.resolve()), "analysis": settings,
                    "control_groups": GROUPS}, indent=2), encoding="utf-8"
    )
    if prepare_only:
        return prepared

    exe_dir = next(
        (p for p in Path(vsp.__file__).resolve().parents if (p / "vspaero.exe").is_file()),
        None,
    )
    if exe_dir is None:
        raise FileNotFoundError("Could not locate vspaero.exe in the OpenVSP distribution")
    vsp.SetVSPAEROPath(str(exe_dir))
    vsp.SetComputationFileName(vsp.DEGEN_GEOM_CSV_TYPE, str(run_dir / "model_DegenGeom.csv"))
    set_inputs("VSPAEROComputeGeometry", common)
    if not vsp.ExecAnalysis("VSPAEROComputeGeometry"):
        raise RuntimeError("VSPAERO geometry generation failed")
    set_inputs("VSPAEROSweep", settings)
    result = vsp.ExecAnalysis("VSPAEROSweep")
    stability = run_dir / "model_DegenGeom.stab"
    if not result or not stability.is_file() or not stability.stat().st_size:
        raise RuntimeError(f"VSPAERO did not write {stability}")
    return stability


def main():
    try:
        print(launch(MODEL_PATH, RUN_DIR, PREPARE_ONLY))
    except (OSError, RuntimeError, ValueError) as exc:
        raise SystemExit(f"{Path(__file__).name}: {exc}") from exc


if __name__ == "__main__":
    main()
