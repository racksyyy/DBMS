"""Load the corpus, graph and embeddings into Oracle.

Safe to re-run: it clears the project tables first.
Usage: python ingest.py
"""
import numpy as np
import oracledb

from corpus import DOCS, RELATIONS
from db import get_connection

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"  # 384-dim


def norm(name):
    return " ".join(name.lower().split())


def insert_returning(cur, sql, params):
    """Run an INSERT ... RETURNING <id> INTO :new_id and return the id."""
    out = cur.var(int)
    cur.execute(sql, {**params, "new_id": out})
    return int(out.getvalue()[0])


def main():
    from sentence_transformers import SentenceTransformer

    conn = get_connection()
    cur = conn.cursor()

    # 1. Clear existing data (child tables first)
    for table in ["embeddings", "chunk_entities", "edges", "chunks", "entities", "documents"]:
        cur.execute(f"DELETE FROM {table}")

    # 2. Documents, chunks, entities, chunk-entity links
    chunk_ids = {}    # (doc title, chunk idx) -> chunk_id
    entity_ids = {}   # (normalized name, type) -> entity_id
    order, texts = [], []

    def get_entity(name, etype):
        key = (norm(name), etype)
        if key not in entity_ids:
            entity_ids[key] = insert_returning(
                cur,
                "INSERT INTO entities (name, normalized_name, entity_type) "
                "VALUES (:name, :nn, :et) RETURNING entity_id INTO :new_id",
                {"name": name, "nn": key[0], "et": etype},
            )
        return entity_ids[key]

    for doc in DOCS:
        doc_id = insert_returning(
            cur,
            "INSERT INTO documents (title, doc_type, source) "
            "VALUES (:title, :dt, :src) RETURNING doc_id INTO :new_id",
            {"title": doc["title"], "dt": doc["doc_type"], "src": doc["source"]},
        )
        for idx, chunk in enumerate(doc["chunks"]):
            chunk_id = insert_returning(
                cur,
                "INSERT INTO chunks (doc_id, chunk_idx, content) "
                "VALUES (:doc_id, :idx, :content) RETURNING chunk_id INTO :new_id",
                {"doc_id": doc_id, "idx": idx, "content": chunk["text"]},
            )
            chunk_ids[(doc["title"], idx)] = chunk_id
            order.append(chunk_id)
            texts.append(chunk["text"])
            for name, etype in chunk["entities"]:
                cur.execute(
                    "INSERT INTO chunk_entities (chunk_id, entity_id) VALUES (:1, :2)",
                    [chunk_id, get_entity(name, etype)],
                )

    # 3. Graph edges, each with provenance
    for src, rel, dst, doc_title, idx in RELATIONS:
        cur.execute(
            "INSERT INTO edges (edge_id, src_entity_id, dst_entity_id, relation, chunk_id) "
            "VALUES (seq_edge.NEXTVAL, :1, :2, :3, :4)",
            [get_entity(*src), get_entity(*dst), rel, chunk_ids[(doc_title, idx)]],
        )

    # 4. Embeddings (normalized, so dot product = cosine similarity)
    print(f"Embedding {len(texts)} chunks with {MODEL_NAME} ...")
    model = SentenceTransformer(MODEL_NAME)
    vecs = model.encode(texts, normalize_embeddings=True).astype(np.float32)
    for chunk_id, vec in zip(order, vecs):
        cur.setinputsizes(None, None, None, oracledb.DB_TYPE_BLOB)
        cur.execute(
            "INSERT INTO embeddings (chunk_id, model_name, dim, vec) VALUES (:1, :2, :3, :4)",
            [chunk_id, MODEL_NAME, int(vec.shape[0]), vec.tobytes()],
        )

    conn.commit()

    for table in ["documents", "chunks", "entities", "edges", "chunk_entities", "embeddings"]:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        print(f"{table:15s} {cur.fetchone()[0]}")


if __name__ == "__main__":
    main()