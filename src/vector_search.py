"""
Vector Search Module

Handles similarity search using pluggable vector DB backends:
- AWS OpenSearch (serverless/managed)
- Pinecone
- Mock fallback
"""

import json
import logging
import os
import time
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    import boto3  # used for OpenSearch SigV4 auth
except Exception:  # pragma: no cover
    boto3 = None

try:
    from pinecone import Pinecone  # type: ignore
except Exception:  # pragma: no cover
    Pinecone = None

try:
    from qdrant_client import QdrantClient  # type: ignore
    from qdrant_client.models import Distance, PointStruct, VectorParams  # type: ignore
except Exception:  # pragma: no cover
    QdrantClient = None
    Distance = None
    PointStruct = None
    VectorParams = None
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src import metrics as _metrics
from src.config import config
from src.exceptions import VectorSearchError
from src.resilience import circuit_breaker

# Set up logging
logger = logging.getLogger(__name__)

# Optional OpenSearch dependency (graceful fallback when missing)
try:
    from opensearchpy import OpenSearch, RequestsHttpConnection
    from opensearchpy.helpers.signer import AWSV4SignerAuth
except Exception:  # pragma: no cover - optional dependency
    OpenSearch = None
    RequestsHttpConnection = None
    AWSV4SignerAuth = None

# Global clients (lazy initialization)
_pinecone_client: Optional[Pinecone] = None
_pinecone_index = None
_opensearch_client = None
_qdrant_client = None

# Local in-process vector search (ChEMBL fingerprints -> cosine similarity).
_local_vectors: Optional[np.ndarray] = None
_local_norms: Optional[np.ndarray] = None
_local_metadata: Optional[List[Dict[str, Any]]] = None
_local_lock = Lock()


def _local_cache_path() -> Path:
    cache_dir = Path(config.LOCAL_VECTOR_CACHE_DIR)
    cache_dir.mkdir(parents=True, exist_ok=True)
    # Cache key includes the most important settings so results don't go stale.
    return (
        cache_dir
        / f"chembl_local_vectors_bits{config.FINGERPRINT_BITS}_limit{config.CHEMBL_LIMIT}.npz"
    )


def _load_local_index_from_cache() -> bool:
    """Load vectors+metadata from disk cache. Returns True if loaded."""
    global _local_vectors, _local_norms, _local_metadata

    cache_path = _local_cache_path()
    if not cache_path.exists():
        return False

    try:
        data = np.load(cache_path, allow_pickle=False)
        vectors = data["vectors"].astype(np.float32, copy=False)
        norms = data["norms"].astype(np.float32, copy=False)
        meta_json = data["meta_json"]
        metadata = [json.loads(s) for s in meta_json.tolist()]

        if len(metadata) != vectors.shape[0]:
            logger.warning("Local vector cache metadata size mismatch; rebuilding")
            return False

        _local_vectors = vectors
        _local_norms = norms
        _local_metadata = metadata
        return True
    except Exception as e:
        logger.warning(f"Failed to load local vector cache: {e}; rebuilding")
        return False


def _build_local_index() -> Tuple[np.ndarray, np.ndarray, List[Dict[str, Any]]]:
    """
    Build the local vector index from the on-disk ChEMBL SQLite DB.
    This is cached to disk so it only happens once per limit.
    """
    from src.chembl_processor import batch_extract_drugs, find_chembl_db_path

    db_path = config.CHEMBL_DB_PATH or find_chembl_db_path()
    if not db_path:
        raise VectorSearchError("ChEMBL DB not found for local vector index")

    # Extract + prepare vectors. batch_extract_drugs already computes fingerprints.
    records = batch_extract_drugs(db_path, limit=config.CHEMBL_LIMIT, batch_size=200)
    if not records:
        raise VectorSearchError("No ChEMBL records loaded for local vector index")

    vectors = np.array([rec["vector"] for rec in records], dtype=np.float32)
    norms = np.linalg.norm(vectors, axis=1).astype(np.float32)
    metadata = [rec["metadata"] for rec in records]

    # Persist for future runs.
    cache_path = _local_cache_path()
    try:
        meta_json = np.array(
            [json.dumps(m, ensure_ascii=False) for m in metadata], dtype=str
        )
        np.savez_compressed(
            cache_path,
            vectors=vectors,
            norms=norms,
            meta_json=meta_json,
        )
    except Exception as e:
        # Non-fatal: we can still operate without the disk cache.
        logger.warning(f"Could not write local vector cache: {e}")

    return vectors, norms, metadata


