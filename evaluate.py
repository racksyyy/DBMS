"""Compare vector-only, graph-only and hybrid retrieval on a labelled question set.

Each question lists the chunks that SHOULD be retrieved, as (document title, chunk index).
The labels below were written by hand for the placeholder corpus. Review them, and
rewrite them when you switch to your real documents.

Metrics at K (default 3):
  Precision@K - share of the K returned chunks that are relevant
  Recall@K    - share of the relevant chunks that were returned
  MRR         - 1 / rank of the first relevant chunk (0 if none)

Usage: python evaluate.py
"""
import numpy as np

from search import Store, rank

K = 3
MODES = ["vector", "graph", "hybrid"]

CAT = "Course Catalog - CSE"
REG = "Academic Regulations"
EXAM = "Examination Rules"
MINOR = "Minor Program Guidelines"

QUESTIONS = [
    ("Can I take Machine Learning without Data Structures?",
     [(CAT, 2), (REG, 2)]),
    ("What do I need to finish before Database Systems?",
     [(CAT, 1), (CAT, 0)]),
    ("Which department teaches the statistics prerequisite for Machine Learning?",
     [(CAT, 2), (CAT, 3)]),
    ("What happens if I am detained for low attendance?",
     [(EXAM, 0), (REG, 0)]),
    ("Can I get condonation if my attendance is 70%?",
     [(REG, 1), (REG, 0)]),
    ("Can I do the Data Science Minor without taking Data Structures?",
     [(MINOR, 0), (CAT, 2)]),
    ("Do minor courses affect my CGPA?",
     [(MINOR, 1), (REG, 3)]),
    ("What happens if my CGPA stays below 5?",
     [(REG, 3)]),
    ("How many times can I attempt a supplementary exam?",
     [(EXAM, 1)]),
    ("Who can approve an exception to the prerequisites?",
     [(REG, 2)]),
    ("Is Probability and Statistics compulsory for my program?",
     [(CAT, 3)]),
    ("What is the chain of courses before I can take Machine Learning?",
     [(CAT, 2), (CAT, 0)]),
]


def evaluate(store, encode, k=K):
    """encode(text) -> normalized float32 vector. Returns (rows, totals)."""
    rows = []
    totals = {m: {"p": 0.0, "r": 0.0, "mrr": 0.0} for m in MODES}
    for question, gold in QUESTIONS:
        gold = set(gold)
        qvec = encode(question)
        row = {"question": question, "gold": gold, "modes": {}}
        for mode in MODES:
            results, _ = rank(store, qvec, mode, k)
            keys = [(store.chunks[r["chunk_id"]]["doc"], store.chunks[r["chunk_id"]]["idx"])
                    for r in results]
            hits = [key in gold for key in keys]
            precision = sum(hits) / k
            recall = sum(hits) / len(gold)
            mrr = next((1.0 / (i + 1) for i, h in enumerate(hits) if h), 0.0)
            row["modes"][mode] = {"keys": keys, "p": precision, "r": recall, "mrr": mrr}
            totals[mode]["p"] += precision
            totals[mode]["r"] += recall
            totals[mode]["mrr"] += mrr
        rows.append(row)
    n = len(QUESTIONS)
    for mode in MODES:
        for metric in totals[mode]:
            totals[mode][metric] /= n
    return rows, totals


def print_report(rows, totals, k=K):
    print(f"\nPer-question Recall@{k}  (vector / graph / hybrid)")
    print("-" * 90)
    for i, row in enumerate(rows, 1):
        recalls = " / ".join(f"{row['modes'][m]['r']:.2f}" for m in MODES)
        print(f"{i:2d}. {recalls}   {row['question']}")

    print(f"\nSummary over {len(rows)} questions (K={k})")
    print("-" * 52)
    print(f"{'mode':8s} {'Precision@K':>12s} {'Recall@K':>10s} {'MRR':>8s}")
    for mode in MODES:
        t = totals[mode]
        print(f"{mode:8s} {t['p']:12.3f} {t['r']:10.3f} {t['mrr']:8.3f}")
    print("\nNote: with 1-2 relevant chunks per question, Precision@K cannot reach 1.0 "
          "at K=3; compare modes against each other.\n")


def main():
    from sentence_transformers import SentenceTransformer
    from db import get_connection

    store = Store(get_connection())
    model = SentenceTransformer(store.model_name)

    def encode(text):
        return model.encode([text], normalize_embeddings=True)[0].astype(np.float32)

    rows, totals = evaluate(store, encode)
    print_report(rows, totals)


if __name__ == "__main__":
    main()