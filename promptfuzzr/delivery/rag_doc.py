"""RAG-corpus delivery �?" writes payload into a document that gets
indexed into the target's retrieval store, so it fires whenever any
future session retrieves it (propagation=cross_session candidate).

Supports a `position` kwarg (start|middle|end) for Study 3
placement-sensitivity testing.
"""

from __future__ import annotations
from pathlib import Path
from datetime import datetime
import uuid

# A simple in-memory "RAG store" shared across channel instances during
# a single fuzz run. In a production setting this would be connected to
# an actual retriever (Chroma, FAISS, etc.).
_RAG_STORE: dict[str, dict] = {}


class RagDocChannel:
    name = "rag_doc"

    def __init__(self, store: dict | None = None) -> None:
        self.store = store or _RAG_STORE

    def deliver(self, payload: str, position: str = "end", **kwargs) -> str:
        """Index `payload` into the RAG store at the given position.

        Returns a reference string that cleanup() uses to remove the
        document again.
        """
        doc_id = str(uuid.uuid4())
        self.store[doc_id] = {
            "payload": payload,
            "position": position,
            "indexed_at": str(datetime.now()),
        }
        return doc_id

    def read_content(self, reference: str) -> str:
        """Return the payload stored at `reference` �?" used by the
        orchestrator to build the "here's the retrieved context" trigger
        prompt sent to the agent.
        """
        doc = self.store.get(reference)
        if doc is None:
            return ""
        return doc["payload"]

    def cleanup(self, reference: str) -> None:
        """Remove the document from the RAG store."""
        self.store.pop(reference, None)