"""Add L2BL4 evidence contract surfaces.

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-15 00:00:01.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("ots_stamps", sa.Column("bitcoin_block", sa.BigInteger(), nullable=True))
    op.create_check_constraint(
        "ck_ots_stamps_bitcoin_block_positive",
        "ots_stamps",
        "bitcoin_block IS NULL OR bitcoin_block > 0",
    )
    op.execute(text("""
        CREATE INDEX idx_ots_stamps_ticket_confirmed
        ON ots_stamps (ticket_id, bitcoin_block)
        WHERE bitcoin_block IS NOT NULL
    """))

    op.add_column(
        "l2bl4_badges",
        sa.Column("badge_class", sa.String(16), server_default=sa.text("'keepsake'"), nullable=False),
    )
    op.add_column("l2bl4_badges", sa.Column("ots_stamp_id", sa.BigInteger(), nullable=True))
    op.add_column("l2bl4_badges", sa.Column("composite_sig_hash", sa.String(128), nullable=True))
    op.add_column(
        "l2bl4_badges",
        sa.Column("contract_version", sa.String(32), server_default=sa.text("'l2bl4.v1'"), nullable=False),
    )
    op.create_check_constraint(
        "ck_l2bl4_badges_badge_class",
        "l2bl4_badges",
        "badge_class IN ('public', 'sovereign', 'keepsake')",
    )
    op.create_check_constraint(
        "ck_l2bl4_badges_composite_sig_hash_nonempty",
        "l2bl4_badges",
        "composite_sig_hash IS NULL OR length(btrim(composite_sig_hash)) > 0",
    )
    op.create_foreign_key(
        "fk_l2bl4_badges_ots_stamp_id",
        "l2bl4_badges",
        "ots_stamps",
        ["ots_stamp_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "idx_l2bl4_badges_class_status",
        "l2bl4_badges",
        ["project_id", "badge_class", "issuance_status"],
    )
    op.execute(text("""
        CREATE INDEX idx_l2bl4_badges_ots_stamp_id
        ON l2bl4_badges (ots_stamp_id)
        WHERE ots_stamp_id IS NOT NULL
    """))

    op.execute(text("""
        CREATE OR REPLACE FUNCTION l2bl4_jsonb_int_at(payload jsonb, path text[])
        RETURNS integer
        LANGUAGE sql
        IMMUTABLE
        AS $$
            SELECT CASE
                WHEN payload #> path IS NULL THEN NULL
                WHEN jsonb_typeof(payload #> path) = 'number'
                     AND payload #>> path ~ '^[0-9]+$'
                    THEN (payload #>> path)::integer
                WHEN jsonb_typeof(payload #> path) = 'string'
                     AND payload #>> path ~ '^[0-9]+$'
                    THEN (payload #>> path)::integer
                ELSE NULL
            END
        $$
    """))

    op.execute(text("""
        CREATE VIEW v_l2bl4_ticket_evidence_contract AS
        WITH ticket_base AS (
            SELECT
                at.ticket_id,
                at.project_id,
                at.flow_name,
                at.ticket_type,
                at.status,
                at.output_json,
                COALESCE(
                    l2bl4_jsonb_int_at(at.output_json, ARRAY['sorry_gated']),
                    l2bl4_jsonb_int_at(at.output_json, ARRAY['audit', 'sorry_gated']),
                    l2bl4_jsonb_int_at(at.output_json, ARRAY['ticket', 'data', 'sorry_gated']),
                    l2bl4_jsonb_int_at(at.output_json, ARRAY['sorry_count']),
                    l2bl4_jsonb_int_at(at.output_json, ARRAY['audit', 'sorry_count']),
                    l2bl4_jsonb_int_at(at.output_json, ARRAY['ticket', 'data', 'sorry_count'])
                ) AS reported_sorry_gated_count
            FROM audit_tickets at
        )
        SELECT
            tb.ticket_id,
            tb.project_id,
            tb.flow_name,
            tb.ticket_type,
            tb.status = 'success' AS audit_success,
            tb.reported_sorry_gated_count,
            COALESCE(ob.sorry_obligation_count, 0)::integer AS sorry_obligation_count,
            CASE
                WHEN tb.reported_sorry_gated_count IS NULL
                    THEN COALESCE(ob.sorry_obligation_count, 0) = 0
                ELSE tb.reported_sorry_gated_count = COALESCE(ob.sorry_obligation_count, 0)
            END AS obligation_count_matches,
            COALESCE(st.has_ticket_ots_stamp, false) AS has_ticket_ots_stamp,
            COALESCE(st.has_confirmed_ots_stamp, false) AS has_confirmed_ots_stamp,
            st.ots_stamp_id,
            st.bitcoin_block,
            st.stamp_provider,
            st.verification_status AS ots_verification_status,
            (
                tb.status = 'success'
                AND COALESCE(st.has_ticket_ots_stamp, false)
                AND COALESCE(st.has_confirmed_ots_stamp, false)
                AND CASE
                    WHEN tb.reported_sorry_gated_count IS NULL
                        THEN COALESCE(ob.sorry_obligation_count, 0) = 0
                    ELSE tb.reported_sorry_gated_count = COALESCE(ob.sorry_obligation_count, 0)
                END
            ) AS public_ready,
            tb.status = 'success' AS keepsake_ready,
            jsonb_build_object(
                'contract_version', 'l2bl4.v1',
                'ticket_id', tb.ticket_id,
                'audit_success', tb.status = 'success',
                'reported_sorry_gated_count', tb.reported_sorry_gated_count,
                'sorry_obligation_count', COALESCE(ob.sorry_obligation_count, 0)::integer,
                'obligation_count_matches', CASE
                    WHEN tb.reported_sorry_gated_count IS NULL
                        THEN COALESCE(ob.sorry_obligation_count, 0) = 0
                    ELSE tb.reported_sorry_gated_count = COALESCE(ob.sorry_obligation_count, 0)
                END,
                'has_ticket_ots_stamp', COALESCE(st.has_ticket_ots_stamp, false),
                'has_confirmed_ots_stamp', COALESCE(st.has_confirmed_ots_stamp, false),
                'ots_stamp_id', st.ots_stamp_id,
                'bitcoin_block', st.bitcoin_block,
                'ots_verification_status', st.verification_status,
                'linked_obligation_count', COALESCE(ob.linked_obligation_count, 0)::integer
            ) AS evidence_contract
        FROM ticket_base tb
        LEFT JOIN LATERAL (
            SELECT
                COUNT(po.id) AS linked_obligation_count,
                COALESCE(
                    SUM(
                        COALESCE(
                            l2bl4_jsonb_int_at(po.evidence, ARRAY['sorry_count']),
                            l2bl4_jsonb_int_at(po.evidence, ARRAY['sorry_gated']),
                            1
                        )
                    ) FILTER (
                        WHERE po.obligation_type IN (
                            'sorry',
                            'sorry_gated',
                            'sorry_in_proof',
                            'admit',
                            'axiom',
                            'declared_axiom'
                        )
                    ),
                    0
                ) AS sorry_obligation_count
            FROM proof_obligations po
            WHERE po.ticket_id = tb.ticket_id
        ) ob ON true
        LEFT JOIN LATERAL (
            SELECT
                EXISTS (
                    SELECT 1 FROM ots_stamps os
                    WHERE os.ticket_id = tb.ticket_id
                ) AS has_ticket_ots_stamp,
                EXISTS (
                    SELECT 1 FROM ots_stamps os
                    WHERE os.ticket_id = tb.ticket_id
                      AND os.bitcoin_block IS NOT NULL
                ) AS has_confirmed_ots_stamp,
                best.id AS ots_stamp_id,
                best.bitcoin_block,
                best.stamp_provider,
                best.verification_status
            FROM LATERAL (
                SELECT os.id, os.bitcoin_block, os.stamp_provider, os.verification_status
                FROM ots_stamps os
                WHERE os.ticket_id = tb.ticket_id
                ORDER BY
                    (os.bitcoin_block IS NOT NULL) DESC,
                    os.bitcoin_block DESC NULLS LAST,
                    os.verified_at DESC NULLS LAST,
                    os.created_at DESC,
                    os.id DESC
                LIMIT 1
            ) best
        ) st ON true
    """))

    op.execute(text("""
        CREATE OR REPLACE FUNCTION l2bl4_ticket_evidence_snapshot(p_ticket_id text)
        RETURNS jsonb
        LANGUAGE sql
        STABLE
        AS $$
            SELECT evidence_contract
            FROM v_l2bl4_ticket_evidence_contract
            WHERE ticket_id = p_ticket_id
        $$
    """))

    op.execute(text("""
        CREATE OR REPLACE FUNCTION l2bl4_badge_contract_error(
            p_ticket_id text,
            p_badge_class text,
            p_composite_sig_hash text DEFAULT NULL
        )
        RETURNS text
        LANGUAGE plpgsql
        STABLE
        AS $$
        DECLARE
            contract record;
        BEGIN
            IF p_badge_class IS NULL
               OR p_badge_class NOT IN ('public', 'sovereign', 'keepsake') THEN
                RETURN 'unsupported_badge_class';
            END IF;

            IF p_ticket_id IS NULL OR length(btrim(p_ticket_id)) = 0 THEN
                RETURN 'ticket_required';
            END IF;

            SELECT *
              INTO contract
              FROM v_l2bl4_ticket_evidence_contract
             WHERE ticket_id = p_ticket_id;

            IF NOT FOUND OR NOT contract.audit_success THEN
                RETURN 'audit_ticket_must_succeed';
            END IF;

            IF p_badge_class = 'keepsake' THEN
                RETURN NULL;
            END IF;

            IF NOT contract.has_ticket_ots_stamp THEN
                RETURN 'ots_stamp_required';
            END IF;

            IF NOT contract.has_confirmed_ots_stamp THEN
                RETURN 'bitcoin_block_required';
            END IF;

            IF NOT contract.obligation_count_matches THEN
                RETURN 'sorry_obligation_count_mismatch';
            END IF;

            IF p_badge_class = 'sovereign'
               AND NULLIF(btrim(COALESCE(p_composite_sig_hash, '')), '') IS NULL THEN
                RETURN 'composite_sig_hash_required';
            END IF;

            RETURN NULL;
        END
        $$
    """))

    op.execute(text("""
        CREATE OR REPLACE FUNCTION enforce_l2bl4_badge_contract()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            contract_error text;
        BEGIN
            IF NEW.issuance_status = 'issued' THEN
                contract_error := l2bl4_badge_contract_error(
                    NEW.ticket_id,
                    NEW.badge_class,
                    NEW.composite_sig_hash
                );

                IF contract_error IS NOT NULL THEN
                    RAISE EXCEPTION 'L2BL4 badge contract violation: %', contract_error
                        USING ERRCODE = '23514';
                END IF;

                IF NEW.badge_class = 'keepsake' THEN
                    NEW.evidence := jsonb_strip_nulls(
                        COALESCE(NEW.evidence, '{}'::jsonb)
                        || jsonb_build_object(
                            'l2bl4_marker', 'keepsake_unverified',
                            'verified', false
                        )
                    );
                END IF;
            END IF;

            RETURN NEW;
        END
        $$
    """))

    op.execute(text("""
        CREATE TRIGGER trg_l2bl4_badges_enforce_contract
        BEFORE INSERT OR UPDATE OF ticket_id, badge_class, composite_sig_hash, issuance_status, evidence
        ON l2bl4_badges
        FOR EACH ROW
        EXECUTE FUNCTION enforce_l2bl4_badge_contract()
    """))

    op.execute(text("""
        CREATE VIEW v_l2bl4_badge_validity AS
        SELECT
            b.id,
            b.badge_id,
            b.project_id,
            b.ticket_id,
            b.subject_type,
            b.subject_key,
            b.subject_digest,
            b.badge_type,
            b.badge_class,
            b.issuance_status,
            b.ots_stamp_id,
            b.composite_sig_hash,
            b.contract_version,
            b.issued_at,
            b.revoked_at,
            c.audit_success,
            c.has_ticket_ots_stamp,
            c.has_confirmed_ots_stamp,
            c.reported_sorry_gated_count,
            c.sorry_obligation_count,
            c.obligation_count_matches,
            c.bitcoin_block,
            c.ots_verification_status,
            l2bl4_badge_contract_error(b.ticket_id, b.badge_class, b.composite_sig_hash) AS contract_error,
            CASE
                WHEN b.issuance_status <> 'issued' THEN false
                WHEN b.badge_class = 'keepsake' THEN COALESCE(c.audit_success, false)
                WHEN b.badge_class = 'public' THEN COALESCE(c.public_ready, false)
                WHEN b.badge_class = 'sovereign' THEN COALESCE(c.public_ready, false)
                    AND NULLIF(btrim(COALESCE(b.composite_sig_hash, '')), '') IS NOT NULL
                ELSE false
            END AS is_currently_valid,
            CASE
                WHEN b.issuance_status <> 'issued' THEN 'not_issued'
                WHEN b.badge_class = 'keepsake' AND COALESCE(c.audit_success, false)
                    THEN 'keepsake_unverified'
                WHEN b.badge_class = 'public' AND COALESCE(c.public_ready, false)
                    THEN 'public_confirmed'
                WHEN b.badge_class = 'sovereign'
                     AND COALESCE(c.public_ready, false)
                     AND NULLIF(btrim(COALESCE(b.composite_sig_hash, '')), '') IS NOT NULL
                    THEN 'sovereign_confirmed'
                ELSE 'invalid'
            END AS contract_status,
            c.evidence_contract
        FROM l2bl4_badges b
        LEFT JOIN v_l2bl4_ticket_evidence_contract c ON c.ticket_id = b.ticket_id
    """))


def downgrade() -> None:
    op.execute(text("DROP VIEW IF EXISTS v_l2bl4_badge_validity"))
    op.execute(text("DROP TRIGGER IF EXISTS trg_l2bl4_badges_enforce_contract ON l2bl4_badges"))
    op.execute(text("DROP FUNCTION IF EXISTS enforce_l2bl4_badge_contract()"))
    op.execute(text("DROP FUNCTION IF EXISTS l2bl4_badge_contract_error(text, text, text)"))
    op.execute(text("DROP FUNCTION IF EXISTS l2bl4_ticket_evidence_snapshot(text)"))
    op.execute(text("DROP VIEW IF EXISTS v_l2bl4_ticket_evidence_contract"))
    op.execute(text("DROP FUNCTION IF EXISTS l2bl4_jsonb_int_at(jsonb, text[])"))

    op.execute(text("DROP INDEX IF EXISTS idx_l2bl4_badges_ots_stamp_id"))
    op.drop_index("idx_l2bl4_badges_class_status", table_name="l2bl4_badges")
    op.drop_constraint("fk_l2bl4_badges_ots_stamp_id", "l2bl4_badges", type_="foreignkey")
    op.drop_constraint("ck_l2bl4_badges_composite_sig_hash_nonempty", "l2bl4_badges", type_="check")
    op.drop_constraint("ck_l2bl4_badges_badge_class", "l2bl4_badges", type_="check")
    op.drop_column("l2bl4_badges", "contract_version")
    op.drop_column("l2bl4_badges", "composite_sig_hash")
    op.drop_column("l2bl4_badges", "ots_stamp_id")
    op.drop_column("l2bl4_badges", "badge_class")

    op.execute(text("DROP INDEX IF EXISTS idx_ots_stamps_ticket_confirmed"))
    op.drop_constraint("ck_ots_stamps_bitcoin_block_positive", "ots_stamps", type_="check")
    op.drop_column("ots_stamps", "bitcoin_block")