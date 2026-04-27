#!/usr/bin/env python3
"""
OpenSearch Vector Index Setup Script

Creates an OpenSearch index for molecular fingerprint vector search
with 2048-dim vectors and drug metadata fields.
"""

import os
import sys
from urllib.parse import urlparse

import boto3
from dotenv import load_dotenv

try:
    from opensearchpy import OpenSearch, RequestsHttpConnection
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
        timeout=60,
    )
    return client


def main():
    index_name = os.getenv("OPENSEARCH_INDEX", "drug-index")
    vector_field = os.getenv("OPENSEARCH_VECTOR_FIELD", "vector")

    print("=" * 60)
    print("OpenSearch Vector Index Setup")
    print("=" * 60)
    print(f"Index: {index_name}")
    print(f"Vector field: {vector_field}")
    print("Dimension: 2048")

    client = _build_client()

    try:
        # OpenSearch Serverless may not support cluster-level health APIs.
        # Use index existence call as the connectivity/auth check.
        client.indices.exists(index=index_name)
        print("✓ Connected to OpenSearch endpoint")
    except Exception as e:
        print(f"ERROR: Cannot connect to OpenSearch endpoint: {e}")
        sys.exit(1)

    try:
        if client.indices.exists(index=index_name):
            print(f"✓ Index '{index_name}' already exists")
            return
    except Exception as e:
        print(f"ERROR: Failed checking index existence: {e}")
        sys.exit(1)

    body = {
        "settings": {"index": {"knn": True}},
        "mappings": {
            "properties": {
                vector_field: {"type": "knn_vector", "dimension": 2048},
                "name": {"type": "text"},
                "smiles": {"type": "keyword"},
                "known_side_effects": {"type": "text"},
                "targets": {"type": "text"},
                "chembl_id": {"type": "keyword"},
                "max_phase": {"type": "integer"},
            }
        },
    }

    try:
        client.indices.create(index=index_name, body=body)
        print(f"✓ Created index '{index_name}'")
    except Exception as e:
        print(f"ERROR: Failed creating index '{index_name}': {e}")
        print("\nCommon fixes:")
        print("1. Ensure OpenSearch collection/domain exists and is ACTIVE")
        print(
            "2. Ensure data access policy grants your IAM principal index permissions"
        )
        print(
            "3. Ensure service is correct: OPENSEARCH_SERVICE=aoss (serverless) or es"
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