def _get_local_index() -> Tuple[np.ndarray, np.ndarray, List[Dict[str, Any]]]:
    """Get local vectors+norms+metadata, loading from cache or building."""
    global _local_vectors, _local_norms, _local_metadata

    if (
        _local_vectors is not None
        and _local_norms is not None
        and _local_metadata is not None
    ):
        return _local_vectors, _local_norms, _local_metadata

    with _local_lock:
        # Re-check inside lock
        if (
            _local_vectors is not None
            and _local_norms is not None
            and _local_metadata is not None
        ):
            return _local_vectors, _local_norms, _local_metadata

        if not config.LOCAL_VECTOR_REBUILD and _load_local_index_from_cache():
            assert _local_vectors is not None
            assert _local_norms is not None
            assert _local_metadata is not None
            return _local_vectors, _local_norms, _local_metadata

        vectors, norms, metadata = _build_local_index()
        _local_vectors, _local_norms, _local_metadata = vectors, norms, metadata
        return vectors, norms, metadata


def _query_local(vector: List[float], top_k: int) -> List[str]:
    """
    Query local cosine similarity index (no OpenSearch/Pinecone).
    Returns formatted drug strings (same format as other backends).
    """
    vectors, norms, metadata = _get_local_index()

    if vectors.shape[0] == 0:
        return []

    q = np.array(vector, dtype=np.float32)
    q_norm = float(np.linalg.norm(q))
    if q_norm == 0.0:
        return []

    # Cosine similarity: (X·q) / (||X||·||q||)
    sims = (vectors @ q) / (norms * q_norm + 1e-8)

    pool_k = top_k
    rerank_path_str = config.DRUG_RERANKER_PATH
    rerank_path = Path(rerank_path_str) if rerank_path_str else None
    if rerank_path is not None and rerank_path.is_file():
        pool_k = max(top_k, min(config.DRUG_RERANKER_POOL, int(sims.shape[0])))

    k = min(pool_k, int(sims.shape[0]))
    if k <= 0:
        return []

    # Top pool_k by cosine (then optional ML rerank down to top_k)
    top_idx = np.argpartition(-sims, k - 1)[:k]
    top_idx = top_idx[np.argsort(-sims[top_idx])]

    if rerank_path is not None and rerank_path.is_file():
        from src.ml.drug_reranker import rerank_top_indices

        top_idx, used = rerank_top_indices(q, top_idx, vectors, rerank_path, top_k)
        if used:
            logger.info("Applied drug similarity reranker (%s)", rerank_path)

    else:
        top_idx = top_idx[:top_k]

    found = []
    for i in top_idx.tolist():
        found.append(_format_drug_from_metadata(metadata[int(i)]))
    return found


def _get_pinecone_index():
    """
    Get or initialize Pinecone index with lazy loading.

    Returns:
        Pinecone Index object or None if unavailable

    Raises:
        VectorSearchError: If initialization fails and no fallback available
    """
    global _pinecone_client, _pinecone_index

    if _pinecone_index is not None:
        return _pinecone_index

    if Pinecone is None:
        return None
    if not config.PINECONE_API_KEY:
        logger.info("PINECONE_API_KEY not found")
        return None

    try:
        logger.info("Initializing Pinecone connection...")
        _pinecone_client = Pinecone(api_key=config.PINECONE_API_KEY)
        _pinecone_index = _pinecone_client.Index(config.PINECONE_INDEX)
        logger.info(f"✓ Connected to Pinecone index: {config.PINECONE_INDEX}")
        return _pinecone_index
    except Exception as e:
        logger.warning(
            f"Could not initialize Pinecone: {e} - falling back to mock data"
        )
        return None


def _get_opensearch_client():
    """
    Get or initialize AWS OpenSearch client with SigV4 auth.
    Supports both OpenSearch Serverless (service=aoss) and managed (service=es).
    """
    global _opensearch_client

    if _opensearch_client is not None:
        return _opensearch_client

    if not config.OPENSEARCH_HOST:
        logger.info("OPENSEARCH_HOST not set")
        return None
    if boto3 is None:
        logger.warning("boto3 is not installed; cannot use OpenSearch backend")
        return None
    if OpenSearch is None or AWSV4SignerAuth is None or RequestsHttpConnection is None:
        logger.warning("opensearch-py is not installed - cannot use OpenSearch backend")
        return None

    try:
        session = boto3.Session()
        creds = session.get_credentials()
        if creds is None:
            logger.warning(
                "AWS credentials not available for OpenSearch - falling back"
            )
            return None

        auth = AWSV4SignerAuth(
            creds,
            config.OPENSEARCH_REGION,
            config.OPENSEARCH_SERVICE,
        )
        _opensearch_client = OpenSearch(
            hosts=[{"host": config.OPENSEARCH_HOST, "port": 443}],
            http_auth=auth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            timeout=config.PINECONE_TIMEOUT,
        )
        # Lightweight ping to fail fast on bad endpoint/auth.
        _opensearch_client.ping()
        logger.info(f"✓ Connected to OpenSearch index: {config.OPENSEARCH_INDEX}")
        return _opensearch_client
    except Exception as e:
        logger.warning(f"Could not initialize OpenSearch: {e} - falling back")
        return None


