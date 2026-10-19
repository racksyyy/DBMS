"""Sanity check: Python -> Oracle XE 11.2, schema present, float32 BLOB round-trip.

Setup:
  pip install oracledb
  Install Oracle Instant Client (thick mode is required for an 11.2 database;
  the default thin mode only supports 12.1+). Match your Python bitness (64-bit).

Environment variables (or edit the defaults below):
  ORA_USER, ORA_PASSWORD, ORA_DSN (default localhost:1521/XE), ORA_CLIENT_LIB
"""
import os
import sys
from array import array

import oracledb

USER = os.getenv("ORA_USER", "hybrid")
PASSWORD = os.getenv("ORA_PASSWORD", "ChangeMe_123")
DSN = os.getenv("ORA_DSN", "localhost:1521/XE")
CLIENT_LIB = os.getenv("ORA_CLIENT_LIB")  # e.g. C:\\oracle\\instantclient_19_x

EXPECTED_TABLES = {"DOCUMENTS", "CHUNKS", "ENTITIES", "EDGES", "CHUNK_ENTITIES", "EMBEDDINGS"}


def main():
    try:
        oracledb.init_oracle_client(lib_dir=CLIENT_LIB) if CLIENT_LIB else oracledb.init_oracle_client()
    except Exception as e:
        print("Could not start thick mode (Instant Client missing or wrong path):", e)
        sys.exit(1)

    with oracledb.connect(user=USER, password=PASSWORD, dsn=DSN) as conn:
        cur = conn.cursor()
        cur.execute("SELECT banner FROM v$version WHERE ROWNUM = 1")
        print("Connected:", cur.fetchone()[0])

        cur.execute("SELECT table_name FROM user_tables")
        found = {r[0] for r in cur.fetchall()}
        missing = EXPECTED_TABLES - found
        print("Schema tables missing:", sorted(missing) if missing else "none")
        if missing:
            return

        # BLOB round-trip with a fake 4-dim float32 vector (rolled back afterwards)
        cur.execute("INSERT INTO documents (title) VALUES ('__test__') RETURNING doc_id INTO :1",
                    [cur.var(int)])
        doc_id = cur.bindvars[0].getvalue()[0]
        cur.execute("INSERT INTO chunks (doc_id, chunk_idx, content) VALUES (:1, 0, 'test') "
                    "RETURNING chunk_id INTO :2", [doc_id, cur.var(int)])
        chunk_id = cur.bindvars[1].getvalue()[0]

        original = array("f", [0.1, 0.2, 0.3, 0.4])
        cur.execute("INSERT INTO embeddings (chunk_id, model_name, dim, vec) VALUES (:1, 'test', 4, :2)",
                    [chunk_id, original.tobytes()])
        cur.execute("SELECT vec FROM embeddings WHERE chunk_id = :1", [chunk_id])
        blob = cur.fetchone()[0]
        restored = array("f")
        restored.frombytes(blob.read() if hasattr(blob, "read") else blob)
        print("BLOB round-trip OK:", list(restored) == list(original))
        conn.rollback()


if __name__ == "__main__":
    main()