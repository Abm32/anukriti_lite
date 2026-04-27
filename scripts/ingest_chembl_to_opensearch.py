#!/usr/bin/env python3
"""
ChEMBL to OpenSearch Ingestion Script

Extracts drugs from ChEMBL database and ingests them into an OpenSearch
vector index for molecular similarity search.
"""

import os
import sys
from urllib.parse import urlparse

import boto3
from dotenv import load_dotenv

# Ensure script works when run as `python scripts/...` from repo root.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.chembl_processor import batch_extract_drugs, find_chembl_db_path

try:
    from opensearchpy import OpenSearch, RequestsHttpConnection, helpers
    from opensearchpy.helpers.signer import AWSV4SignerAuth
except Exception as e:
    print(f"ERROR: opensearch-py is required: {e}")
    print("Install with: pip install opensearch-py")
    sys.exit(1)


load_dotenv()


def _normalize_host(raw_host: str) -> str:
    host = (raw_host or "").strip()
    if not host:
        return ""
    if host.startswith("http://") or host.startswith("https://"):
        parsed = urlparse(host)
        return parsed.netloc
    return host.split("/")[0]


def _build_client():
    host = _normalize_host(os.getenv("OPENSEARCH_HOST", ""))
    if not host:
        print("ERROR: OPENSEARCH_HOST is not set.")
        print(
            "Set OPENSEARCH_HOST to your endpoint host, e.g. "
            "abc123.us-east-1.aoss.amazonaws.com"
        )
        sys.exit(1)

    region = os.getenv(
        "OPENSEARCH_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    )
    service = os.getenv("OPENSEARCH_SERVICE", "aoss")

    session = boto3.Session()
    creds = session.get_credentials()
    if creds is None:
        print("ERROR: AWS credentials not found.")
        print("Set AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY or use an IAM role.")
        sys.exit(1)

    auth = AWSV4SignerAuth(creds, region, service)
    client = OpenSearch(
        hosts=[{"host": host, "port": 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=120,
    )
    return client


def main():
    index_name = os.getenv("OPENSEARCH_INDEX", "drug-index")
    vector_field = os.getenv("OPENSEARCH_VECTOR_FIELD", "vector")
    chembl_limit = int(os.getenv("CHEMBL_LIMIT", "1000"))
    batch_size = int(os.getenv("OPENSEARCH_BULK_BATCH_SIZE", "200"))

    print("=" * 60)
    print("ChEMBL -> OpenSearch Ingestion")
    print("=" * 60)
    print(f"Index: {index_name}")
    print(f"Vector field: {vector_field}")
    print(f"CHEMBL_LIMIT: {chembl_limit}")
    print(f"Batch size: {batch_size}")

    client = _build_client()

    try:
        if not client.indices.exists(index=index_name):
            print(f"ERROR: Index '{index_name}' not found.")
            print("Run: python scripts/setup_opensearch_index.py")
            sys.exit(1)
    except Exception as e:
        print(f"ERROR: Cannot access OpenSearch index '{index_name}': {e}")
        sys.exit(1)

    print("\nLocating ChEMBL database...")
    db_path = find_chembl_db_path()
    if not db_path:
        print("ERROR: ChEMBL database not found!")
        print("Expected one of:")
        print("  - data/chembl/chembl_34_sqlite/chembl_34.db")
        print("  - data/chembl/chembl_34.db")
        sys.exit(1)
    print(f"✓ Found ChEMBL database: {db_path}")

    print("\nExtracting and preparing drug vectors...")
    vector_records = batch_extract_drugs(db_path, limit=chembl_limit)
    if not vector_records:
        print("ERROR: No drug vectors were prepared from ChEMBL.")
        sys.exit(1)
    print(f"✓ Prepared {len(vector_records)} records")

    total_ingested = 0
    print("\nBulk ingesting to OpenSearch...")
    for i in range(0, len(vector_records), batch_size):
        batch = vector_records[i : i + batch_size]
        actions = []
        for rec in batch:
            source = dict(rec["metadata"])
            source[vector_field] = rec["vector"]
            actions.append(
                {
                    "_op_type": "index",
                    "_index": index_name,
                    "_source": source,
                }
            )
        try:
            helpers.bulk(client, actions, request_timeout=120)
            total_ingested += len(batch)
            print(
                f"  Ingested batch {i//batch_size + 1}: "
                f"{total_ingested}/{len(vector_records)}"
            )
        except Exception as e:
            print(f"  ERROR in batch {i//batch_size + 1}: {e}")

    print(f"\n✓ Ingestion complete. Total ingested: {total_ingested}")
    try:
        client.indices.refresh(index=index_name)
        cnt = client.count(index=index_name).get("count", "N/A")
        print(f"Index doc count: {cnt}")
    except Exception as e:
        print(f"Could not fetch index count: {e}")


if __name__ == "__main__":
    main()
