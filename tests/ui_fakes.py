"""A fake DocBot API for UI tests: an httpx MockTransport with canned responses."""

import json
from typing import Any

import httpx

DOC = {"id": "d1", "filename": "DM-STD-BRK-001_Brake_System_Design_Standard.pdf",
       "doc_type": "pdf", "size_bytes": 3232, "page_count": 3, "ocr_page_count": 0,
       "chunk_count": 3, "status": "indexed", "created_at": "2026-10-25T08:00:00Z"}
STATUS = {"retriever": "vector", "generator": "extractive", "embed_model": "BAAI/bge-small-en-v1.5",
          "documents": 1, "chunks": 3, "fallbacks": [], "notices": []}
ANSWER = {"answer": "Front | 276 mm | 3.5 mm [1]", "grounded": True, "retriever": "vector",
          "generator_used": "extractive", "fallback_reason": None, "latency_ms": 12.0,
          "citations": [{"n": 1, "chunk_id": "c1", "document_id": "d1", "filename": DOC["filename"],
                         "page": 2, "score": 0.88, "passage": "Front | 276 mm | 3.5 mm"}]}
EVAL = {"summary": {"cases": 2, "hit_rate_at_k": 100.0, "answer_accuracy": 50.0,
                    "refusal_accuracy": 100.0, "retriever": "vector", "generator": "extractive",
                    "top_k": 4},
        "results": [
            {"question": "What is the minimum thickness?", "expected_file": DOC["filename"],
             "expected_page": 2, "retrieved_files": [DOC["filename"]], "hit": True,
             "fact_found": True, "expect_refusal": False, "refused": False,
             "refusal_correct": True},
            {"question": "What is the top speed?", "expected_file": None, "expected_page": None,
             "retrieved_files": [], "hit": False, "fact_found": False, "expect_refusal": True,
             "refused": True, "refusal_correct": True}]}


class FakeApi:
    def __init__(self, **overrides: Any) -> None:
        self.routes: dict[tuple[str, str], tuple[int, Any]] = {
            ("GET", "/health"): (200, {"status": "ok"}),
            ("GET", "/status"): (200, STATUS),
            ("GET", "/documents"): (200, [DOC]),
            ("GET", "/documents/d1/chunks"): (200, [
                {"id": "c1", "page": 2, "ordinal": 1, "source": "text",
                 "text": "Front | 276 mm | 3.5 mm"}]),
            ("DELETE", "/documents/d1"): (200, {"deleted_id": "d1"}),
            ("POST", "/ask"): (200, ANSWER),
            ("POST", "/documents"): (201, {"document": DOC, "duplicate": False}),
            ("POST", "/samples/load"): (200, {"indexed": 8, "duplicates": 0, "failed": []}),
            ("POST", "/eval/run"): (200, EVAL),
        }
        self.routes.update(overrides)
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        status, body = self.routes.get((request.method, request.url.path), (404, {
            "code": "not_found", "message": "No such route."}))
        return httpx.Response(status, content=json.dumps(body).encode(),
                              headers={"content-type": "application/json"})

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)

    def calls(self, method: str, path: str) -> int:
        return sum(1 for r in self.requests if r.method == method and r.url.path == path)


def down_transport() -> httpx.MockTransport:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    return httpx.MockTransport(refuse)
