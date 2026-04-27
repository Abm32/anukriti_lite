"""
Local PGx Retrieval Layer

Provides a simple hybrid retrieval over curated CPIC/PGx JSON files using
Titan embeddings. This replaces the earlier stubbed context in the RAG
pipeline with real, explainable pharmacogenomics snippets.
"""

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from src.embeddings_bedrock import get_embedding
from src.exceptions import LLMError

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BASE_DIR = _REPO_ROOT / "data" / "pgx" / "cpic"
# Bump the cache filename whenever doc-id construction changes.
_CACHE_PATH = _REPO_ROOT / "data" / "models" / "pgx_retriever_index_v2.npz"
_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class PgxDoc:
    doc_id: str
    source: str
    key: str
    text: str


_DOCUMENTS: List[PgxDoc] = []
_EMBEDDINGS: Optional[np.ndarray] = None  # shape: (N, D)
_LOADED: bool = False
_VECTORIZER: Optional[TfidfVectorizer] = None
_EMBED_MODE: str = "unset"  # "titan" | "tfidf"


def _flatten_cpic_obj(obj: Any, prefix: str = "") -> Iterator[Tuple[str, str]]:
    """
    Yield (path_key, value_str) leaves for nested dicts/lists.

    This intentionally matches the keying scheme used by
    `training/lm_finetune/export_pgx_sft_jsonl.py` so that retrieval eval labels
    (meta.source + meta.key) align with indexed doc_ids (<source>::<key>).
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).startswith("_"):
                continue
            p = f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v, dict):
                yield from _flatten_cpic_obj(v, p)
            elif isinstance(v, (str, int, float, bool)):
                yield p, str(v)
            else:
                yield p, json.dumps(v, ensure_ascii=False)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _flatten_cpic_obj(v, f"{prefix}[{i}]")


def _load_cache() -> bool:
    global _DOCUMENTS, _EMBEDDINGS, _VECTORIZER, _EMBED_MODE
    if not _CACHE_PATH.is_file():
        return False
    try:
        data = np.load(_CACHE_PATH, allow_pickle=False)
        emb = data["embeddings"].astype(np.float32, copy=False)
        meta_json = data["meta_json"]
        embed_mode_obj = data.get("embed_mode", "titan")
        if isinstance(embed_mode_obj, np.ndarray):
            embed_mode_list = embed_mode_obj.tolist()
            embed_mode = str(embed_mode_list[0] if embed_mode_list else "titan")
        else:
            embed_mode = str(embed_mode_obj)
        docs: List[PgxDoc] = []
        for s in meta_json.tolist():
            obj = json.loads(s)
            docs.append(
                PgxDoc(
                    doc_id=obj["doc_id"],
                    source=obj["source"],
                    key=obj["key"],
                    text=obj["text"],
                )
            )
        if emb.shape[0] != len(docs):
            return False
        _DOCUMENTS = docs
        _EMBEDDINGS = emb
        _EMBED_MODE = embed_mode
        _VECTORIZER = None  # rebuilt on demand for tfidf
        return True
    except Exception:
        return False


def _save_cache(docs: List[PgxDoc], embeddings: np.ndarray) -> None:
    try:
        meta_json = np.array(
            [
                json.dumps(
                    {
                        "doc_id": d.doc_id,
                        "source": d.source,
                        "key": d.key,
                        "text": d.text,
                    },
                    ensure_ascii=False,
                )
                for d in docs
            ],
            dtype=str,
        )
        np.savez_compressed(
            _CACHE_PATH,
            embeddings=embeddings,
            meta_json=meta_json,
            embed_mode=np.array([_EMBED_MODE], dtype=str),
        )
    except Exception:
        # Non-fatal; retrieval can still work without cache.
        return


def _load_documents() -> None:
    """
    Load CPIC-style PGx JSON files and pre-compute embeddings.
    """
    global _LOADED, _DOCUMENTS, _EMBEDDINGS
    if _LOADED:  # idempotent
        return

    # Try cache first (saves Bedrock calls).
    if _load_cache():
        _LOADED = True
        return

    if not _BASE_DIR.is_dir():
        _LOADED = True
        return

    global _VECTORIZER, _EMBED_MODE
    docs: List[PgxDoc] = []
    embs: List[List[float]] = []
    skipped_files = 0
    skipped_embeddings = 0

    for path in sorted(_BASE_DIR.glob("*.json")):
        data = None
        try:
            with path.open("r") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(f"Skipping unreadable PGx file {path.name}: {exc}")
            skipped_files += 1
            data = None
        if not data:
            continue

        # Flatten each entry to a text blob
        source = path.name
        for key, value_str in _flatten_cpic_obj(data):
            doc_id = f"{source}::{key}"
            text = json.dumps(
                {"source": source, "key": key, "value": value_str}, ensure_ascii=False
            )
            emb = None
            try:
                emb = get_embedding(text)
            except LLMError as exc:
                logger.warning(f"Embedding failed for {doc_id}: {exc}")
                skipped_embeddings += 1
                emb = None
            docs.append(PgxDoc(doc_id=doc_id, source=source, key=key, text=text))
            if emb is not None:
                embs.append(emb)

    if skipped_files or skipped_embeddings:
        logger.warning(
            f"RAG index built with gaps: {skipped_files} file(s) skipped, "
            f"{skipped_embeddings} embedding(s) failed. "
            "Context quality may be reduced."
        )
    if not docs:
        logger.warning(
            "RAG retriever: no documents indexed. All LLM responses will use "
            "the hardcoded fallback context. Check Bedrock Titan credentials and "
            f"that {_BASE_DIR} contains valid JSON files."
        )

    _DOCUMENTS = docs
    if embs and len(embs) == len(docs):
        _EMBED_MODE = "titan"
        embeddings = np.array(embs, dtype=np.float32)
        _VECTORIZER = None
        _EMBEDDINGS = embeddings
        _save_cache(docs, embeddings)
    else:
        # Fall back to a local TF-IDF embedding space if Bedrock embeddings are not usable.
        # This keeps evaluation and demos working in offline / non-AWS environments.
        _EMBED_MODE = "tfidf"
        _VECTORIZER = TfidfVectorizer(
            lowercase=True,
            token_pattern=r"(?u)\b[\w*./-]+\b",  # nosec B106 - token regex, not a password
            ngram_range=(1, 2),
            min_df=1,
            max_features=8192,
        )
        mat = _VECTORIZER.fit_transform([d.text for d in docs])
        _EMBEDDINGS = mat.toarray().astype(np.float32, copy=False)
        _save_cache(docs, _EMBEDDINGS)
    _LOADED = True


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


_GENE_TOKENS = (
    "CYP2D6",
    "CYP2C19",
    "CYP2C9",
    "UGT1A1",
    "SLCO1B1",
    "VKORC1",
    "TPMT",
    "DPYD",
)


def _extract_query_hints(query: str) -> Dict[str, Any]:
    """
    Pull high-signal hints out of the natural-language query.

    Many of our prompts include explicit `source` + `key` (e.g. SFT-derived eval set),
    so we should use those for deterministic filtering before embedding search.
    """
    q = (query or "").strip()
    hints: Dict[str, Any] = {}

    m_src = re.search(r"\bfrom\s+([a-z0-9_.-]+\.json)\b", q, flags=re.IGNORECASE)
    if m_src:
        hints["source"] = m_src.group(1)

    m_key = re.search(r"\bkey\s*[`'\"]([^`'\"]+)[`'\"]", q, flags=re.IGNORECASE)
    if m_key:
        hints["key"] = m_key.group(1).strip()

    m_drug = re.search(
        r"\bDrug of interest\s*:\s*([A-Za-z0-9_.-]+)", q, flags=re.IGNORECASE
    )
    if m_drug:
        hints["drug"] = m_drug.group(1).strip().lower()

    genes: List[str] = []
    for g in _GENE_TOKENS:
        if re.search(rf"\b{re.escape(g)}\b", q, flags=re.IGNORECASE):
            genes.append(g)
    if genes:
        hints["genes"] = genes

    m_rs = re.search(r"\b(rs\d{3,})\b", q, flags=re.IGNORECASE)
    if m_rs:
        hints["rsid"] = m_rs.group(1).lower()

    return hints


def _rewrite_query_for_embedding(query: str, hints: Dict[str, Any]) -> str:
    """
    Convert verbose prompts into a compact, retrieval-oriented query to reduce
    boilerplate dilution.
    """
    parts: List[str] = ["task=pgx_row_lookup"]
    genes = hints.get("genes") or []
    if genes:
        parts.append("genes=" + ",".join(genes))
    if hints.get("drug"):
        parts.append(f"drug={hints['drug']}")
    if hints.get("rsid"):
        parts.append(f"rsid={hints['rsid']}")
    if hints.get("source"):
        parts.append(f"source={hints['source']}")
    if hints.get("key"):
        parts.append(f"key={hints['key']}")

    return "; ".join(parts) if len(parts) > 1 else (query or "")


def _candidate_indices(
    hints: Dict[str, Any], docs: List[PgxDoc]
) -> Optional[np.ndarray]:
    """
    Return indices to consider (filters) or None for "all docs".
    """
    src = (hints.get("source") or "").strip()
    key = (hints.get("key") or "").strip()
    genes = hints.get("genes") or []
    rsid = (hints.get("rsid") or "").strip()

    # Strongest: exact source/key match.
    if src or key:
        keep: List[int] = []
        for i, d in enumerate(docs):
            if src and d.source != src:
                continue
            if key and d.key != key:
                continue
            keep.append(i)
        return np.array(keep, dtype=np.int32)

    # Next: gene token by filename.
    if genes:
        keep = []
        for i, d in enumerate(docs):
            s = d.source.lower()
            if any(g.lower() in s for g in genes):
                keep.append(i)
        if keep:
            return np.array(keep, dtype=np.int32)

    # rsID fallback.
    if rsid:
        keep = []
        for i, d in enumerate(docs):
            if rsid in d.text.lower():
                keep.append(i)
        if keep:
            return np.array(keep, dtype=np.int32)

    return None


def retrieve_docs(query: str, top_k: int = 3) -> List[PgxDoc]:
    """
    Retrieve top_k PGx documents most similar to the query.
    Returns structured docs with stable identifiers (source::key).
    """
    global _VECTORIZER
    _load_documents()
    if not _DOCUMENTS or _EMBEDDINGS is None:
        return []

    hints = _extract_query_hints(query)
    embed_query = _rewrite_query_for_embedding(query, hints)
    cand = _candidate_indices(hints, _DOCUMENTS)
    if cand is not None and cand.size == 0:
        cand = None

    if _EMBED_MODE == "tfidf":
        if _VECTORIZER is None:
            # Cache could have been loaded; rebuild TF-IDF on current docs.
            _VECTORIZER = TfidfVectorizer(
                lowercase=True,
                token_pattern=r"(?u)\b[\w*./-]+\b",  # nosec B106 - token regex, not a password
                ngram_range=(1, 2),
                min_df=1,
                max_features=8192,
            )
            _VECTORIZER.fit([d.text for d in _DOCUMENTS])
        query_emb = (
            _VECTORIZER.transform([embed_query])
            .toarray()[0]
            .astype(np.float32, copy=False)
        )
    else:
        query_emb = np.array(get_embedding(embed_query), dtype=np.float32)
    embs = _EMBEDDINGS

    return [d for d, _ in retrieve_docs_scored(query, top_k=top_k)]


def retrieve_docs_scored(query: str, top_k: int = 3) -> List[Tuple[PgxDoc, float]]:
    """
    Retrieve top_k documents and return (doc, similarity_score).

    The score is cosine similarity in the embedding space:
    - Titan embeddings when available
    - TF-IDF fallback otherwise
    """
    global _VECTORIZER
    _load_documents()
    if not _DOCUMENTS or _EMBEDDINGS is None:
        return []

    hints = _extract_query_hints(query)
    embed_query = _rewrite_query_for_embedding(query, hints)
    cand = _candidate_indices(hints, _DOCUMENTS)
    if cand is not None and cand.size == 0:
        cand = None

    if _EMBED_MODE == "tfidf":
        if _VECTORIZER is None:
            _VECTORIZER = TfidfVectorizer(
                lowercase=True,
                token_pattern=r"(?u)\b[\w*./-]+\b",  # nosec B106 - token regex, not a password
                ngram_range=(1, 2),
                min_df=1,
                max_features=8192,
            )
            _VECTORIZER.fit([d.text for d in _DOCUMENTS])
        query_emb = (
            _VECTORIZER.transform([embed_query])
            .toarray()[0]
            .astype(np.float32, copy=False)
        )
    else:
        query_emb = np.array(get_embedding(embed_query), dtype=np.float32)

    embs = _EMBEDDINGS
    if cand is None:
        scores = (
            embs
            @ query_emb
            / (np.linalg.norm(embs, axis=1) * np.linalg.norm(query_emb) + 1e-8)
        )
        top_indices = np.argsort(-scores)[:top_k]
        return [(_DOCUMENTS[int(i)], float(scores[int(i)])) for i in top_indices]

    sub = embs[cand]
    scores = (
        sub
        @ query_emb
        / (np.linalg.norm(sub, axis=1) * np.linalg.norm(query_emb) + 1e-8)
    )
    k = min(int(top_k), int(scores.shape[0]))
    local_top = np.argsort(-scores)[:k]
    out: List[Tuple[PgxDoc, float]] = []
    for idx in local_top.tolist():
        global_i = int(cand[int(idx)])
        out.append((_DOCUMENTS[global_i], float(scores[int(idx)])))
    return out


def retrieve(query: str, top_k: int = 3) -> List[str]:
    """
    Retrieve top_k PGx documents most similar to the query.

    Returns a list of JSON strings (flattened rows) that can be fed as
    context to the LLM.
    """
    return [d.text for d in retrieve_docs(query, top_k=top_k)]


def get_retriever_status() -> Dict[str, Any]:
    """
    Small status payload for demos/monitoring.

    Note: Calling this may lazily initialize the index (and thus may take time
    the first time it runs).
    """
    _load_documents()
    return {
        "embed_mode": _EMBED_MODE,
        "docs_indexed": len(_DOCUMENTS),
        "base_dir": str(_BASE_DIR),
        "cache_path": str(_CACHE_PATH),
        "cache_present": _CACHE_PATH.is_file(),
    }
