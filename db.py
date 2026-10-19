"""Shared Oracle connection helper (thick mode, required for XE 11.2)."""
import os

import oracledb

USER = os.getenv("ORA_USER", "hybrid")
PASSWORD = os.getenv("ORA_PASSWORD", "ChangeMe_123")
DSN = os.getenv("ORA_DSN", "localhost:1521/XE")
CLIENT_LIB = os.getenv("ORA_CLIENT_LIB")

_initialized = False


def get_connection():
    global _initialized
    if not _initialized:
        if CLIENT_LIB:
            oracledb.init_oracle_client(lib_dir=CLIENT_LIB)
        else:
            oracledb.init_oracle_client()
        # Return CLOB as str and BLOB as bytes instead of LOB objects
        oracledb.defaults.fetch_lobs = False
        _initialized = True
    return oracledb.connect(user=USER, password=PASSWORD, dsn=DSN)