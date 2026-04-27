#!/usr/bin/env python3
"""
Initialize Pharmacogenes Database

Creates and populates the pharmacogenes.db SQLite database with gene panel data.
Supports Tier 1 (critical), Tier 2 (standard), and Tier 3 (research) genes.

Usage:
    python scripts/init_gene_database.py --tier 1     # Load Tier 1 genes only
    python scripts/init_gene_database.py --tier 2     # Load Tier 2 genes only
    python scripts/init_gene_database.py --all        # Load all genes
    python scripts/init_gene_database.py --status     # Check database status
"""

import argparse
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Database path
DB_PATH = Path(__file__).parent.parent / "data" / "pgx" / "pharmacogenes.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"

# Tier 1 Genes (Critical - Immediate Implementation)
TIER_1_GENES = [
    # Current genes (already implemented)
    ("CYP2D6", "22", 42522500, 42530900, 1, "GRCh37"),
    ("CYP2C19", "10", 96535040, 96625463, 1, "GRCh37"),
    ("CYP2C9", "10", 96698415, 96749147, 1, "GRCh37"),
    ("UGT1A1", "2", 234668875, 234689625, 1, "GRCh37"),
    ("SLCO1B1", "12", 21288593, 21397223, 1, "GRCh37"),
    ("VKORC1", "16", 31102163, 31107800, 1, "GRCh37"),
    ("TPMT", "6", 18128542, 18155374, 1, "GRCh37"),
    ("DPYD", "1", 97543299, 97883432, 1, "GRCh37"),
    # New critical genes (high priority expansion)
    ("CYP3A4", "7", 99376140, 99391055, 1, "GRCh37"),
    ("CYP3A5", "7", 99245913, 99277621, 1, "GRCh37"),
    ("CYP1A2", "15", 75041185, 75048543, 1, "GRCh37"),
    ("CYP2B6", "19", 41497204, 41524792, 1, "GRCh37"),
    ("NAT2", "8", 18248755, 18258723, 1, "GRCh37"),
    ("GSTM1", "1", 110230414, 110237831, 1, "GRCh37"),
    ("GSTT1", "22", 24376190, 24384284, 1, "GRCh37"),
]

# Tier 2 Genes (Standard - Next Phase)
TIER_2_GENES = [
    # Phase II Enzymes
    ("SULT1A1", "16", 28618915, 28622326, 2, "GRCh37"),
    ("UGT2B7", "4", 69047683, 69115280, 2, "GRCh37"),
    ("UGT2B15", "4", 69409283, 69429283, 2, "GRCh37"),
    # Transporters
    ("ABCB1", "7", 87133179, 87342639, 2, "GRCh37"),  # MDR1/P-glycoprotein
    ("ABCG2", "4", 89011416, 89152474, 2, "GRCh37"),  # BCRP
    ("SLC22A1", "6", 160679018, 160735093, 2, "GRCh37"),  # OCT1
    ("SLC22A2", "6", 160680149, 160726509, 2, "GRCh37"),  # OCT2
    ("SLCO1B3", "12", 21331549, 21386289, 2, "GRCh37"),
    # Additional CYPs
    ("CYP2E1", "10", 135340880, 135352893, 2, "GRCh37"),
    ("CYP2J2", "1", 60388626, 60428626, 2, "GRCh37"),
    # Cardiovascular
    ("ADRB1", "10", 115803056, 115806056, 2, "GRCh37"),
    ("ADRB2", "5", 148206156, 148208156, 2, "GRCh37"),
    ("ACE", "17", 61554422, 61575822, 2, "GRCh37"),
    # Oncology
    ("TYMS", "18", 657603, 673603, 2, "GRCh37"),
    ("MTHFR", "1", 11845780, 11866780, 2, "GRCh37"),
    ("ERCC1", "19", 45919478, 45935478, 2, "GRCh37"),
]

# Tier 3 Genes (Research - Future)
TIER_3_GENES = [
    # Psychiatry
    ("HTR2A", "13", 47471478, 47534478, 3, "GRCh37"),
    ("HTR2C", "X", 114086491, 114322491, 3, "GRCh37"),
    ("DRD2", "11", 113280317, 113346317, 3, "GRCh37"),
    # Pain Management
    ("OPRM1", "6", 154039662, 154158662, 3, "GRCh37"),
    ("COMT", "22", 19929263, 19957263, 3, "GRCh37"),
    # Coagulation
    ("F2", "11", 46739505, 46761505, 3, "GRCh37"),
    ("F5", "1", 169511148, 169589148, 3, "GRCh37"),
    ("F7", "13", 113759888, 113779888, 3, "GRCh37"),
]


def create_database():
    """Create database and initialize schema."""
    # Ensure directory exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Check if schema file exists
    if not SCHEMA_PATH.exists():
        print(f"❌ Error: Schema file not found: {SCHEMA_PATH}")
        sys.exit(1)

    # Read schema
    with open(SCHEMA_PATH, "r") as f:
        schema_sql = f.read()

    # Create database
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(schema_sql)
    conn.commit()

    print(f"✅ Database created: {DB_PATH}")
    print(f"✅ Schema initialized from: {SCHEMA_PATH}")

    return conn


