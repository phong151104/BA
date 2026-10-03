"""Execute notebooks with this Python interpreter, preserving source notebooks."""
import sys
import time
from pathlib import Path
import nbformat
from nbclient import NotebookClient
from jupyter_client import KernelManager
from telco_retention.common import ROOT, write_json

out = ROOT / "artifacts/qa/notebooks"
out.mkdir(parents=True, exist_ok=True)
results = []
for path in sorted((ROOT / "notebooks").glob("*.ipynb")):
    start = time.perf_counter()
    notebook = nbformat.read(path, as_version=4)
    manager = KernelManager(kernel_name="python3")
    manager.kernel_spec.argv = [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"]
    client = NotebookClient(notebook, timeout=180, kernel_name="python3", km=manager, resources={"metadata": {"path": str(ROOT)}})
    client.execute()
    nbformat.write(notebook, out / path.name)
    results.append({"notebook": path.name, "status": "passed", "seconds": time.perf_counter() - start})
    print(f"PASS {path.name}", flush=True)
write_json(ROOT / "artifacts/qa/notebooks.json", results)
