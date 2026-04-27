#!/usr/bin/env python3
"""
Anukriti - In Silico Pharmacogenomics Platform
Main Entry Point

This script simulates drug effects on synthetic patient cohorts using Agentic AI.
Supports both manual patient profiles and VCF-derived profiles from 1000 Genomes Project.
"""

import argparse
import json
import os
from typing import List, Union, cast

from src.agent_engine import run_simulation
from src.allele_caller import call_gene_from_variants, interpret_cyp2c19
from src.config import config
from src.exceptions import ConfigurationError
from src.input_processor import get_drug_fingerprint
from src.logging_config import setup_logging
from src.slco1b1_caller import interpret_slco1b1, interpret_slco1b1_from_vcf
from src.variant_db import get_phenotype_prediction
from src.vcf_processor import (
    discover_vcf_paths,
    generate_patient_profile_from_vcf,
    get_sample_ids_from_vcf,
)
from src.vector_search import find_similar_drugs
from src.warfarin_caller import interpret_warfarin

# Set up logging
setup_logging()


def _variants_from_row(row: dict) -> dict:
    """Build variant map for allele_caller from JSON. Expects 'variants': {rsid: {ref, alt, gt}} or {rsid: [ref, alt, gt]}."""
    raw = row.get("variants") or {}
    out = {}
    for rsid, v in raw.items():
        if isinstance(v, (list, tuple)) and len(v) >= 3:
            out[rsid] = (str(v[0]), str(v[1]), str(v[2]))
        elif isinstance(v, dict) and "ref" in v and "alt" in v and "gt" in v:
            out[rsid] = (str(v["ref"]), str(v["alt"]), str(v["gt"]))
    return out


def _is_simple_variant_dict(v: dict) -> bool:
    """True if variants is rsid -> alt (all values are strings)."""
    if not v:
        return False
    return all(isinstance(x, str) for x in v.values())


