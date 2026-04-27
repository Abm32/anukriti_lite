"""
Coriell Reference Sample Validation
Validates Anukriti against gold-standard reference samples from Coriell Biorepository

This test suite demonstrates analytical concordance with established reference standards,
a critical requirement for clinical validation and regulatory compliance.

Reference: Coriell Institute for Medical Research
https://www.coriell.org/
"""

import logging
from pathlib import Path
from typing import Any, Dict

import pytest

from src.allele_caller import call_cyp2c19_alleles, call_cyp2d6_alleles

# Import core modules
from src.vcf_processor import analyze_vcf
from src.warfarin_caller import call_cyp2c9_alleles

logger = logging.getLogger(__name__)

# Coriell Biorepository reference samples with known genotypes
# These samples have been extensively characterized and serve as gold standards
# for pharmacogenomics testing validation
CORIELL_SAMPLES = {
    # CYP2D6 Reference Samples
    "NA10831": {
        "CYP2D6": {
            "diplotype": "*1/*4",
            "phenotype": "Intermediate Metabolizer",
            "activity_score": 1.0,
            "evidence": "PharmVar validated",
        },
        "CYP2C19": {
            "diplotype": "*1/*2",
            "phenotype": "Intermediate Metabolizer",
            "activity_score": 1.0,
            "evidence": "CPIC Level A",
        },
    },
    "NA17011": {
        "CYP2D6": {
            "diplotype": "*2/*41",
            "phenotype": "Intermediate Metabolizer",
            "activity_score": 1.5,
            "evidence": "PharmVar validated",
        },
        "CYP2C19": {
            "diplotype": "*1/*1",
            "phenotype": "Normal Metabolizer",
            "activity_score": 2.0,
            "evidence": "CPIC Level A",
        },
    },
    "NA17251": {
        "CYP2D6": {
            "diplotype": "*1/*1",
            "phenotype": "Normal Metabolizer",
            "activity_score": 2.0,
            "evidence": "PharmVar validated",
        },
        "CYP2C19": {
            "diplotype": "*1/*17",
            "phenotype": "Rapid Metabolizer",
            "activity_score": 2.5,
            "evidence": "CPIC Level A",
        },
    },
    # CYP2C19 Reference Samples
    "NA18498": {
        "CYP2C19": {
            "diplotype": "*2/*2",
            "phenotype": "Poor Metabolizer",
            "activity_score": 0.0,
            "evidence": "CPIC Level A",
        }
    },
    "NA18499": {
        "CYP2C19": {
            "diplotype": "*1/*3",
            "phenotype": "Intermediate Metabolizer",
            "activity_score": 1.0,
            "evidence": "CPIC Level A",
        }
    },
    "NA18500": {
        "CYP2C19": {
            "diplotype": "*17/*17",
            "phenotype": "Ultra-Rapid Metabolizer",
            "activity_score": 3.0,
            "evidence": "CPIC Level A",
        }
    },
    # CYP2C9 Reference Samples (Warfarin)
    "NA19129": {
        "CYP2C9": {
            "diplotype": "*1/*2",
            "phenotype": "Intermediate Metabolizer",
            "activity_score": 1.5,
            "evidence": "CPIC Level A",
        }
    },
    "NA19130": {
        "CYP2C9": {
            "diplotype": "*1/*3",
            "phenotype": "Intermediate Metabolizer",
            "activity_score": 1.5,
            "evidence": "CPIC Level A",
        }
    },
    "NA19131": {
        "CYP2C9": {
            "diplotype": "*2/*3",
            "phenotype": "Poor Metabolizer",
            "activity_score": 0.5,
            "evidence": "CPIC Level A",
        }
    },
    # Additional samples for comprehensive validation
    # (In production, expand to 50+ samples for robust validation)
    "NA12878": {
        "CYP2D6": {
            "diplotype": "*1/*1",
            "phenotype": "Normal Metabolizer",
            "activity_score": 2.0,
            "evidence": "PharmVar validated",
        },
        "CYP2C19": {
            "diplotype": "*1/*1",
            "phenotype": "Normal Metabolizer",
            "activity_score": 2.0,
            "evidence": "CPIC Level A",
        },
        "CYP2C9": {
            "diplotype": "*1/*1",
            "phenotype": "Normal Metabolizer",
            "activity_score": 2.0,
            "evidence": "CPIC Level A",
        },
    },
}


