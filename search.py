"""Hybrid graph + vector retrieval with an explanation trace.

Pipeline:
  1. Embed the query and score every chunk by cosine similarity (vector leg).
  2. Take the top few chunks; their entities become graph seeds, weighted by similarity.
  3. Walk the graph (edges table in Oracle) up to MAX_HOPS; weight decays per hop.
  4. Chunks earn graph credit three ways, each tied to a concrete piece of evidence:
       edge     - the chunk is the source passage of a relation on a path from a seed
       mention  - the chunk mentions an entity reached by the walk
       shared   - the chunk mentions a seed entity itself (discounted)
  5. Fuse: final = W_VEC * vector + W_GRAPH * graph. Explain every result.

Usage:
  python search.py "Can I take Machine Learning without Data Structures?"
  python search.py "attendance below 75%" --mode vector
  python search.py            (interactive)
"""
import argparse
from collections import defaultdict

import numpy as np

MAX_HOPS = 2
DECAY = 0.5          # graph weight multiplier per hop
SEED_CHUNKS = 3      # how many top vector hits seed the graph walk
SEED_MENTION = 0.5   # credit factor for chunks that merely share a seed entity
W_VEC, W_GRAPH = 0.6, 0.4


class Store:
    """Loads chunk, entity and embedding data from Oracle; queries edges on demand."""

    def __init__(self, conn):
        self.conn = conn
        cur = conn.cursor()
        cur.execute("SELECT c.chunk_id, c.chunk_idx, c.content, d.title "
                    "FROM chunks c JOIN documents d ON d.doc_id = c.doc_id")
        self.chunks = {r[0]: {"idx": r[1], "text": r[2], "doc": r[3]} for r in cur.fetchall()}

        cur.execute("SELECT entity_id, name, entity_type FROM entities")
        self.entities = {r[0]: {"name": r[1], "type": r[2]} for r in cur.fetchall()}

        self.chunk_ents = defaultdict(list)
        self.ent_chunks = defaultdict(list)
        cur.execute("SELECT chunk_id, entity_id FROM chunk_entities")
        for chunk_id, entity_id in cur.fetchall():
            self.chunk_ents[chunk_id].append(entity_id)
            self.ent_chunks[entity_id].append(chunk_id)

        cur.execute("SELECT chunk_id, model_name, vec FROM embeddings ORDER BY chunk_id")
        rows = cur.fetchall()
        if not rows:
            raise SystemExit("No embeddings found. Run ingest.py first.")
        self.model_name = rows[0][1]
        self.chunk_order = [r[0] for r in rows]
        self.matrix = np.vstack([np.frombuffer(r[2], dtype=np.float32) for r in rows])
        self._neighbors = {}

    def neighbors(self, entity_id):
        """All edges touching an entity (either direction), cached per entity."""
        if entity_id not in self._neighbors:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT edge_id, src_entity_id, dst_entity_id, relation, chunk_id "
                "FROM edges WHERE src_entity_id = :id OR dst_entity_id = :id",
                {"id": entity_id},
            )
            self._neighbors[entity_id] = cur.fetchall()
        return self._neighbors[entity_id]


def propagate(store, seeds):
    """Spread weight from seed entities through the graph and credit chunks.

    seeds: {entity_id: weight}
    returns {chunk_id: (value, kind, seed_entity_id, path, entity_id)}
      kind = "edge" | "mention" | "shared"
      path = [(from_entity, relation, to_entity, forward?, supporting_chunk_id), ...]
    """
    evidence = {}

    def credit(chunk_id, value, kind, seed_id, path, entity_id):
        if chunk_id is not None and value > evidence.get(chunk_id, (0.0,))[0]:
            evidence[chunk_id] = (value, kind, seed_id, path, entity_id)

    for seed_id, weight in seeds.items():
        visited = {seed_id}
        frontier = [(seed_id, [])]
        for depth in range(1, MAX_HOPS + 1):
            value = weight * (DECAY ** depth)
            next_frontier = []
            for node, path in frontier:
                for _edge_id, src, dst, rel, chunk_id in store.neighbors(node):
                    other = dst if src == node else src
                    new_path = path + [(node, rel, other, src == node, chunk_id)]
                    credit(chunk_id, value, "edge", seed_id, new_path, other)
                    if other in visited:
                        continue
                    visited.add(other)
                    next_frontier.append((other, new_path))
                    for cid in store.ent_chunks[other]:
                        credit(cid, value, "mention", seed_id, new_path, other)
            frontier = next_frontier

    for seed_id, weight in seeds.items():
        for cid in store.ent_chunks[seed_id]:
            credit(cid, weight * SEED_MENTION, "shared", seed_id, [], seed_id)
    return evidence


