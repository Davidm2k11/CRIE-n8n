-- =====================================================================
-- CRIE — Migration 0029_orphan_sweep.sql
-- Operational safeguard: Orphan-Document Sweep.
-- Spec refs: §154 (HUMAN_REVIEW failure route), §239.1 (processing_history
--            append-only), §374 (stage vocabulary), §569 (Alert Center).
-- Docs: DEPLOYMENT_GUIDE §6, IMPLEMENTATION_NOTES "Operational safeguards".
--
-- All Rights Reserved, Copyright (c) 2026 Dawod Manasra. Unauthorized copying,
-- modification, distribution, or commercial use is prohibited without written
-- permission.
--
-- ADDITIVE ONLY. Adds a read-only detector view (monitoring.vw_orphaned_documents)
-- and an idempotent sweep function (monitoring.sweep_orphaned_documents). Edits
-- NO historical migration and relaxes NO constraint.
--
-- WHY THIS EXISTS: a worker crash (OOM/restart) mid-pipeline skips WF-001's
-- in-workflow HUMAN_REVIEW paths, leaving a document silently in-progress. This
-- sweep detects such documents and remediates them the SAME way WF-001 does on a
-- handled failure, using ONLY append-safe operations:
--   1. repository.documents.status := 'HUMAN_REVIEW'   (documents is mutable)
--   2. INSERT a NEW terminal FAILED processing_history row (never UPDATE an
--      existing one — the table is append-only per migration 0022's trigger)
--   3. INSERT the corresponding monitoring.alerts row (Alert Center, 0026)
--
-- Rollback: 0029_orphan_sweep_rollback.sql
-- =====================================================================

BEGIN;

-- ---------------------------------------------------------------------
-- Detector (read-only). Lists documents whose LATEST processing_history
-- row is still PENDING with no terminal (COMPLETED/FAILED) successor, and
-- whose document status is not already terminal/handled. No age threshold
-- is baked in — the consumer (sweep function or BI) filters on
-- minutes_stuck, keeping the operational threshold configuration-driven
-- (Principle 7). Surfacing candidates as a view also lets the BI layer
-- watch orphans without remediating them.
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW monitoring.vw_orphaned_documents AS
WITH latest AS (
    -- Most recent lifecycle row per document (append-only log, so the row
    -- with the greatest created_at is the current state of the pipeline).
    SELECT DISTINCT ON (ph.document_id)
           ph.document_id,
           ph.stage,
           ph.status,
           ph.correlation_id,
           ph.created_at
    FROM monitoring.processing_history ph
    ORDER BY ph.document_id, ph.created_at DESC, ph.id DESC
)
SELECT d.id                                              AS document_id,
       d.filename                                        AS filename,
       d.status                                          AS document_status,
       l.stage                                           AS stuck_stage,
       l.correlation_id                                  AS correlation_id,
       l.created_at                                      AS stuck_since,
       (EXTRACT(EPOCH FROM (now() - l.created_at)) / 60.0)::numeric AS minutes_stuck
FROM latest l
JOIN repository.documents d ON d.id = l.document_id
WHERE l.status = 'PENDING'
  -- Exclude documents already routed to a terminal / handled state. Matches
  -- the statuses WF-001 and SW-014/SW-015 write on their success/failure paths.
  AND d.status NOT IN ('PROCESSED', 'CERTIFIED', 'HUMAN_REVIEW');

COMMENT ON VIEW monitoring.vw_orphaned_documents IS
    'Candidate orphaned documents: latest processing_history is PENDING with no '
    'terminal successor and document not already handled. minutes_stuck lets the '
    'consumer apply a configuration-driven staleness threshold. Read-only.';

-- ---------------------------------------------------------------------
-- Sweep (transactional, idempotent). Remediates orphans older than
-- p_stale_minutes, up to p_limit per run. Both parameters are supplied by
-- the caller (the standalone Orphan Sweep workflow reads them from config),
-- so NO cadence or threshold is hardcoded here. Returns one row per
-- remediated document for logging/notification. Re-running is safe: a
-- remediated document leaves this view immediately (status becomes
-- HUMAN_REVIEW and a terminal FAILED row is appended), so it cannot match
-- again on the next sweep.
-- ---------------------------------------------------------------------
CREATE OR REPLACE FUNCTION monitoring.sweep_orphaned_documents(
    p_stale_minutes integer DEFAULT 30,
    p_limit         integer DEFAULT 100
)
RETURNS TABLE (
    document_id   uuid,
    stuck_stage   text,
    minutes_stuck numeric,
    alert_id      uuid
)
LANGUAGE plpgsql
AS $$
DECLARE
    r         RECORD;
    v_updated integer;
    v_alert   uuid;
BEGIN
    FOR r IN
        SELECT o.document_id,
               o.stuck_stage,
               o.correlation_id,
               o.minutes_stuck
        FROM monitoring.vw_orphaned_documents o
        WHERE o.minutes_stuck >= p_stale_minutes
        ORDER BY o.stuck_since ASC          -- oldest first
        LIMIT GREATEST(p_limit, 0)
    LOOP
        -- 1) Route the document to human review. Guarded so a concurrent
        --    sweep (or a handled failure that landed first) cannot cause a
        --    duplicate remediation; if no row is updated we skip the rest.
        UPDATE repository.documents
           SET status = 'HUMAN_REVIEW'
         WHERE id = r.document_id
           AND status NOT IN ('PROCESSED', 'CERTIFIED', 'HUMAN_REVIEW');
        GET DIAGNOSTICS v_updated = ROW_COUNT;
        IF v_updated = 0 THEN
            CONTINUE;
        END IF;

        -- 2) Append (NEVER modify) a terminal FAILED lifecycle row for the
        --    stuck stage. 'FAILED' is the only terminal status the §239.1
        --    CHECK allows and is exactly what WF-001 writes on a handled
        --    HUMAN_REVIEW route.
        INSERT INTO monitoring.processing_history
            (document_id, stage, status, correlation_id)
        VALUES
            (r.document_id, r.stuck_stage, 'FAILED', r.correlation_id);

        -- 3) Raise the corresponding Alert Center row (§569).
        INSERT INTO monitoring.alerts
            (alert_type, severity, source, message, context, correlation_id)
        VALUES
            ('WorkflowFailure',
             'Warning',
             'orphan-sweep',
             'Document stuck in-progress was remediated to HUMAN_REVIEW by the orphan sweep',
             jsonb_build_object(
                 'document_id',              r.document_id,
                 'stuck_stage',              r.stuck_stage,
                 'minutes_stuck',            round(r.minutes_stuck, 1),
                 'stale_threshold_minutes',  p_stale_minutes
             ),
             r.correlation_id)
        RETURNING id INTO v_alert;

        document_id   := r.document_id;
        stuck_stage   := r.stuck_stage;
        minutes_stuck := round(r.minutes_stuck, 1);
        alert_id      := v_alert;
        RETURN NEXT;
    END LOOP;
END;
$$;

COMMENT ON FUNCTION monitoring.sweep_orphaned_documents(integer, integer) IS
    'Orphan-document sweep. Remediates documents stuck PENDING beyond '
    'p_stale_minutes (up to p_limit) via append-only operations: document '
    'status -> HUMAN_REVIEW, new FAILED processing_history row, monitoring.alerts '
    'row. Idempotent. Called on schedule by the standalone Orphan Sweep workflow. '
    'Also a SUPPORTED MANUAL/OPERATOR entry point: a DBA may invoke it directly, '
    'e.g. SELECT * FROM monitoring.sweep_orphaned_documents(); (defaults 30 min / '
    'limit 100) or with overrides, e.g. monitoring.sweep_orphaned_documents(5, 10). '
    'It returns the remediated set and produces the identical audit trail as the '
    'scheduled path (the workflow adds no remediation logic of its own).';

COMMIT;
