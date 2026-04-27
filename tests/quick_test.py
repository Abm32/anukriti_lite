#!/usr/bin/env python3
"""
Quick test script to verify VCF and ChEMBL integration works.
"""

import os
import sys


def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    try:
        from src.chembl_processor import connect_chembl, find_chembl_db_path
        from src.input_processor import get_drug_fingerprint
        from src.vcf_processor import extract_cyp_variants, get_sample_ids_from_vcf
        from src.vector_search import find_similar_drugs

        print("✓ All imports successful")
        return True
    except Exception as e:
        print(f"✗ Import failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_vcf_file():
    """Test VCF file exists and can be read."""
    print("\nTesting VCF file...")
    from src.vcf_processor import discover_vcf_paths

    discovered = discover_vcf_paths("data/genomes")
    vcf_path = (
        discovered.get("chr22")
        or "data/genomes/ALL.chr22.phase3_shapeit2_mvncall_integrated_v5a.20130502.genotypes.vcf.gz"
    )
    if not vcf_path or not os.path.exists(vcf_path):
        print(
            f"⚠ VCF file not found: {vcf_path or 'data/genomes (no chr22 discovered)'}"
        )
        return False

    print(f"✓ VCF file exists: {vcf_path}")

    try:
        from src.vcf_processor import get_sample_ids_from_vcf

        samples = get_sample_ids_from_vcf(vcf_path, limit=3)
        if samples:
            print(f"✓ Found {len(samples)} sample IDs: {samples[:3]}")
            return True
        else:
            print("⚠ No samples found in VCF (file may be empty or corrupted)")
            return False
    except Exception as e:
        print(f"✗ Error reading VCF: {e}")
        return False


def test_chembl_db():
    """Test ChEMBL database exists."""
    print("\nTesting ChEMBL database...")

    try:
        from src.chembl_processor import find_chembl_db_path

        db_path = find_chembl_db_path()

        if not db_path:
            print("⚠ ChEMBL database not found")
            print("  Expected locations:")
            print("    - data/chembl/chembl_34_sqlite/chembl_34.db")
            print("    - data/chembl/chembl_34.db")
            return False

        print(f"✓ ChEMBL database found: {db_path}")

        # Try to connect
        from src.chembl_processor import connect_chembl

        conn = connect_chembl(db_path)
        conn.close()
        print("✓ Can connect to ChEMBL database")
        return True

    except Exception as e:
        print(f"✗ Error with ChEMBL: {e}")
        return False


def test_drug_processing():
    """Test drug fingerprint generation."""
    print("\nTesting drug processing...")

    try:
        from src.input_processor import get_drug_fingerprint

        fingerprint = get_drug_fingerprint("CC(=O)Nc1ccc(O)cc1")  # Paracetamol
        assert len(fingerprint) == 2048
        print(f"✓ Drug fingerprint generated: {len(fingerprint)} bits")
        return True
    except Exception as e:
        print(f"✗ Drug processing failed: {e}")
        return False


def main():
    print("=" * 60)
    print("Quick Integration Test")
    print("=" * 60)

    results = []
    results.append(("Imports", test_imports()))
    results.append(("VCF File", test_vcf_file()))
    results.append(("ChEMBL DB", test_chembl_db()))
    results.append(("Drug Processing", test_drug_processing()))

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {name}")

    passed = sum(1 for _, r in results if r)
    total = len(results)

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All quick tests passed!")
        print("\nNext steps:")
        print("1. Run full validation: python tests/validation_tests.py")
        print("2. Ingest ChEMBL data: python ingest_chembl_to_pinecone.py")
        print("3. Test with VCF: python main.py --vcf data/genomes/...vcf.gz")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        print("Check the errors above and ensure:")
        print("- VCF file is in data/genomes/")
        print("- ChEMBL database is extracted in data/chembl/")


if __name__ == "__main__":
    main()
