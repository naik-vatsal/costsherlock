"""Document ingestion pipeline for CostSherlock RAG system."""

import logging
from collections import defaultdict
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from langchain_text_splitters import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

# Sorted longest-first so 'nat_gateway' matches before 'nat', 'elasticache' before 'elastic', etc.
_KNOWN_SERVICES: list[str] = sorted(
    [
        "nat_gateway", "elasticache", "cloudwatch", "cloudfront", "cloudtrail",
        "dynamodb", "fargate", "lambda", "ec2", "rds", "ebs", "vpc", "s3",
        "iam", "ecs", "alb", "nlb", "elb", "sqs", "sns",
    ],
    key=len,
    reverse=True,
)

_COLLECTION_NAME = "costsherlock_docs"


def extract_service_mentioned(filename: str) -> str:
    """Extract the primary AWS service name from a document filename.

    Scans the filename stem for known service names (longest match wins).
    Falls back to the first underscore-delimited segment.

    Args:
        filename: Basename of the document file, e.g. 'ec2_ondemand_pricing.md'.

    Returns:
        Lowercase service identifier, e.g. 'ec2', 'rds', 'nat_gateway'.

    Examples:
        >>> extract_service_mentioned('ec2_ondemand_pricing.md')
        'ec2'
        >>> extract_service_mentioned('cost_trap_nat_gateway.md')
        'nat_gateway'
        >>> extract_service_mentioned('troubleshoot_rds_cost_spike.md')
        'rds'
    """
    stem = Path(filename).stem.lower()
    for service in _KNOWN_SERVICES:
        if service in stem:
            return service
    return stem.split("_")[0]


def build_knowledge_base(
    docs_dir: str = "rag/documents",
    db_path: str = "./chroma_db",
    collection_name: str = _COLLECTION_NAME,
) -> dict:
    """Ingest markdown documents into a ChromaDB vector store.

    Reads all .md files from docs_dir, splits them with
    RecursiveCharacterTextSplitter (chunk_size=500, overlap=50), embeds
    each chunk with all-MiniLM-L6-v2, and stores the vectors in a local
    ChromaDB persistent collection.

    Re-running this function deletes and recreates the collection so the
    index stays consistent with the documents directory.

    Args:
        docs_dir: Path to the directory containing .md source documents.
        db_path: Directory path for persistent ChromaDB storage.
        collection_name: Name to use for the ChromaDB collection.

    Returns:
        Summary dict with keys: docs_processed, total_chunks, chunks_per_service.

    Raises:
        FileNotFoundError: If no .md files are found in docs_dir.
    """
    docs_path = Path(docs_dir)
    md_files = sorted(docs_path.glob("*.md"))
    if not md_files:
        raise FileNotFoundError(f"No markdown files found in '{docs_dir}'")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        length_function=len,
    )

    embedding_fn = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    client = chromadb.PersistentClient(path=db_path)

    # Drop and recreate so re-ingestion is always idempotent.
    try:
        client.delete_collection(collection_name)
        logger.info("Dropped existing collection '%s'", collection_name)
    except Exception:
        pass

    collection = client.create_collection(
        name=collection_name,
        embedding_function=embedding_fn,
        metadata={"hnsw:space": "cosine"},
    )

    ids: list[str] = []
    texts: list[str] = []
    metadatas: list[dict] = []
    chunks_per_service: dict[str, int] = defaultdict(int)

    for md_file in md_files:
        raw = md_file.read_text(encoding="utf-8")
        service = extract_service_mentioned(md_file.name)
        chunks = splitter.split_text(raw)

        for idx, chunk in enumerate(chunks):
            chunk_id = f"{md_file.stem}__chunk_{idx:04d}"
            ids.append(chunk_id)
            texts.append(chunk)
            metadatas.append(
                {
                    "source": md_file.name,
                    "chunk_id": chunk_id,
                    "service_mentioned": service,
                }
            )
            chunks_per_service[service] += 1

        logger.debug(
            "%s → %d chunks  (service: %s)", md_file.name, len(chunks), service
        )

    # Batch upserts to keep memory usage bounded.
    batch_size = 100
    for start in range(0, len(ids), batch_size):
        end = start + batch_size
        collection.add(
            ids=ids[start:end],
            documents=texts[start:end],
            metadatas=metadatas[start:end],
        )
        logger.info("Upserted chunks %d–%d", start, min(end, len(ids)) - 1)

    docs_processed = len(md_files)
    total_chunks = len(ids)

    # ── Summary ──────────────────────────────────────────────────────────────
    width = 52
    print(f"\n{'='*width}")
    print(f"  Knowledge base build complete")
    print(f"{'='*width}")
    print(f"  Documents processed : {docs_processed}")
    print(f"  Total chunks        : {total_chunks}")
    print(f"  Collection          : {collection_name}")
    print(f"  DB path             : {db_path}")
    print(f"\n  Chunks per service:")
    for svc, count in sorted(chunks_per_service.items()):
        bar = "#" * min(count, 30)
        print(f"    {svc:<22} {count:>3}  {bar}")
    print(f"{'='*width}\n")

    return {
        "docs_processed": docs_processed,
        "total_chunks": total_chunks,
        "chunks_per_service": dict(chunks_per_service),
    }


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
    )
    build_knowledge_base()