def _get_qdrant_client():
    """
    Get or initialize Qdrant client (local or remote).

    Supports:
      - Remote Qdrant server via QDRANT_URL env var
      - Local on-disk storage via QDRANT_PATH env var
      - In-memory storage as fallback for testing
    """
    global _qdrant_client

    if _qdrant_client is not None:
        return _qdrant_client

    if QdrantClient is None:
        logger.warning("qdrant-client is not installed; cannot use Qdrant backend")
        return None

    qdrant_url = os.getenv("QDRANT_URL")
    qdrant_api_key = os.getenv("QDRANT_API_KEY")
    qdrant_path = os.getenv("QDRANT_PATH")

    try:
        if qdrant_url:
            _qdrant_client = QdrantClient(
                url=qdrant_url,
                api_key=qdrant_api_key,
                timeout=config.PINECONE_TIMEOUT,
            )
            logger.info("Connected to Qdrant at %s", qdrant_url)
        elif qdrant_path:
            _qdrant_client = QdrantClient(path=qdrant_path)
            logger.info("Connected to Qdrant (on-disk) at %s", qdrant_path)
        else:
            _qdrant_client = QdrantClient(location=":memory:")
            logger.info(
                "Using in-memory Qdrant instance (no QDRANT_URL or QDRANT_PATH set)"
            )

        _ensure_qdrant_collection(_qdrant_client)
        return _qdrant_client
    except Exception as e:
        logger.warning("Could not initialize Qdrant: %s - falling back", e)
        return None


def _ensure_qdrant_collection(client) -> None:
    """
    Ensure the configured Qdrant collection exists with expected vector schema.
    """
    collection_name = os.getenv("QDRANT_COLLECTION", config.PINECONE_INDEX)
    try:
        exists = client.collection_exists(collection_name=collection_name)
    except Exception:
        try:
            client.get_collection(collection_name=collection_name)
            exists = True
        except Exception:
            exists = False

    if exists:
        return

    if VectorParams is None or Distance is None:
        raise VectorSearchError(
            "qdrant-client models unavailable for collection creation",
            index_name=collection_name,
        )

    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=int(config.FINGERPRINT_BITS),
            distance=Distance.COSINE,
        ),
    )
    logger.info(
        "Created Qdrant collection '%s' (size=%d, distance=cosine)",
        collection_name,
        int(config.FINGERPRINT_BITS),
    )


@circuit_breaker(failure_threshold=5, reset_timeout=30, name="Qdrant-DB")
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    retry=retry_if_exception_type((Exception,)),
    reraise=True,
)
def _query_qdrant_with_retry(vector: List[float], top_k: int) -> List[Dict[str, Any]]:
    """Query Qdrant collection with retry logic and circuit breaker."""
    client = _get_qdrant_client()
    if client is None:
        raise VectorSearchError("Qdrant client unavailable")

    collection_name = os.getenv("QDRANT_COLLECTION", config.PINECONE_INDEX)
    try:
        results = client.search(
            collection_name=collection_name,
            query_vector=vector,
            limit=top_k,
            with_payload=True,
        )
        return [{"metadata": hit.payload or {}, "score": hit.score} for hit in results]
    except Exception as e:
        logger.warning("Qdrant query failed (will retry if circuit closed): %s", e)
        raise VectorSearchError(
            f"Qdrant query failed: {e}",
            index_name=collection_name,
            query_vector_size=len(vector),
        ) from e


