from __future__ import annotations
from pathlib import Path
from datetime import datetime
import uuid

_RAG_STORE: dict[str, dict] = {}


class RagDocChannel:
    name = "rag_doc"

    def __init__(self, store: dict | None = None) -> None:
        self.store = store or _RAG_STORE

    def deliver(self, payload: str, position: str = "end", **kwargs) -> str:
        doc_id = str(uuid.uuid4())
        self.store[doc_id] = {
            "payload": payload,
            "position": position,
            "indexed_at": str(datetime.now()),
        }
        return doc_id

    def read_content(self, reference: str) -> str:
        doc = self.store.get(reference)
        if doc is None:
            return ""
        return doc["payload"]

    def cleanup(self, reference: str) -> None:
        self.store.pop(reference, None)