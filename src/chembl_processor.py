"""
ChEMBL Database Processor Module

Handles extraction of drug-target interaction data from ChEMBL SQLite database.
Extracts drug molecules, targets, and known side effects for vector database ingestion.
"""

import os
import sqlite3
from typing import Dict, List, Optional, Tuple

import numpy as np
from rdkit import Chem
from rdkit.Chem import AllChem

from src.input_processor import get_drug_fingerprint


def connect_chembl(db_path: str) -> sqlite3.Connection:
    """
    Connect to ChEMBL SQLite database.

    Args:
        db_path: Path to ChEMBL SQLite database file

    Returns:
        SQLite connection object

    Raises:
        FileNotFoundError: If database file doesn't exist
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"ChEMBL database not found: {db_path}")

    conn = sqlite3.connect(db_path)
    return conn


def extract_drug_molecules(
    conn: sqlite3.Connection, limit: Optional[int] = None
) -> List[Dict]:
    """
    Extract drug molecules with SMILES from ChEMBL.

    Args:
        conn: SQLite connection to ChEMBL database
        limit: Maximum number of drugs to extract (None = all)

    Returns:
        List of dictionaries with drug information
    """
    query = """
    SELECT
        m.molregno,
        m.pref_name,
        m.max_phase,
        cs.canonical_smiles,
        cs.standard_inchi,
        cs.standard_inchi_key
    FROM
        molecule_dictionary m
    JOIN
        compound_structures cs ON m.molregno = cs.molregno
    WHERE
        m.max_phase >= 2  -- Only approved drugs (phase 2+)
        AND cs.canonical_smiles IS NOT NULL
        AND cs.canonical_smiles != ''
    ORDER BY
        m.max_phase DESC, m.pref_name
    """

    if limit:
        query += f" LIMIT {limit}"

    cursor = conn.cursor()
    cursor.execute(query)

    drugs = []
    for row in cursor.fetchall():
        molregno, pref_name, max_phase, smiles, inchi, inchi_key = row

        # Validate SMILES
        try:
            mol = Chem.MolFromSmiles(smiles)
            if mol:
                drugs.append(
                    {
                        "molregno": molregno,
                        "name": pref_name or f"Compound_{molregno}",
                        "max_phase": max_phase,
                        "smiles": smiles,
                        "inchi": inchi,
                        "inchi_key": inchi_key,
                    }
                )
        except Exception:  # nosec B112 - skip invalid SMILES
            continue

    return drugs


def extract_drug_targets(conn: sqlite3.Connection, molregno: int) -> List[Dict]:
    """
    Extract target information for a specific drug molecule.

    Args:
        conn: SQLite connection to ChEMBL database
        molregno: ChEMBL molecule registration number

    Returns:
        List of target dictionaries
    """
    query = """
    SELECT DISTINCT
        t.tid,
        t.pref_name,
        t.organism,
        t.target_type,
        act.standard_type,
        act.standard_value,
        act.standard_units,
        act.standard_relation
    FROM
        activities act
    JOIN
        assays a ON act.assay_id = a.assay_id
    JOIN
        target_dictionary t ON a.tid = t.tid
    WHERE
        act.molregno = ?
        AND act.standard_value IS NOT NULL
        AND act.standard_type IN ('IC50', 'Ki', 'Kd', 'EC50', 'ED50')
    ORDER BY
        act.standard_value ASC
    LIMIT 10
    """

    cursor = conn.cursor()
    cursor.execute(query, (molregno,))

    targets = []
    for row in cursor.fetchall():
        (
            tid,
            pref_name,
            organism,
            target_type,
            std_type,
            std_value,
            std_units,
            std_relation,
        ) = row
        targets.append(
            {
                "tid": tid,
                "name": pref_name,
                "organism": organism,
                "type": target_type,
                "activity_type": std_type,
                "value": std_value,
                "units": std_units,
                "relation": std_relation,
            }
        )

    return targets


def extract_side_effects(conn: sqlite3.Connection, molregno: int) -> List[str]:
    """
    Extract known side effects/adverse events for a drug.

    Note: ChEMBL doesn't directly store side effects, but we can infer from:
    - Drug warnings
    - Target information (e.g., CYP enzymes)
    - Mechanism of action

    Args:
        conn: SQLite connection to ChEMBL database
        molregno: ChEMBL molecule registration number

    Returns:
        List of side effect descriptions
    """
    side_effects = []

    # Check if drug targets CYP enzymes (common source of drug-drug interactions)
    query = """
    SELECT DISTINCT t.pref_name
    FROM activities act
    JOIN assays a ON act.assay_id = a.assay_id
    JOIN target_dictionary t ON a.tid = t.tid
    WHERE act.molregno = ?
    AND (t.pref_name LIKE '%CYP%' OR t.pref_name LIKE '%cytochrome%')
    """

    cursor = conn.cursor()
    cursor.execute(query, (molregno,))

    cyp_targets = [row[0] for row in cursor.fetchall()]
    if cyp_targets:
        side_effects.append(f"Interacts with: {', '.join(cyp_targets)}")

    # Check for drug warnings (if available in molecule_properties or similar)
    # This is a placeholder - actual ChEMBL schema may vary

    return side_effects


def prepare_drug_for_vector_db(drug: Dict, conn: sqlite3.Connection) -> Optional[Dict]:
    """
    Prepare a drug record for vector database ingestion.

    Args:
        drug: Drug dictionary from extract_drug_molecules
        conn: SQLite connection to ChEMBL database

    Returns:
        Dictionary ready for Pinecone ingestion with:
        - id: Unique identifier
        - vector: Molecular fingerprint
        - metadata: Drug name, targets, side effects
    """
    try:
        # Generate molecular fingerprint (returns list of integers)
        fingerprint = get_drug_fingerprint(drug["smiles"])

        # Convert to floats (Pinecone requires float vectors)
        fingerprint_float = [float(x) for x in fingerprint]

        # Extract targets
        targets = extract_drug_targets(conn, drug["molregno"])
        target_names = [t["name"] for t in targets[:5]]  # Top 5 targets

        # Extract side effects
        side_effects = extract_side_effects(conn, drug["molregno"])

        # Build metadata
        metadata = {
            "name": drug["name"],
            "smiles": drug["smiles"],
            "max_phase": drug["max_phase"],
            "targets": ", ".join(target_names) if target_names else "Unknown",
            "known_side_effects": (
                "; ".join(side_effects) if side_effects else "None listed"
            ),
            "chembl_id": f"CHEMBL{drug['molregno']}",
        }

        return {
            "id": f"chembl_{drug['molregno']}",
            "vector": fingerprint_float,
            "metadata": metadata,
        }

    except Exception as e:
        print(f"Error preparing drug {drug.get('name', 'Unknown')}: {e}")
        return None


def batch_extract_drugs(
    db_path: str, limit: Optional[int] = 1000, batch_size: int = 100
) -> List[Dict]:
    """
    Extract drugs from ChEMBL in batches for vector database ingestion.

    Args:
        db_path: Path to ChEMBL SQLite database
        limit: Maximum number of drugs to extract
        batch_size: Number of drugs to process per batch

    Returns:
        List of drug dictionaries ready for Pinecone
    """
    conn = connect_chembl(db_path)

    try:
        # Extract drug molecules
        print(f"Extracting up to {limit} drugs from ChEMBL...")
        drugs = extract_drug_molecules(conn, limit=limit)
        print(f"Found {len(drugs)} valid drugs")

        # Prepare for vector DB
        vector_db_records = []

        for i, drug in enumerate(drugs):
            if i % batch_size == 0:
                print(f"Processing batch {i//batch_size + 1}... ({i}/{len(drugs)})")

            record = prepare_drug_for_vector_db(drug, conn)
            if record:
                vector_db_records.append(record)

        print(
            f"Successfully prepared {len(vector_db_records)} drugs for vector database"
        )
        return vector_db_records

    finally:
        conn.close()


def find_chembl_db_path() -> Optional[str]:
    """
    Find ChEMBL database file in common locations.

    Returns:
        Path to ChEMBL database or None if not found
    """
    possible_paths = [
        "data/chembl/chembl_34/chembl_34_sqlite/chembl_34.db",  # Extracted tar.gz structure
        "data/chembl/chembl_34_sqlite/chembl_34.db",
        "data/chembl/chembl_34.db",
        "data/chembl/chembl.db",
        "../data/chembl/chembl_34/chembl_34_sqlite/chembl_34.db",
        "../data/chembl/chembl_34_sqlite/chembl_34.db",
    ]

    for path in possible_paths:
        if os.path.exists(path):
            return path

    return None
