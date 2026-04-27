-- Pharmacogenes Database Schema
-- Version: 1.0
-- Date: 2026-04-10
-- Purpose: Scalable storage for 100+ pharmacogene panel

-- Pharmacogene definitions
CREATE TABLE IF NOT EXISTS genes (
    gene_id INTEGER PRIMARY KEY AUTOINCREMENT,
    gene_symbol TEXT NOT NULL UNIQUE,
    chromosome TEXT NOT NULL,
    start_pos INTEGER NOT NULL,
    end_pos INTEGER NOT NULL,
    build TEXT NOT NULL DEFAULT 'GRCh37',
    tier INTEGER NOT NULL DEFAULT 2,  -- 1=critical, 2=standard, 3=research
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_tier CHECK (tier IN (1, 2, 3))
);

CREATE INDEX IF NOT EXISTS idx_gene_symbol ON genes(gene_symbol);
CREATE INDEX IF NOT EXISTS idx_chromosome ON genes(chromosome);
CREATE INDEX IF NOT EXISTS idx_tier ON genes(tier);

-- Variant definitions (PharmVar)
CREATE TABLE IF NOT EXISTS variants (
    variant_id INTEGER PRIMARY KEY AUTOINCREMENT,
    gene_id INTEGER NOT NULL,
    rsid TEXT NOT NULL,
    chromosome TEXT NOT NULL,
    position INTEGER NOT NULL,
    ref_allele TEXT NOT NULL,
    alt_allele TEXT NOT NULL,
    allele_name TEXT NOT NULL,  -- e.g., "*2", "*3"
    function TEXT NOT NULL,      -- "Normal function", "Reduced function", "No function"
    activity_score REAL NOT NULL,
    pharmvar_version TEXT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (gene_id) REFERENCES genes(gene_id) ON DELETE CASCADE,
    CONSTRAINT chk_activity_score CHECK (activity_score >= 0.0 AND activity_score <= 2.0)
);

CREATE INDEX IF NOT EXISTS idx_rsid ON variants(rsid);
CREATE INDEX IF NOT EXISTS idx_gene_rsid ON variants(gene_id, rsid);
CREATE INDEX IF NOT EXISTS idx_position ON variants(chromosome, position);
CREATE INDEX IF NOT EXISTS idx_allele_name ON variants(gene_id, allele_name);

-- Diplotype to phenotype mappings (CPIC)
CREATE TABLE IF NOT EXISTS phenotypes (
    phenotype_id INTEGER PRIMARY KEY AUTOINCREMENT,
    gene_id INTEGER NOT NULL,
    diplotype TEXT NOT NULL,
    phenotype_display TEXT NOT NULL,
    phenotype_normalized TEXT NOT NULL,
    cpic_version TEXT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (gene_id) REFERENCES genes(gene_id) ON DELETE CASCADE,
    UNIQUE(gene_id, diplotype)
);

CREATE INDEX IF NOT EXISTS idx_gene_diplotype ON phenotypes(gene_id, diplotype);
CREATE INDEX IF NOT EXISTS idx_phenotype_normalized ON phenotypes(phenotype_normalized);

-- Drug-gene interactions
CREATE TABLE IF NOT EXISTS drug_gene_pairs (
    pair_id INTEGER PRIMARY KEY AUTOINCREMENT,
    drug_name TEXT NOT NULL,
    gene_id INTEGER NOT NULL,
    cpic_level TEXT,  -- "A", "B", "C", "D"
    guideline_url TEXT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (gene_id) REFERENCES genes(gene_id) ON DELETE CASCADE,
    CONSTRAINT chk_cpic_level CHECK (cpic_level IN ('A', 'B', 'C', 'D', NULL))
);

CREATE INDEX IF NOT EXISTS idx_drug ON drug_gene_pairs(drug_name);
CREATE INDEX IF NOT EXISTS idx_gene ON drug_gene_pairs(gene_id);
CREATE INDEX IF NOT EXISTS idx_drug_gene ON drug_gene_pairs(drug_name, gene_id);

-- Data provenance tracking
CREATE TABLE IF NOT EXISTS data_versions (
    version_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,  -- "PharmVar", "CPIC"
    version TEXT NOT NULL,
    download_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    record_count INTEGER,
    checksum TEXT
);

CREATE INDEX IF NOT EXISTS idx_source ON data_versions(source);

-- Metadata table for database version tracking
CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert initial metadata
INSERT OR REPLACE INTO metadata (key, value) VALUES ('schema_version', '1.0');
INSERT OR REPLACE INTO metadata (key, value) VALUES ('created_date', datetime('now'));
INSERT OR REPLACE INTO metadata (key, value) VALUES ('description', 'Anukriti Pharmacogenes Database');

-- Create views for common queries
CREATE VIEW IF NOT EXISTS gene_summary AS
SELECT 
    g.gene_symbol,
    g.chromosome,
    g.tier,
    COUNT(DISTINCT v.variant_id) as variant_count,
    COUNT(DISTINCT p.phenotype_id) as phenotype_count,
    g.last_updated
FROM genes g
LEFT JOIN variants v ON g.gene_id = v.gene_id
LEFT JOIN phenotypes p ON g.gene_id = p.gene_id
GROUP BY g.gene_id;

CREATE VIEW IF NOT EXISTS tier1_genes AS
SELECT * FROM genes WHERE tier = 1 ORDER BY gene_symbol;

CREATE VIEW IF NOT EXISTS tier2_genes AS
SELECT * FROM genes WHERE tier = 2 ORDER BY gene_symbol;

-- Trigger to update last_updated timestamp
CREATE TRIGGER IF NOT EXISTS update_gene_timestamp 
AFTER UPDATE ON genes
BEGIN
    UPDATE genes SET last_updated = CURRENT_TIMESTAMP WHERE gene_id = NEW.gene_id;
END;

CREATE TRIGGER IF NOT EXISTS update_variant_timestamp 
AFTER UPDATE ON variants
BEGIN
    UPDATE variants SET last_updated = CURRENT_TIMESTAMP WHERE variant_id = NEW.variant_id;
END;

CREATE TRIGGER IF NOT EXISTS update_phenotype_timestamp 
AFTER UPDATE ON phenotypes
BEGIN
    UPDATE phenotypes SET last_updated = CURRENT_TIMESTAMP WHERE phenotype_id = NEW.phenotype_id;
END;
