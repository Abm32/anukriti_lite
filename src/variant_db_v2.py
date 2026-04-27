"""
Database-backed Pharmacogenomic Variants Module (v2)

Replaces hardcoded VARIANT_DB dictionary with SQLite database backend
for scalable 100+ gene panel support. Provides backward-compatible API
with sub-100ms query performance.

Migration Path:
- Phase 1: Parallel implementation (this module + variant_db.py)
- Phase 2: Update callers to try DB first, fallback to TSV
- Phase 3: Deprecate variant_db.py hardcoded dict

Database Schema:
- genes: gene metadata (symbol, chromosome, position, tier)
- variants: rsID → allele, function, activity score
- phenotypes: diplotype → phenotype translations
- drug_gene_pairs: drug-gene interaction mappings
"""

import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Default database path (repo-relative)
DEFAULT_DB_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "pgx" / "pharmacogenes.db"
)

# Singleton connection (thread-safe for read-only operations)
_db_connection: Optional[sqlite3.Connection] = None


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """
    Get singleton database connection.

    Args:
        db_path: Optional path to database file (defaults to DEFAULT_DB_PATH)

    Returns:
        SQLite connection object

    Raises:
        FileNotFoundError: If database file doesn't exist
    """
    global _db_connection

    if _db_connection is not None:
        return _db_connection

    path = db_path or DEFAULT_DB_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"Pharmacogenes database not found: {path}. "
            f"Run: python scripts/init_gene_database.py --tier 1"
        )

    # Read-only connection for safety (multiple processes can read simultaneously)
    _db_connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    _db_connection.row_factory = sqlite3.Row  # Access columns by name

    logger.info(f"Connected to pharmacogenes database: {path}")
    return _db_connection


def get_gene_variants(
    gene_symbol: str, db_path: Optional[Path] = None
) -> Dict[str, Dict[str, Any]]:
    """
    Get all variants for a gene in VARIANT_DB-compatible format.

    Args:
        gene_symbol: Gene symbol (e.g., "CYP2D6", "CYP2C19")
        db_path: Optional path to database file

    Returns:
        Dictionary mapping rsID to variant info:
        {
            "rs3892097": {
                "allele": "*4",
                "impact": "Null",
                "name": "Splicing Defect (1846G>A)",
                "activity_score": 0.0
            },
            ...
        }

    Example:
        >>> variants = get_gene_variants("CYP2D6")
        >>> print(variants["rs3892097"]["allele"])
        *4
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # Query variants for this gene
    cursor.execute(
        """
        SELECT rsid, allele_name, function, activity_score,
               ref_allele, alt_allele, position
        FROM variants
        WHERE gene_id = (SELECT gene_id FROM genes WHERE gene_symbol = ?)
        ORDER BY rsid
    """,
        (gene_symbol,),
    )

    variants = {}
    for row in cursor.fetchall():
        rsid = row["rsid"]
        # Build variant name from position and alleles
        variant_name = f"{row['ref_allele']}>{row['alt_allele']}"
        variants[rsid] = {
            "allele": row["allele_name"],
            "impact": row["function"],  # "Null", "Reduced", "Normal", "Increased"
            "name": variant_name,
            "activity_score": float(row["activity_score"]),
        }

    # Add structural variants (gene deletion/duplication)
    # These use special keys like "CYP2D6_DEL", "CYP2D6_DUP"
    cursor.execute(
        """
        SELECT allele_name, function, activity_score
        FROM variants
        WHERE gene_id = (SELECT gene_id FROM genes WHERE gene_symbol = ?)
        AND (rsid LIKE '%_DEL' OR rsid LIKE '%_DUP')
    """,
        (gene_symbol,),
    )

    for row in cursor.fetchall():
        if "_DEL" in row["allele_name"]:
            key = f"{gene_symbol}_DEL"
            variants[key] = {
                "allele": row["allele_name"],
                "impact": "Null",
                "name": "Gene Deletion",
                "activity_score": 0.0,
            }
        elif "_DUP" in row["allele_name"] or "xN" in row["allele_name"]:
            key = f"{gene_symbol}_DUP"
            variants[key] = {
                "allele": row["allele_name"],
                "impact": "Increased",
                "name": "Gene Duplication",
                "activity_score": 1.0,
            }

    return variants


def get_phenotype_translation(
    gene_symbol: str, db_path: Optional[Path] = None
) -> Dict[str, str]:
    """
    Get diplotype → phenotype translation map for a gene.

    Args:
        gene_symbol: Gene symbol (e.g., "CYP2C19")
        db_path: Optional path to database file

    Returns:
        Dictionary mapping diplotype to phenotype display string:
        {
            "*1/*1": "Normal Metabolizer",
            "*1/*2": "Intermediate Metabolizer",
            "*2/*2": "Poor Metabolizer",
            ...
        }

    Example:
        >>> translations = get_phenotype_translation("CYP2C19")
        >>> print(translations["*1/*2"])
        Intermediate Metabolizer
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT diplotype, phenotype_display
        FROM phenotypes
        WHERE gene_id = (SELECT gene_id FROM genes WHERE gene_symbol = ?)
        ORDER BY diplotype
    """,
        (gene_symbol,),
    )

    translations = {}
    for row in cursor.fetchall():
        translations[row["diplotype"]] = row["phenotype_display"]

    return translations


def get_gene_location(
    gene_symbol: str, build: str = "GRCh37", db_path: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    """
    Get genomic location for a gene.

    Args:
        gene_symbol: Gene symbol (e.g., "CYP2D6")
        build: Genome build ("GRCh37" or "GRCh38")
        db_path: Optional path to database file

    Returns:
        Dictionary with chromosome and position:
        {
            "chrom": "22",
            "start": 42522500,
            "end": 42530900
        }
        Returns None if gene not found.

    Example:
        >>> location = get_gene_location("CYP2D6", "GRCh37")
        >>> print(f"chr{location['chrom']}:{location['start']}-{location['end']}")
        chr22:42522500-42530900
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT chromosome, start_pos, end_pos
        FROM genes
        WHERE gene_symbol = ? AND build = ?
    """,
        (gene_symbol, build),
    )

    row = cursor.fetchone()
    if not row:
        return None

    return {
        "chrom": row["chromosome"],
        "start": row["start_pos"],
        "end": row["end_pos"],
    }


def list_supported_genes(
    tier: Optional[int] = None, db_path: Optional[Path] = None
) -> List[str]:
    """
    List all supported genes, optionally filtered by tier.

    Args:
        tier: Optional tier filter (1, 2, or 3)
        db_path: Optional path to database file

    Returns:
        List of gene symbols sorted alphabetically

    Example:
        >>> tier1_genes = list_supported_genes(tier=1)
        >>> print(tier1_genes)
        ['CYP1A2', 'CYP2B6', 'CYP2C19', 'CYP2C9', 'CYP2D6', ...]
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()

    if tier is not None:
        cursor.execute(
            """
            SELECT DISTINCT gene_symbol
            FROM genes
            WHERE tier = ?
            ORDER BY gene_symbol
        """,
            (tier,),
        )
    else:
        cursor.execute("""
            SELECT DISTINCT gene_symbol
            FROM genes
            ORDER BY gene_symbol
        """)

    return [row["gene_symbol"] for row in cursor.fetchall()]


