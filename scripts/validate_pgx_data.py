#!/usr/bin/env python3
"""
PGx Data Validation

Validates pharmacogene database for completeness, consistency, and quality.
Checks for missing data, invalid entries, and data integrity issues.

Usage:
    python scripts/validate_pgx_data.py --all          # Validate all genes
    python scripts/validate_pgx_data.py --gene CYP3A4  # Validate single gene
    python scripts/validate_pgx_data.py --tier 1       # Validate Tier 1 genes
"""

import argparse
import logging
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Paths
DB_PATH = Path(__file__).parent.parent / "data" / "pgx" / "pharmacogenes.db"

# Validation thresholds
MIN_VARIANTS_PER_GENE = 3  # Minimum expected variants per gene
MIN_PHENOTYPES_PER_GENE = 3  # Minimum expected phenotypes per gene


def get_connection() -> sqlite3.Connection:
    """Get database connection."""
    if not DB_PATH.exists():
        logger.error(f"Database not found: {DB_PATH}")
        logger.error("Run: python scripts/init_gene_database.py --tier 1")
        sys.exit(1)
    return sqlite3.connect(DB_PATH)


def validate_gene_metadata(
    conn: sqlite3.Connection, gene_symbol: str
) -> Tuple[bool, List[str]]:
    """Validate gene metadata (chromosome, positions, tier)."""
    issues = []
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT gene_id, chromosome, start_pos, end_pos, tier, build
        FROM genes
        WHERE gene_symbol = ?
    """,
        (gene_symbol,),
    )

    row = cursor.fetchone()
    if not row:
        issues.append(f"Gene {gene_symbol} not found in database")
        return False, issues

    gene_id, chrom, start, end, tier, build = row

    # Validate chromosome
    valid_chroms = [str(i) for i in range(1, 23)] + ["X", "Y", "MT"]
    if chrom not in valid_chroms:
        issues.append(f"Invalid chromosome: {chrom}")

    # Validate positions
    if start <= 0 or end <= 0:
        issues.append(f"Invalid positions: start={start}, end={end}")
    if start >= end:
        issues.append(f"Start position >= end position: {start} >= {end}")

    # Validate tier
    if tier not in (1, 2, 3):
        issues.append(f"Invalid tier: {tier}")

    # Validate build
    if build not in ("GRCh37", "GRCh38"):
        issues.append(f"Invalid genome build: {build}")

    return len(issues) == 0, issues


def validate_gene_variants(
    conn: sqlite3.Connection, gene_symbol: str
) -> Tuple[bool, List[str]]:
    """Validate variants for a gene."""
    issues = []
    cursor = conn.cursor()

    # Get gene_id
    cursor.execute("SELECT gene_id FROM genes WHERE gene_symbol = ?", (gene_symbol,))
    row = cursor.fetchone()
    if not row:
        issues.append(f"Gene {gene_symbol} not found")
        return False, issues

    gene_id = row[0]

    # Check variant count
    cursor.execute("SELECT COUNT(*) FROM variants WHERE gene_id = ?", (gene_id,))
    variant_count = cursor.fetchone()[0]

    if variant_count == 0:
        issues.append(f"No variants found for {gene_symbol}")
        return False, issues

    if variant_count < MIN_VARIANTS_PER_GENE:
        issues.append(
            f"Low variant count: {variant_count} (expected >= {MIN_VARIANTS_PER_GENE})"
        )

    # Validate variant data quality
    cursor.execute(
        """
        SELECT rsid, allele_name, function, activity_score
        FROM variants
        WHERE gene_id = ?
    """,
        (gene_id,),
    )

    invalid_variants = 0
    for rsid, allele, function, activity_score in cursor.fetchall():
        # Check rsID format
        if not rsid or rsid == "-":
            invalid_variants += 1
            continue

        # Check allele name
        if not allele or allele == "-":
            invalid_variants += 1
            continue

        # Check function
        if not function or function == "-":
            invalid_variants += 1
            continue

        # Check activity score range
        if activity_score < 0.0 or activity_score > 2.0:
            issues.append(f"Invalid activity score for {rsid}: {activity_score}")

    if invalid_variants > 0:
        issues.append(f"Found {invalid_variants} invalid variants")

    return len(issues) == 0, issues


def validate_gene_phenotypes(
    conn: sqlite3.Connection, gene_symbol: str
) -> Tuple[bool, List[str]]:
    """Validate phenotypes for a gene."""
    issues = []
    cursor = conn.cursor()

    # Get gene_id
    cursor.execute("SELECT gene_id FROM genes WHERE gene_symbol = ?", (gene_symbol,))
    row = cursor.fetchone()
    if not row:
        issues.append(f"Gene {gene_symbol} not found")
        return False, issues

    gene_id = row[0]

    # Check phenotype count
    cursor.execute("SELECT COUNT(*) FROM phenotypes WHERE gene_id = ?", (gene_id,))
    phenotype_count = cursor.fetchone()[0]

    if phenotype_count == 0:
        issues.append(f"No phenotypes found for {gene_symbol}")
        return False, issues

    if phenotype_count < MIN_PHENOTYPES_PER_GENE:
        issues.append(
            f"Low phenotype count: {phenotype_count} (expected >= {MIN_PHENOTYPES_PER_GENE})"
        )

    # Validate phenotype data quality
    cursor.execute(
        """
        SELECT diplotype, phenotype_display, phenotype_normalized
        FROM phenotypes
        WHERE gene_id = ?
    """,
        (gene_id,),
    )

    invalid_phenotypes = 0
    for diplotype, display, normalized in cursor.fetchall():
        # Check diplotype format
        if not diplotype or diplotype == "-":
            invalid_phenotypes += 1
            continue

        # Check phenotype display
        if not display or display == "-":
            invalid_phenotypes += 1
            continue

        # Check phenotype normalized
        if not normalized or normalized == "-":
            invalid_phenotypes += 1
            continue

    if invalid_phenotypes > 0:
        issues.append(f"Found {invalid_phenotypes} invalid phenotypes")

    return len(issues) == 0, issues


def validate_gene(conn: sqlite3.Connection, gene_symbol: str) -> Dict:
    """Validate all aspects of a gene."""
    logger.info(f"\n{'='*60}")
    logger.info(f"Validating {gene_symbol}...")
    logger.info(f"{'='*60}")

    results = {
        "gene": gene_symbol,
        "valid": True,
        "issues": [],
        "warnings": [],
        "stats": {},
    }

    # Validate metadata
    valid, issues = validate_gene_metadata(conn, gene_symbol)
    if not valid:
        results["valid"] = False
        results["issues"].extend(issues)

    # Validate variants
    valid, issues = validate_gene_variants(conn, gene_symbol)
    if not valid:
        results["valid"] = False
        results["issues"].extend(issues)
    else:
        results["warnings"].extend(issues)  # Warnings, not errors

    # Validate phenotypes
    valid, issues = validate_gene_phenotypes(conn, gene_symbol)
    if not valid:
        results["valid"] = False
        results["issues"].extend(issues)
    else:
        results["warnings"].extend(issues)  # Warnings, not errors

    # Get statistics
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT 
            (SELECT COUNT(*) FROM variants WHERE gene_id = (SELECT gene_id FROM genes WHERE gene_symbol = ?)) as variant_count,
            (SELECT COUNT(*) FROM phenotypes WHERE gene_id = (SELECT gene_id FROM genes WHERE gene_symbol = ?)) as phenotype_count
    """,
        (gene_symbol, gene_symbol),
    )

    row = cursor.fetchone()
    if row:
        results["stats"] = {"variants": row[0], "phenotypes": row[1]}

    # Print results
    if results["valid"]:
        logger.info(f"✓ {gene_symbol} validation PASSED")
        logger.info(f"  Variants: {results['stats']['variants']}")
        logger.info(f"  Phenotypes: {results['stats']['phenotypes']}")
        if results["warnings"]:
            logger.warning(f"  Warnings: {len(results['warnings'])}")
            for warning in results["warnings"]:
                logger.warning(f"    - {warning}")
    else:
        logger.error(f"✗ {gene_symbol} validation FAILED")
        logger.error(f"  Issues: {len(results['issues'])}")
        for issue in results["issues"]:
            logger.error(f"    - {issue}")

    return results