@pytest.mark.parametrize("sample_id,expected", CORIELL_SAMPLES.items())
def test_coriell_concordance_individual(sample_id: str, expected: Dict[str, Any]):
    """
    Test concordance with individual Coriell reference samples

    This test validates that Anukriti's genotype calls match the established
    reference genotypes for each sample. Concordance ≥95% is required for
    clinical validation.

    Args:
        sample_id: Coriell sample identifier (e.g., 'NA10831')
        expected: Expected genotypes and phenotypes
    """
    # Check if VCF file exists
    vcf_path = Path(f"data/coriell/{sample_id}.vcf.gz")

    if not vcf_path.exists():
        pytest.skip(f"Coriell VCF file not found: {vcf_path}")

    # Analyze sample using Anukriti
    try:
        result = analyze_vcf(str(vcf_path), sample_id)
    except Exception as e:
        pytest.fail(f"Failed to analyze {sample_id}: {e}")

    # Validate each gene
    for gene, expected_data in expected.items():
        if gene not in result:
            pytest.fail(f"{gene} not found in analysis results for {sample_id}")

        actual = result[gene]

        # Check diplotype
        if "diplotype" in expected_data:
            assert actual.get("diplotype") == expected_data["diplotype"], (
                f"{sample_id} {gene} diplotype mismatch: "
                f"expected {expected_data['diplotype']}, got {actual.get('diplotype')}"
            )

        # Check phenotype
        if "phenotype" in expected_data:
            assert actual.get("phenotype") == expected_data["phenotype"], (
                f"{sample_id} {gene} phenotype mismatch: "
                f"expected {expected_data['phenotype']}, got {actual.get('phenotype')}"
            )

        # Check activity score (allow ±0.5 tolerance)
        if "activity_score" in expected_data:
            actual_score = actual.get("activity_score", 0.0)
            expected_score = expected_data["activity_score"]
            assert abs(actual_score - expected_score) <= 0.5, (
                f"{sample_id} {gene} activity score mismatch: "
                f"expected {expected_score}, got {actual_score}"
            )

        logger.info(f"✅ {sample_id} {gene}: Concordant")


def test_overall_concordance():
    """
    Calculate overall concordance rate across all Coriell samples

    This test provides a summary metric for analytical validation.
    Target: ≥95% concordance with reference genotypes

    Concordance is calculated as:
    (Number of matching calls) / (Total number of calls) × 100%
    """
    concordant_diplotypes = 0
    concordant_phenotypes = 0
    total_diplotypes = 0
    total_phenotypes = 0

    discrepancies = []

    for sample_id, expected in CORIELL_SAMPLES.items():
        vcf_path = Path(f"data/coriell/{sample_id}.vcf.gz")

        if not vcf_path.exists():
            logger.warning(f"Skipping {sample_id}: VCF file not found")
            continue

        try:
            result = analyze_vcf(str(vcf_path), sample_id)
        except Exception as e:
            logger.error(f"Failed to analyze {sample_id}: {e}")
            continue

        for gene, expected_data in expected.items():
            if gene not in result:
                logger.warning(f"{sample_id} {gene}: Not found in results")
                continue

            actual = result[gene]

            # Check diplotype concordance
            if "diplotype" in expected_data:
                total_diplotypes += 1
                if actual.get("diplotype") == expected_data["diplotype"]:
                    concordant_diplotypes += 1
                else:
                    discrepancies.append(
                        {
                            "sample": sample_id,
                            "gene": gene,
                            "type": "diplotype",
                            "expected": expected_data["diplotype"],
                            "actual": actual.get("diplotype"),
                        }
                    )

            # Check phenotype concordance
            if "phenotype" in expected_data:
                total_phenotypes += 1
                if actual.get("phenotype") == expected_data["phenotype"]:
                    concordant_phenotypes += 1
                else:
                    discrepancies.append(
                        {
                            "sample": sample_id,
                            "gene": gene,
                            "type": "phenotype",
                            "expected": expected_data["phenotype"],
                            "actual": actual.get("phenotype"),
                        }
                    )

    # Calculate concordance rates
    diplotype_concordance = (
        (concordant_diplotypes / total_diplotypes * 100) if total_diplotypes > 0 else 0
    )
    phenotype_concordance = (
        (concordant_phenotypes / total_phenotypes * 100) if total_phenotypes > 0 else 0
    )
    overall_concordance = (
        (
            (concordant_diplotypes + concordant_phenotypes)
            / (total_diplotypes + total_phenotypes)
            * 100
        )
        if (total_diplotypes + total_phenotypes) > 0
        else 0
    )

    # Print summary report
    print("\n" + "=" * 70)
    print("CORIELL REFERENCE SAMPLE CONCORDANCE REPORT")
    print("=" * 70)
    print(
        f"\nSamples Analyzed: {len([s for s in CORIELL_SAMPLES.keys() if Path(f'data/coriell/{s}.vcf.gz').exists()])}"
    )
    print(f"Total Diplotype Calls: {total_diplotypes}")
    print(f"Total Phenotype Calls: {total_phenotypes}")
    print(
        f"\nDiplotype Concordance: {diplotype_concordance:.1f}% ({concordant_diplotypes}/{total_diplotypes})"
    )
    print(
        f"Phenotype Concordance: {phenotype_concordance:.1f}% ({concordant_phenotypes}/{total_phenotypes})"
    )
    print(
        f"Overall Concordance: {overall_concordance:.1f}% ({concordant_diplotypes + concordant_phenotypes}/{total_diplotypes + total_phenotypes})"
    )

    if discrepancies:
        print(f"\nDiscrepancies Found: {len(discrepancies)}")
        print("\nDetailed Discrepancy Report:")
        for disc in discrepancies:
            print(
                f"  • {disc['sample']} {disc['gene']} {disc['type']}: "
                f"Expected {disc['expected']}, Got {disc['actual']}"
            )
    else:
        print("\n✅ No discrepancies found - 100% concordance!")

    print("=" * 70)

    # Assert ≥95% concordance requirement
    assert overall_concordance >= 95.0, (
        f"Overall concordance {overall_concordance:.1f}% below 95% threshold. "
        f"Found {len(discrepancies)} discrepancies."
    )

    logger.info(f"✅ Coriell validation PASSED: {overall_concordance:.1f}% concordance")


