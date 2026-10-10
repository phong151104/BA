"""All deliverables are in English. Original source titles in the reference list are exempt."""
import re
from telco_retention.common import ROOT

# Letters used only in Vietnamese (a/o/u with horn or breve, d-stroke, Latin Extended Additional block).
VIETNAMESE = re.compile("[\u0102\u0103\u0110\u0111\u01a0\u01a1\u01af\u01b0\u1ea0-\u1ef9]")
EXEMPT = {"docs/references.md"}


def deliverables():
    patterns = ["README.md", "CHANGELOG.md", "configs/*.yaml", "app/*.py", "src/**/*.py", "src/**/*.j2", "scripts/*.py", "tests/*.py",
                "docs/*.md", "reports/*.md", "reports/presentation/*.md", "notebooks/*.ipynb"]
    for pattern in patterns:
        for path in ROOT.glob(pattern):
            rel = path.relative_to(ROOT).as_posix()
            if rel not in EXEMPT:
                yield rel, path


def test_no_vietnamese_text_in_deliverables():
    offenders = [rel for rel, path in deliverables() if VIETNAMESE.search(path.read_text(encoding="utf-8"))]
    assert offenders == []
