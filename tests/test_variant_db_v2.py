"""
Unit tests for database-backed variant lookup (variant_db_v2.py)

Tests database backend functionality for 100+ gene panel support.
"""

import sqlite3
import tempfile
from pathlib import Path

import pytest

from src.variant_db_v2 import (
    close_connection,
    get_connection,
    get_database_stats,
    get_gene_info,
    get_gene_location,
    get_gene_variants,
    get_phenotype_translation,
    list_supported_genes,
)


@pytest.fixture
def temp_db():
    """Create a temporary test database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    # Create test database schema
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create tables
    cursor.execute("""
        CREATE TABLE genes (
            gene_id INTEGER PRIMARY KEY AUTOINCREMENT,
            gene_symbol TEXT NOT NULL,
            chromosome TEXT NOT NULL,
            start_pos INTEGER NOT NULL,
            end_pos INTEGER NOT NULL,
            tier INTEGER NOT NULL DEFAULT 1,
            build TEXT NOT NULL DEFAULT 'GRCh37',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE variants (
            variant_id INTEGER PRIMARY KEY AUTOINCREMENT,
            gene_id INTEGER NOT NULL,
            rsid TEXT NOT NULL,
            chromosome TEXT NOT NULL,
            position INTEGER NOT NULL,
            ref_allele TEXT NOT NULL,
            alt_allele TEXT NOT NULL,
            allele_name TEXT NOT NULL,
            function TEXT NOT NULL,
            activity_score REAL NOT NULL,
            pharmvar_version TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (gene_id) REFERENCES genes(gene_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE phenotypes (
            phenotype_id INTEGER PRIMARY KEY AUTOINCREMENT,
            gene_id INTEGER NOT NULL,
            diplotype TEXT NOT NULL,
            phenotype_display TEXT NOT NULL,
            phenotype_normalized TEXT NOT NULL,
            cpic_version TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (gene_id) REFERENCES genes(gene_id)
        )
    """)

    # Insert test data
    cursor.execute("""
        INSERT INTO genes (gene_symbol, chromosome, start_pos, end_pos, tier, build)
        VALUES ('CYP2D6', '22', 42522500, 42530900, 1, 'GRCh37')
    """)
    gene_id = cursor.lastrowid

    # Insert test variants
    test_variants = [
        (gene_id, "rs3892097", "22", 42526883, "G", "A", "*4", "Null", 0.0, None),
        (gene_id, "rs1065852", "22", 42526694, "C", "T", "*10", "Reduced", 0.5, None),
        (gene_id, "rs16947", "22", 42524175, "C", "T", "*2", "Normal", 1.0, None),
        (gene_id, "CYP2D6_DEL", "22", 42522500, "-", "-", "*5", "Null", 0.0, None),
        (
            gene_id,
            "CYP2D6_DUP",
            "22",
            42522500,
            "+",
            "+",
            "*1xN",
            "Increased",
            1.0,
            None,
        ),
    ]

    cursor.executemany(
        """
        INSERT INTO variants (gene_id, rsid, chromosome, position, ref_allele, alt_allele, allele_name, function, activity_score, pharmvar_version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        test_variants,
    )

    # Insert test phenotypes
    test_phenotypes = [
        (gene_id, "*1/*1", "Normal Metabolizer", "extensive_metabolizer", None),
        (gene_id, "*1/*2", "Normal Metabolizer", "extensive_metabolizer", None),
        (
            gene_id,
            "*1/*4",
            "Intermediate Metabolizer",
            "intermediate_metabolizer",
            None,
        ),
        (gene_id, "*4/*4", "Poor Metabolizer", "poor_metabolizer", None),
    ]

    cursor.executemany(
        """
        INSERT INTO phenotypes (gene_id, diplotype, phenotype_display, phenotype_normalized, cpic_version)
        VALUES (?, ?, ?, ?, ?)
    """,
        test_phenotypes,
    )

    conn.commit()
    conn.close()

    yield db_path

    # Cleanup
    close_connection()
    db_path.unlink()


def test_get_connection(temp_db):
    """Test database connection."""
    conn = get_connection(temp_db)
    assert conn is not None
    assert isinstance(conn, sqlite3.Connection)

    # Test singleton behavior
    conn2 = get_connection(temp_db)
    assert conn is conn2


def test_get_connection_missing_db():
    """Test connection to missing database."""
    close_connection()  # Reset singleton
    with pytest.raises(FileNotFoundError):
        get_connection(Path("/nonexistent/database.db"))


def test_get_gene_variants(temp_db):
    """Test retrieving variants for a gene."""
    variants = get_gene_variants("CYP2D6", temp_db)

    assert len(variants) >= 3  # At least 3 SNP variants
    assert "rs3892097" in variants
    assert variants["rs3892097"]["allele"] == "*4"
    assert variants["rs3892097"]["impact"] == "Null"
    assert variants["rs3892097"]["activity_score"] == 0.0

    # Test structural variants
    assert "CYP2D6_DEL" in variants
    assert variants["CYP2D6_DEL"]["allele"] == "*5"
    assert "CYP2D6_DUP" in variants


def test_get_gene_variants_unknown_gene(temp_db):
    """Test retrieving variants for unknown gene."""
    variants = get_gene_variants("UNKNOWN_GENE", temp_db)
    assert len(variants) == 0


def test_get_phenotype_translation(temp_db):
    """Test retrieving phenotype translations."""
    translations = get_phenotype_translation("CYP2D6", temp_db)

    assert len(translations) >= 4
    assert translations["*1/*1"] == "Normal Metabolizer"
    assert translations["*1/*4"] == "Intermediate Metabolizer"
    assert translations["*4/*4"] == "Poor Metabolizer"


def test_get_gene_location(temp_db):
    """Test retrieving gene location."""
    location = get_gene_location("CYP2D6", "GRCh37", temp_db)

    assert location is not None
    assert location["chrom"] == "22"
    assert location["start"] == 42522500
    assert location["end"] == 42530900


def test_get_gene_location_unknown_gene(temp_db):
    """Test retrieving location for unknown gene."""
    location = get_gene_location("UNKNOWN_GENE", "GRCh37", temp_db)
    assert location is None


def test_list_supported_genes(temp_db):
    """Test listing supported genes."""
    genes = list_supported_genes(db_path=temp_db)

    assert len(genes) >= 1
    assert "CYP2D6" in genes


def test_list_supported_genes_by_tier(temp_db):
    """Test listing genes filtered by tier."""
    tier1_genes = list_supported_genes(tier=1, db_path=temp_db)

    assert len(tier1_genes) >= 1
    assert "CYP2D6" in tier1_genes

    # Tier 2 should be empty in test database
    tier2_genes = list_supported_genes(tier=2, db_path=temp_db)
    assert len(tier2_genes) == 0


def test_get_gene_info(temp_db):
    """Test retrieving complete gene information."""
    info = get_gene_info("CYP2D6", temp_db)

    assert info is not None
    assert info["gene_symbol"] == "CYP2D6"
    assert info["chromosome"] == "22"
    assert info["tier"] == 1
    assert info["build"] == "GRCh37"
    assert info["variant_count"] >= 5  # At least 5 variants


def test_get_gene_info_unknown_gene(temp_db):
    """Test retrieving info for unknown gene."""
    info = get_gene_info("UNKNOWN_GENE", temp_db)
    assert info is None


def test_get_database_stats(temp_db):
    """Test retrieving database statistics."""
    stats = get_database_stats(temp_db)

    assert stats["gene_count"] >= 1
    assert stats["variant_count"] >= 5
    assert stats["phenotype_count"] >= 4
    assert stats["tier1_genes"] >= 1
    assert stats["database_size_mb"] > 0


def test_close_connection(temp_db):
    """Test closing database connection."""
    # Open connection
    conn = get_connection(temp_db)
    assert conn is not None

    # Close connection
    close_connection()

    # Verify singleton is reset (will create new connection)
    conn2 = get_connection(temp_db)
    assert conn2 is not None
    assert conn2 is not conn  # Different connection object


def test_backward_compatibility(temp_db):
    """Test backward compatibility with VARIANT_DB format."""
    from src.variant_db_v2 import get_variant_db_for_gene

    variants = get_variant_db_for_gene("CYP2D6")

    # Should have same structure as old VARIANT_DB
    assert isinstance(variants, dict)
    if "rs3892097" in variants:
        assert "allele" in variants["rs3892097"]
        assert "impact" in variants["rs3892097"]
        assert "activity_score" in variants["rs3892097"]


def test_query_performance(temp_db):
    """Test query performance (should be < 100ms)."""
    import time

    # Warm up connection
    get_connection(temp_db)

    # Test variant lookup performance
    start = time.time()
    for _ in range(100):
        variants = get_gene_variants("CYP2D6", temp_db)
    elapsed = time.time() - start

    avg_time_ms = (elapsed / 100) * 1000
    assert avg_time_ms < 100, f"Query too slow: {avg_time_ms:.2f}ms (expected < 100ms)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
