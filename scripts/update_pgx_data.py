#!/usr/bin/env python3
"""
Update or validate PGx curated data (PharmVar / CPIC).

Best practice: use one-time curated tables in data/pgx/, not live APIs at runtime.
This script helps (1) validate existing TSV/JSON and (2) optionally refresh from
open sources (CPIC API, PharmVar downloads, or documented file URLs).

Usage:
  python scripts/update_pgx_data.py --validate
  python scripts/update_pgx_data.py --gene cyp2c19 [--fetch]
  python scripts/update_pgx_data.py --help
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Repo root
REPO_ROOT = Path(__file__).resolve().parent.parent
PGX_DIR = REPO_ROOT / "data" / "pgx"
PHARMVAR_DIR = PGX_DIR / "pharmvar"
CPIC_DIR = PGX_DIR / "cpic"

# Known open endpoints (for optional fetch)
CPIC_API_BASE = "https://api.cpicpgx.org/v1"
CPIC_FILES_BASE = "https://files.cpicpgx.org/data/report/current"
PHARMVAR_DOWNLOAD = "https://www.pharmvar.org/download"


def validate_pharmvar_tsv(path: Path) -> list[str]:
    """Check PharmVar TSV has required columns and valid rows. Returns list of errors."""
    errs = []
    if not path.is_file():
        return [f"File not found: {path}"]
    with open(path) as f:
        lines = [l.rstrip() for l in f if l.strip()]
    if not lines:
        return ["Empty file"]
    header = lines[0].lower().split("\t")
    # Allele table: allele, rsid, alt, function
    if "allele" in header:
        for col in ("allele", "rsid", "alt", "function"):
            if col not in header:
                errs.append(f"Missing column: {col}")
    # Variant table (e.g. VKORC1): variant, rsid, risk_allele, effect
    elif "variant" in header and "rsid" in header:
        for col in ("variant", "rsid", "risk_allele", "effect"):
            if col not in header:
                errs.append(f"Missing column: {col}")
    else:
        errs.append(
            "Expected allele (allele/rsid/alt/function) or variant (variant/rsid/risk_allele/effect) columns"
        )
    if len(lines) < 2:
        errs.append("No data rows")
    return errs


def validate_cpic_json(path: Path) -> list[str]:
    """Check CPIC JSON is a dict of diplotype -> phenotype. Returns list of errors."""
    errs = []
    if not path.is_file():
        return [f"File not found: {path}"]
    try:
        with open(path) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return [f"Invalid JSON: {e}"]
    if not isinstance(data, dict):
        return ["Root must be a JSON object"]
    for k, v in data.items():
        if k.startswith("_"):
            continue
        if not isinstance(v, str):
            errs.append(f"Value for '{k}' must be string")
    return errs


def run_validate() -> int:
    """Validate all existing PGx files; print status and return 0 if all ok."""
    ok = True
    for d in (PHARMVAR_DIR, CPIC_DIR):
        if not d.is_dir():
            print(f"Skip (no dir): {d}")
            continue
        for f in d.iterdir():
            if f.suffix == ".tsv":
                errs = validate_pharmvar_tsv(f)
                if errs:
                    print(f"FAIL {f}: {errs}")
                    ok = False
                else:
                    print(f"OK   {f}")
            elif f.suffix == ".json":
                errs = validate_cpic_json(f)
                if errs:
                    print(f"FAIL {f}: {errs}")
                    ok = False
                else:
                    print(f"OK   {f}")
    if ok:
        print("All PGx files valid.")
    return 0 if ok else 1


def fetch_cpic_alleles_for_gene(gene: str) -> dict | None:
    """Fetch allele list for gene from CPIC API. Returns parsed JSON or None."""
    try:
        import urllib.request

        url = f"{CPIC_API_BASE}/allele?genesymbol={gene.upper()}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        print(f"CPIC API fetch failed: {e}", file=sys.stderr)
        return None


def fetch_cpic_phenotypes_for_gene(gene: str) -> dict | None:
    """
    Try to build diplotype -> phenotype map from CPIC API.
    CPIC has genotype_to_phenotype and phenotype endpoints; we try to assemble a simple lookup.
    """
    try:
        import urllib.request

        # Gene-specific phenotype table if available
        url = f"{CPIC_API_BASE}/gene?genesymbol={gene.upper()}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        # API may return list; we need genotype->phenotype. For now return None so we keep local file.
        return None
    except Exception as e:
        print(f"CPIC phenotype fetch failed: {e}", file=sys.stderr)
        return None


def run_fetch_gene(gene: str) -> int:
    """
    Optionally fetch from CPIC (and later PharmVar) and write to data/pgx/.
    If fetch fails or is not implemented, print instructions and do not overwrite.
    """
    gene = gene.lower()
    print(f"Gene: {gene}")
    print(
        "PharmVar: Download from",
        PHARMVAR_DOWNLOAD,
        "and save as",
        PHARMVAR_DIR / f"{gene}_alleles.tsv",
    )
    alleles = fetch_cpic_alleles_for_gene(gene)
    if alleles:
        print(
            "CPIC alleles response:",
            type(alleles),
            "length" if isinstance(alleles, list) else "keys",
            len(alleles) if isinstance(alleles, (list, dict)) else "N/A",
        )
    phenotypes = fetch_cpic_phenotypes_for_gene(gene)
    if phenotypes:
        out = CPIC_DIR / f"{gene}_phenotypes.json"
        CPIC_DIR.mkdir(parents=True, exist_ok=True)
        with open(out, "w") as f:
            json.dump(phenotypes, f, indent=2)
        print("Wrote", out)
    else:
        print(
            "CPIC phenotype table: use files from",
            CPIC_FILES_BASE,
            "or api.cpicpgx.org; then convert to",
            CPIC_DIR / f"{gene}_phenotypes.json",
        )
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Validate or optionally refresh PGx data (PharmVar/CPIC). See data/pgx/sources.md."
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate existing TSV/JSON in data/pgx/",
    )
    parser.add_argument(
        "--gene", type=str, metavar="GENE", help="Gene to update (e.g. cyp2c19)"
    )
    parser.add_argument(
        "--fetch",
        action="store_true",
        help="Try to fetch from CPIC/PharmVar (optional)",
    )
    args = parser.parse_args()

    if args.validate:
        return run_validate()
    if args.gene:
        return run_fetch_gene(args.gene)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
