#!/usr/bin/env python3
"""
ChEMBL to Pinecone Ingestion Script

Extracts drugs from ChEMBL database and ingests them into Pinecone vector database.
This populates the drug-index with real drug data for similarity search.
"""

import os
import sys

from dotenv import load_dotenv
from pinecone import Pinecone

from src.chembl_processor import batch_extract_drugs, find_chembl_db_path

# Load environment variables
load_dotenv()


def main():
    """Main ingestion function."""

    # Check for Pinecone API key
    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        print("ERROR: PINECONE_API_KEY not found in environment variables")
        print("Please set it with: export PINECONE_API_KEY='your_key'")
        sys.exit(1)

    # Initialize Pinecone
    print("Connecting to Pinecone...")
    try:
        pc = Pinecone(api_key=api_key)

        # Check if index exists
        index_name = "drug-index"
        existing_indexes = [idx.name for idx in pc.list_indexes()]

        if index_name not in existing_indexes:
            print(f"\n⚠️  Index '{index_name}' not found!")
            print("\nTo create the index, run:")
            print("  python setup_pinecone_index.py")
            print("\nOr create it manually in the Pinecone dashboard:")
            print("  1. Go to https://app.pinecone.io/")
            print("  2. Click 'Create Index'")
            print("  3. Name: drug-index")
            print("  4. Dimensions: 2048")
            print("  5. Metric: cosine")
            print("  6. Click 'Create Index'")
            sys.exit(1)

        index = pc.Index(index_name)
        print(f"✓ Connected to Pinecone index '{index_name}'")

        # Verify index configuration
        try:
            index_desc = pc.describe_index(index_name)
            if index_desc.dimension != 2048:
                print(
                    f"\n⚠️  WARNING: Index dimension is {index_desc.dimension}, expected 2048"
                )
                print("This may cause issues. Consider recreating the index.")
        except Exception:
            pass  # Can't always get index description

    except Exception as e:
        print(f"ERROR: Could not connect to Pinecone: {e}")
        print("\nMake sure:")
        print("1. PINECONE_API_KEY is set correctly")
        print("2. Index 'drug-index' exists (run: python setup_pinecone_index.py)")
        print("3. Index has 2048 dimensions")
        sys.exit(1)

    # Find ChEMBL database
    print("\nLocating ChEMBL database...")
    db_path = find_chembl_db_path()
    if not db_path:
        print("ERROR: ChEMBL database not found!")
        print("Please ensure ChEMBL SQLite database is in one of these locations:")
        print("  - data/chembl/chembl_34_sqlite/chembl_34.db")
        print("  - data/chembl/chembl_34.db")
        print("\nTo download ChEMBL:")
        print(
            "  curl -L https://ftp.ebi.ac.uk/pub/databases/chembl/ChEMBLdb/releases/chembl_34/chembl_34_sqlite.tar.gz -o data/chembl/chembl_34_sqlite.tar.gz"
        )
        sys.exit(1)

    print(f"✓ Found ChEMBL database: {db_path}")

    # Extract drugs from ChEMBL
    print("\nExtracting drugs from ChEMBL...")
    print("(This may take several minutes for large datasets)")

    # Limit to first 1000 drugs for initial ingestion (can be increased)
    limit = int(os.getenv("CHEMBL_LIMIT", "1000"))
    vector_records = batch_extract_drugs(db_path, limit=limit)

    if not vector_records:
        print("ERROR: No drugs extracted from ChEMBL")
        sys.exit(1)

    print(f"\n✓ Prepared {len(vector_records)} drugs for ingestion")

    # Ingest into Pinecone in batches
    print("\nIngesting into Pinecone...")
    batch_size = 100  # Pinecone batch limit

    total_ingested = 0
    for i in range(0, len(vector_records), batch_size):
        batch = vector_records[i : i + batch_size]

        # Prepare batch for Pinecone (format: list of tuples)
        vectors_to_upsert = []
        for record in batch:
            vectors_to_upsert.append(
                {
                    "id": record["id"],
                    "values": record["vector"],
                    "metadata": record["metadata"],
                }
            )

        try:
            index.upsert(vectors=vectors_to_upsert)
            total_ingested += len(batch)
            print(
                f"  Ingested batch {i//batch_size + 1}: {total_ingested}/{len(vector_records)} drugs"
            )
        except Exception as e:
            print(f"  ERROR ingesting batch {i//batch_size + 1}: {e}")
            continue

    print(f"\n✓ Successfully ingested {total_ingested} drugs into Pinecone")
    print("\nYou can now use the vector search with real ChEMBL data!")

    # Show index stats
    try:
        stats = index.describe_index_stats()
        print(f"\nIndex Statistics:")
        print(f"  Total vectors: {stats.get('total_vector_count', 'N/A')}")
    except Exception as e:
        print(f"\nCould not retrieve index stats: {e}")


if __name__ == "__main__":
    main()
