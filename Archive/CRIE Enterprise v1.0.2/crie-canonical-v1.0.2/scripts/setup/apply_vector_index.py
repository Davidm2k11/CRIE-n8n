#!/usr/bin/env python3
"""apply_vector_index.py — Generate the vector index DDL from configuration (§227).

§227: "Configuration determines implementation." The vector index type and params
are read from embedding.vectorIndex in configuration/providers.yaml; this script
emits the matching CREATE INDEX so switching HNSW<->IVFFlat or changing params is a
config change only — no SQL editing. Emits SQL to stdout (or --apply with psycopg).
"""
import argparse, os, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OPS = {"cosine": ("vector_cosine_ops", "idx_embeddings_hnsw_cosine", "idx_embeddings_ivfflat_cosine"),
       "l2":     ("vector_l2_ops",     "idx_embeddings_hnsw_l2",     "idx_embeddings_ivfflat_l2"),
       "ip":     ("vector_ip_ops",     "idx_embeddings_hnsw_ip",     "idx_embeddings_ivfflat_ip")}


def build():
    import yaml
    prov = yaml.safe_load(open(os.path.join(ROOT, "configuration", "providers.yaml")))
    vi = (prov.get("embedding") or {}).get("vectorIndex") or {}
    itype = vi.get("type", "hnsw")
    metric = vi.get("metric", "cosine")
    if metric not in OPS:
        raise SystemExit(f"unsupported metric: {metric}")
    ops, hnsw_name, ivf_name = OPS[metric]
    lines = ["-- Generated from embedding.vectorIndex (§227). Config-driven; do not hand-edit.",
             "DROP INDEX IF EXISTS repository.idx_embeddings_hnsw_cosine;",
             "DROP INDEX IF EXISTS repository.idx_embeddings_ivfflat_cosine;",
             "DROP INDEX IF EXISTS repository.idx_embeddings_hnsw_l2;",
             "DROP INDEX IF EXISTS repository.idx_embeddings_ivfflat_l2;",
             "DROP INDEX IF EXISTS repository.idx_embeddings_hnsw_ip;",
             "DROP INDEX IF EXISTS repository.idx_embeddings_ivfflat_ip;"]
    if itype == "hnsw":
        h = vi.get("hnsw", {})
        m = int(h.get("m", 16)); efc = int(h.get("efConstruction", 64))
        lines.append(f"CREATE INDEX {hnsw_name} ON repository.embeddings "
                     f"USING hnsw (embedding {ops}) WITH (m = {m}, ef_construction = {efc});")
    elif itype == "ivfflat":
        iv = vi.get("ivfflat", {})
        lists = int(iv.get("lists", 100))
        lines.append(f"CREATE INDEX {ivf_name} ON repository.embeddings "
                     f"USING ivfflat (embedding {ops}) WITH (lists = {lists});")
    else:
        raise SystemExit(f"unsupported vector index type: {itype}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    sql = build()
    if args.apply:
        try:
            import psycopg  # noqa
        except Exception:
            print("psycopg unavailable; emitting SQL.\n", file=sys.stderr); print(sql); return
        dsn = os.environ.get("DATABASE_URL")
        if not dsn: raise SystemExit("DATABASE_URL not set")
        with psycopg.connect(dsn) as c, c.cursor() as cur: cur.execute(sql)
        print("vector index applied")
    else:
        print(sql)


if __name__ == "__main__":
    main()
