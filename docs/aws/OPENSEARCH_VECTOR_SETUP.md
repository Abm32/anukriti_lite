# OpenSearch Vector Setup (AWS)

This guide sets up AWS OpenSearch as the vector backend for SynthaTrial.

## 1) Create OpenSearch Serverless collection

- AWS Console -> OpenSearch Serverless -> Collections -> Create collection
- Collection type: `Vector search`
- Name: e.g. `synthatrial-vectors`
- Wait until status is `Active`

## 2) Configure access policies

You need both:

- **Network policy**: allow your client network (or public for testing).
- **Data access policy**: allow your IAM principal to:
  - `aoss:ReadDocument`
  - `aoss:WriteDocument`
  - `aoss:CreateIndex`
  - `aoss:UpdateIndex`
  - `aoss:DescribeIndex`

Your IAM user/role should also have:

- `aoss:APIAccessAll` on the collection

## 3) Set environment variables

In `.env`:

```bash
VECTOR_DB_BACKEND=opensearch
OPENSEARCH_HOST=your-collection-id.us-east-1.aoss.amazonaws.com
OPENSEARCH_INDEX=drug-index
OPENSEARCH_REGION=us-east-1
OPENSEARCH_SERVICE=aoss
OPENSEARCH_VECTOR_FIELD=vector
OPENSEARCH_TOP_K=3
```

Keep `PINECONE_*` env vars optional; they are no longer required when using OpenSearch.

## 4) Create the vector index

```bash
conda run -n synthatrial python scripts/setup_opensearch_index.py
```

This creates an index with:
- KNN enabled
- vector field with 2048 dimensions
- metadata fields used by SynthaTrial (`name`, `smiles`, `targets`, `known_side_effects`)

## 5) Ingest ChEMBL vectors

Ensure ChEMBL SQLite exists (e.g. `data/chembl/chembl_34_sqlite/chembl_34.db`), then:

```bash
CHEMBL_LIMIT=1000 conda run -n synthatrial python scripts/ingest_chembl_to_opensearch.py
```

Increase `CHEMBL_LIMIT` gradually (e.g. `5000`, `10000`) once baseline ingest works.

## 6) Verify in SynthaTrial

Start API and check:

```bash
curl -s http://127.0.0.1:8000/data-status | jq
curl -s http://127.0.0.1:8000/health | jq
```

Expected:
- `vector_db`: `opensearch`
- `vector_db_configured`: `opensearch`

If OpenSearch is unreachable or misconfigured, backend falls back to `mock`.