def get_gene_info(
    gene_symbol: str, db_path: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    """
    Get complete gene information including metadata.

    Args:
        gene_symbol: Gene symbol (e.g., "CYP2D6")
        db_path: Optional path to database file

    Returns:
        Dictionary with gene metadata:
        {
            "gene_id": 1,
            "gene_symbol": "CYP2D6",
            "chromosome": "22",
            "start_pos": 42522500,
            "end_pos": 42530900,
            "tier": 1,
            "build": "GRCh37",
            "variant_count": 12
        }
        Returns None if gene not found.
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            g.gene_id,
            g.gene_symbol,
            g.chromosome,
            g.start_pos,
            g.end_pos,
            g.tier,
            g.build,
            COUNT(v.variant_id) as variant_count
        FROM genes g
        LEFT JOIN variants v ON g.gene_id = v.gene_id
        WHERE g.gene_symbol = ?
        GROUP BY g.gene_id
    """,
        (gene_symbol,),
    )

    row = cursor.fetchone()
    if not row:
        return None

    return {
        "gene_id": row["gene_id"],
        "gene_symbol": row["gene_symbol"],
        "chromosome": row["chromosome"],
        "start_pos": row["start_pos"],
        "end_pos": row["end_pos"],
        "tier": row["tier"],
        "build": row["build"],
        "variant_count": row["variant_count"],
    }


def get_database_stats(db_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Get database statistics for monitoring and validation.

    Args:
        db_path: Optional path to database file

    Returns:
        Dictionary with database statistics:
        {
            "gene_count": 15,
            "variant_count": 180,
            "phenotype_count": 45,
            "tier1_genes": 15,
            "tier2_genes": 0,
            "tier3_genes": 0,
            "database_size_mb": 0.5
        }
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # Get counts
    cursor.execute("SELECT COUNT(*) as count FROM genes")
    gene_count = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM variants")
    variant_count = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM phenotypes")
    phenotype_count = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM genes WHERE tier = 1")
    tier1_count = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM genes WHERE tier = 2")
    tier2_count = cursor.fetchone()["count"]

    cursor.execute("SELECT COUNT(*) as count FROM genes WHERE tier = 3")
    tier3_count = cursor.fetchone()["count"]

    # Get database file size
    db_path = db_path or DEFAULT_DB_PATH
    db_size_mb = db_path.stat().st_size / (1024 * 1024) if db_path.exists() else 0

    return {
        "gene_count": gene_count,
        "variant_count": variant_count,
        "phenotype_count": phenotype_count,
        "tier1_genes": tier1_count,
        "tier2_genes": tier2_count,
        "tier3_genes": tier3_count,
        "database_size_mb": round(db_size_mb, 2),
    }


def close_connection():
    """Close the singleton database connection."""
    global _db_connection
    if _db_connection is not None:
        _db_connection.close()
        _db_connection = None
        logger.info("Closed pharmacogenes database connection")


# Backward compatibility: provide VARIANT_DB-style interface
def get_variant_db_for_gene(gene_symbol: str) -> Dict[str, Dict[str, Any]]:
    """
    Get VARIANT_DB-compatible dictionary for a gene.
    This is a convenience wrapper for backward compatibility.

    Args:
        gene_symbol: Gene symbol (e.g., "CYP2D6")

    Returns:
        VARIANT_DB-style dictionary for the gene
    """
    return get_gene_variants(gene_symbol)
