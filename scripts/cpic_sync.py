#!/usr/bin/env python3
"""
CPIC Phenotype Synchronization

Automated synchronization of CPIC phenotype translations to database.
Scrapes CPIC guidelines and populates the phenotypes table.

Usage:
    python scripts/cpic_sync.py --gene CYP3A4      # Sync single gene
    python scripts/cpic_sync.py --tier 1           # Sync all Tier 1 genes
    python scripts/cpic_sync.py --all              # Sync all genes
"""

import argparse
import json
import logging
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Paths
DB_PATH = Path(__file__).parent.parent / "data" / "pgx" / "pharmacogenes.db"
CPIC_BASE = "https://cpicpgx.org"

# Standard CPIC phenotype mappings (fallback when scraping fails)
STANDARD_PHENOTYPES = {
    "CYP2D6": {
        "*1/*1": "Normal Metabolizer",
        "*1/*2": "Normal Metabolizer",
        "*1/*4": "Intermediate Metabolizer",
        "*1/*5": "Intermediate Metabolizer",
        "*1/*10": "Intermediate Metabolizer",
        "*1/*17": "Intermediate Metabolizer",
        "*1/*41": "Intermediate Metabolizer",
        "*2/*2": "Normal Metabolizer",
        "*2/*4": "Intermediate Metabolizer",
        "*2/*5": "Intermediate Metabolizer",
        "*4/*4": "Poor Metabolizer",
        "*4/*5": "Poor Metabolizer",
        "*5/*5": "Poor Metabolizer",
        "*1/*1xN": "Ultrarapid Metabolizer",
        "*1/*2xN": "Ultrarapid Metabolizer",
        "*2/*2xN": "Ultrarapid Metabolizer",
    },
    "CYP2C19": {
        "*1/*1": "Normal Metabolizer",
        "*1/*2": "Intermediate Metabolizer",
        "*1/*3": "Intermediate Metabolizer",
        "*1/*17": "Rapid Metabolizer",
        "*2/*2": "Poor Metabolizer",
        "*2/*3": "Poor Metabolizer",
        "*17/*17": "Ultrarapid Metabolizer",
        "*1/*1xN": "Ultrarapid Metabolizer",
        "*17/*17xN": "Ultrarapid Metabolizer",
    },
    "CYP2C9": {
        "*1/*1": "Normal Metabolizer",
        "*1/*2": "Intermediate Metabolizer",
        "*1/*3": "Intermediate Metabolizer",
        "*2/*2": "Intermediate Metabolizer",
        "*2/*3": "Poor Metabolizer",
        "*3/*3": "Poor Metabolizer",
    },
    "CYP3A4": {
        "*1/*1": "Normal Metabolizer",
        "*1/*22": "Intermediate Metabolizer",
        "*22/*22": "Poor Metabolizer",
    },
    "CYP3A5": {
        "*1/*1": "Normal Metabolizer",
        "*1/*3": "Intermediate Metabolizer",
        "*3/*3": "Poor Metabolizer",
    },
    "CYP1A2": {
        "*1/*1": "Normal Metabolizer",
        "*1/*1C": "Rapid Metabolizer",
        "*1/*1F": "Rapid Metabolizer",
        "*1C/*1C": "Ultrarapid Metabolizer",
        "*1F/*1F": "Ultrarapid Metabolizer",
    },
    "CYP2B6": {
        "*1/*1": "Normal Metabolizer",
        "*1/*6": "Intermediate Metabolizer",
        "*6/*6": "Poor Metabolizer",
    },
    "NAT2": {
        "*4/*4": "Rapid Acetylator",
        "*4/*5": "Intermediate Acetylator",
        "*4/*6": "Intermediate Acetylator",
        "*5/*5": "Slow Acetylator",
        "*5/*6": "Slow Acetylator",
        "*6/*6": "Slow Acetylator",
    },
    "GSTM1": {
        "Present/Present": "Normal Function",
        "Present/Null": "Intermediate Function",
        "Null/Null": "No Function",
    },
    "GSTT1": {
        "Present/Present": "Normal Function",
        "Present/Null": "Intermediate Function",
        "Null/Null": "No Function",
    },
    "UGT1A1": {
        "*1/*1": "Normal Metabolizer",
        "*1/*28": "Intermediate Metabolizer",
        "*1/*80": "Intermediate Metabolizer",
        "*28/*28": "Poor Metabolizer",
        "*28/*80": "Poor Metabolizer",
        "*80/*80": "Poor Metabolizer",
    },
    "SLCO1B1": {
        "*1/*1": "Normal Function",
        "*1/*5": "Decreased Function",
        "*1/*15": "Decreased Function",
        "*5/*5": "Poor Function",
        "*5/*15": "Poor Function",
        "*15/*15": "Poor Function",
    },
    "VKORC1": {
        "GG": "Low Sensitivity",
        "GA": "Intermediate Sensitivity",
        "AA": "High Sensitivity",
    },
    "TPMT": {
        "*1/*1": "Normal Metabolizer",
        "*1/*2": "Intermediate Metabolizer",
        "*1/*3A": "Intermediate Metabolizer",
        "*1/*3C": "Intermediate Metabolizer",
        "*2/*2": "Poor Metabolizer",
        "*2/*3A": "Poor Metabolizer",
        "*3A/*3A": "Poor Metabolizer",
        "*3A/*3C": "Poor Metabolizer",
        "*3C/*3C": "Poor Metabolizer",
    },
    "DPYD": {
        "*1/*1": "Normal Metabolizer",
        "*1/*2A": "Intermediate Metabolizer",
        "*1/*13": "Intermediate Metabolizer",
        "*2A/*2A": "Poor Metabolizer",
        "*2A/*13": "Poor Metabolizer",
        "*13/*13": "Poor Metabolizer",
    },
}


