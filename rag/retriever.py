"""ChromaDB retrieval interface for CostSherlock RAG pipeline."""

import logging
from typing import Optional

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

logger = logging.getLogger(__name__)

_COLLECTION_NAME = "costsherlock_docs"


class CostSherlockRetriever:
    """Retrieves relevant document chunks from the ChromaDB knowledge base.

    Wraps a ChromaDB collection with a simple query interface.  Supports
    optional service-scoped filtering via ChromaDB's metadata ``where``
    clause so callers can restrict results to a specific AWS service.

    Usage::

        retriever = CostSherlockRetriever()
        hits = retriever.retrieve("why did NAT Gateway costs spike?", k=5)
        hits = retriever.retrieve("multi-az pricing", k=3, service_filter="rds")
    """

    def __init__(
        self,
        db_path: str = "./chroma_db",
        collection_name: str = _COLLECTION_NAME,
    ) -> None:
        """Connect to an existing ChromaDB collection.

        Args:
            db_path: Path to the persistent ChromaDB storage directory.
            collection_name: Name of the collection to query.

        Raises:
            ValueError: If the collection does not exist.  Run
                ``python rag/ingest.py`` first to build the knowledge base.
        """
        embedding_fn = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
        client = chromadb.PersistentClient(path=db_path)

        try:
            self._collection = client.get_collection(
                name=collection_name,
                embedding_function=embedding_fn,
            )
        except Exception as exc:
            raise ValueError(
                f"Collection '{collection_name}' not found at '{db_path}'. "
                "Run `python rag/ingest.py` first to build the knowledge base."
            ) from exc

        logger.info(
            "Retriever ready — collection='%s', total_chunks=%d",
            collection_name,
            self._collection.count(),
        )

    def retrieve(
        self,
        query: str,
        k: int = 5,
        service_filter: Optional[str] = None,
    ) -> list[dict]:
        """Retrieve the k most relevant chunks for a natural-language query.

        Args:
            query: The question or context description to search for.
            k: Maximum number of results to return.
            service_filter: When provided, restricts results to chunks whose
                ``service_mentioned`` metadata field exactly equals this value
                (e.g. ``'ec2'``, ``'rds'``, ``'nat_gateway'``).  Values come
                from the service labels assigned during ingest.

        Returns:
            List of result dicts, ordered by descending similarity score::

                [
                    {
                        "text":   str,    # chunk content
                        "source": str,    # source filename, e.g. "rds_instance_pricing.md"
                        "score":  float,  # cosine similarity in [0, 1]; higher = more relevant
                    },
                    ...
                ]

            May return fewer than k items if the collection (or the filtered
            subset) has fewer matching documents.
        """
        where = (
            {"service_mentioned": {"$eq": service_filter}}
            if service_filter
            else None
        )

        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=k,
                where=where,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            # ChromaDB raises if k > number of items matching the where filter.
            # Retry once without a limit constraint — return whatever exists.
            logger.warning(
                "Query failed (k=%d, filter=%s): %s — retrying with k=1",
                k,
                service_filter,
                exc,
            )
            results = self._collection.query(
                query_texts=[query],
                n_results=1,
                where=where,
                include=["documents", "metadatas", "distances"],
            )

        docs = results["documents"][0]
        metas = results["metadatas"][0]
        distances = results["distances"][0]

        output: list[dict] = []
        for doc, meta, dist in zip(docs, metas, distances):
            # ChromaDB cosine distance: 0.0 = identical, 1.0 = orthogonal.
            # Convert to a familiar similarity score in [0, 1].
            score = round(max(0.0, 1.0 - dist), 4)
            output.append(
                {
                    "text": doc,
                    "source": meta.get("source", "unknown"),
                    "score": score,
                }
            )

        return output


if __name__ == "__main__":
    import sys

    # Windows consoles default to CP1252; force UTF-8 so markdown text prints cleanly.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
    )

    retriever = CostSherlockRetriever()

    test_cases: list[tuple[str, Optional[str]]] = [
        ("Why did NAT Gateway data processing costs spike this month?", None),
        ("How much does a db.r5.2xlarge Multi-AZ instance cost per month?", "rds"),
        ("Lambda function timing out and charging for full duration", "lambda"),
        ("S3 lifecycle policy was deleted and objects are not transitioning", "s3"),
        ("Reserved instance expired and costs reverted to on-demand", None),
    ]

    sep = "-" * 70
    for query, svc in test_cases:
        print(f"\n{sep}")
        label = f"  service_filter={svc!r}" if svc else "  (no filter)"
        print(f"  QUERY : {query}")
        print(label)
        print(sep)

        hits = retriever.retrieve(query, k=3, service_filter=svc)
        for rank, hit in enumerate(hits, start=1):
            print(f"\n  [{rank}] score={hit['score']:.4f}  source={hit['source']}")
            # Print a short preview (first 200 chars of the chunk)
            preview = hit["text"].replace("\n", " ")[:200]
            print(f"      {preview}...")

    print(f"\n{sep}\nAll test queries complete.\n")
