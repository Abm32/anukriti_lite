#!/usr/bin/env python3
"""
PharmVar Data Synchronization

Automated synchronization of PharmVar allele definitions to database.
Downloads allele definition files and populates the variants table.

Usage:
    python scripts/pharmvar_sync.py --gene CYP3A4      # Sync single gene
    python scripts/pharmvar_sync.py --tier 1           # Sync all Tier 1 genes
    python scripts/pharmvar_sync.py --all              # Sync all genes
"""

import argparse
import io
import json
import logging
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Paths
DB_PATH = Path(__file__).parent.parent / "data" / "pgx" / "pharmacogenes.db"
PHARMVAR_BASE = "https://www.pharmvar.org"

# Function mapping for activity scores
FUNCTION_TO_SCORE = {
    "Normal function": 1.0,
    "Normal Function": 1.0,
    "Increased function": 1.5,
    "Increased Function": 1.5,
    "Reduced function": 0.5,
    "Reduced Function": 0.5,
    "Decreased function": 0.5,
    "Decreased Function": 0.5,
    "No function": 0.0,
    "No Function": 0.0,
    "Loss of function": 0.0,
    "Loss of Function": 0.0,
    "Unknown function": 0.5,  # Conservative default
    "Unknown Function": 0.5,
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


def download_pharmvar_alleles(gene_symbol: str) -> Optional[pd.DataFrame]:
    """
    Download PharmVar allele definitions for a gene.

    Note: PharmVar doesn't have a stable public API, so this is a best-effort
    implementation that may need updates if their website structure changes.

    For production, consider:
    1. Manual downloads from https://www.pharmvar.org/download
    2. Local TSV files in data/pgx/pharmvar/
    3. Periodic manual updates
    """
    logger.info(f"Attempting to download PharmVar data for {gene_symbol}...")

    # Try direct download URL pattern (may not work for all genes)
    gene_lower = gene_symbol.lower()
    download_url = f"{PHARMVAR_BASE}/download/{gene_lower}_alleles.tsv"

    try:
        response = requests.get(download_url, timeout=30)
        response.raise_for_status()

        # Parse TSV
        df = pd.read_csv(io.StringIO(response.text), sep="\t", comment="#", dtype=str)

        # Standardize column names (PharmVar format may vary)
        column_mapping = {
            "Allele": "allele",
            "allele": "allele",
            "Star Allele": "allele",
            "rsID": "rsid",
            "rsid": "rsid",
            "RS ID": "rsid",
            "Alt": "alt",
            "alt": "alt",
            "ALT": "alt",
            "Function": "function",
            "function": "function",
            "Activity": "function",
        }

        df = df.rename(columns=column_mapping)

        # Ensure required columns exist
        required_cols = ["allele", "rsid", "alt", "function"]
        missing_cols = [col for col in required_cols if col not in df.columns]

        if missing_cols:
            logger.warning(f"Missing columns in PharmVar data: {missing_cols}")
            return None

        # Map function to activity score
        df["activity_score"] = df["function"].map(FUNCTION_TO_SCORE)
        df["activity_score"] = df["activity_score"].fillna(0.5)  # Default for unknown

        logger.info(f"✓ Downloaded {len(df)} variants for {gene_symbol}")
        return df

    except requests.RequestException as e:
        logger.warning(f"Could not download from PharmVar: {e}")
        logger.info(f"Falling back to local TSV file...")
        return load_local_pharmvar_file(gene_symbol)
    except Exception as e:
        logger.error(f"Error parsing PharmVar data: {e}")
        return None


def load_local_pharmvar_file(gene_symbol: str) -> Optional[pd.DataFrame]:
    """Load PharmVar data from local TSV file."""
    gene_lower = gene_symbol.lower()
    local_path = (
        Path(__file__).parent.parent
        / "data"
        / "pgx"
        / "pharmvar"
        / f"{gene_lower}_alleles.tsv"
    )

    if not local_path.exists():
        logger.warning(f"Local file not found: {local_path}")
        return None

    try:
        df = pd.read_csv(local_path, sep="\t", comment="#", dtype=str)

        # Standardize columns
        column_mapping = {
            "Allele": "allele",
            "rsID": "rsid",
            "Alt": "alt",
            "Function": "function",
        }
        df = df.rename(columns=column_mapping)

        # Map function to activity score
        df["activity_score"] = df["function"].map(FUNCTION_TO_SCORE)
        df["activity_score"] = df["activity_score"].fillna(0.5)

        logger.info(f"✓ Loaded {len(df)} variants from local file")
        return df

    except Exception as e:
        logger.error(f"Error loading local file: {e}")
        return None


def sync_gene_to_database(
    gene_symbol: str, conn: sqlite3.Connection, force: bool = False
) -> bool:
    """Sync PharmVar data for a gene to database."""
    logger.info(f"\n{'='*60}")
    logger.info(f"Syncing {gene_symbol}...")
    logger.info(f"{'='*60}")

    # Get gene_id
    gene_id = get_gene_id(conn, gene_symbol)
    if not gene_id:
        logger.error(f"Gene {gene_symbol} not found in database")
        return False

    # Check if already synced
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM variants WHERE gene_id = ?", (gene_id,))
    existing_count = cursor.fetchone()[0]

    if existing_count > 0 and not force:
        logger.info(
            f"⊘ {gene_symbol} already has {existing_count} variants (use --force to re-sync)"
        )
        return True

    # Download data
    df = download_pharmvar_alleles(gene_symbol)
    if df is None or df.empty:
        logger.error(f"✗ No data available for {gene_symbol}")
        return False

    # Get chromosome from genes table
    cursor.execute("SELECT chromosome FROM genes WHERE gene_id = ?", (gene_id,))
    chromosome = cursor.fetchone()[0]

    # Delete existing variants if force
    if force and existing_count > 0:
        cursor.execute("DELETE FROM variants WHERE gene_id = ?", (gene_id,))
        logger.info(f"Deleted {existing_count} existing variants")

    # Insert variants
    inserted = 0
    skipped = 0

    for _, row in df.iterrows():
        rsid = str(row.get("rsid", "")).strip()
        allele = str(row.get("allele", "")).strip()
        alt = str(row.get("alt", "")).strip()
        function = str(row.get("function", "")).strip()
        activity_score = float(row.get("activity_score", 0.5))

        # Skip invalid rows
        if not rsid or rsid == "-" or not allele or allele == "-":
            skipped += 1
            continue

        # Ensure allele starts with *
        if not allele.startswith("*"):
            allele = f"*{allele}"

        try:
            cursor.execute(
                """
                INSERT INTO variants 
                (gene_id, rsid, chromosome, position, ref_allele, alt_allele, 
                 allele_name, function, activity_score, pharmvar_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    gene_id,
                    rsid,
                    chromosome,
                    0,  # position=0 (will be updated later)
                    "N",
                    alt,  # ref_allele="N" (placeholder)
                    allele,
                    function,
                    activity_score,
                    datetime.now().strftime("%Y-%m"),
                ),
            )
            inserted += 1
        except sqlite3.IntegrityError as e:
            logger.debug(f"Skipped duplicate: {rsid} {allele}")
            skipped += 1

    conn.commit()

    # Record data version
    cursor.execute(
        """
        INSERT INTO data_versions (source, version, record_count)
        VALUES (?, ?, ?)
    """,
        (f"PharmVar_{gene_symbol}", datetime.now().strftime("%Y-%m"), inserted),
    )
    conn.commit()

    logger.info(f"✓ Inserted {inserted} variants")
    if skipped > 0:
        logger.info(f"⊘ Skipped {skipped} variants (invalid or duplicate)")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Sync PharmVar allele definitions to database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/pharmvar_sync.py --gene CYP3A4    # Sync single gene
  python scripts/pharmvar_sync.py --tier 1         # Sync Tier 1 genes
  python scripts/pharmvar_sync.py --all            # Sync all genes
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
    print(f"SYNC COMPLETE")
    print(f"{'='*60}")
    print(f"✓ Success: {success_count} genes")
    if fail_count > 0:
        print(f"✗ Failed: {fail_count} genes")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
