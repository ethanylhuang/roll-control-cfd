#!/usr/bin/env python3
"""OpenFOAM helpers: openfoam-app wrapper exec, dict edits, output parsers."""
import json
import os
import re
import subprocess

OPENFOAM = "/Applications/OpenFOAM-v2606.app/Contents/Resources/etc/openfoam"


class FoamError(RuntimeError):
    def __init__(self, msg, log_path=None):
        super().__init__(msg)
        self.log_path = log_path


def foam_run(case, cmd, log_name=None, check=True, timeout=None):
    """Run one command inside the openfoam-app environment, cwd = case."""
    case = os.path.abspath(case)
    log_path = None
    if log_name:
        log_path = os.path.join(case, f"log.{log_name}")
    proc = subprocess.run(
        [OPENFOAM, "-c", f"cd '{case}' && {cmd}"],
        capture_output=True, text=True, timeout=timeout,
    )
    out = proc.stdout + ("\n--- stderr ---\n" + proc.stderr if proc.stderr.strip() else "")
    if log_path:
        with open(log_path, "w") as f:
            f.write(out)
    if check and proc.returncode != 0:
        tail = "\n".join(out.splitlines()[-30:])
        raise FoamError(f"'{cmd}' failed rc={proc.returncode} in {case}\n{tail}", log_path)
    return proc.returncode, out


def foam_dict_set(case, dictfile, entry, value):
    foam_run(case, f"foamDictionary -entry '{entry}' -set '{value}' {dictfile}",
             log_name=None, check=True)


def latest_time(case):
    """Largest numeric time directory (reconstructed)."""
    best = None
    for d in os.listdir(case):
        if re.fullmatch(r"[0-9]+(\.[0-9]+)?", d):
            v = float(d)
            if best is None or v > best[0]:
                best = (v, d)
    return best  # (float, name) or None


def latest_time_processor(case):
    p0 = os.path.join(case, "processor0")
    return latest_time(p0) if os.path.isdir(p0) else None


def parse_dat(path):
    """Parse an OpenFOAM functionObject .dat file (coefficient.dat, moment.dat).

    Returns (headers, ndarray columns). Vector parentheses are stripped.
    Column names come from the last '#' header line."""
    import numpy as np
    headers, rows = [], []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if line.startswith("#"):
                parts = line[1:].split()
                if len(parts) > 1:
                    headers = parts
                continue
            line = line.replace("(", " ").replace(")", " ")
            rows.append([float(x) for x in line.split()])
    data = np.array(rows)
    return headers, data


def find_fo_file(case, fo_name, filename):
    """Locate postProcessing/<fo_name>/<time>/<filename>, newest time first."""
    root = os.path.join(case, "postProcessing", fo_name)
    if not os.path.isdir(root):
        return None
    times = sorted(os.listdir(root), key=lambda s: float(s) if
                   re.fullmatch(r"[0-9.]+", s) else -1, reverse=True)
    for t in times:
        p = os.path.join(root, t, filename)
        if os.path.exists(p):
            return p
    return None


def variant():
    """Dataset variant, from $AERO_VARIANT (empty = the historical layout).

    Lets one pipeline drive several geometry/config variants side by side --
    e.g. v3 with and without the boattail -- without cloning the tree, so the
    two are guaranteed to share solver settings, mesh tiers and protocol. Any
    difference between them is then geometry and nothing else.
    """
    return os.environ.get("AERO_VARIANT", "").strip()


def apply_variant(cfg):
    """Overlay cfg["variants"][$AERO_VARIANT] onto cfg (shallow, top-level).

    Used so the boattail study is a config overlay on ONE STEP export rather
    than a second CAD export: identical solids, identical solver settings, the
    boattail simply denylisted at tessellation. Any measured difference is then
    the boattail and nothing else."""
    v = variant()
    if not v:
        return cfg
    over = (cfg.get("variants") or {}).get(v)
    if over is None:
        raise SystemExit(f"AERO_VARIANT={v!r} not found in config['variants'] "
                         f"(have: {sorted((cfg.get('variants') or {}))})")
    out = dict(cfg)
    out.update(over)
    return out


def runs_root(root):
    v = variant()
    return os.path.join(root, f"runs_{v}" if v else "runs")


def results_root(root):
    v = variant()
    return os.path.join(root, "results", v) if v else os.path.join(root, "results")


def models_root(root):
    v = variant()
    return os.path.join(root, "models", v) if v else os.path.join(root, "models")


def fo_stats(case, fo_name="forceCoeffs_total", window=400,
             names=("Cd", "CmRoll", "CmPitch", "CmYaw")):
    """mean/std/SNR of each coefficient over the last `window` iterations.

    SNR = |mean| / std is the honest reliability measure for a steady-RANS
    average. Roll runs 10-60 here; pitch runs under 2, because at AoA 0 the
    tab's side force has zero moment arm about the pitch axis and what is left
    is a second-order drag term buried in the residual scatter. Recording this
    per case stops an unconverged column from being read as data.
    """
    path = find_fo_file(case, fo_name, "coefficient.dat")
    if path is None:
        return {}
    headers, data = parse_dat(path)
    if len(data) == 0:
        return {}
    out = {"n_samples": int(min(window, len(data)))}
    for n in names:
        if n not in headers:
            continue
        a = data[:, headers.index(n)][-window:]
        mu, sd = float(a.mean()), float(a.std())
        out[n] = dict(mean=mu, std=sd,
                      snr=(abs(mu) / sd if sd > 0 else float("inf")))
    return out


def classify_stop(log_text, endtime=None):
    """Why did the solver stop?

    Note: every parallel log contains the header line "Floating point exception
    trapping enabled" — a crash is identified by FATAL/abort text instead."""
    if "FOAM FATAL" in log_text or "MPI_ABORT" in log_text \
            or "Foam::sigFpe" in log_text:
        return "diverged"
    if "SIMPLE solution converged in" in log_text:
        return "converged_residual"
    if re.search(r"^End$", log_text, re.M) or "Finalising parallel run" in log_text:
        it = last_iteration(log_text)
        if endtime is not None and it is not None and float(it) < endtime:
            return "runTimeControl"
        return "endTime"
    return "unknown"


def last_iteration(log_text):
    it = None
    for m in re.finditer(r"^Time = (\S+)", log_text, re.M):
        it = m.group(1)
    return it


if __name__ == "__main__":
    import sys
    rc, out = foam_run(sys.argv[1] if len(sys.argv) > 1 else ".",
                       "foamVersion || echo $WM_PROJECT_VERSION", check=False)
    print(out.strip()[-500:])
