"""
Citation overlap / grounding for LLM explanations (Agent 5).

Compares explanation sentences to retrieved CPIC/RAG passages using word and
substring overlap. No extra model calls.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence

# Very common English words; avoid counting them as "content" overlap.
_STOP = frozenset(
    """
    the and for with from that this were was are has have had not but can may
    its their they them then than when what which while will would could should
    patient drug gene risk level more most some such also into about over after
    before between through during using used use per via
    """.split()
)


def _sentences(text: str) -> List[str]:
    if not (text or "").strip():
        return []
    t = re.sub(r"\s+", " ", text.strip())
    parts = re.split(r"(?<=[.!?])\s+", t)
    out: List[str] = []
    for p in parts:
        p = p.strip()
        if len(p) > 12:
            out.append(p)
    return out


def _content_words(s: str) -> List[str]:
    words = re.findall(r"[a-z0-9]{4,}", s.lower())
    return [w for w in words if w not in _STOP]


def _sentence_grounded(sentence: str, corpus: str) -> bool:
    if not sentence.strip():
        return True
    s_low = sentence.lower()
    c = corpus.lower()
    words = _content_words(sentence)
    if not words:
        return False
    c_words = set(_content_words(corpus))
    hits = sum(1 for w in words if w in c_words)
    if hits / len(words) >= 0.18:
        return True
    # Substring: catch paraphrases that share long spans with CPIC text
    clean = re.sub(r"\s+", " ", s_low)
    for n in (48, 36, 28, 20):
        if len(clean) < n:
            continue
        step = max(4, n // 8)
        for i in range(0, len(clean) - n + 1, step):
            if clean[i : i + n] in c:
                return True
    return False


def compute_explanation_grounding(
    explanation: str, retrieved_passages: Sequence[str]
) -> Dict[str, Any]:
    """
    Fraction of explanation sentences with lexical overlap against retrieved text.

    If there are no retrieved passages, grounded_sentence_fraction is None and
    ungrounded_sentences lists all sentences (honest "no retrieval to ground against").
    """
    passages = [p for p in retrieved_passages if p and str(p).strip()]
    corpus = "\n\n".join(str(p) for p in passages)
    sents = _sentences(explanation)
    if not sents:
        return {
            "grounded_sentence_fraction": None,
            "grounded_sentence_count": 0,
            "ungrounded_sentence_count": 0,
            "sentence_count": 0,
            "ungrounded_sentences": [],
            "retrieval_passage_count": len(passages),
            "retrieval_char_count": len(corpus),
        }

    if not corpus.strip():
        return {
            "grounded_sentence_fraction": None,
            "grounded_sentence_count": 0,
            "ungrounded_sentence_count": len(sents),
            "sentence_count": len(sents),
            "ungrounded_sentences": sents[:12],
            "retrieval_passage_count": 0,
            "retrieval_char_count": 0,
        }

    ungrounded: List[str] = []
    grounded_n = 0
    for s in sents:
        if _sentence_grounded(s, corpus):
            grounded_n += 1
        else:
            ungrounded.append(s)

    total = len(sents)
    frac = grounded_n / total if total else None
    return {
        "grounded_sentence_fraction": frac,
        "grounded_sentence_count": grounded_n,
        "ungrounded_sentence_count": len(ungrounded),
        "sentence_count": total,
        "ungrounded_sentences": ungrounded[:12],
        "retrieval_passage_count": len(passages),
        "retrieval_char_count": len(corpus),
    }