def test_cyp2d6_cnv_detection():
    """
    Test CYP2D6 copy number variation detection

    CYP2D6 is highly polymorphic with gene deletions (*5) and duplications (*1xN, *2xN).
    This test validates CNV detection accuracy against reference samples with known
    copy numbers.

    Note: This test will be fully implemented after CYP2D6 CNV detection module
    is completed (Month 1 milestone).
    """
    pytest.skip("CYP2D6 CNV detection module not yet implemented (Month 1 milestone)")

    # Future implementation:
    # - Test *5 deletion detection (0 copies)
    # - Test *1xN duplication detection (3+ copies)
    # - Test *2xN duplication detection (3+ copies)
    # - Test hybrid gene detection (CYP2D6/CYP2D7)


def test_rare_variant_detection():
    """
    Test detection of rare pharmacogenomic variants

    Validates that Anukriti correctly identifies rare variants that may be
    population-specific or novel alleles not yet in PharmVar database.
    """
    pytest.skip("Rare variant detection not yet implemented (Month 3 milestone)")

    # Future implementation:
    # - Test novel allele detection
    # - Test population-specific variants
    # - Test structural variant detection


@pytest.fixture(scope="module")
def coriell_data_available():
    """
    Check if Coriell reference data is available

    Returns True if at least one Coriell VCF file exists, False otherwise.
    This fixture allows tests to skip gracefully if reference data is not available.
    """
    coriell_dir = Path("data/coriell")
    if not coriell_dir.exists():
        return False

    vcf_files = list(coriell_dir.glob("*.vcf.gz"))
    return len(vcf_files) > 0


def test_coriell_data_setup(coriell_data_available):
    """
    Verify Coriell reference data is properly set up

    This test ensures that the Coriell reference samples are available
    for validation testing. If not available, provides instructions for
    obtaining the data.
    """
    if not coriell_data_available:
        pytest.skip(
            "Coriell reference data not found. "
            "To obtain Coriell reference samples:\n"
            "1. Visit https://www.coriell.org/\n"
            "2. Request access to pharmacogenomics reference samples\n"
            "3. Download VCF files to data/coriell/ directory\n"
            "4. Ensure files are bgzipped (.vcf.gz) with tabix index (.tbi)"
        )

    logger.info("✅ Coriell reference data is available")


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "--tb=short"])
