# CRIE Entity-Relationship Diagram

Referential model (§233). `-->` = foreign key (child references parent);
`ON DELETE CASCADE` prevents orphans.

```mermaid
erDiagram
    documents ||--o{ metadata : has
    documents ||--o{ knowledge_units : yields
    documents ||--o{ citations : referenced_by
    knowledge_units ||--o{ evidence : supports
    knowledge_units ||--o{ retrieval_chunks : chunked_into
    knowledge_units ||--o{ knowledge_relationships : source
    knowledge_units ||--o{ knowledge_tags : tagged
    knowledge_units ||--o| knowledge_units : previous_version
    evidence ||--o{ citations : cited_by
    retrieval_chunks ||--o{ embeddings : embedded_as

    documents {
        uuid id PK
        text sha256 UK
        text status
        text authority
        timestamptz uploaded_at
    }
    knowledge_units {
        uuid id PK
        uuid document_id FK
        text category "CHECK 16-value enum (R-05)"
        text lifecycle_state "Draft|Validated|Certified|Deprecated|Archived"
        uuid previous_version FK "lineage (R-15/§519)"
        int authority_score
        numeric quality_score
    }
    evidence {
        uuid id PK
        uuid knowledge_unit_id FK
    }
    citations {
        uuid id PK
        uuid evidence_id FK "R-06"
        uuid document_id FK "R-06"
    }
    retrieval_chunks {
        uuid id PK
        uuid knowledge_unit_id FK
        int chunk_order
    }
    embeddings {
        uuid id PK
        uuid chunk_id FK
        vector embedding "vector(1536) (R-09)"
    }
    knowledge_relationships {
        uuid id PK
        uuid source_ku_id FK
        uuid target_ku_id FK
        text relationship_type "§441"
    }
    knowledge_tags {
        uuid id PK
        uuid knowledge_unit_id FK
        text tag
    }
    metadata {
        uuid id PK
        uuid document_id FK
        text key
        text value
    }
```

Chain (§233): documents → knowledge_units → evidence → citations;
knowledge_units → retrieval_chunks → embeddings.

Supporting schemas (`configuration`, `monitoring`, `audit`) are documented in
`docs/architecture/Database_Schema.md`; they are not part of the repository FK
chain (monitoring/audit are decoupled per §229/§230).
