"""FastAPI backend for the wealth advisor Databricks App (FR-7, ADR-0003)."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

from agent_memory.agents.run import run_turn_with_state
from agent_memory.agents.streaming import stream_advisor_events, stream_ingest_events
from agent_memory.config import Settings, ensure_databricks_auth, get_workspace_client
from agent_memory.memory.profile_models import DistilledClientProfile
from agent_memory.memory.profile_store import DeltaProfileStore
from agent_memory.memory.proposal_models import ProfileProposal
from agent_memory.memory.proposal_store import LakebaseProposalStore
from agent_memory.memory.store import LakebaseArtifactStore
from agent_memory.ui.schemas import (
    ArtifactOut,
    ChatRequest,
    ChatResponse,
    ClientInfo,
    ClientProfileOut,
    DistillResponse,
    DistillRunStatus,
    HealthResponse,
    ProfileEditRequest,
    ProfileEditResponse,
    ProposalAcceptRequest,
    ProposalActionResponse,
    ProposalOut,
    ProposalRejectRequest,
    retrieved_chunks_from_state,
)


def _resolve_static_dir() -> Path | None:
    """Locate built React assets (local editable install, wheel, or synced app root)."""
    here = Path(__file__).resolve().parent
    candidates = (
        here / "frontend" / "dist",
        # Databricks Apps: package is pip-installed but dist stays in synced source tree.
        Path.cwd() / "src" / "agent_memory" / "ui" / "frontend" / "dist",
    )
    for path in candidates:
        if path.is_dir() and (path / "index.html").is_file():
            return path
    return None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = Settings.from_env()
    if not ensure_databricks_auth(settings):
        try:
            get_workspace_client(settings).current_user.me()
        except Exception as err:
            raise RuntimeError(f"Databricks auth failed. {settings.auth_diagnostics()}") from err
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Wealth Advisor Memory", lifespan=lifespan)
    _register_routes(app)
    static_dir = _resolve_static_dir()
    if static_dir is not None:
        app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")

        @app.api_route(
            "/{full_path:path}",
            methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
        )
        def spa_fallback(full_path: str) -> FileResponse:
            if full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="Not found")
            return FileResponse(static_dir / "index.html")

    else:

        @app.get("/")
        def ui_not_deployed() -> None:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Advisor UI not built. Run ./scripts/build_frontend.sh before deploy "
                    "(or ./scripts/deploy_bundle.sh dev). API is at /api/health."
                ),
            )

    return app


_CLIENT_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _validate_client_id(client_id: str) -> None:
    """Reject client_id values that could traverse paths or escape SQL quoting."""
    if not _CLIENT_ID_RE.match(client_id):
        raise HTTPException(
            status_code=422,
            detail=(
                "client_id must contain only letters, digits, underscores, and hyphens."
            ),
        )


def _register_routes(app: FastAPI) -> None:
    def _dependency_error(exc: Exception) -> HTTPException | None:
        msg = str(exc)
        if "Lakebase not configured" in msg:
            return HTTPException(status_code=503, detail=msg)
        if "Lakebase credential refresh failed" in msg:
            return HTTPException(status_code=503, detail=msg)
        if "more than one authorization method configured" in msg:
            return HTTPException(
                status_code=503,
                detail="Databricks auth conflict in app environment (oauth + pat).",
            )
        if "INSUFFICIENT_PERMISSIONS" in msg and "USE CATALOG" in msg:
            return HTTPException(
                status_code=503,
                detail=(
                    "Missing Unity Catalog permission: grant USE CATALOG on "
                    "the configured UC_CATALOG to the app service principal."
                ),
            )
        if "OAuth: User is not authorized" in msg:
            return HTTPException(
                status_code=503,
                detail=(
                    "Lakebase OAuth user is not authorized for this database endpoint. "
                    "Grant the app service principal access to the Lakebase endpoint."
                ),
            )
        if "SQL warehouse" in msg:
            return HTTPException(
                status_code=503,
                detail=(
                    "SQL warehouse not running. Start it in the workspace or set "
                    "DATABRICKS_SQL_WAREHOUSE_ID in .env"
                ),
            )
        return None

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        settings = Settings.from_env()
        # databricks_host is already populated (the Databricks App injects it); avoid
        # constructing a WorkspaceClient here — it's slow without creds and not needed.
        # The App injects the bare hostname (no scheme); prepend https:// so the value
        # is an absolute URL — otherwise the frontend <a href> resolves it relative to
        # the app origin and just reopens the app.
        host = (settings.databricks_host or "").rstrip("/")
        if host and not host.startswith(("http://", "https://")):
            host = f"https://{host}"
        workspace_url = host or None
        return HealthResponse(
            status="ok",
            lakebase_configured=settings.lakebase_configured,
            databricks_app=bool(os.environ.get("DATABRICKS_APP_NAME")),
            uc_catalog=settings.uc_catalog,
            uc_schema=settings.uc_schema,
            volume_name=settings.volume_name,
            workspace_url=workspace_url,
        )

    @app.get("/api/clients", response_model=list[ClientInfo])
    def list_clients() -> list[ClientInfo]:
        try:
            return [
                ClientInfo(id=cid, display_name=name)
                for cid, name in LakebaseArtifactStore().list_clients()
            ]
        except Exception as exc:
            mapped = _dependency_error(exc)
            if mapped is not None:
                raise mapped from exc
            raise

    @app.get("/api/advisors", response_model=list[str])
    def list_advisors() -> list[str]:
        try:
            return LakebaseArtifactStore().list_advisors()
        except Exception as exc:
            mapped = _dependency_error(exc)
            if mapped is not None:
                raise mapped from exc
            raise

    @app.post("/api/distill", response_model=DistillResponse)
    def trigger_distill() -> DistillResponse:
        """Trigger the HITL distillation job on-demand via the Jobs API."""
        settings = Settings.from_env()
        try:
            wc = get_workspace_client(settings)
            job_name = f"agent-memory-distillation-hitl-{os.environ.get('BUNDLE_TARGET', 'dev')}"
            jobs = list(wc.jobs.list(name=job_name))
            if not jobs:
                jobs = [
                    j for j in wc.jobs.list()
                    if ((j.settings.name if j.settings else None) or "").endswith(f"] {job_name}")
                ]
            if not jobs:
                return DistillResponse(
                    status="error",
                    message=f"Job '{job_name}' not found. Deploy the bundle first.",
                )
            job_id = jobs[0].job_id
            if job_id is None:
                return DistillResponse(
                    status="error",
                    message="Job found but job_id is None — bundle may be in a bad state.",
                )
            run = wc.jobs.run_now(job_id=job_id)
            return DistillResponse(status="triggered", run_id=run.run_id)
        except Exception as exc:
            return DistillResponse(status="error", message=str(exc))

    @app.get("/api/distill/{run_id}", response_model=DistillRunStatus)
    def distill_run_status(run_id: int) -> DistillRunStatus:
        """Lifecycle of a triggered distillation run."""
        settings = Settings.from_env()
        wc = get_workspace_client(settings)
        run = wc.jobs.get_run(run_id=run_id)
        state = run.state
        life = state.life_cycle_state.value if state and state.life_cycle_state else ""
        result = state.result_state.value if state and state.result_state else None
        finished = life in ("TERMINATED", "SKIPPED", "INTERNAL_ERROR")
        return DistillRunStatus(
            run_id=run_id, life_cycle_state=life, result_state=result, finished=finished
        )

    @app.get("/api/clients/{client_id}/profile", response_model=ClientProfileOut | None)
    def get_profile(client_id: str) -> ClientProfileOut | None:
        _validate_client_id(client_id)
        try:
            profile = DeltaProfileStore().get_profile(client_id)
        except Exception as exc:
            mapped = _dependency_error(exc)
            if mapped is not None:
                raise mapped from exc
            raise
        if profile is None:
            return None
        return ClientProfileOut(
            client_id=profile.client_id,
            risk_tolerance=profile.risk_tolerance,
            investment_goals=profile.investment_goals,
            family_context=profile.family_context,
            stated_preferences=profile.stated_preferences,
            summary=profile.summary,
            source_artifact_ids=profile.source_artifact_ids,
            distilled_at=profile.distilled_at,
        )

    @app.post("/api/chat", response_model=ChatResponse)
    def chat(body: ChatRequest) -> ChatResponse:
        final = run_turn_with_state(
            client_id=body.client_id,
            advisor_id=body.advisor_id,
            user_message=body.message,
        )
        return ChatResponse(
            response=final.get("response") or "",
            retrieved_chunks=retrieved_chunks_from_state(
                final.get("retrieved_chunks") or []
            ),
            agent_run_id=final.get("agent_run_id"),
        )

    @app.post("/api/chat/stream")
    def chat_stream(body: ChatRequest) -> StreamingResponse:
        """FR-9: SSE stream — retrieve first, tokens during generate."""

        def sse_events() -> Iterator[str]:
            for event in stream_advisor_events(
                client_id=body.client_id,
                advisor_id=body.advisor_id,
                user_message=body.message,
            ):
                yield f"data: {json.dumps(event)}\n\n"

        return StreamingResponse(
            sse_events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # ------------------------------------------------------------------
    # Artifact ingest endpoint (D4, ADR-0010, ADR-0011)
    # ------------------------------------------------------------------

    @app.post("/api/clients/{client_id}/artifacts/ingest")
    async def ingest_artifact(
        client_id: str,
        file: UploadFile,
        advisor_id: str = Form(...),
    ) -> StreamingResponse:
        """Multipart upload → SSE progress stream.

        Rejects oversize files with HTTP 413 before any Volume or DB write (ADR-0011).
        SSE events: step(saved) → step(extracted) → step(embedded) → step(summarized)
        → step(proposed)? → done. Any failure yields error and the stream ends.
        """
        _validate_client_id(client_id)
        settings = Settings.from_env()
        limit = settings.max_upload_bytes
        cap_mb = limit / (1024 * 1024)

        # Reject early when Content-Length (or starlette's file.size) is already known,
        # so a huge upload can't be fully buffered before we check.
        declared_size: int | None = getattr(file, "size", None)
        if declared_size is not None and declared_size > limit:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"File exceeds {cap_mb:.0f} MB ingest cap "
                    f"({declared_size / (1024 * 1024):.1f} MB). "
                    "Split the document or raise MAX_UPLOAD_BYTES."
                ),
            )

        # Read into a bounded buffer: read one byte beyond the cap so we can detect
        # oversize bodies that didn't send Content-Length up front.
        raw_bytes = await file.read(limit + 1)
        if len(raw_bytes) > limit:
            mb = len(raw_bytes) / (1024 * 1024)
            raise HTTPException(
                status_code=413,
                detail=(
                    f"File exceeds {cap_mb:.0f} MB ingest cap ({mb:.1f} MB). "
                    "Split the document or raise MAX_UPLOAD_BYTES."
                ),
            )

        original_filename = file.filename or "upload"
        ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else ""
        kind_map = {
            "pdf": "pdf",
            "jpg": "image", "jpeg": "image", "png": "image",
            "tiff": "image", "tif": "image",
            "docx": "docx", "doc": "docx",
            "txt": "text",
        }
        kind = kind_map.get(ext, "other")

        def sse_frames() -> Iterator[str]:
            for event in stream_ingest_events(
                client_id=client_id,
                advisor_id=advisor_id,
                original_filename=original_filename,
                kind=kind,
                raw_bytes=raw_bytes,
                settings=settings,
            ):
                yield f"data: {json.dumps(event)}\n\n"

        return StreamingResponse(
            sse_frames(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # ------------------------------------------------------------------
    # Artifact read routes (D6 provenance)
    # ------------------------------------------------------------------

    @app.get("/api/clients/{client_id}/artifacts", response_model=list[ArtifactOut])
    def list_artifacts(client_id: str) -> list[ArtifactOut]:
        """Dossier timeline, newest first. extracted_text omitted on list view."""
        _validate_client_id(client_id)
        try:
            store = LakebaseArtifactStore()
            records = store.list_artifacts(client_id=client_id)
        except Exception as exc:
            mapped = _dependency_error(exc)
            if mapped is not None:
                raise mapped from exc
            raise
        # contributed_to_profile is a best-effort badge sourced from the Delta
        # profile (read via a SQL warehouse). A warehouse/Delta hiccup must NOT
        # break the timeline, which is sourced entirely from Lakebase.
        try:
            profile = DeltaProfileStore().get_profile(client_id)
            source_ids: set[int] = set(profile.source_artifact_ids) if profile else set()
        except Exception:
            source_ids = set()
        return [
            ArtifactOut(
                artifact_id=r.artifact_id,
                client_id=r.client_id,
                advisor_id=r.advisor_id,
                kind=r.kind,
                original_filename=r.original_filename,
                volume_path=r.volume_path,
                content_hash=r.content_hash,
                summary=r.summary,
                extracted_text=None,   # omitted on list route
                sensitivity_tags=r.sensitivity_tags,
                contributed_to_profile=r.artifact_id in source_ids,
                ingested_at=r.ingested_at,
            )
            for r in records
        ]

    @app.get("/api/artifacts/{artifact_id}", response_model=ArtifactOut)
    def get_artifact(artifact_id: int) -> ArtifactOut:
        """Detail view: includes extracted_text and summary."""
        try:
            store = LakebaseArtifactStore()
            record = store.get_artifact(artifact_id)
        except Exception as exc:
            mapped = _dependency_error(exc)
            if mapped is not None:
                raise mapped from exc
            raise
        if record is None:
            raise HTTPException(status_code=404, detail="Artifact not found")
        return ArtifactOut(
            artifact_id=record.artifact_id,
            client_id=record.client_id,
            advisor_id=record.advisor_id,
            kind=record.kind,
            original_filename=record.original_filename,
            volume_path=record.volume_path,
            content_hash=record.content_hash,
            summary=record.summary,
            extracted_text=record.extracted_text,
            sensitivity_tags=record.sensitivity_tags,
            contributed_to_profile=False,
            ingested_at=record.ingested_at,
        )

    @app.get("/api/artifacts/{artifact_id}/raw")
    def get_artifact_raw(artifact_id: int) -> Response:
        """Provenance download — raw bytes from UC Volume."""
        try:
            store = LakebaseArtifactStore()
            record = store.get_artifact(artifact_id)
        except Exception as exc:
            mapped = _dependency_error(exc)
            if mapped is not None:
                raise mapped from exc
            raise
        if record is None:
            raise HTTPException(status_code=404, detail="Artifact not found")
        try:
            from agent_memory.memory.volume_store import download_raw
            settings = Settings.from_env()
            raw_io = download_raw(volume_path=record.volume_path, settings=settings)
            raw_bytes = raw_io.read()
        except Exception as exc:
            mapped = _dependency_error(exc)
            if mapped is not None:
                raise mapped from exc
            raise
        content_type = {
            "pdf": "application/pdf",
            "image": "image/jpeg",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "text": "text/plain",
        }.get(record.kind, "application/octet-stream")
        return Response(
            content=raw_bytes,
            media_type=content_type,
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{record.original_filename}"'
                )
            },
        )

    # ------------------------------------------------------------------
    # Proposals & profile edit
    # ------------------------------------------------------------------

    @app.get("/api/proposals", response_model=list[ProposalOut])
    def list_proposals(status: str = "pending", client_id: str | None = None) -> list[ProposalOut]:
        try:
            proposals = LakebaseProposalStore().list_proposals(status=status, client_id=client_id)
        except Exception as exc:
            mapped = _dependency_error(exc)
            if mapped is not None:
                raise mapped from exc
            raise
        return [_proposal_to_out(p) for p in proposals]

    @app.post("/api/proposals/{proposal_id}/accept", response_model=ProposalActionResponse)
    def accept_proposal(
        proposal_id: str, body: ProposalAcceptRequest
    ) -> ProposalActionResponse:
        overrides: dict[str, object] = {}
        if body.risk_tolerance is not None:
            overrides["risk_tolerance"] = body.risk_tolerance
        if body.investment_goals is not None:
            overrides["investment_goals"] = body.investment_goals
        if body.family_context is not None:
            overrides["family_context"] = body.family_context
        if body.stated_preferences is not None:
            overrides["stated_preferences"] = body.stated_preferences
        if body.summary is not None:
            overrides["summary"] = body.summary
        try:
            version = LakebaseProposalStore().accept_proposal(
                proposal_id,
                reviewed_by=body.reviewed_by,
                overrides=overrides or None,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            mapped = _dependency_error(exc)
            if mapped is not None:
                raise mapped from exc
            raise
        return ProposalActionResponse(
            status="accepted", proposal_id=proposal_id, delta_version=version
        )

    @app.post("/api/proposals/{proposal_id}/reject", response_model=ProposalActionResponse)
    def reject_proposal(
        proposal_id: str, body: ProposalRejectRequest
    ) -> ProposalActionResponse:
        try:
            LakebaseProposalStore().reject_proposal(proposal_id, reviewed_by=body.reviewed_by)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            mapped = _dependency_error(exc)
            if mapped is not None:
                raise mapped from exc
            raise
        return ProposalActionResponse(status="rejected", proposal_id=proposal_id)

    @app.put("/api/clients/{client_id}/profile", response_model=ProfileEditResponse)
    def edit_profile(client_id: str, body: ProfileEditRequest) -> ProfileEditResponse:
        """Manual (no-LLM) advisor edit: commit straight to Delta with an advisor audit row."""
        try:
            store = DeltaProfileStore()
            current = store.get_profile(client_id)
            profile = DistilledClientProfile(
                client_id=client_id,
                risk_tolerance=body.risk_tolerance,  # type: ignore[arg-type]
                investment_goals=body.investment_goals,
                family_context=body.family_context,
                stated_preferences=body.stated_preferences,
                summary=body.summary,
                source_artifact_ids=current.source_artifact_ids if current else [],
            )
            version = store.upsert_profile(
                profile,
                audit_actor=body.edited_by,
                audit_actor_kind="advisor",
                audit_action="manual_profile_edit",
            )
        except Exception as exc:
            mapped = _dependency_error(exc)
            if mapped is not None:
                raise mapped from exc
            raise
        return ProfileEditResponse(
            status="committed", client_id=client_id, delta_version=version
        )


def _proposal_to_out(p: ProfileProposal) -> ProposalOut:
    return ProposalOut(
        proposal_id=p.proposal_id,
        client_id=p.client_id,
        status=p.status,
        proposed_at=p.proposed_at,
        reviewed_at=p.reviewed_at,
        reviewed_by=p.reviewed_by,
        risk_tolerance=p.proposed_profile.risk_tolerance,
        investment_goals=p.proposed_profile.investment_goals,
        family_context=p.proposed_profile.family_context,
        stated_preferences=p.proposed_profile.stated_preferences,
        summary=p.proposed_profile.summary,
        source_artifact_ids=p.proposed_profile.source_artifact_ids,
    )


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run(
        "agent_memory.ui.server:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        reload=bool(os.environ.get("UVICORN_RELOAD")),
    )


if __name__ == "__main__":
    main()
