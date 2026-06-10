"""Lakebase CRUD for HITL profile proposals (FR-6, M9)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Protocol

from agent_memory.memory.lakebase_ddl import ensure_audit_log, ensure_profile_proposals
from agent_memory.memory.profile_models import DistilledClientProfile
from agent_memory.memory.proposal_models import ProfileProposal

if TYPE_CHECKING:
    from agent_memory.config import Settings
    from agent_memory.memory.profile_store import ProfileStore


class ProposalCreator(Protocol):
    """Minimal interface needed by run_distillation for HITL mode."""

    def create_proposal(
        self, profile: DistilledClientProfile, *, run_id: str | None = None
    ) -> str: ...

    def latest_source_artifact_id(self, client_id: str) -> int | None:
        """Highest artifact_id any prior proposal for this client distilled.

        Used as a high-water mark so distillation skips clients with no new artifacts
        (the LLM is non-deterministic, so re-running on unchanged artifacts is pure churn).
        """
        ...


class LakebaseProposalStore:
    """Read/write profile proposals from/to Lakebase (M9)."""

    def __init__(
        self,
        settings: Settings | None = None,
        profile_store: ProfileStore | None = None,
    ) -> None:
        # Deferred imports so the store can be imported without a workspace connection.
        from agent_memory.config import Settings as _Settings
        from agent_memory.memory.profile_store import DeltaProfileStore

        self._settings = settings or _Settings.from_env()
        self._profile_store: ProfileStore = profile_store or DeltaProfileStore(self._settings)

    def create_proposal(
        self,
        profile: DistilledClientProfile,
        *,
        run_id: str | None = None,
    ) -> str:
        """Write a pending proposal to Lakebase and return the proposal_id."""
        from agent_memory.memory.connection import lakebase_connection

        proposal_id = str(uuid.uuid4())
        payload = {
            "risk_tolerance": profile.risk_tolerance,
            "investment_goals": profile.investment_goals,
            "family_context": profile.family_context,
            "stated_preferences": profile.stated_preferences,
            "summary": profile.summary,
        }
        with lakebase_connection() as conn, conn.cursor() as cur:
            ensure_profile_proposals(cur)
            ensure_audit_log(cur)
            # T18: supersede still-pending proposals for this client so they don't
            # accumulate across distillation runs; only the newest stays reviewable.
            cur.execute(
                """
                UPDATE profile_proposals
                SET status = 'superseded', reviewed_at = now()
                WHERE client_id = %s AND status = 'pending'
                RETURNING proposal_id
                """,
                (profile.client_id,),
            )
            for (superseded_id,) in cur.fetchall():
                cur.execute(
                    """
                    INSERT INTO audit_log (actor, actor_kind, action, target_ref, payload)
                    VALUES ('distillation', 'job', 'supersede_proposal', %s, %s::jsonb)
                    """,
                    (
                        f"client:{profile.client_id}/proposal:{superseded_id}",
                        json.dumps(
                            {"superseded_by": proposal_id, "client_id": profile.client_id}
                        ),
                    ),
                )
            cur.execute(
                """
                INSERT INTO profile_proposals
                    (proposal_id, client_id, proposed_profile, source_artifact_ids, run_id)
                VALUES (%s, %s, %s::jsonb, %s, %s)
                """,
                (
                    proposal_id,
                    profile.client_id,
                    json.dumps(payload),
                    profile.source_artifact_ids,
                    run_id,
                ),
            )
            conn.commit()
        return proposal_id

    def latest_source_artifact_id(self, client_id: str) -> int | None:
        from agent_memory.memory.connection import lakebase_connection

        with lakebase_connection() as conn, conn.cursor() as cur:
            ensure_profile_proposals(cur)
            cur.execute(
                """
                SELECT MAX(t)
                FROM profile_proposals, unnest(source_artifact_ids) AS t
                WHERE client_id = %s
                """,
                (client_id,),
            )
            row = cur.fetchone()
        return int(row[0]) if row and row[0] is not None else None

    def get_proposal(self, proposal_id: str) -> ProfileProposal | None:
        from agent_memory.memory.connection import lakebase_connection

        with lakebase_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT proposal_id, client_id, proposed_profile, source_artifact_ids,
                       status, proposed_at, reviewed_at, reviewed_by, run_id
                FROM profile_proposals
                WHERE proposal_id = %s
                """,
                (proposal_id,),
            )
            row = cur.fetchone()
        return _row_to_proposal(row) if row else None

    def list_proposals(
        self,
        *,
        status: str = "pending",
        client_id: str | None = None,
    ) -> list[ProfileProposal]:
        from agent_memory.memory.connection import lakebase_connection

        if client_id:
            sql = """
            SELECT proposal_id, client_id, proposed_profile, source_artifact_ids,
                   status, proposed_at, reviewed_at, reviewed_by, run_id
            FROM profile_proposals
            WHERE status = %s AND client_id = %s
            ORDER BY proposed_at DESC
            """
            params: tuple = (status, client_id)
        else:
            sql = """
            SELECT proposal_id, client_id, proposed_profile, source_artifact_ids,
                   status, proposed_at, reviewed_at, reviewed_by, run_id
            FROM profile_proposals
            WHERE status = %s
            ORDER BY proposed_at DESC
            """
            params = (status,)
        with lakebase_connection() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [_row_to_proposal(r) for r in rows]

    def accept_proposal(
        self,
        proposal_id: str,
        *,
        reviewed_by: str,
        overrides: dict[str, object] | None = None,
    ) -> int | None:
        """Commit proposal to Delta, write audit, mark accepted.

        overrides: optional field-level edits applied before the Delta write —
        supports the Edit-then-Accept UI flow without a separate edit endpoint.
        """
        from agent_memory.memory.connection import lakebase_connection

        proposal = self.get_proposal(proposal_id)
        if proposal is None:
            raise ValueError(f"Proposal {proposal_id!r} not found")
        if proposal.status != "pending":
            raise ValueError(f"Proposal {proposal_id!r} already has status {proposal.status!r}")

        profile = proposal.proposed_profile
        if overrides:
            profile = profile.model_copy(update=overrides)

        delta_version = self._profile_store.upsert_profile(profile)
        now = datetime.now(tz=timezone.utc)

        with lakebase_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE profile_proposals
                SET status = 'accepted', reviewed_at = %s, reviewed_by = %s
                WHERE proposal_id = %s
                """,
                (now, reviewed_by, proposal_id),
            )
            ensure_audit_log(cur)
            cur.execute(
                """
                INSERT INTO audit_log (actor, actor_kind, action, target_ref, payload)
                VALUES (%s, 'advisor', 'accept_proposal', %s, %s::jsonb)
                """,
                (
                    reviewed_by,
                    f"client:{profile.client_id}/proposal:{proposal_id}",
                    json.dumps(
                        {
                            "proposal_id": proposal_id,
                            "client_id": profile.client_id,
                            "delta_version": delta_version,
                            "overrides_applied": bool(overrides),
                        }
                    ),
                ),
            )
            conn.commit()
        return delta_version

    def reject_proposal(self, proposal_id: str, *, reviewed_by: str) -> None:
        """Mark proposal rejected and write audit row. No Delta write."""
        from agent_memory.memory.connection import lakebase_connection

        proposal = self.get_proposal(proposal_id)
        if proposal is None:
            raise ValueError(f"Proposal {proposal_id!r} not found")
        if proposal.status != "pending":
            raise ValueError(f"Proposal {proposal_id!r} already has status {proposal.status!r}")

        now = datetime.now(tz=timezone.utc)
        with lakebase_connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                UPDATE profile_proposals
                SET status = 'rejected', reviewed_at = %s, reviewed_by = %s
                WHERE proposal_id = %s
                """,
                (now, reviewed_by, proposal_id),
            )
            ensure_audit_log(cur)
            cur.execute(
                """
                INSERT INTO audit_log (actor, actor_kind, action, target_ref, payload)
                VALUES (%s, 'advisor', 'reject_proposal', %s, %s::jsonb)
                """,
                (
                    reviewed_by,
                    f"client:{proposal.client_id}/proposal:{proposal_id}",
                    json.dumps(
                        {"proposal_id": proposal_id, "client_id": proposal.client_id}
                    ),
                ),
            )
            conn.commit()