def run_benchmark(json_path: str) -> None:
    """
    Run evaluation mode: load CPIC-style examples from JSON, report predicted vs expected.
    Supports:
    - CYP2C19 + "expected" (display): {"gene": "CYP2C19", "variants": {"rs4244285": "A"}, "expected": "Intermediate Metabolizer"} -> interpret_cyp2c19
    - allele-based: {"gene", "alleles", "expected_phenotype"} (normalized)
    - variant-based (VCF): {"gene", "variants": {rsid: {ref, alt, gt}}, "expected_phenotype"} (normalized)
    """
    if not os.path.isfile(json_path):
        print(f"Error: Benchmark file not found: {json_path}")
        return
    with open(json_path, "r") as f:
        examples = json.load(f)
    if not isinstance(examples, list):
        examples = [examples]
    results = []
    for i, row in enumerate(examples):
        predicted: str = ""
        alleles: Union[List[str], str] = []
        gene = row.get("gene", "CYP2D6")
        expected_display = row.get("expected")
        expected_normalized = (
            (row.get("expected_phenotype") or "").strip().lower().replace(" ", "_")
        )
        variants_raw = row.get("variants") or {}

        # Statin benchmark (statin_examples.json): drug + genotype → expected recommendation
        if "drug" in row and "genotype" in row and "expected" in row:
            slco_result = interpret_slco1b1(
                row["genotype"].strip().upper(), row["drug"]
            )
            if slco_result:
                predicted = slco_result["recommendation"]
                match = predicted == row["expected"]
                results.append(
                    {
                        "gene": "SLCO1B1",
                        "alleles": slco_result["genotype"],
                        "expected": row["expected"],
                        "predicted": predicted,
                        "match": match,
                        "drug_name": row["drug"],
                        "description": "",
                    }
                )
                continue

        # SLCO1B1: rs4149056 with [ref, alt, gt] or ref/alt/gt dict; expected = phenotype text
        slco_var_map = None
        if expected_display and variants_raw and "rs4149056" in variants_raw:
            raw_rs = variants_raw.get("rs4149056")
            if isinstance(raw_rs, (list, tuple)) and len(raw_rs) >= 3:
                slco_var_map = {
                    "rs4149056": (str(raw_rs[0]), str(raw_rs[1]), str(raw_rs[2]))
                }
            elif (
                isinstance(raw_rs, dict)
                and "ref" in raw_rs
                and "alt" in raw_rs
                and "gt" in raw_rs
            ):
                slco_var_map = {
                    "rs4149056": (raw_rs["ref"], raw_rs["alt"], raw_rs["gt"])
                }
        if slco_var_map:
            slco_result = interpret_slco1b1_from_vcf(slco_var_map)
            if slco_result:
                predicted = slco_result["phenotype"]
                match = predicted == expected_display
                alleles = slco_result["genotype"]
                expected_out = expected_display
                gene = "SLCO1B1"
                results.append(
                    {
                        "gene": gene,
                        "alleles": alleles,
                        "expected": expected_out,
                        "predicted": predicted,
                        "match": match,
                        "drug_name": row.get("drug_name", ""),
                        "description": row.get("description", ""),
                    }
                )
                continue
        # Warfarin: variants include VKORC1 (rs9923231) and optional CYP2C9; expected = recommendation text
        if expected_display and variants_raw and _is_simple_variant_dict(variants_raw):
            if gene == "Warfarin" or "rs9923231" in variants_raw:
                result = interpret_warfarin(variants_raw)
                predicted = result["recommendation"]
                match = predicted == expected_display
                alleles = f"{result['CYP2C9']} + {result['VKORC1']}"
                expected_out = expected_display
                gene = "Warfarin"
            elif gene == "CYP2C19":
                result = interpret_cyp2c19(variants_raw)
                predicted = result["phenotype"]
                match = predicted == expected_display
                alleles = result.get("alleles", "*1/*1")
                expected_out = expected_display
            else:
                variant_map = _variants_from_row(row)
                if variant_map:
                    cpic_result = call_gene_from_variants(gene, variant_map)
                    if cpic_result:
                        predicted = cpic_result["phenotype_normalized"]
                        alleles = cast(
                            List[str],
                            cpic_result.get("alleles_detected", []),
                        )
                    else:
                        predicted = "unknown"
                        alleles = []
                    expected_out = expected_normalized
                    match = predicted == expected_normalized
                else:
                    alleles = cast(List[str], row.get("alleles", []))
                    copy_number = row.get("copy_number", 2)
                    predicted = get_phenotype_prediction(gene, alleles, copy_number)
                    expected_out = expected_normalized
                    match = predicted == expected_normalized
        else:
            variant_map = _variants_from_row(row)
            if variant_map:
                cpic_result = call_gene_from_variants(gene, variant_map)
                if cpic_result:
                    predicted = cpic_result["phenotype_normalized"]
                    alleles = cast(
                        List[str],
                        cpic_result.get("alleles_detected", []),
                    )
                else:
                    predicted = "unknown"
                    alleles = []
                expected_out = expected_normalized
                match = predicted == expected_normalized
            else:
                alleles = cast(List[str], row.get("alleles", []))
                copy_number = row.get("copy_number", 2)
                predicted = get_phenotype_prediction(gene, alleles, copy_number)
                expected_out = expected_normalized
                match = predicted == expected_normalized

        results.append(
            {
                "gene": gene,
                "alleles": alleles,
                "expected": expected_out,
                "predicted": predicted,
                "match": match,
                "drug_name": row.get("drug_name", ""),
                "description": row.get("description", ""),
            }
        )
    matches = sum(1 for r in results if r["match"])
    pct = (100.0 * matches / len(results)) if results else 0
    print("\n=== Anukriti CPIC Benchmark ===\n")
    print(
        f"{'Gene':<10} {'Alleles':<20} {'Expected':<25} {'Predicted':<25} {'Match':<6}"
    )
    print("-" * 90)
    for r in results:
        al = r["alleles"]
        alleles_str = al if isinstance(al, str) else (",".join(al) if al else "*1/*1")
        print(
            f"{r['gene']:<10} {alleles_str:<20} {r['expected']:<25} {r['predicted']:<25} {'Yes' if r['match'] else 'No':<6}"
        )
    print("-" * 90)
    print(f"Match: {matches}/{len(results)} ({pct:.1f}%)\n")
    if any(not r["match"] for r in results):
        print("Mismatches:")
        for r in results:
            if not r["match"]:
                print(
                    f"  {r['gene']} {r['alleles']}: expected {r['expected']}, got {r['predicted']}"
                )


