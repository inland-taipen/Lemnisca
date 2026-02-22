"""
Retrieval layer — TF-IDF over PDF chunks, no external RAG libraries.

Chunking: each PDF is split into overlapping windows (~1 600 chars, ~400 tokens)
with 200-char overlap so context is not lost at boundaries.  At query time the
same TF-IDF vocabulary is reused to vectorise the question and rank chunks by
cosine similarity.
"""

import math
import pickle
import re
from collections import defaultdict
from pathlib import Path
from typing import Optional

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None  # type: ignore[assignment,misc]


# Paths & tunables


_DOCS_DIR = Path(__file__).resolve().parent.parent / "clearpath_docs"
_CACHE_PATH = Path(__file__).resolve().parent / ".rag_cache.pkl"
_CHUNK_SIZE = 1600
_OVERLAP     = 200
_DEFAULT_K   = 5
_FLOOR_SCORE = 0.05


# PDF extraction


def _pages_from_pdf(path: Path) -> list[tuple[int, str]]:
    if PdfReader is None:
        raise ImportError("pypdf is required but not installed")
    reader = PdfReader(str(path))
    out: list[tuple[int, str]] = []
    for idx, pg in enumerate(reader.pages, 1):
        body = (pg.extract_text() or "").strip()
        if body:
            out.append((idx, body))
    return out


# Chunking


def _split_into_windows(text: str) -> list[str]:
    windows, pos, length = [], 0, len(text)
    while pos < length:
        end = min(pos + _CHUNK_SIZE, length)
        fragment = text[pos:end].strip()
        if fragment:
            windows.append(fragment)
        if end >= length:
            break
        pos += _CHUNK_SIZE - _OVERLAP
    return windows


def _build_chunk_corpus(docs_dir: Path = _DOCS_DIR) -> list[dict]:
    corpus: list[dict] = []
    for pdf in sorted(docs_dir.glob("*.pdf")):
        try:
            pages = _pages_from_pdf(pdf)
        except Exception as exc:
            print(f"[rag] skipping {pdf.name}: {exc}")
            continue
        seq = 0
        for page_no, page_text in pages:
            for window in _split_into_windows(page_text):
                corpus.append({
                    "text": window,
                    "document": pdf.name,
                    "page": page_no,
                    "chunk_index": seq,
                })
                seq += 1
    print(f"[rag] corpus ready: {len(corpus)} chunks from {len(list(docs_dir.glob('*.pdf')))} files")
    return corpus


# Tokeniser & stop-words


_STOP = frozenset(
    "the a an and or but in on at to for of with is it this that are was were be "
    "been has have had do does did will would could should may might i my we our "
    "you your he she they their its from by as if so not no can get also than then".split()
)

def _tokenise(text: str) -> list[str]:
    lowered = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    return [w for w in lowered.split() if len(w) > 1 and w not in _STOP]


# TF-IDF


def _compute_vectors(corpus: list[dict]) -> tuple[list[dict[str, float]], dict[str, float]]:
    n = len(corpus)
    doc_freq: dict[str, int] = defaultdict(int)
    tf_per_chunk: list[dict[str, float]] = []

    for chunk in corpus:
        tokens = _tokenise(chunk["text"])
        freq: dict[str, float] = defaultdict(float)
        for t in tokens:
            freq[t] += 1.0
        total = sum(freq.values()) or 1.0
        normalised = {t: c / total for t, c in freq.items()}
        tf_per_chunk.append(normalised)
        for t in set(tokens):
            doc_freq[t] += 1

    idf = {t: math.log((n + 1) / (df + 1)) + 1.0 for t, df in doc_freq.items()}

    vectors = [
        {t: w * idf.get(t, 0.0) for t, w in tf.items()}
        for tf in tf_per_chunk
    ]
    return vectors, idf


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(a.get(k, 0.0) * v for k, v in b.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


# Index


class _Index:
    __slots__ = ("corpus", "vectors", "idf")

    def __init__(self) -> None:
        self.corpus: list[dict] = []
        self.vectors: list[dict[str, float]] = []
        self.idf: dict[str, float] = {}

    def build_from_scratch(self) -> None:
        self.corpus = _build_chunk_corpus()
        self.vectors, self.idf = _compute_vectors(self.corpus)
        with open(_CACHE_PATH, "wb") as fh:
            pickle.dump({"corpus": self.corpus, "vectors": self.vectors, "idf": self.idf}, fh)
        print(f"[rag] index persisted to {_CACHE_PATH}")

    def load_or_build(self) -> None:
        if _CACHE_PATH.exists():
            try:
                with open(_CACHE_PATH, "rb") as fh:
                    blob = pickle.load(fh)
                self.corpus = blob["corpus"]
                self.vectors = blob["vectors"]
                self.idf = blob["idf"]
                print(f"[rag] loaded cached index ({len(self.corpus)} chunks)")
                return
            except Exception as exc:
                print(f"[rag] cache unusable ({exc}), rebuilding")
        self.build_from_scratch()

    def _vectorise_query(self, text: str) -> dict[str, float]:
        tokens = _tokenise(text)
        freq: dict[str, float] = defaultdict(float)
        for t in tokens:
            freq[t] += 1.0
        total = sum(freq.values()) or 1.0
        return {t: (c / total) * self.idf.get(t, 0.0) for t, c in freq.items()}

    def search(self, query: str, k: int = _DEFAULT_K) -> list[dict]:
        qv = self._vectorise_query(query)
        scored = []
        for i, cv in enumerate(self.vectors):
            s = _cosine(qv, cv)
            if s >= _FLOOR_SCORE:
                scored.append((s, i))
        scored.sort(reverse=True, key=lambda pair: pair[0])

        results: list[dict] = []
        seen: set[tuple] = set()
        for score, idx in scored[: k * 3]:
            c = self.corpus[idx]
            key = (c["document"], c["chunk_index"])
            if key in seen:
                continue
            seen.add(key)
            results.append({**c, "relevance_score": round(score, 4)})
            if len(results) >= k:
                break
        return results

    @staticmethod
    def _score(a: dict[str, float], b: dict[str, float]) -> float:
        return _cosine(a, b)


# Singleton access


_instance: Optional[_Index] = None

def _get() -> _Index:
    global _instance
    if _instance is None:
        _instance = _Index()
        _instance.load_or_build()
    return _instance

def warm_up_index() -> None:
    """Called once at app startup so the first query doesn't pay the build cost."""
    print("[rag] warming index …")
    _get()
    print("[rag] ready")

def retrieve_chunks(query: str, top_k: int = _DEFAULT_K) -> list[dict]:
    return _get().search(query, k=top_k)