def rank(store, query_vec, mode="hybrid", k=5):
    sims = store.matrix @ query_vec
    vec_score = {cid: max(0.0, float(s)) for cid, s in zip(store.chunk_order, sims)}

    top = sorted(vec_score, key=vec_score.get, reverse=True)[:SEED_CHUNKS]
    seeds = {}
    for cid in top:
        for eid in store.chunk_ents[cid]:
            seeds[eid] = max(seeds.get(eid, 0.0), vec_score[cid])
    evidence = propagate(store, seeds) if mode != "vector" else {}

    results = []
    for cid in store.chunk_order:
        v = vec_score[cid]
        ev = evidence.get(cid)
        g = ev[0] if ev else 0.0
        if mode == "vector":
            score = v
        elif mode == "graph":
            if g <= 0:
                continue
            score = g + 1e-3 * v          # vector score only breaks ties
        else:
            score = W_VEC * v + W_GRAPH * g
        if score > 0:
            results.append({"chunk_id": cid, "score": score, "vector": v,
                            "graph": g, "evidence": ev})
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:k], seeds


def describe_step(store, step):
    a, rel, b, forward, chunk_id = step
    na, nb = store.entities[a]["name"], store.entities[b]["name"]
    arrow = f"{na} -[{rel}]-> {nb}" if forward else f"{na} <-[{rel}]- {nb}"
    src = store.chunks.get(chunk_id)
    where = f"  (source: {src['doc']}, chunk {src['idx']})" if src else ""
    return arrow + where


def show(store, results, mode):
    for i, r in enumerate(results, 1):
        c = store.chunks[r["chunk_id"]]
        print(f"\n#{i}  [{c['doc']}, chunk {c['idx']}]  score={r['score']:.3f}")
        print(f"    {c['text']}")
        print(f"    vector={r['vector']:.3f}  graph={r['graph']:.3f}")
        if mode == "vector":
            continue
        ev = r["evidence"]
        if not ev:
            print("    why: no graph connection to the top vector matches")
            continue
        _value, kind, seed_id, path, ent_id = ev
        seed = store.entities[seed_id]["name"]
        ent = store.entities[ent_id]["name"]
        if kind == "shared":
            print(f"    why: shares the entity '{ent}' with a top vector match")
            continue
        if kind == "mention":
            print(f"    why: mentions '{ent}', reached from '{seed}' in {len(path)} hop(s):")
        else:
            print(f"    why: this passage is the source of a relation "
                  f"{len(path)} hop(s) from '{seed}':")
        for step in path:
            print(f"         {describe_step(store, step)}")
    print()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("query", nargs="?")
    parser.add_argument("--mode", choices=["vector", "graph", "hybrid"], default="hybrid")
    parser.add_argument("--k", type=int, default=5)
    args = parser.parse_args()

    from sentence_transformers import SentenceTransformer
    from db import get_connection

    store = Store(get_connection())
    model = SentenceTransformer(store.model_name)

    def run(query):
        q = model.encode([query], normalize_embeddings=True)[0].astype(np.float32)
        results, _ = rank(store, q, args.mode, args.k)
        show(store, results, args.mode)

    if args.query:
        run(args.query)
    else:
        while True:
            query = input("query (blank to quit)> ").strip()
            if not query:
                break
            run(query)


if __name__ == "__main__":
    main()