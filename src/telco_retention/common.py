from __future__ import annotations

import hashlib
import json
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


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jsonable(value), indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_csv(frame, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8-sig")


def now():
    return datetime.now(timezone.utc).isoformat()


def latest_run():
    pointer = ROOT / "artifacts/latest.json"
    if not pointer.exists():
        raise FileNotFoundError("Chưa có mô hình. Chạy: python -m telco_retention run-all")
    return ROOT / "artifacts/runs" / read_json(pointer)["run_id"]


def table(frame, digits=3):
    return frame.to_markdown(index=False, floatfmt=f".{digits}f")
