from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from app.sample_interface import SampleController

from signnow.core.factory import SdkFactory
from signnow.api.document.request.document_post_request import DocumentPostRequest
from signnow.api.documentgroup.request.document_group_get_request import DocumentGroupGetRequest
from signnow.api.documentgroup.request.document_group_post_request import DocumentGroupPostRequest
from signnow.api.documentgroup.request.document_group_recipients_get_request import DocumentGroupRecipientsGetRequest
from signnow.api.documentgroup.request.download_document_group_post_request import DownloadDocumentGroupPostRequest
from signnow.api.documentgroupinvite.request.group_invite_get_request import GroupInviteGetRequest
from signnow.api.embeddedsending.request.document_group_embedded_sending_link_post_request import DocumentGroupEmbeddedSendingLinkPostRequest


APP_URL = "http://localhost:8080"
SAMPLE_NAME = "UploadEmbeddedSender"
REDIRECT_BASE_URL = f"{APP_URL}/samples/{SAMPLE_NAME}"
PDF_FILE_NAME = "Sales Proposal.pdf"


class IndexController(SampleController):
    def handle_get(self, query_params: dict[str, str]) -> Response:
        html_path = Path(__file__).parent / "index.html"
        return HTMLResponse(html_path.read_text())

    def handle_post(self, form_data: dict[str, Any]) -> Response:
        action = form_data.get("action", "")
        client = SdkFactory.create_api_client()

        if action == "upload_and_create_dg":
            return self._upload_and_create_document_group(client)
        if action == "invite-status":
            dg_id = form_data["document_group_id"]
            signers = self._get_document_group_signers_status(client, dg_id)
            return JSONResponse(signers)
        if action == "download-doc-group":
            return self._download_document_group(form_data, client)

        return JSONResponse({
            "success": False,
            "message": "Invalid action",
        }, status_code=400)

    def _upload_and_create_document_group(self, client) -> Response:
        document_id = self._upload_document(client)
        dg_id = self._create_document_group(client, document_id)
        embedded_url = self._create_embedded_sending_url(client, dg_id)

        return JSONResponse({
            "success": True,
            "message": "Document uploaded and embedded sending link created successfully",
            "embedded_url": embedded_url,
        })

    def _upload_document(self, client) -> str:
        pdf_path = Path(__file__).parent / PDF_FILE_NAME
        req = DocumentPostRequest(
            file=str(pdf_path),
            name="Sales Proposal",
        )
        resp = client.send(req).get_response()
        return resp.id

    def _create_document_group(self, client, document_id: str) -> str:
        req = DocumentGroupPostRequest([document_id], "Uploaded Document Group")
        resp = client.send(req).get_response()
        return resp.id

    def _create_embedded_sending_url(self, client, dg_id: str) -> str:
        redirect_url = f"{REDIRECT_BASE_URL}?page=status-page&document_group_id={dg_id}"
        req = DocumentGroupEmbeddedSendingLinkPostRequest(
            redirect_url, 15, "self", "edit"
        ).with_document_group_id(dg_id)
        resp = client.send(req).get_response()
        return resp.data["url"]

    def _download_document_group(self, data: dict[str, Any], client) -> Response:
        dg_id = data["document_group_id"]
        file_path = self._download_document_group_file(client, dg_id)
        return FileResponse(
            path=file_path,
            media_type="application/pdf",
            filename=Path(file_path).name,
        )

    def _download_document_group_file(self, client, dg_id: str) -> str:
        req = DownloadDocumentGroupPostRequest(
            "merged", "no", []
        ).with_document_group_id(dg_id)
        resp = client.send(req).get_response()
        return resp.file_path

    def _get_document_group_signers_status(self, client, dg_id: str) -> list[dict[str, Any]]:
        recipients_resp = self._get_document_group_recipients(client, dg_id)
        signers: list[dict[str, Any]] = []

        dg = self._get_document_group(client, dg_id)
        invite_id = dg.invite_id if hasattr(dg, "invite_id") else None

        if not invite_id:
            for recipient in recipients_resp.data["recipients"]:
                signers.append({
                    "name": recipient.get("name"),
                    "email": recipient.get("email"),
                    "status": "not_invited",
                    "order": recipient.get("order"),
                    "timestamp": None,
                })
            return signers

        status_req = (GroupInviteGetRequest()
                      .with_document_group_id(dg_id)
                      .with_invite_id(invite_id))
        status_resp = client.send(status_req).get_response()

        statuses: dict[str, str] = {}
        invite = getattr(status_resp, "invite", None) or {}
        steps = invite.get("steps", []) if isinstance(invite, dict) else []
        for step in steps:
            for action in step.get("actions", []):
                statuses[action.get("role_name")] = action.get("status")

        for recipient in recipients_resp.data["recipients"]:
            signers.append({
                "name": recipient.get("name"),
                "email": recipient.get("email"),
                "status": statuses.get(recipient.get("name"), "unknown"),
                "order": recipient.get("order"),
                "timestamp": None,
            })
        return signers

    def _get_document_group(self, client, dg_id: str):
        req = DocumentGroupGetRequest().with_document_group_id(dg_id)
        return client.send(req).get_response()

    def _get_document_group_recipients(self, client, dg_id: str):
        req = DocumentGroupRecipientsGetRequest().with_document_group_id(dg_id)
        return client.send(req).get_response()