def _row_to_proposal(row: tuple) -> ProfileProposal:
    (
        proposal_id,
        client_id,
        proposed_profile_json,
        source_artifact_ids,
        status,
        proposed_at,
        reviewed_at,
        reviewed_by,
        run_id,
    ) = row
    data = (
        json.loads(proposed_profile_json)
        if isinstance(proposed_profile_json, str)
        else proposed_profile_json
    )
    profile = DistilledClientProfile(
        client_id=str(client_id),
        risk_tolerance=data.get("risk_tolerance", "unknown"),
        investment_goals=data.get("investment_goals", []),
        family_context=data.get("family_context", ""),
        stated_preferences=data.get("stated_preferences", ""),
        summary=data.get("summary", ""),
        source_artifact_ids=list(source_artifact_ids) if source_artifact_ids else [],
    )
    return ProfileProposal(
        proposal_id=str(proposal_id),
        client_id=str(client_id),
        proposed_profile=profile,
        status=str(status),  # type: ignore[arg-type]
        proposed_at=proposed_at if isinstance(proposed_at, datetime) else datetime.now(tz=timezone.utc),
        reviewed_at=reviewed_at if isinstance(reviewed_at, datetime) else None,
        reviewed_by=str(reviewed_by) if reviewed_by else None,
        run_id=str(run_id) if run_id else None,
    )


