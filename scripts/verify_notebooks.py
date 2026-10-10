"""Re-execute the committed notebooks into artifacts/qa and check the committed copies are executed for the current run."""
import time
import nbformat
from telco_retention.common import ROOT, latest_run, write_json
from telco_retention.notebooks import NOTEBOOKS, execute

run = latest_run()
out = ROOT / "artifacts/qa/notebooks"
results = []
for name in NOTEBOOKS:
    path = ROOT / "notebooks" / f"{name}.ipynb"
    committed = nbformat.read(path, as_version=4)
    code = [c for c in committed.cells if c.cell_type == "code"]
    assert all(c.execution_count for c in code), f"{name}: committed notebook has unexecuted cells"
    assert not any(o.get("output_type") == "error" for c in code for o in c.outputs), f"{name}: committed notebook has errors"
    assert run.name in str(code[0].outputs), f"{name}: committed outputs are from another run"
    start = time.perf_counter()
    executed = nbformat.read(execute([path], out_dir=out)[0], as_version=4)
    assert not any(o.get("output_type") == "error" for c in executed.cells if c.cell_type == "code" for o in c.outputs)
    results.append({"notebook": path.name, "status": "passed", "code_cells": len(code), "seconds": round(time.perf_counter() - start, 2), "run_id": run.name})
    print(f"PASS {path.name}", flush=True)
write_json(ROOT / "artifacts/qa/notebooks.json", results)