def get_vector_backend_status() -> Dict[str, Any]:
    """
    Resolve active vector backend status for health/data endpoints.

    This reports what backend *would* be used for a query (opensearch/pinecone/mock),
    but it does not know yet whether a particular call will fall back to mock.
    """
    configured = (config.VECTOR_DB_BACKEND or "pinecone").strip().lower()

    if configured == "mock":
        return {"configured": configured, "active": "mock", "ready": True}

    if configured == "local":
        # Do not build/build index at health-check time; report readiness by cache presence.
        ready = _local_cache_path().exists()
        return {
            "configured": configured,
            "active": "local",
            "ready": ready,
        }

    if configured == "opensearch":
        client = _get_opensearch_client()
        return {
            "configured": configured,
            "active": "opensearch" if client is not None else "mock",
            "ready": client is not None,
        }

    if configured == "qdrant":
        client = _get_qdrant_client()
        return {
            "configured": configured,
            "active": "qdrant" if client is not None else "mock",
            "ready": client is not None,
        }

    if configured == "pinecone":
        index = _get_pinecone_index()
        return {
            "configured": configured,
            "active": "pinecone" if index is not None else "mock",
            "ready": index is not None,
        }

    # auto mode: prefer OpenSearch when configured/reachable, then Qdrant, then Pinecone.
    client = _get_opensearch_client()
    if client is not None:
        return {"configured": configured, "active": "opensearch", "ready": True}
    qdrant = _get_qdrant_client()
    if qdrant is not None:
        return {"configured": configured, "active": "qdrant", "ready": True}
    index = _get_pinecone_index()
    if index is not None:
        return {"configured": configured, "active": "pinecone", "ready": True}
    return {"configured": configured, "active": "mock", "ready": False}


def _format_drug_from_metadata(metadata: Dict[str, Any]) -> str:
    drug_name = metadata.get("name", "Unknown")
    smiles = metadata.get("smiles", "Not available")
    side_effects = metadata.get("known_side_effects", "None listed")
    targets = metadata.get("targets", "Unknown")
    return (
        f"{drug_name} | SMILES: {smiles} | Side Effects: {side_effects} | "
        f"Targets: {targets}"
    )


def find_similar_drugs(vector: List[int], top_k: Optional[int] = None) -> List[str]:
    """
    Queries the database for similar drugs using vector similarity search.

    Args:
        vector: Molecular fingerprint as a list of integers
        top_k: Number of similar drugs to return (default: from config)

    Returns:
        List of formatted drug strings with structure information:
        ["Drug Name | SMILES: ... | Side Effects: ... | Targets: ...", ...]

    Raises:
        VectorSearchError: If vector search fails and no fallback available
    """
    # Validate vector
    if not vector or len(vector) != config.FINGERPRINT_BITS:
        raise VectorSearchError(
            f"Invalid vector size: expected {config.FINGERPRINT_BITS}, got {len(vector) if vector else 0}",
            query_vector_size=len(vector) if vector else 0,
        )

    # Convert vector to float (Pinecone requires float vectors)
    vector_float = [float(x) for x in vector]
    status = get_vector_backend_status()
    active_backend = status["active"]

    if active_backend == "mock":
        logger.info("Using mock data for vector search")
        _metrics.record_search("mock")
        return _get_mock_drugs()

    if active_backend == "local":
        effective_top_k = top_k if top_k is not None else config.OPENSEARCH_TOP_K
        logger.info(
            f"Searching for {effective_top_k} similar drugs locally (ChEMBL cache)..."
        )
        t0 = time.time()
        try:
            found = _query_local(vector_float, effective_top_k)
            if found:
                _metrics.record_search("local")
                logger.info(
                    f"Local search: {len(found)} results in {time.time()-t0:.2f}s"
                )
                return found
            logger.warning(
                "Local vector search returned no matches; falling back to mock"
            )
            _metrics.record_search("local", fell_back=True)
            return _get_mock_drugs()
        except Exception as e:
            logger.error(f"Local vector search failed: {e}", exc_info=True)
            logger.warning("Falling back to mock data due to error")
            _metrics.record_search("local", fell_back=True, error=True)
            return _get_mock_drugs()

    if active_backend == "opensearch":
        effective_top_k = top_k if top_k is not None else config.OPENSEARCH_TOP_K
        logger.info(f"Searching for {effective_top_k} similar drugs in OpenSearch...")
        t0 = time.time()
        try:
            results = _query_opensearch_with_retry(vector_float, effective_top_k)
            hits = (results or {}).get("hits", {}).get("hits", [])
            found_drugs = []
            for hit in hits:
                metadata = hit.get("_source", {}) or {}
                found_drugs.append(_format_drug_from_metadata(metadata))
            if found_drugs:
                _metrics.record_search("opensearch")
                logger.info(
                    f"OpenSearch: {len(found_drugs)} results in {time.time()-t0:.2f}s"
                )
                return found_drugs
            logger.warning("OpenSearch returned no matches; falling back to mock data")
            _metrics.record_search("opensearch", fell_back=True)
            return _get_mock_drugs()
        except Exception as e:
            logger.error(f"OpenSearch vector search failed: {e}", exc_info=True)
            logger.warning("Falling back to mock data due to error")
            _metrics.record_search("opensearch", fell_back=True, error=True)
            return _get_mock_drugs()

    if active_backend == "qdrant":
        effective_top_k = top_k if top_k is not None else config.OPENSEARCH_TOP_K
        logger.info(f"Searching for {effective_top_k} similar drugs in Qdrant...")
        t0 = time.time()
        try:
            hits = _query_qdrant_with_retry(vector_float, effective_top_k)
            found_drugs = [_format_drug_from_metadata(h["metadata"]) for h in hits]
            if found_drugs:
                _metrics.record_search("qdrant")
                logger.info(
                    f"Qdrant: {len(found_drugs)} results in {time.time()-t0:.2f}s"
                )
                return found_drugs
            logger.warning("Qdrant returned no matches; falling back to mock data")
            _metrics.record_search("qdrant", fell_back=True)
            return _get_mock_drugs()
        except Exception as e:
            logger.error(f"Qdrant vector search failed: {e}", exc_info=True)
            logger.warning("Falling back to mock data due to error")
            _metrics.record_search("qdrant", fell_back=True, error=True)
            return _get_mock_drugs()

    # Default active backend is Pinecone.
    effective_top_k = top_k if top_k is not None else config.PINECONE_TOP_K
    index = _get_pinecone_index()
    if index is None:
        logger.info("Pinecone unavailable, using mock data for vector search")
        _metrics.record_search("pinecone", fell_back=True)
        return _get_mock_drugs()

    logger.info(f"Searching for {effective_top_k} similar drugs in Pinecone...")
    t0 = time.time()
    try:
        results = _query_pinecone_with_retry(index, vector_float, effective_top_k)
        found_drugs = []
        for match in results["matches"]:
            metadata = match.get("metadata", {}) or {}
            found_drugs.append(_format_drug_from_metadata(metadata))
        _metrics.record_search("pinecone")
        logger.info(f"Pinecone: {len(found_drugs)} results in {time.time()-t0:.2f}s")
        return found_drugs

    except Exception as e:
        logger.error(f"Vector search failed: {e}", exc_info=True)
        logger.warning("Falling back to mock data due to error")
        _metrics.record_search("pinecone", fell_back=True, error=True)
        return _get_mock_drugs()


