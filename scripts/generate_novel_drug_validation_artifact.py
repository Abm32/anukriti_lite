#!/usr/bin/env python3
"""
Generate a lightweight validation artifact for novel-drug mode gating.
"""

import json
from pathlib import Path


def _count_examples(path: Path) -> int:
    if not path.is_file():
        return 0
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return len(data) if isinstance(data, list) else 0
    except Exception:
        return 0


def main() -> None:
    repo = Path(__file__).resolve().parent.parent
    cpic_count = _count_examples(repo / "cpic_examples.json")
    warf_count = _count_examples(repo / "warfarin_examples.json")
    artifact = {
        "artifact_name": "novel_drug_validation_artifact",
        "cpic_examples_count": cpic_count,
        "warfarin_examples_count": warf_count,
        "artifact_ready": cpic_count > 0 and warf_count > 0,
        "gate_policy": {
            "decision_grade_requires": [
                "confidence_tier == high",
                "deterministic_coverage.callable_genes not empty",
                "vector_mock_fallback == false",
            ]
        },
        "note": (
            "This artifact is a reproducible baseline summary. "
            "Retrospective/preclinical validation remains required for decision-grade claims."
        ),
    }
    out_dir = repo / "build_reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "novel_drug_validation_artifact.json"
    with out_file.open("w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2)
    print(str(out_file))


if __name__ == "__main__":
    main()