def list_genes_by_tier(conn: sqlite3.Connection, tier: int) -> List[str]:
    """List all genes for a specific tier."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT gene_symbol FROM genes WHERE tier = ? ORDER BY gene_symbol", (tier,)
    )
    return [row[0] for row in cursor.fetchall()]


def list_all_genes(conn: sqlite3.Connection) -> List[str]:
    """List all genes in database."""
    cursor = conn.cursor()
    cursor.execute("SELECT gene_symbol FROM genes ORDER BY gene_symbol")
    return [row[0] for row in cursor.fetchall()]


def main():
    parser = argparse.ArgumentParser(
        description="Validate pharmacogene database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/validate_pgx_data.py --gene CYP3A4    # Validate single gene
  python scripts/validate_pgx_data.py --tier 1         # Validate Tier 1 genes
  python scripts/validate_pgx_data.py --all            # Validate all genes
        """,
    )
    parser.add_argument(
        "--gene", type=str, help="Validate specific gene (e.g., CYP3A4)"
    )
    parser.add_argument(
        "--tier", type=int, choices=[1, 2, 3], help="Validate all genes in tier"
    )
    parser.add_argument("--all", action="store_true", help="Validate all genes")

    args = parser.parse_args()

    if not any([args.gene, args.tier, args.all]):
        parser.print_help()
        print("\n❌ Error: Must specify --gene, --tier, or --all")
        sys.exit(1)

    # Connect to database
    conn = get_connection()

    # Determine genes to validate
    genes_to_validate = []
    if args.gene:
        genes_to_validate = [args.gene.upper()]
    elif args.tier:
        genes_to_validate = list_genes_by_tier(conn, args.tier)
        logger.info(f"Found {len(genes_to_validate)} genes in Tier {args.tier}")
    elif args.all:
        genes_to_validate = list_all_genes(conn)
        logger.info(f"Found {len(genes_to_validate)} genes total")

    # Validate each gene
    results = []
    for gene in genes_to_validate:
        result = validate_gene(conn, gene)
        results.append(result)

    conn.close()

    # Summary
    passed = sum(1 for r in results if r["valid"])
    failed = len(results) - passed
    total_issues = sum(len(r["issues"]) for r in results)
    total_warnings = sum(len(r["warnings"]) for r in results)

    print(f"\n{'='*60}")
    print(f"VALIDATION SUMMARY")
    print(f"{'='*60}")
    print(f"Total genes: {len(results)}")
    print(f"✓ Passed: {passed}")
    if failed > 0:
        print(f"✗ Failed: {failed}")
    if total_issues > 0:
        print(f"⚠ Total issues: {total_issues}")
    if total_warnings > 0:
        print(f"⚠ Total warnings: {total_warnings}")
    print(f"{'='*60}\n")

    # Exit with error code if any validation failed
    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