@circuit_breaker(failure_threshold=5, reset_timeout=30, name="Pinecone-DB")
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    retry=retry_if_exception_type((Exception,)),
    reraise=True,
)
def _query_pinecone_with_retry(index, vector: List[float], top_k: int):
    """
    Query Pinecone with retry logic and circut breaker.
    """
    try:
        return index.query(vector=vector, top_k=top_k, include_metadata=True)
    except Exception as e:
        logger.warning(f"Pinecone query failed (will retry if circuit closed): {e}")
        raise VectorSearchError(
            f"Pinecone query failed: {str(e)}",
            index_name=config.PINECONE_INDEX,
            query_vector_size=len(vector),
        ) from e


@circuit_breaker(failure_threshold=5, reset_timeout=30, name="OpenSearch-DB")
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    retry=retry_if_exception_type((Exception,)),
    reraise=True,
)
def _query_opensearch_with_retry(vector: List[float], top_k: int):
    """
    Query OpenSearch vector index with retry logic and circuit breaker.
    """
    client = _get_opensearch_client()
    if client is None:
        raise VectorSearchError("OpenSearch client unavailable")
    try:
        body = {
            "size": top_k,
            "query": {
                "knn": {
                    config.OPENSEARCH_VECTOR_FIELD: {
                        "vector": vector,
                        "k": top_k,
                    }
                }
            },
        }
        return client.search(index=config.OPENSEARCH_INDEX, body=body)
    except Exception as e:
        logger.warning(f"OpenSearch query failed (will retry if circuit closed): {e}")
        raise VectorSearchError(
            f"OpenSearch query failed: {str(e)}",
            index_name=config.OPENSEARCH_INDEX,
            query_vector_size=len(vector),
        ) from e


def _get_mock_drugs() -> List[str]:
    """
    Return mock drug data for testing/fallback.

    Returns:
        List of formatted mock drug strings
    """
    return [
        "Mock Drug A | SMILES: CC(=O)O | Side Effects: Nausea | Targets: Unknown",
        "Mock Drug B | SMILES: CC(C)CC1=CC=C(C=C1)C(C)C(=O)O | Side Effects: Headache | Targets: Unknown",
        "Mock Drug C | SMILES: CC1=CC=C(C=C1)C(=O)O | Side Effects: Dizziness | Targets: Unknown",
    ]
