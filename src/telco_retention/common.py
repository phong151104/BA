from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
from copy import deepcopy
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]


def config():
    return yaml.safe_load((ROOT / "configs/default.yaml").read_text(encoding="utf-8"))


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def jsonable(value):
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [jsonable(v) for v in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, Path):
        return str(value)
    return value


def canonical(value):
    """Numbers compare by value, so 12 and 12.0 hash identically."""
    if isinstance(value, dict):
        return {str(k): canonical(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [canonical(v) for v in value]
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, float, np.integer, np.floating)):
        return round(float(value), 10) if np.isfinite(value) else None
    return value


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jsonable(value), indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8", newline="\n")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_csv(frame, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig", lineterminator="\n")


def now():
    return datetime.now(timezone.utc).isoformat()


def latest_run():
    pointer = ROOT / "artifacts/latest.json"
    if not pointer.exists():
        raise FileNotFoundError("No trained model yet. Run: python -m telco_retention run-all")
    return ROOT / "artifacts/runs" / read_json(pointer)["run_id"]


def _is_link(path):
    """Symbolic links and Windows junctions point outside the tree: they are removed, never followed."""
    return os.path.islink(path) or os.path.isjunction(path)


def remove_tree(path):
    """shutil.rmtree for trees with read-only entries: Windows marks synced and customised folders read-only, and on POSIX
    a folder without write or read permission blocks deleting what it holds. Permissions change only inside the tree."""
    def open_up(target):
        # Add owner permissions without dropping the others. Best effort: an entry that cannot be changed or has gone is
        # left to rmtree, which reports whatever it cannot delete.
        try:
            if _is_link(target):
                return
            if os.path.isdir(target):
                os.chmod(target, stat.S_IMODE(os.stat(target).st_mode) | stat.S_IRWXU)
                for entry in os.scandir(target):
                    open_up(entry.path)
            elif os.name == "nt":  # Windows will not delete a read-only file; POSIX only needs the folder's permission
                os.chmod(target, stat.S_IMODE(os.stat(target).st_mode) | stat.S_IWRITE)
        except OSError:
            pass
    open_up(path)
    shutil.rmtree(path)


def prune_runs(keep=2):
    """Delete all but the newest `keep` runs; the run in latest.json is always kept."""
    runs = sorted(p for p in (ROOT / "artifacts/runs").iterdir() if p.is_dir())
    current = latest_run()
    kept = set(runs[-keep:]) | {current}
    removed = [p for p in runs if p not in kept]
    for path in removed:
        remove_tree(path)
    return [p.name for p in removed]


def table(frame, digits=3):
    return frame.to_markdown(index=False, floatfmt=f".{digits}f")


def _offer_index(cfg, offer_id):
    for i, offer in enumerate(cfg["offers"]):
        if offer["offer_id"] == offer_id:
            return i
    raise KeyError(f"Unknown offer_id: {offer_id}")


def get_param(cfg, path):
    """Read a dotted config path; `offers.<offer_id>.<field>` addresses an offer by ID."""
    parts = path.split(".")
    node = cfg
    if parts[0] == "offers":
        node, parts = cfg["offers"][_offer_index(cfg, parts[1])], parts[2:]
    for part in parts:
        node = node[part]
    return node


def set_param(cfg, path, value):
    """Return a copy of cfg with one dotted path replaced."""
    out = deepcopy(cfg)
    parts = path.split(".")
    node = out
    if parts[0] == "offers":
        node, parts = out["offers"][_offer_index(out, parts[1])], parts[2:]
    for part in parts[:-1]:
        node = node[part]
    node[parts[-1]] = value
    return out