def get_connection() -> sqlite3.Connection:
    """Get database connection."""
    if not DB_PATH.exists():
        logger.error(f"Database not found: {DB_PATH}")
        logger.error("Run: python scripts/init_gene_database.py --tier 1")
        sys.exit(1)
    return sqlite3.connect(DB_PATH)


def get_gene_id(conn: sqlite3.Connection, gene_symbol: str) -> Optional[int]:
    """Get gene_id for a gene symbol."""
    cursor = conn.cursor()
    cursor.execute("SELECT gene_id FROM genes WHERE gene_symbol = ?", (gene_symbol,))
    row = cursor.fetchone()
    return row[0] if row else None


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


def scrape_cpic_phenotypes(gene_symbol: str) -> Optional[Dict[str, str]]:
    """
    Attempt to scrape CPIC phenotype translations from cpicpgx.org.

    Note: CPIC website structure may change, so this is a best-effort implementation.
    Falls back to standard phenotypes if scraping fails.

    For production, consider:
    1. Manual downloads from https://cpicpgx.org/guidelines/
    2. Local JSON files in data/pgx/cpic/
    3. Periodic manual updates
    """
    logger.info(f"Attempting to scrape CPIC data for {gene_symbol}...")

    # Try CPIC gene page
    gene_lower = gene_symbol.lower()
    cpic_url = f"{CPIC_BASE}/genes/{gene_lower}/"

    try:
        response = requests.get(cpic_url, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Look for phenotype tables (structure varies by gene)
        phenotypes = {}
        tables = soup.find_all("table")

        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all(["td", "th"])
                if len(cells) >= 2:
                    # Try to extract diplotype → phenotype mappings
                    diplotype = cells[0].get_text().strip()
                    phenotype = cells[1].get_text().strip()

                    # Basic validation
                    if "*" in diplotype and (
                        "Metabolizer" in phenotype or "Function" in phenotype
                    ):
                        phenotypes[diplotype] = phenotype

        if phenotypes:
            logger.info(f"✓ Scraped {len(phenotypes)} phenotypes for {gene_symbol}")
            return phenotypes
        else:
            logger.warning(f"No phenotypes found in CPIC page for {gene_symbol}")
            return None

    except requests.RequestException as e:
        logger.warning(f"Could not scrape CPIC: {e}")
        return None
    except Exception as e:
        logger.error(f"Error parsing CPIC data: {e}")
        return None


def load_local_cpic_file(gene_symbol: str) -> Optional[Dict[str, str]]:
    """Load CPIC phenotypes from local JSON file."""
    gene_lower = gene_symbol.lower()
    local_path = (
        Path(__file__).parent.parent
        / "data"
        / "pgx"
        / "cpic"
        / f"{gene_lower}_phenotypes.json"
    )

    if not local_path.exists():
        logger.warning(f"Local file not found: {local_path}")
        return None

    try:
        with open(local_path, "r") as f:
            data = json.load(f)

        # Filter out metadata keys (starting with _)
        phenotypes = {k: v for k, v in data.items() if not k.startswith("_")}

        logger.info(f"✓ Loaded {len(phenotypes)} phenotypes from local file")
        return phenotypes

    except Exception as e:
        logger.error(f"Error loading local file: {e}")
        return None


def get_standard_phenotypes(gene_symbol: str) -> Optional[Dict[str, str]]:
    """Get standard CPIC phenotypes from hardcoded mappings."""
    phenotypes = STANDARD_PHENOTYPES.get(gene_symbol)
    if phenotypes:
        logger.info(f"✓ Using {len(phenotypes)} standard phenotypes for {gene_symbol}")
    return phenotypes


def sync_gene_to_database(
    gene_symbol: str, conn: sqlite3.Connection, force: bool = False
) -> bool:
    """Sync CPIC phenotypes for a gene to database."""
    logger.info(f"\n{'='*60}")
    logger.info(f"Syncing CPIC phenotypes for {gene_symbol}...")
    logger.info(f"{'='*60}")

    # Get gene_id
    gene_id = get_gene_id(conn, gene_symbol)
    if not gene_id:
        logger.error(f"Gene {gene_symbol} not found in database")
        return False

    # Check if already synced
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM phenotypes WHERE gene_id = ?", (gene_id,))
    existing_count = cursor.fetchone()[0]

    if existing_count > 0 and not force:
        logger.info(
            f"⊘ {gene_symbol} already has {existing_count} phenotypes (use --force to re-sync)"
        )
        return True

    # Try multiple sources in order: local file → scraping → standard mappings
    phenotypes = None

    # 1. Try local file first
    phenotypes = load_local_cpic_file(gene_symbol)

    # 2. Try scraping CPIC website
    if not phenotypes:
        phenotypes = scrape_cpic_phenotypes(gene_symbol)

    # 3. Fall back to standard mappings
    if not phenotypes:
        phenotypes = get_standard_phenotypes(gene_symbol)

    if not phenotypes:
        logger.error(f"✗ No phenotype data available for {gene_symbol}")
        return False

    # Delete existing phenotypes if force
    if force and existing_count > 0:
        cursor.execute("DELETE FROM phenotypes WHERE gene_id = ?", (gene_id,))
        logger.info(f"Deleted {existing_count} existing phenotypes")

    # Insert phenotypes
    inserted = 0
    skipped = 0

    for diplotype, phenotype_display in phenotypes.items():
        diplotype = diplotype.strip()
        phenotype_display = phenotype_display.strip()

        # Skip invalid entries
        if not diplotype or not phenotype_display:
            skipped += 1
            continue

        # Normalize phenotype for internal use
        phenotype_normalized = (
            phenotype_display.lower().replace(" ", "_").replace("-", "_")
        )

        try:
            cursor.execute(
                """
                INSERT INTO phenotypes 
                (gene_id, diplotype, phenotype_display, phenotype_normalized, cpic_version)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    gene_id,
                    diplotype,
                    phenotype_display,
                    phenotype_normalized,
                    datetime.now().strftime("%Y-%m"),
                ),
            )
            inserted += 1
        except sqlite3.IntegrityError as e:
            logger.debug(f"Skipped duplicate: {diplotype}")
            skipped += 1

    conn.commit()

    # Record data version
    cursor.execute(
        """
        INSERT INTO data_versions (source, version, record_count)
        VALUES (?, ?, ?)
    """,
        (f"CPIC_{gene_symbol}", datetime.now().strftime("%Y-%m"), inserted),
    )
    conn.commit()

    logger.info(f"✓ Inserted {inserted} phenotypes")
    if skipped > 0:
        logger.info(f"⊘ Skipped {skipped} phenotypes (invalid or duplicate)")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Sync CPIC phenotype translations to database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/cpic_sync.py --gene CYP3A4    # Sync single gene
  python scripts/cpic_sync.py --tier 1         # Sync Tier 1 genes
  python scripts/cpic_sync.py --all            # Sync all genes
        """,
    )
    parser.add_argument("--gene", type=str, help="Sync specific gene (e.g., CYP3A4)")
    parser.add_argument(
        "--tier", type=int, choices=[1, 2, 3], help="Sync all genes in tier"
    )
    parser.add_argument("--all", action="store_true", help="Sync all genes")
    parser.add_argument(
        "--force", action="store_true", help="Force re-sync (overwrite existing)"
    )

    args = parser.parse_args()

    if not any([args.gene, args.tier, args.all]):
        parser.print_help()
        print("\n❌ Error: Must specify --gene, --tier, or --all")
        sys.exit(1)

    # Connect to database
    conn = get_connection()

    # Determine genes to sync
    genes_to_sync = []
    if args.gene:
        genes_to_sync = [args.gene.upper()]
    elif args.tier:
        genes_to_sync = list_genes_by_tier(conn, args.tier)
        logger.info(f"Found {len(genes_to_sync)} genes in Tier {args.tier}")
    elif args.all:
        genes_to_sync = list_all_genes(conn)
        logger.info(f"Found {len(genes_to_sync)} genes total")

    # Sync each gene
    success_count = 0
    fail_count = 0

    for gene in genes_to_sync:
        if sync_gene_to_database(gene, conn, force=args.force):
            success_count += 1
        else:
            fail_count += 1

    conn.close()

    # Summary
    print(f"\n{'='*60}")
    print(f"CPIC SYNC COMPLETE")
    print(f"{'='*60}")
    print(f"✓ Success: {success_count} genes")
    if fail_count > 0:
        print(f"✗ Failed: {fail_count} genes")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
