import uuid
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from rag_pipeline import retrieve_chunks, warm_up_index
from router import classify_and_route, persist_decision
from evaluator import run_quality_checks, describe_flags
from llm_client import generate_answer

load_dotenv()

# Conversation memory (in-process; swap for Redis/DB in production)


_sessions: dict[str, list[dict]] = {}
_HISTORY_CAP = 6

def _recall(sid: str) -> list[dict]:
    return _sessions.get(sid, [])

def _memorise(sid: str, role: str, text: str) -> None:
    buf = _sessions.setdefault(sid, [])
    buf.append({"role": role, "content": text})
    limit = _HISTORY_CAP * 2
    if len(buf) > limit:
        _sessions[sid] = buf[-limit:]


# Lifespan — pre-warm the retrieval index so the first query is fast


@asynccontextmanager
async def lifespan(_app: FastAPI):
    warm_up_index()
    yield


# Application


app = FastAPI(
    title="ClearPath Support API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Wire-format models


class Inquiry(BaseModel):
    question: str
    conversation_id: Optional[str] = None

class TokenCount(BaseModel):
    prompt: int = Field(..., alias="input")
    completion: int = Field(..., alias="output")

    class Config:
        populate_by_name = True

class ResponseMeta(BaseModel):
    model_used: str
    classification: str
    tokens: TokenCount
    latency_ms: int
    chunks_retrieved: int
    evaluator_flags: list[str]
    flag_message: str = ""
    rule_triggered: str = ""

    class Config:
        protected_namespaces = ()

class SourceRef(BaseModel):
    document: str
    page: Optional[int] = None
    relevance_score: Optional[float] = None

class Reply(BaseModel):
    answer: str
    metadata: ResponseMeta
    sources: list[SourceRef]
    conversation_id: str


# POST /query — the single endpoint that ties all layers together


@app.post("/query", response_model=Reply)
async def handle_query(body: Inquiry) -> Reply:
    question = body.question.strip()
    if not question:
        raise HTTPException(400, "question must not be empty")

    sid = body.conversation_id or f"conv_{uuid.uuid4().hex[:12]}"
    history = _recall(sid)

    decision = classify_and_route(question)
    chunks = retrieve_chunks(question, top_k=5)

    answer, tok_in, tok_out, latency = generate_answer(
        question=question,
        chunks=chunks,
        model=decision["model_used"],
        history=history,
    )

    decision["tokens_input"] = tok_in
    decision["tokens_output"] = tok_out
    decision["latency_ms"] = latency
    persist_decision(decision)

    flags = run_quality_checks(answer, len(chunks), question)
    flag_msg = describe_flags(flags)

    _memorise(sid, "user", question)
    _memorise(sid, "assistant", answer)

    return Reply(
        answer=answer,
        metadata=ResponseMeta(
            model_used=decision["model_used"],
            classification=decision["classification"],
            tokens=TokenCount(input=tok_in, output=tok_out),
            latency_ms=latency,
            chunks_retrieved=len(chunks),
            evaluator_flags=flags,
            flag_message=flag_msg,
            rule_triggered=decision["rule_triggered"],
        ),
        sources=[
            SourceRef(
                document=c["document"],
                page=c.get("page"),
                relevance_score=c.get("relevance_score"),
            )
            for c in chunks
        ],
        conversation_id=sid,
    )

@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
