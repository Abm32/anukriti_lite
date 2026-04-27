#!/usr/bin/env python3
"""
Pinecone Index Setup Script

Creates the 'drug-index' index in Pinecone with the correct configuration
for molecular fingerprints (2048 dimensions).
"""

import os
import sys

from dotenv import load_dotenv
from pinecone import Pinecone, ServerlessSpec

# Load environment variables
load_dotenv()


def create_index():
    """Create the Pinecone index if it doesn't exist."""

    # Check for API key
    api_key = os.getenv("PINECONE_API_KEY")
    if not api_key:
        print("ERROR: PINECONE_API_KEY not found in environment variables")
        print("\nPlease set it with:")
        print("  export PINECONE_API_KEY='your_api_key_here'")
        print("\nOr add it to a .env file:")
        print("  PINECONE_API_KEY=your_api_key_here")
        sys.exit(1)

    print("Connecting to Pinecone...")
    try:
        pc = Pinecone(api_key=api_key)
        print("✓ Connected to Pinecone")
    except Exception as e:
        print(f"ERROR: Could not connect to Pinecone: {e}")
        print("Please check your API key is correct")
        sys.exit(1)

    index_name = "drug-index"
    dimension = 2048  # Matching molecular fingerprint size
    metric = "cosine"  # Cosine similarity for molecular fingerprints

    # Check if index already exists
    existing_indexes = [idx.name for idx in pc.list_indexes()]

    if index_name in existing_indexes:
        print(f"\n⚠️  Index '{index_name}' already exists!")
        print("\nOptions:")
        print("1. Use existing index (recommended)")
        print("2. Delete and recreate index (WARNING: will delete all data)")

        choice = input("\nEnter choice (1 or 2): ").strip()

        if choice == "1":
            print(f"\n✓ Using existing index '{index_name}'")
            index = pc.Index(index_name)

            # Check index stats
            try:
                stats = index.describe_index_stats()
                print(f"\nIndex Statistics:")
                print(f"  Total vectors: {stats.get('total_vector_count', 0)}")
                print(f"  Dimension: {dimension}")
                print(f"  Metric: {metric}")
            except Exception as e:
                print(f"  Could not retrieve stats: {e}")

            return

        elif choice == "2":
            print(f"\n⚠️  Deleting existing index '{index_name}'...")
            pc.delete_index(index_name)
            print("✓ Index deleted")
        else:
            print("Invalid choice. Exiting.")
            sys.exit(1)

    # Create new index
    print(f"\nCreating index '{index_name}'...")
    print(f"  Dimension: {dimension}")
    print(f"  Metric: {metric}")
    print(f"  Spec: Serverless (default)")

    try:
        pc.create_index(
            name=index_name,
            dimension=dimension,
            metric=metric,
            spec=ServerlessSpec(
                cloud="aws",  # or "gcp" depending on your preference
                region="us-east-1",  # Change to your preferred region
            ),
        )
        print(f"\n✓ Index '{index_name}' created successfully!")
        print("\nNote: It may take a few minutes for the index to be ready.")
        print("You can check status in the Pinecone dashboard.")

    except Exception as e:
        print(f"\nERROR: Could not create index: {e}")

        if "already exists" in str(e).lower():
            print(f"\nIndex '{index_name}' already exists.")
            print("You can use it directly or delete it first.")
        elif "quota" in str(e).lower() or "limit" in str(e).lower():
            print("\nYou may have reached your Pinecone quota.")
            print("Check your Pinecone dashboard for limits.")
        else:
            print("\nCommon issues:")
            print("1. Invalid API key")
            print("2. Insufficient quota/credits")
            print("3. Network connectivity issues")
            print("4. Invalid region specification")

        sys.exit(1)

    # Verify index was created
    print("\nVerifying index...")
    try:
        index = pc.Index(index_name)
        stats = index.describe_index_stats()
        print(f"✓ Index is ready!")
        print(f"  Total vectors: {stats.get('total_vector_count', 0)}")
    except Exception as e:
        print(f"⚠️  Index created but not ready yet: {e}")
        print("Wait a few minutes and check the Pinecone dashboard.")


def main():
    """Main function."""
    print("=" * 60)
    print("Pinecone Index Setup")
    print("=" * 60)
    print("\nThis script will create the 'drug-index' index required")
    print("for storing molecular fingerprints from ChEMBL.")
    print()

    create_index()

    print("\n" + "=" * 60)
    print("Next Steps")
    print("=" * 60)
    print("1. Wait a few minutes for index to be fully ready")
    print("2. Run: python ingest_chembl_to_pinecone.py")
    print("3. Or check index status in Pinecone dashboard:")
    print("   https://app.pinecone.io/")


if __name__ == "__main__":
    main()
