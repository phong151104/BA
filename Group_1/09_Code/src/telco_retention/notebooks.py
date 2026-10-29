"""Narrative notebooks: rendered from templates (Markdown + ```python fences) and executed in place."""
from __future__ import annotations

import re
import sys
from pathlib import Path
import nbformat
from .common import ROOT
from .templating import render

NOTEBOOKS = ["01-data-eda", "02-models-validation", "03-targeting", "04-sensitivity-fairness"]
FENCE = re.compile(r"^```python\s*\n(.*?)^```\s*$", re.S | re.M)


def to_notebook(text):
    cells, position = [], 0
    for match in FENCE.finditer(text):
        markdown = text[position:match.start()].strip()
        if markdown:
            cells.append(nbformat.v4.new_markdown_cell(markdown))
        cells.append(nbformat.v4.new_code_cell(match.group(1).strip()))
        position = match.end()
    if text[position:].strip():
        cells.append(nbformat.v4.new_markdown_cell(text[position:].strip()))
    nb = nbformat.v4.new_notebook(cells=cells)
    nb.metadata.kernelspec = {"display_name": "Python 3", "language": "python", "name": "python3"}
    nb.metadata.language_info = {"name": "python"}
    return nb


def build(ctx, root=ROOT):
    paths = []
    for name in NOTEBOOKS:
        path = Path(root) / "notebooks" / f"{name}.ipynb"
        path.parent.mkdir(parents=True, exist_ok=True)
        nbformat.write(to_notebook(render(f"notebooks/{name}.md.j2", ctx)), path)
        paths.append(path)
    return paths


def execute(paths, out_dir=None, timeout=300):
    """Run notebooks with this interpreter; write back in place unless out_dir is given."""
    from jupyter_client import KernelManager
    from nbclient import NotebookClient
    results = []
    for path in paths:
        notebook = nbformat.read(path, as_version=4)
        manager = KernelManager(kernel_name="python3")
        manager.kernel_spec.argv = [sys.executable, "-m", "ipykernel_launcher", "-f", "{connection_file}"]
        NotebookClient(notebook, timeout=timeout, kernel_name="python3", km=manager, record_timing=False,
                       resources={"metadata": {"path": str(ROOT)}}).execute()
        target = Path(out_dir) / Path(path).name if out_dir else Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        nbformat.write(notebook, target)
        results.append(target)
    return results
