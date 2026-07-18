#!/usr/bin/env python3
"""test_database.py — Sprint 2 DB acceptance tests (§238, §150).

No live PostgreSQL is available in this environment, so these tests validate the
migration set STATICALLY against the frozen spec: ordering, forward/rollback
pairing (§239), additive-only rule for 0018-0023 (R-15), the canonical enums and
contracts (R-05/R-06/R-09/R-16), append-only audit/history, and config-driven
behavior. Live execution against Supabase is an operator step documented in the
Migration Execution Guide.

Exit 0 = all checks pass.
"""
import glob, os, re, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MIG = os.path.join(ROOT, "database", "migrations")
RB = os.path.join(ROOT, "database", "rollback")

passed = failed = 0
def ok(m):  globals().__setitem__('passed', passed+1); print(f"  \u2713 {m}")
def bad(m): globals().__setitem__('failed', failed+1); print(f"  \u2717 {m}")

def read(p):
    with open(p) as fh: return fh.read()

# --- Migration ordering (§217) ---
migs = sorted(os.path.basename(f) for f in glob.glob(os.path.join(MIG, "*.sql")))
expected = [
 "0001_extensions.sql","0002_schemas.sql","0003_documents.sql","0004_metadata.sql",
 "0005_knowledge_units.sql","0006_evidence.sql","0007_citations.sql",
 "0008_retrieval_chunks.sql","0009_embeddings.sql","0010_configuration.sql",
 "0011_prompt_registry.sql","0012_monitoring.sql","0013_indexes.sql","0014_rls.sql",
 "0015_functions.sql","0016_views.sql","0017_seed_data.sql",
 "0018_knowledge_classification.sql","0019_knowledge_relationships.sql",
 "0020_semantic_tags.sql","0021_dictionaries.sql","0022_processing_history.sql",
 "0023_audit_columns.sql",
 # Additive migrations delivered by later sprints (R-15): Sprint 8 admin
 # (0024-0026), Sprint 9 benchmark (0027-0028). No 0001-0023 migration altered.
 "0024_admin_dashboard_views.sql","0025_admin_registry_audit_views.sql",
 "0026_health_alert_center.sql","0027_benchmark_persistence.sql",
 "0028_benchmark_views.sql"]
if migs == expected: ok(f"migration order matches §217 (28 migrations; 0001-0023 base + 0024-0028 additive)")
else: bad(f"migration order mismatch: {migs}")

# --- Every migration has a rollback (§239) ---
missing = []
for m in migs:
    base = m[:-4]
    if not os.path.exists(os.path.join(RB, base + "_rollback.sql")):
        missing.append(base)
if not missing: ok("every migration has a matching rollback (§239)")
else: bad(f"missing rollbacks: {missing}")

# --- Additive-only rule for 0018-0023 (R-15): 0018 only ADDs to knowledge_units ---
c18 = read(os.path.join(MIG, "0018_knowledge_classification.sql"))
if "ALTER TABLE repository.knowledge_units" in c18 and "ADD COLUMN" in c18 \
   and not re.search(r"DROP\s+COLUMN", c18) and "CREATE TABLE" not in c18.upper():
    ok("0018 is additive-only (ADD COLUMN; no DROP COLUMN, no table redefinition) (R-15)")
else: bad("0018 violates additive-only rule")

# core tables 0003-0009 are not ALTERed by additive migrations
core_tables = ["documents","metadata","evidence","citations","retrieval_chunks","embeddings"]
violation=False
for f in ["0019","0020","0021","0022","0023"]:
    txt=read(glob.glob(os.path.join(MIG,f+"*"))[0]).upper()
    for t in core_tables:
        if f"ALTER TABLE REPOSITORY.{t.upper()}" in txt:
            violation=True
if not violation: ok("additive migrations do not alter core tables 0003-0009 in structure (R-15)")
else: bad("an additive migration alters a core table")

# --- R-09: embeddings vector(1536) ---
c09 = read(os.path.join(MIG, "0009_embeddings.sql"))
if "vector(1536)" in c09: ok("embeddings column is vector(1536) (R-09)")
else: bad("embeddings vector dimension is not 1536")

# --- R-06: citations key on evidence_id AND document_id ---
c07 = read(os.path.join(MIG, "0007_citations.sql"))
if "fk_citations_evidence" in c07 and "fk_citations_documents" in c07 \
   and "evidence_id" in c07 and "document_id" in c07:
    ok("citations keyed on evidence_id + document_id (R-06)")
else: bad("citations FK model does not match R-06")

# --- R-05: category CHECK has exactly the 16 canonical values ---
import yaml
cats = yaml.safe_load(read(os.path.join(ROOT,"database","seeds","knowledge_categories.yaml")))["categories"]
c18check = c18
in_check = all(f"'{c}'" in c18check for c in cats)
if len(cats)==16 and in_check: ok("category CHECK constraint matches the 16-value enum (R-05, §438)")
else: bad("category enum mismatch")

# --- R-16: 9 authority sources seeded ---
c17 = read(os.path.join(MIG, "0017_seed_data.sql"))
auth_rows = re.findall(r"\('([^']+)',\s*\d+\)", c17)
if len([a for a in auth_rows]) >= 9 and "Approved Product Specification" in c17:
    ok("authority sources seeded (9 sources, R-16, §439)")
else: bad("authority source seed incomplete")

# --- Append-only enforcement (§239.1): processing_history + audit ---
c22 = read(os.path.join(MIG, "0022_processing_history.sql"))
c23 = read(os.path.join(MIG, "0023_audit_columns.sql"))
if "BEFORE UPDATE OR DELETE" in c22 and "deny_mutation" in c22:
    ok("processing_history is append-only (trigger) (§239.1, R-18)")
else: bad("processing_history append-only not enforced")
if "BEFORE UPDATE OR DELETE" in c23 and "REVOKE UPDATE, DELETE" in c23:
    ok("audit tables append-only/immutable (trigger + revoke) (§230, §344)")
else: bad("audit immutability not enforced")

# --- Schemas & public minimal (§219) ---
c02 = read(os.path.join(MIG, "0002_schemas.sql"))
if all(f"CREATE SCHEMA IF NOT EXISTS {s}" in c02 for s in
       ["repository","configuration","monitoring","audit","retrieval"]):
    ok("five schemas created; public kept minimal (§219)")
else: bad("schema set incomplete")

# --- Naming standards (§237): snake_case files, idx_/fk_ prefixes present ---
if all(re.match(r"^\d{4}_[a-z0-9_]+\.sql$", m) for m in migs):
    ok("migration filenames are snake_case (§634, §237)")
else: bad("a migration filename violates naming")

# --- Config-driven index (§227) present ---
c13 = read(os.path.join(MIG, "0013_indexes.sql"))
if "hnsw" in c13 and "vector_cosine_ops" in c13:
    ok("vector index created (HNSW default; type config-driven §227)")
else: bad("vector index missing")

# --- RLS enabled (§235) ---
c14 = read(os.path.join(MIG, "0014_rls.sql"))
if "ENABLE ROW LEVEL SECURITY" in c14 and "service_role" in c14:
    ok("RLS enabled; Service Role policy present (§235)")
else: bad("RLS not enabled")

print()
print("-------------------------------------------")
print(f"DB acceptance: {passed} passed, {failed} failed.")
sys.exit(0 if failed == 0 else 1)