class InMemoryProposalStore:
    """Test double — no Lakebase required."""

    def __init__(self, profile_store: ProfileStore | None = None) -> None:
        from agent_memory.memory.profile_store import InMemoryProfileStore

        self._profile_store: ProfileStore = profile_store or InMemoryProfileStore()
        self._proposals: dict[str, ProfileProposal] = {}

    def create_proposal(
        self,
        profile: DistilledClientProfile,
        *,
        run_id: str | None = None,
    ) -> str:
        proposal_id = str(uuid.uuid4())
        # T18: supersede still-pending proposals for this client.
        for pid, existing in list(self._proposals.items()):
            if existing.client_id == profile.client_id and existing.status == "pending":
                self._proposals[pid] = existing.model_copy(
                    update={"status": "superseded", "reviewed_at": datetime.now(tz=timezone.utc)}
                )
        self._proposals[proposal_id] = ProfileProposal(
            proposal_id=proposal_id,
            client_id=profile.client_id,
            proposed_profile=profile,
            status="pending",
            proposed_at=datetime.now(tz=timezone.utc),
            run_id=run_id,
        )
        return proposal_id

    def latest_source_artifact_id(self, client_id: str) -> int | None:
        artifact_ids = [
            aid
            for p in self._proposals.values()
            if p.client_id == client_id
            for aid in p.proposed_profile.source_artifact_ids
        ]
        return max(artifact_ids) if artifact_ids else None

    def get_proposal(self, proposal_id: str) -> ProfileProposal | None:
        return self._proposals.get(proposal_id)

    def list_proposals(
        self,
        *,
        status: str = "pending",
        client_id: str | None = None,
    ) -> list[ProfileProposal]:
        results = [p for p in self._proposals.values() if p.status == status]
        if client_id:
            results = [p for p in results if p.client_id == client_id]
        return sorted(results, key=lambda p: p.proposed_at, reverse=True)

    def accept_proposal(
        self,
        proposal_id: str,
        *,
        reviewed_by: str,
        overrides: dict[str, object] | None = None,
    ) -> int | None:
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"Proposal {proposal_id!r} not found")
        if proposal.status != "pending":
            raise ValueError(f"Proposal {proposal_id!r} already has status {proposal.status!r}")

        profile = proposal.proposed_profile
        if overrides:
            profile = profile.model_copy(update=overrides)

        delta_version = self._profile_store.upsert_profile(
            profile,
            audit_actor=reviewed_by,
            audit_actor_kind="advisor",
            audit_action="accept_proposal",
        )
        self._proposals[proposal_id] = proposal.model_copy(
            update={
                "status": "accepted",
                "reviewed_at": datetime.now(tz=timezone.utc),
                "reviewed_by": reviewed_by,
            }
        )
        return delta_version

    def reject_proposal(self, proposal_id: str, *, reviewed_by: str) -> None:
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise ValueError(f"Proposal {proposal_id!r} not found")
        if proposal.status != "pending":
            raise ValueError(f"Proposal {proposal_id!r} already has status {proposal.status!r}")
        self._proposals[proposal_id] = proposal.model_copy(
            update={
                "status": "rejected",
                "reviewed_at": datetime.now(tz=timezone.utc),
                "reviewed_by": reviewed_by,
            }
        )
