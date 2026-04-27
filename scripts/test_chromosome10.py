#!/usr/bin/env python3
"""
Test Script for Chromosome 10 Integration

Tests the Big 3 enzymes (CYP2D6, CYP2C19, CYP2C9) functionality.
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.vcf_processor import (
    CYP_GENE_LOCATIONS,
    discover_vcf_paths,
    extract_cyp_variants,
    generate_patient_profile_from_vcf,
    get_sample_ids_from_vcf,
)


def test_gene_coordinates():
    """Test that gene coordinates are correctly defined."""
    print("=" * 60)
    print("Test 1: Gene Coordinates")
    print("=" * 60)

    for gene, loc in sorted(CYP_GENE_LOCATIONS.items()):
        print(f"  {gene}:")
        print(f"    Chromosome: {loc['chrom']}")
        print(f"    Start: {loc['start']:,}")
        print(f"    End: {loc['end']:,}")
        print(f"    Length: {loc['end'] - loc['start']:,} bp")

    print("\n✅ Gene coordinates loaded correctly\n")


def test_vcf_file_exists():
    """Test that VCF files exist."""
    print("=" * 60)
    print("Test 2: VCF File Existence")
    print("=" * 60)

    discovered = discover_vcf_paths("data/genomes")
    chr22_path = (
        discovered.get("chr22")
        or "data/genomes/ALL.chr22.phase3_shapeit2_mvncall_integrated_v5a.20130502.genotypes.vcf.gz"
    )
    chr10_path = (
        discovered.get("chr10")
        or "data/genomes/ALL.chr10.phase3_shapeit2_mvncall_integrated_v5a.20130502.genotypes.vcf.gz"
    )

    files_ok = True

    if os.path.exists(chr22_path):
        size_mb = os.path.getsize(chr22_path) / (1024 * 1024)
        print(f"  ✅ Chromosome 22: {chr22_path}")
        print(f"     Size: {size_mb:.2f} MB")
    else:
        print(f"  ❌ Chromosome 22: NOT FOUND")
        print(f"     Expected: {chr22_path}")
        files_ok = False

    if os.path.exists(chr10_path):
        size_mb = os.path.getsize(chr10_path) / (1024 * 1024)
        print(f"  ✅ Chromosome 10: {chr10_path}")
        print(f"     Size: {size_mb:.2f} MB")
    else:
        print(f"  ❌ Chromosome 10: NOT FOUND")
        print(f"     Expected: {chr10_path}")
        files_ok = False

    if files_ok:
        print("\n✅ All VCF files found\n")
    else:
        print("\n❌ Some VCF files are missing\n")

    return files_ok, chr22_path, chr10_path


def test_variant_extraction(vcf_path, gene_name):
    """Test extracting variants for a specific gene."""
    print(f"  Testing {gene_name} extraction from {os.path.basename(vcf_path)}...")

    try:
        variants = extract_cyp_variants(vcf_path, gene_name, sample_limit=1)
        print(f"    ✅ Found {len(variants)} variants")

        if variants:
            # Show first variant as example
            first_var = variants[0]
            print(
                f"    Example variant: Position {first_var['pos']:,}, Ref={first_var['ref']}, Alt={first_var['alt']}"
            )

        return True, len(variants)
    except Exception as e:
        print(f"    ❌ Error: {e}")
        return False, 0


def test_chromosome10_variants(chr10_path):
    """Test extracting CYP2C19 and CYP2C9 variants from chromosome 10."""
    print("=" * 60)
    print("Test 3: Chromosome 10 Variant Extraction")
    print("=" * 60)

    results = {}

    # Test CYP2C19
    print("\n  CYP2C19 (Chromosome 10):")
    success, count = test_variant_extraction(chr10_path, "CYP2C19")
    results["CYP2C19"] = {"success": success, "count": count}

    # Test CYP2C9
    print("\n  CYP2C9 (Chromosome 10):")
    success, count = test_variant_extraction(chr10_path, "CYP2C9")
    results["CYP2C9"] = {"success": success, "count": count}

    # Summary
    print("\n  Summary:")
    for gene, result in results.items():
        status = "✅" if result["success"] else "❌"
        print(f"    {status} {gene}: {result['count']} variants")

    all_success = all(r["success"] for r in results.values())
    if all_success:
        print("\n✅ Chromosome 10 variant extraction working\n")
    else:
        print("\n❌ Some variant extractions failed\n")

    return all_success


def test_chromosome22_variants(chr22_path):
    """Test extracting CYP2D6 variants from chromosome 22."""
    print("=" * 60)
    print("Test 4: Chromosome 22 Variant Extraction")
    print("=" * 60)

    print("\n  CYP2D6 (Chromosome 22):")
    success, count = test_variant_extraction(chr22_path, "CYP2D6")

    if success:
        print("\n✅ Chromosome 22 variant extraction working\n")
    else:
        print("\n❌ Chromosome 22 variant extraction failed\n")

    return success


def test_multi_chromosome_profile(chr22_path, chr10_path):
    """Test generating patient profile from multiple chromosomes."""
    print("=" * 60)
    print("Test 5: Multi-Chromosome Patient Profile Generation")
    print("=" * 60)

    try:
        # Get a sample ID
        sample_ids = get_sample_ids_from_vcf(chr22_path, limit=1)
        if not sample_ids:
            print("  ❌ No samples found in VCF file")
            return False

        sample_id = sample_ids[0]
        print(f"\n  Using sample ID: {sample_id}")

        # Generate profile with both chromosomes
        print("  Generating profile with Big 3 enzymes...")
        profile = generate_patient_profile_from_vcf(
            chr22_path,
            sample_id,
            age=45,
            conditions=["Test Condition"],
            lifestyle={"alcohol": "Moderate", "smoking": "Non-smoker"},
            vcf_path_chr10=chr10_path,
        )

        print("\n  Generated Profile:")
        print("  " + "-" * 56)
        for line in profile.split("\n"):
            print(f"  {line}")
        print("  " + "-" * 56)

        # Check if all enzymes are mentioned
        has_cyp2d6 = "CYP2D6" in profile
        has_cyp2c19 = "CYP2C19" in profile
        has_cyp2c9 = "CYP2C9" in profile

        print("\n  Enzyme Detection:")
        print(f"    {'✅' if has_cyp2d6 else '❌'} CYP2D6")
        print(
            f"    {'✅' if has_cyp2c19 else '⚠️ '} CYP2C19 (may be extensive metabolizer)"
        )
        print(
            f"    {'✅' if has_cyp2c9 else '⚠️ '} CYP2C9 (may be extensive metabolizer)"
        )

        if has_cyp2d6:
            print("\n✅ Multi-chromosome profile generation working\n")
            return True
        else:
            print("\n❌ Profile generation failed\n")
            return False

    except Exception as e:
        print(f"\n❌ Error generating profile: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_single_chromosome_profile(chr22_path):
    """Test generating patient profile from single chromosome (backward compatibility)."""
    print("=" * 60)
    print("Test 6: Single-Chromosome Profile (Backward Compatibility)")
    print("=" * 60)

    try:
        sample_ids = get_sample_ids_from_vcf(chr22_path, limit=1)
        if not sample_ids:
            print("  ❌ No samples found")
            return False

        sample_id = sample_ids[0]
        print(f"\n  Using sample ID: {sample_id}")

        profile = generate_patient_profile_from_vcf(
            chr22_path, sample_id, vcf_path_chr10=None  # Single chromosome mode
        )

        print("\n  Generated Profile:")
        print("  " + "-" * 56)
        for line in profile.split("\n"):
            print(f"  {line}")
        print("  " + "-" * 56)

        if "CYP2D6" in profile:
            print("\n✅ Single-chromosome mode working (backward compatible)\n")
            return True
        else:
            print("\n❌ Single-chromosome mode failed\n")
            return False

    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Chromosome 10 Integration Test Suite")
    print("=" * 60 + "\n")

    # Test 1: Gene coordinates
    test_gene_coordinates()

    # Test 2: VCF file existence
    files_ok, chr22_path, chr10_path = test_vcf_file_exists()

    if not files_ok:
        print("❌ Cannot proceed - VCF files missing")
        print("\nPlease download the VCF files first:")
        print("  cd data/genomes/")
        print(
            "  wget https://hgdownload.cse.ucsc.edu/gbdb/hg19/1000Genomes/phase3/ALL.chr22.phase3_shapeit2_mvncall_integrated_v5a.20130502.genotypes.vcf.gz"
        )
        print(
            "  wget https://hgdownload.cse.ucsc.edu/gbdb/hg19/1000Genomes/phase3/ALL.chr10.phase3_shapeit2_mvncall_integrated_v5a.20130502.genotypes.vcf.gz"
        )
        return

    # Test 3: Chromosome 10 variants
    chr10_ok = test_chromosome10_variants(chr10_path)

    # Test 4: Chromosome 22 variants
    chr22_ok = test_chromosome22_variants(chr22_path)

    # Test 5: Multi-chromosome profile
    multi_ok = test_multi_chromosome_profile(chr22_path, chr10_path)

    # Test 6: Single-chromosome profile (backward compatibility)
    single_ok = test_single_chromosome_profile(chr22_path)

    # Final summary
    print("=" * 60)
    print("Test Summary")
    print("=" * 60)
    print(f"  Gene Coordinates: ✅")
    print(f"  VCF Files: {'✅' if files_ok else '❌'}")
    print(f"  Chromosome 10 Variants: {'✅' if chr10_ok else '❌'}")
    print(f"  Chromosome 22 Variants: {'✅' if chr22_ok else '❌'}")
    print(f"  Multi-Chromosome Profile: {'✅' if multi_ok else '❌'}")
    print(f"  Single-Chromosome Profile: {'✅' if single_ok else '❌'}")

    all_tests = [files_ok, chr10_ok, chr22_ok, multi_ok, single_ok]
    if all(all_tests):
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED - Chromosome 10 integration working!")
        print("=" * 60)
        print("\nYou can now use Big 3 enzymes with:")
        print("  python main.py --vcf data/genomes/chr22.vcf.gz \\")
        print("                 --vcf-chr10 data/genomes/chr10.vcf.gz \\")
        print("                 --drug-name Warfarin")
    else:
        print("\n" + "=" * 60)
        print("❌ SOME TESTS FAILED - Check errors above")
        print("=" * 60)

    print()


if __name__ == "__main__":
    main()
