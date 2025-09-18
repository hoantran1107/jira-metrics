import re
from typing import List, Optional

from dotenv import load_dotenv

from src.confluence_client import get_space_corpus

load_dotenv()


def _tokenize(text: str) -> List[str]:
    return [t.lower() for t in re.findall(r"\w+", text)]


def _build_query_from_metrics_summary(summary_markdown: str) -> str:
    return summary_markdown[:2000]


def retrieve_confluence_context(
    *,
    space_key: str,
    summary_markdown: str,
    top_k: int = 5,
    limit_pages: int = 200,
) -> Optional[str]:
    try:
        from rank_bm25 import BM25Okapi  # type: ignore
    except Exception:  # pragma: no cover
        return None

    corpus = get_space_corpus(space_key, limit=limit_pages)
    if not corpus:
        return None

    documents = [doc["text"] for doc in corpus]
    tokenized_corpus = [_tokenize(d) for d in documents]
    bm25 = BM25Okapi(tokenized_corpus)
    query_text = _build_query_from_metrics_summary(summary_markdown)
    tokenized_query = _tokenize(query_text)
    scores = bm25.get_scores(tokenized_query)

    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[
        :top_k
    ]
    chunks: List[str] = []
    for idx in top_indices:
        title = corpus[idx]["title"]
        text = documents[idx]
        chunks.append(f"# {title}\n{text[:2000]}")
    if not chunks:
        return None
    return "\n\n---\n\n".join(chunks)