def load_genes(conn, tier=None, all_tiers=False):
    """Load genes into database."""
    genes_to_load = []

    if all_tiers:
        genes_to_load = TIER_1_GENES + TIER_2_GENES + TIER_3_GENES
        print("📊 Loading all tiers (1, 2, 3)...")
    elif tier == 1:
        genes_to_load = TIER_1_GENES
        print("📊 Loading Tier 1 genes (critical)...")
    elif tier == 2:
        genes_to_load = TIER_2_GENES
        print("📊 Loading Tier 2 genes (standard)...")
    elif tier == 3:
        genes_to_load = TIER_3_GENES
        print("📊 Loading Tier 3 genes (research)...")
    else:
        print("❌ Error: Invalid tier. Use --tier 1, --tier 2, --tier 3, or --all")
        sys.exit(1)

    cursor = conn.cursor()
    loaded_count = 0
    skipped_count = 0

    for gene_symbol, chrom, start, end, tier_num, build in genes_to_load:
        try:
            cursor.execute(
                """
                INSERT INTO genes (gene_symbol, chromosome, start_pos, end_pos, tier, build)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (gene_symbol, chrom, start, end, tier_num, build),
            )
            loaded_count += 1
            print(f"  ✓ {gene_symbol} (chr{chrom}, tier {tier_num})")
        except sqlite3.IntegrityError:
            skipped_count += 1
            print(f"  ⊘ {gene_symbol} (already exists)")

    conn.commit()

    print(f"\n✅ Loaded {loaded_count} genes")
    if skipped_count > 0:
        print(f"⊘ Skipped {skipped_count} genes (already in database)")

    # Record data version
    cursor.execute(
        """
        INSERT INTO data_versions (source, version, record_count)
        VALUES ('GenePanel', ?, ?)
    """,
        (datetime.now().strftime("%Y-%m-%d"), loaded_count),
    )
    conn.commit()


def show_status(conn):
    """Show database status."""
    cursor = conn.cursor()

    print("\n" + "=" * 60)
    print("DATABASE STATUS")
    print("=" * 60)

    # Database info
    cursor.execute("SELECT value FROM metadata WHERE key = 'schema_version'")
    schema_version = cursor.fetchone()[0]
    print(f"\n📊 Schema Version: {schema_version}")
    print(f"📁 Database Path: {DB_PATH}")
    print(f"💾 Database Size: {DB_PATH.stat().st_size / 1024:.1f} KB")

    # Gene counts by tier
    print("\n🧬 Gene Counts by Tier:")
    cursor.execute("""
        SELECT tier, COUNT(*) as count
        FROM genes
        GROUP BY tier
        ORDER BY tier
    """)
    for tier, count in cursor.fetchall():
        tier_name = {1: "Critical", 2: "Standard", 3: "Research"}.get(tier, "Unknown")
        print(f"  Tier {tier} ({tier_name}): {count} genes")

    # Total counts
    cursor.execute("SELECT COUNT(*) FROM genes")
    total_genes = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM variants")
    total_variants = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM phenotypes")
    total_phenotypes = cursor.fetchone()[0]

    print(f"\n📈 Total Statistics:")
    print(f"  Genes: {total_genes}")
    print(f"  Variants: {total_variants}")
    print(f"  Phenotypes: {total_phenotypes}")

    # Recent genes
    print(f"\n🔬 Recently Added Genes:")
    cursor.execute("""
        SELECT gene_symbol, chromosome, tier
        FROM genes
        ORDER BY last_updated DESC
        LIMIT 5
    """)
    for gene, chrom, tier in cursor.fetchall():
        print(f"  {gene} (chr{chrom}, tier {tier})")

    # Data versions
    print(f"\n📅 Data Versions:")
    cursor.execute("""
        SELECT source, version, download_date, record_count
        FROM data_versions
        ORDER BY download_date DESC
        LIMIT 5
    """)
    for source, version, date, count in cursor.fetchall():
        print(f"  {source} v{version} ({date}): {count} records")

    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Initialize Pharmacogenes Database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/init_gene_database.py --tier 1     # Load Tier 1 genes
  python scripts/init_gene_database.py --all        # Load all genes
  python scripts/init_gene_database.py --status     # Check status
        """,
    )
    parser.add_argument(
        "--tier",
        type=int,
        choices=[1, 2, 3],
        help="Load specific tier (1=critical, 2=standard, 3=research)",
    )
    parser.add_argument("--all", action="store_true", help="Load all tiers")
    parser.add_argument("--status", action="store_true", help="Show database status")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force recreate database (WARNING: deletes existing data)",
    )

    args = parser.parse_args()

    # Check if database exists
    db_exists = DB_PATH.exists()

    if args.force and db_exists:
        print(f"⚠️  WARNING: Deleting existing database: {DB_PATH}")
        DB_PATH.unlink()
        db_exists = False

    # Create or connect to database
    if not db_exists:
        print("🔨 Creating new database...")
        conn = create_database()
    else:
        print(f"📂 Connecting to existing database: {DB_PATH}")
        conn = sqlite3.connect(DB_PATH)

    # Execute requested action
    if args.status:
        show_status(conn)
    elif args.tier or args.all:
        load_genes(conn, tier=args.tier, all_tiers=args.all)
        show_status(conn)
    else:
        parser.print_help()
        print("\n❌ Error: Must specify --tier, --all, or --status")
        sys.exit(1)

    conn.close()
    print("\n✅ Done!")


if __name__ == "__main__":
    main()
