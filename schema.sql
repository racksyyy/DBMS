-- Hybrid Graph-Vector schema for Oracle XE 11.2
-- 11g constraints respected: no identity columns, no FETCH FIRST, no JSON, no VECTOR type.
-- Graph = nodes + edges tables. Vectors = float32 bytes stored in a BLOB.

-- ---------------------------------------------------------------
-- STEP 0 (run once as SYSTEM, in SQL*Plus or SQL Workshop):
--   CREATE USER hybrid IDENTIFIED BY "ChangeMe_123";
--   GRANT CONNECT, RESOURCE, CREATE VIEW TO hybrid;
--   ALTER USER hybrid QUOTA UNLIMITED ON USERS;
-- Then connect as HYBRID and run the rest of this file.
-- ---------------------------------------------------------------

-- Sequences
CREATE SEQUENCE seq_document START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE seq_chunk    START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE seq_entity   START WITH 1 INCREMENT BY 1 NOCACHE;
CREATE SEQUENCE seq_edge     START WITH 1 INCREMENT BY 1 NOCACHE;

-- Source documents (policies, course pages, handbooks)
CREATE TABLE documents (
  doc_id      NUMBER PRIMARY KEY,
  title       VARCHAR2(300) NOT NULL,
  doc_type    VARCHAR2(50),            -- e.g. POLICY, COURSE, HANDBOOK
  source      VARCHAR2(500),           -- file name or URL
  created_at  DATE DEFAULT SYSDATE
);

-- Text chunks: the unit of vector retrieval and of provenance
CREATE TABLE chunks (
  chunk_id    NUMBER PRIMARY KEY,
  doc_id      NUMBER NOT NULL REFERENCES documents(doc_id),
  chunk_idx   NUMBER NOT NULL,
  content     CLOB NOT NULL,
  created_at  DATE DEFAULT SYSDATE,
  CONSTRAINT uq_chunk UNIQUE (doc_id, chunk_idx)
);

-- Graph nodes
CREATE TABLE entities (
  entity_id        NUMBER PRIMARY KEY,
  name             VARCHAR2(300) NOT NULL,
  normalized_name  VARCHAR2(300) NOT NULL,   -- lowercase, trimmed, for dedup
  entity_type      VARCHAR2(50),             -- COURSE, DEPARTMENT, POLICY, PROGRAM, RULE...
  CONSTRAINT uq_entity UNIQUE (normalized_name, entity_type)
);

-- Graph edges, each with provenance (which chunk supports this relation)
CREATE TABLE edges (
  edge_id        NUMBER PRIMARY KEY,
  src_entity_id  NUMBER NOT NULL REFERENCES entities(entity_id),
  dst_entity_id  NUMBER NOT NULL REFERENCES entities(entity_id),
  relation       VARCHAR2(100) NOT NULL,     -- PREREQUISITE_OF, OFFERED_BY, APPLIES_TO...
  weight         NUMBER DEFAULT 1,
  chunk_id       NUMBER REFERENCES chunks(chunk_id),
  CONSTRAINT chk_no_self_loop CHECK (src_entity_id <> dst_entity_id)
);
CREATE INDEX ix_edges_src ON edges(src_entity_id, relation);
CREATE INDEX ix_edges_dst ON edges(dst_entity_id, relation);

-- Which entities are mentioned in which chunk (bridge between vector and graph)
CREATE TABLE chunk_entities (
  chunk_id   NUMBER NOT NULL REFERENCES chunks(chunk_id),
  entity_id  NUMBER NOT NULL REFERENCES entities(entity_id),
  PRIMARY KEY (chunk_id, entity_id)
);
CREATE INDEX ix_ce_entity ON chunk_entities(entity_id);

-- Embeddings: float32 array serialized to bytes.
-- model_name + dim stored so a future migration to a native VECTOR column is trivial.
CREATE TABLE embeddings (
  chunk_id    NUMBER PRIMARY KEY REFERENCES chunks(chunk_id),
  model_name  VARCHAR2(200) NOT NULL,
  dim         NUMBER NOT NULL,
  vec         BLOB NOT NULL
);

-- Auto-assign IDs (11g style)
CREATE OR REPLACE TRIGGER trg_document_id BEFORE INSERT ON documents FOR EACH ROW
BEGIN IF :NEW.doc_id IS NULL THEN SELECT seq_document.NEXTVAL INTO :NEW.doc_id FROM dual; END IF; END;
/
CREATE OR REPLACE TRIGGER trg_chunk_id BEFORE INSERT ON chunks FOR EACH ROW
BEGIN IF :NEW.chunk_id IS NULL THEN SELECT seq_chunk.NEXTVAL INTO :NEW.chunk_id FROM dual; END IF; END;
/
CREATE OR REPLACE TRIGGER trg_entity_id BEFORE INSERT ON entities FOR EACH ROW
BEGIN IF :NEW.entity_id IS NULL THEN SELECT seq_entity.NEXTVAL INTO :NEW.entity_id FROM dual; END IF; END;
/
CREATE OR REPLACE TRIGGER trg_edge_id BEFORE INSERT ON edges FOR EACH ROW
BEGIN IF :NEW.edge_id IS NULL THEN SELECT seq_edge.NEXTVAL INTO :NEW.edge_id FROM dual; END IF; END;