def main():
    parser = argparse.ArgumentParser(
        description="Run pharmacogenomics simulation (research prototype; not for clinical use). Supports Big 3 enzymes and UGT1A1/SLCO1B1.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Disclaimer: Anukriti is a research prototype. Outputs are synthetic predictions and must not be used for clinical decision-making.

Examples:
  # Single chromosome (CYP2D6 only):
  python main.py --vcf data/genomes/chr22.vcf.gz --drug-name Codeine

  # Multiple chromosomes (Big 3 enzymes):
  python main.py --vcf data/genomes/chr22.vcf.gz --vcf-chr10 data/genomes/chr10.vcf.gz --drug-name Warfarin

  # Manual profile:
  python main.py --cyp2d6-status poor_metabolizer --drug-name Tramadol

  # Evaluation mode (CPIC benchmark):
  python main.py --benchmark cpic_examples.json
        """,
    )
    parser.add_argument(
        "--benchmark",
        metavar="JSON",
        help="Run evaluation mode: load CPIC-style examples from JSON, report predicted vs expected phenotype and match %%",
    )
    parser.add_argument(
        "--drug-smiles", default="CC(=O)Nc1ccc(O)cc1", help="SMILES string of drug"
    )
    parser.add_argument(
        "--drug-name", default="Synthetic-Para-101", help="Name of the drug"
    )
    parser.add_argument("--vcf", help="Path to VCF file for chromosome 22 (CYP2D6)")
    parser.add_argument(
        "--vcf-chr10", help="Path to VCF file for chromosome 10 (CYP2C9 and CYP2C19)"
    )
    parser.add_argument("--sample-id", help="Sample ID from VCF file")
    parser.add_argument(
        "--cyp2d6-status",
        choices=[
            "extensive_metabolizer",
            "intermediate_metabolizer",
            "poor_metabolizer",
            "ultra_rapid_metabolizer",
        ],
        default="poor_metabolizer",
        help="CYP2D6 metabolizer status (if not using VCF)",
    )

    args = parser.parse_args()

    # Evaluation mode: benchmark predicted vs expected phenotypes
    if args.benchmark:
        run_benchmark(args.benchmark)
        return

    # Resolve VCF paths: CLI args > env (config) > discovered files in data/genomes
    genomes_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "data", "genomes"
    )
    discovered = discover_vcf_paths(genomes_dir)
    vcf_chr22 = args.vcf or config.VCF_CHR22_PATH or discovered.get("chr22")
    vcf_chr10 = args.vcf_chr10 or config.VCF_CHR10_PATH or discovered.get("chr10")
    # Build full chromosome map for profile (chr2=UGT1A1, chr10=CYP2C9/CYP2C19, chr12=SLCO1B1, chr22=CYP2D6)
    vcf_paths_by_chrom = dict(discovered) if discovered else {}
    if vcf_chr22:
        vcf_paths_by_chrom["chr22"] = vcf_chr22
    if vcf_chr10:
        vcf_paths_by_chrom["chr10"] = vcf_chr10

    user_drug_smiles = args.drug_smiles
    user_drug_name = args.drug_name

    print(f"--- Starting Simulation for {user_drug_name} ---")

    # 2. Define Patient Profile
    vcf_available = vcf_chr22 and (
        os.path.exists(vcf_chr22) or str(vcf_chr22).startswith("s3://")
    )
    if vcf_available:
        print(f"\n[VCF Mode] Using patient profile from VCF files")
        # List all discovered chromosomes (from data/genomes)
        if discovered:
            chroms_sorted = sorted(discovered.keys(), key=lambda c: (len(c), c))
            print(
                f"  Discovered chromosomes ({len(discovered)}): {', '.join(chroms_sorted)}"
            )
        print(f"  Chromosome 22 (CYP2D6): {vcf_chr22}")
        if vcf_chr10:
            print(f"  Chromosome 10 (CYP2C9/CYP2C19): {vcf_chr10}")
        if vcf_paths_by_chrom.get("chr2"):
            print(f"  Chromosome 2 (UGT1A1): {vcf_paths_by_chrom['chr2']}")
        if vcf_paths_by_chrom.get("chr12"):
            print(f"  Chromosome 12 (SLCO1B1): {vcf_paths_by_chrom['chr12']}")
        if vcf_chr10:
            print("  ✓ Big 3 enzymes + UGT1A1/SLCO1B1 when chr2/chr12 present")
        elif not (vcf_paths_by_chrom.get("chr2") or vcf_paths_by_chrom.get("chr12")):
            print(
                "  ⚠ Only CYP2D6 enabled (add chr10/chr2/chr12 VCFs for full profile)"
            )

        try:
            if args.sample_id:
                sample_id = args.sample_id
            else:
                # Get first available sample from chromosome 22
                sample_ids = get_sample_ids_from_vcf(vcf_chr22, limit=1)
                if sample_ids:
                    sample_id = sample_ids[0]
                else:
                    raise ValueError("No samples found in VCF file")

            print(f"  Sample ID: {sample_id}")
            patient_profile = generate_patient_profile_from_vcf(
                vcf_chr22,
                sample_id,
                age=45,
                conditions=["Chronic Liver Disease (Mild)"],
                lifestyle={"alcohol": "Moderate", "smoking": "Non-smoker"},
                vcf_path_chr10=vcf_chr10,
                vcf_paths_by_chrom=vcf_paths_by_chrom,
                drug_name=user_drug_name,
            )
            print("  ✓ Generated patient profile from VCF")
        except Exception as e:
            print(f"  ⚠ Error processing VCF: {e}")
            print("  Falling back to manual profile...")
            patient_profile = create_manual_profile(args.cyp2d6_status)
    else:
        print("\n[Manual Mode] Using manually defined patient profile")
        patient_profile = create_manual_profile(args.cyp2d6_status)

    print(f"\nPatient Profile:")
    print(patient_profile)

    # 3. Process Drug
    print("\n--- Step 1: Processing Drug ---")
    try:
        vector = get_drug_fingerprint(user_drug_smiles)
        print(f"✓ Drug digitized: {len(vector)}-bit fingerprint")
    except Exception as e:
        print(f"✗ Error processing drug: {e}")
        return

    # 4. Search for Similar Drugs
    print("\n--- Step 2: Vector Similarity Search ---")
    similar_drugs = find_similar_drugs(vector)
    print(f"✓ Found {len(similar_drugs)} similar drugs:")
    for i, drug in enumerate(similar_drugs, 1):
        print(f"  {i}. {drug}")

    # 5. Run AI Simulation
    print("\n--- Step 3: AI Simulation ---")
    # Validate configuration
    is_valid, missing_keys = config.validate_required()
    if not is_valid:
        print(
            f"⚠️ Configuration Error: Missing required keys: {', '.join(missing_keys)}"
        )
        print(
            "Please set GOOGLE_API_KEY or GEMINI_API_KEY in your environment or .env file."
        )
        return

    if config.GOOGLE_API_KEY:
        try:
            result = run_simulation(
                user_drug_name,
                similar_drugs,
                patient_profile,
                drug_smiles=user_drug_smiles,
            )
            print("\n" + "=" * 60)
            print("SIMULATION RESULT")
            print("=" * 60)
            print(result)
        except Exception as e:
            print(f"✗ Error running simulation: {e}")
            import traceback

            traceback.print_exc()
    else:
        print("⚠ GOOGLE_API_KEY not found. Skipping LLM simulation.")
        print("\nExpected Input for LLM:")
        print(f"  Drug: {user_drug_name}")
        print(f"  Similar Drugs: {', '.join(similar_drugs)}")
        print(f"  Patient Profile:\n{patient_profile}")


def create_manual_profile(cyp2d6_status: str) -> str:
    """Create a manual patient profile."""
    return f"""ID: SP-01
Age: 45
Genetics: CYP2D6 {cyp2d6_status.replace('_', ' ').title()}
Conditions: Chronic Liver Disease (Mild)
Lifestyle: Alcohol consumer (Moderate)"""


if __name__ == "__main__":
    main()
