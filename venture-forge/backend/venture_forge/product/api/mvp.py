"""Scoped research and selected-record export contracts for the founder MVP."""
import base64
from typing import Literal
from fastapi import Depends, Query, Response
from pydantic import Field
from venture_forge.product.core.schemas import Input
from venture_forge.product.core.models import Activity
from venture_forge.product.core.workflow_models import Artifact, Receipt
from venture_forge.product.agents.runtime import scoped, record_scope
from venture_forge.product.research.reader import extract_document, fetch_source, web_search, ReadFailure
from venture_forge.product.core.mvp_exports import export_hash, render_export, ExportFailure


class FileRead(Input):
    filename: str = Field(min_length=1, max_length=200, pattern=r"^[^/\\:]+\.(?:pdf|txt|md|csv)$")
    content_base64: str = Field(min_length=1, max_length=5600000)


class SourceRead(Input):
    url: str = Field(min_length=8, max_length=2000)
    approved: Literal[True]


class WebSearch(Input):
    query: str = Field(min_length=3, max_length=400)
    approved: Literal[True]


class ExportSelection(Input):
    artifact_ids: list[str] = Field(min_length=1, max_length=15)
    purpose: str = Field(min_length=5, max_length=300)


class ExportApproval(ExportSelection):
    preview_hash: str = Field(min_length=64, max_length=64)
    format: Literal["pdf", "docx", "csv", "json"]
    approved: Literal[True]


def install_mvp(app, db, owner, owned_venture, fail, settings):
    def audit(session, venture, event, message):
        session.add(Activity(venture_id=venture.id, owner_id=venture.owner_id, event_type=event, description=message))
        session.commit()

    @app.get("/api/v1/ventures/{venture_id}/research/sources")
    def search_saved(venture_id: str, q: str = Query(default="", max_length=400), founder=Depends(owner), session=Depends(db)):
        venture = owned_venture(session, founder, venture_id)
        terms = q.casefold().split()
        return {"sources": [{"id": r.id, "title": r.title, "locator": r.locator, "collected_on": r.collected_on, "content": r.content} for r in record_scope(session, Receipt, venture) if not r.withdrawn and all(t in (r.title + " " + r.content).casefold() for t in terms)], "web_search_configured": bool(settings.research_search_api_key.get_secret_value()), "approved_hosts": settings.research_allowed_hosts}

    @app.post("/api/v1/ventures/{venture_id}/research/read-file")
    def read_file(venture_id: str, body: FileRead, founder=Depends(owner), session=Depends(db)):
        venture = owned_venture(session, founder, venture_id)
        try:
            payload = base64.b64decode(body.content_base64, validate=True)
            result = extract_document(payload, body.filename)
        except (ValueError, ReadFailure) as error:
            fail("SOURCE_READ_FAILED", str(error) if isinstance(error, ReadFailure) else "Invalid file encoding.", 422)
        audit(session, venture, "research.file_read", "Founder opened a supplied file for source review; no claim was accepted.")
        return result

    @app.post("/api/v1/ventures/{venture_id}/research/read-source")
    def read_source(venture_id: str, body: SourceRead, founder=Depends(owner), session=Depends(db)):
        venture = owned_venture(session, founder, venture_id)
        try: result = fetch_source(body.url, settings)
        except ReadFailure as error: fail("SOURCE_READ_FAILED", str(error), 422)
        audit(session, venture, "research.public_read", "Founder approved a bounded public source read; no claim was accepted.")
        return result

    @app.post("/api/v1/ventures/{venture_id}/research/web-search")
    def search_web(venture_id: str, body: WebSearch, founder=Depends(owner), session=Depends(db)):
        venture = owned_venture(session, founder, venture_id)
        try: results = web_search(body.query, settings)
        except ReadFailure as error: fail("SEARCH_UNAVAILABLE", str(error), 503)
        audit(session, venture, "research.web_search", "Founder approved one search query; discovery results require original-source review.")
        return {"results": results}

    def selected_payload(session, venture, selection):
        chosen, source_ids = [], set()
        for ident in dict.fromkeys(selection.artifact_ids):
            artifact = scoped(session, Artifact, ident, venture)
            if not artifact: fail("NOT_FOUND", "An artifact is outside this venture.", 404)
            if artifact.status != "ACCEPTED": fail("EXPORT_REVIEW_REQUIRED", "Only accepted, current artifacts can be exported.", 409)
            result = artifact.result.get("data", artifact.result)
            report = result.get("workspace", {})
            sections = report.get("sections", [])
            if not sections:
                sections = [{"key": "result", "title": "Reviewed result", "description": "", "rows": [{k: str(v) for k, v in result.items()}]}]
            chosen.append({"id": artifact.id, "title": artifact.title, "application": artifact.capability, "classification": artifact.result.get("evidence_class", "FOUNDER_ASSUMPTION"), "sections": sections, "gaps": report.get("gaps", []), "version_hash": export_hash(artifact.result)})
            source_ids.update(artifact.evidence_ids)
        sources = []
        for ident in sorted(source_ids):
            source = scoped(session, Receipt, ident, venture)
            if not source or source.withdrawn: fail("SOURCE_WITHDRAWN", "A selected source is no longer available.", 409)
            if source.consent not in {"public_source", "quote_permitted"}: fail("EXPORT_CONSENT_REQUIRED", "A selected artifact depends on private or notes-only evidence. It cannot be included in a distributable export.", 409)
            sources.append({"id": source.id, "title": source.title, "locator": source.locator, "collected_on": source.collected_on})
        return {"venture": {"id": venture.id, "name": venture.name, "revision": venture.revision}, "purpose": selection.purpose, "artifacts": chosen, "sources": sources}

    @app.post("/api/v1/ventures/{venture_id}/mvp-exports/preview")
    def preview(venture_id: str, body: ExportSelection, founder=Depends(owner), session=Depends(db)):
        venture = owned_venture(session, founder, venture_id)
        payload = selected_payload(session, venture, body)
        return {"payload": payload, "preview_hash": export_hash(payload)}

    @app.post("/api/v1/ventures/{venture_id}/mvp-exports/download")
    def download(venture_id: str, body: ExportApproval, founder=Depends(owner), session=Depends(db)):
        venture = owned_venture(session, founder, venture_id)
        payload = selected_payload(session, venture, body)
        if export_hash(payload) != body.preview_hash: fail("EXPORT_CHANGED", "The selected versions changed. Preview and approve the current export.", 409)
        try: content, mime = render_export(payload, body.format)
        except ExportFailure as error: fail("EXPORT_FORMAT_UNSUPPORTED", str(error), 422)
        audit(session, venture, "export.approved", f"Founder approved a {body.format.upper()} export of {len(payload['artifacts'])} exact artifact versions.")
        return Response(content=content, media_type=mime, headers={"Content-Disposition": f'attachment; filename="venture-forge-mvp.{body.format}"', "X-Content-SHA256": export_hash(payload), "Cache-Control": "no-store"})
