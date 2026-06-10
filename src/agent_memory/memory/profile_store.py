"""Write distilled profiles to UC Delta and log audit events (ADR-0005)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Protocol

from agent_memory.config import Settings
from agent_memory.memory.connection import lakebase_connection
from agent_memory.memory.lakebase_ddl import ensure_audit_log
from agent_memory.memory.profile_models import DistilledClientProfile
from agent_memory.memory.sql_warehouse import (
    _sql_array_bigints,
    _sql_array_strings,
    _sql_string,
    execute_sql,
    fetch_sql,
)


class ProfileStore(Protocol):
    def upsert_profile(
        self,
        profile: DistilledClientProfile,
        *,
        audit_actor: str | None = None,
        audit_actor_kind: str | None = None,
        audit_action: str | None = None,
    ) -> int | None: ...

    def get_profile(self, client_id: str) -> DistilledClientProfile | None: ...


class InMemoryProfileStore:
    """Test double — records upserts without UC."""

    def __init__(self) -> None:
        self.profiles: dict[str, DistilledClientProfile] = {}
        self.audit_events: list[dict] = []
        self._version = 0

    def upsert_profile(
        self,
        profile: DistilledClientProfile,
        *,
        audit_actor: str | None = None,
        audit_actor_kind: str | None = None,
        audit_action: str | None = None,
    ) -> int | None:
        self._version += 1
        stamped = profile.model_copy(
            update={"distilled_at": profile.distilled_at or datetime.now(tz=timezone.utc)}
        )
        self.profiles[profile.client_id] = stamped
        self.audit_events.append(
            {
                "client_id": profile.client_id,
                "delta_version": self._version,
                "source_artifact_ids": profile.source_artifact_ids,
                "audit_actor": audit_actor,
                "audit_actor_kind": audit_actor_kind,
                "audit_action": audit_action,
            }
        )
        return self._version

    def get_profile(self, client_id: str) -> DistilledClientProfile | None:
        return self.profiles.get(client_id)


class DeltaProfileStore:
    """MERGE into UC Delta `client_profile` via SQL warehouse."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings.from_env()

    @property
    def table_fqn(self) -> str:
        return f"{self._settings.uc_catalog}.{self._settings.uc_schema}.client_profile"

    def get_profile(self, client_id: str) -> DistilledClientProfile | None:
        sql = f"""
        SELECT client_id, risk_tolerance, investment_goals, family_context,
               stated_preferences, summary, source_artifact_ids, distilled_at
        FROM {self.table_fqn}
        WHERE client_id = {_sql_string(client_id)}
        LIMIT 1
        """
        rows = fetch_sql(sql, settings=self._settings)
        if not rows:
            return None
        row = rows[0]
        goals = _parse_sql_array(row[2] or "[]")
        artifact_ids = [int(x) for x in _parse_sql_array(row[6] or "[]") if str(x).isdigit()]
        return DistilledClientProfile(
            client_id=row[0] or client_id,
            risk_tolerance=row[1] or "unknown",  # type: ignore[arg-type]
            investment_goals=goals,
            family_context=row[3] or "",
            stated_preferences=row[4] or "",
            summary=row[5] or "",
            source_artifact_ids=artifact_ids,
            distilled_at=_parse_timestamp(row[7]),
        )

    def upsert_profile(
        self,
        profile: DistilledClientProfile,
        *,
        audit_actor: str | None = None,
        audit_actor_kind: str | None = None,
        audit_action: str | None = None,
    ) -> int | None:
        """Commit a profile to Delta and write an audit row.

        The audit actor defaults to the nightly job. A manual advisor edit passes
        audit_actor/kind/action so the compliance trail attributes the human.
        """
        merge_sql = f"""
        MERGE INTO {self.table_fqn} AS target
        USING (
          SELECT
            {_sql_string(profile.client_id)} AS client_id,
            {_sql_string(profile.risk_tolerance)} AS risk_tolerance,
            {_sql_array_strings(profile.investment_goals)} AS investment_goals,
            {_sql_string(profile.family_context)} AS family_context,
            {_sql_string(profile.stated_preferences)} AS stated_preferences,
            {_sql_string(profile.summary)} AS summary,
            {_sql_array_bigints(profile.source_artifact_ids)} AS source_artifact_ids,
            current_timestamp() AS distilled_at,
            current_timestamp() AS updated_at
        ) AS source
        ON target.client_id = source.client_id
        WHEN MATCHED THEN UPDATE SET
          risk_tolerance = source.risk_tolerance,
          investment_goals = source.investment_goals,
          family_context = source.family_context,
          stated_preferences = source.stated_preferences,
          summary = source.summary,
          source_artifact_ids = source.source_artifact_ids,
          distilled_at = source.distilled_at,
          updated_at = source.updated_at
        WHEN NOT MATCHED THEN INSERT (
          client_id, risk_tolerance, investment_goals, family_context,
          stated_preferences, summary, source_artifact_ids, distilled_at, updated_at
        ) VALUES (
          source.client_id, source.risk_tolerance, source.investment_goals,
          source.family_context, source.stated_preferences, source.summary,
          source.source_artifact_ids, source.distilled_at, source.updated_at
        )
        """
        execute_sql(merge_sql, settings=self._settings)
        version = self._latest_table_version()
        audit_kwargs: dict[str, str] = {}
        if audit_actor is not None:
            audit_kwargs["actor"] = audit_actor
        if audit_actor_kind is not None:
            audit_kwargs["actor_kind"] = audit_actor_kind
        if audit_action is not None:
            audit_kwargs["action"] = audit_action
        log_profile_upsert_audit(
            profile,
            table_fqn=self.table_fqn,
            delta_version=version,
            settings=self._settings,
            **audit_kwargs,
        )
        return version

    def _latest_table_version(self) -> int | None:
        history_sql = f"DESCRIBE HISTORY {self.table_fqn} LIMIT 1"
        rows = fetch_sql(history_sql, settings=self._settings)
        if not rows:
            return None
        # DESCRIBE HISTORY columns: version is first column in default output
        try:
            raw = rows[0][0]
            return int(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None


def _parse_sql_array(raw: str) -> list[str]:
    text = raw.strip()
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        if not inner:
            return []
        return [part.strip().strip('"') for part in inner.split(",")]
    return [text] if text else []


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def log_profile_upsert_audit(
    profile: DistilledClientProfile,
    *,
    table_fqn: str,
    delta_version: int | None,
    settings: Settings | None = None,
    agent_run_id: str | None = None,
    actor: str = "distillation_nightly",
    actor_kind: str = "job",
    action: str = "upsert_profile",
) -> None:
    """Append Lakebase audit row for a successful profile upsert (FR-5).

    Defaults attribute the nightly job; a manual advisor edit overrides actor/kind/action.
    """
    payload = {
        "client_id": profile.client_id,
        "delta_table": table_fqn,
        "delta_version": delta_version,
        "source_artifact_ids": profile.source_artifact_ids,
        "risk_tolerance": profile.risk_tolerance,
    }
    with lakebase_connection() as conn, conn.cursor() as cur:
        ensure_audit_log(cur)
        cur.execute(
            """
            INSERT INTO audit_log (actor, actor_kind, action, target_ref, payload, agent_run_id)
            VALUES (%s, %s, %s, %s, %s::jsonb, %s)
            """,
            (
                actor,
                actor_kind,
                action,
                f"client:{profile.client_id}",
                json.dumps(payload),
                agent_run_id,
            ),
        )
        conn.commit()
