from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from app.sample_interface import SampleController

from signnow.core.factory import SdkFactory
from signnow.api.document.request.document_get_request import DocumentGetRequest
from signnow.api.documentfield.request.document_prefill_put_request import DocumentPrefillPutRequest
from signnow.api.documentfield.request.data.field import Field
from signnow.api.documentfield.request.data.field_collection import FieldCollection
from signnow.api.documentgroup.request.document_group_get_request import DocumentGroupGetRequest
from signnow.api.documentgroup.request.document_group_recipients_get_request import DocumentGroupRecipientsGetRequest
from signnow.api.documentgroup.request.document_group_recipients_put_request import DocumentGroupRecipientsPutRequest
from signnow.api.documentgroup.request.download_document_group_post_request import DownloadDocumentGroupPostRequest
from signnow.api.documentgroupinvite.request.group_invite_get_request import GroupInviteGetRequest
from signnow.api.documentgrouptemplate.request.document_group_template_post_request import DocumentGroupTemplatePostRequest
from signnow.api.embeddedsending.request.document_group_embedded_sending_link_post_request import DocumentGroupEmbeddedSendingLinkPostRequest


DOCUMENT_GROUP_TEMPLATE_ID = "e486ebf3fb814d55888bcbf75ceaf62b6db0de5a"
USER_EMAIL = "example@example.com"
APP_URL = "http://localhost:8080"
SAMPLE_NAME = "EmbeddedSenderWithFormDGAdjunct"
REDIRECT_BASE_URL = f"{APP_URL}/samples/{SAMPLE_NAME}"
GROUP_NAME = "ADJUNCT PROFESSOR CONTRACT"


class IndexController(SampleController):
    def handle_get(self, query_params: dict[str, str]) -> Response:
        html_path = Path(__file__).parent / "index.html"
        html = html_path.read_text()
        page = query_params.get("page")
        if page:
            html = html.replace(
                "<!-- DEMO_PAGE_CONTENT -->",
                f"<div class='demo-note'>Showing demo page: {page}</div>",
            )
        return HTMLResponse(html)

    def handle_post(self, form_data: dict[str, Any]) -> Response:
        action = form_data.get("action", "")
        client = SdkFactory.create_api_client()

        if action == "prepare_dg":
            return self._prepare_document_group(form_data, client)
        if action == "invite-status":
            return self._get_invite_status(form_data, client)
        if action == "download-doc-group":
            return self._download_document_group(form_data, client)

        return JSONResponse({
            "success": False,
            "message": f"Invalid action: {action}",
            "available_actions": ["prepare_dg", "invite-status", "download-doc-group"],
        }, status_code=400)

    def _prepare_document_group(self, data: dict[str, Any], client) -> Response:
        name = data.get("name")
        email = data.get("email")

        if not name or not email:
            return JSONResponse({
                "success": False,
                "message": "Name and email are required",
            }, status_code=400)

        dg_id = self._create_document_group_from_template(client)
        self._update_document_fields(client, dg_id, name)
        self._update_document_group_recipients(client, dg_id, email, USER_EMAIL)
        embedded_url = self._create_embedded_sending_url(client, dg_id)

        return JSONResponse({
            "success": True,
            "message": "Document group prepared and embedded sending link created successfully",
            "embedded_url": embedded_url,
        })

    def _get_invite_status(self, data: dict[str, Any], client) -> Response:
        dg_id = data["document_group_id"]
        signers = self._get_document_group_signers_status(client, dg_id)
        return JSONResponse(signers)

    def _download_document_group(self, data: dict[str, Any], client) -> Response:
        dg_id = data["document_group_id"]
        file_path = self._download_document_group_file(client, dg_id)
        return FileResponse(
            path=file_path,
            media_type="application/pdf",
            filename=Path(file_path).name,
        )

    def _create_document_group_from_template(self, client) -> str:
        req = DocumentGroupTemplatePostRequest(
            GROUP_NAME, "", None
        ).with_template_group_id(DOCUMENT_GROUP_TEMPLATE_ID)
        resp = client.send(req).get_response()
        return resp.data["unique_id"]

    def _update_document_fields(self, client, dg_id: str, name: str) -> None:
        dg = self._get_document_group(client, dg_id)
        for doc_item in dg.documents or []:
            doc_id = doc_item["id"]
            doc_data = self._get_document(client, doc_id)
            existing_fields = self._extract_field_names(doc_data)

            fields = FieldCollection()
            if "Name" in existing_fields:
                fields.add(Field("Name", name))

            if len(fields.to_list()) > 0:
                prefill_req = DocumentPrefillPutRequest(fields).with_document_id(doc_id)
                client.send(prefill_req)

    def _extract_field_names(self, doc_data) -> list[str]:
        names: list[str] = []
        for field in doc_data.fields or []:
            name = self._extract_field_name(field)
            if name is not None:
                names.append(name)
        return names

    def _extract_field_name(self, field) -> str | None:
        if not isinstance(field, dict):
            return None
        json_attrs = field.get("json_attributes") or field.get("jsonAttributes")
        if isinstance(json_attrs, dict):
            n = json_attrs.get("name")
            return str(n) if n is not None else None
        return None

    def _update_document_group_recipients(self, client, dg_id: str, customer_email: str, preparer_email: str) -> None:
        resp = self._get_document_group_recipients(client, dg_id)
        current = resp.data["recipients"]

        updated = []
        for recipient in current:
            rname = recipient.get("name")
            req_docs = []
            for doc in recipient.get("documents", []):
                req_docs.append({
                    "id": doc.get("id"),
                    "role": doc.get("role"),
                    "action": doc.get("action"),
                })
            if rname == "Recipient 1":
                email_to_use = preparer_email
            elif rname == "Recipient 2":
                email_to_use = customer_email
            else:
                email_to_use = ""
            updated.append({
                "name": rname,
                "email": email_to_use,
                "order": recipient.get("order"),
                "documents": req_docs,
            })

        put_req = DocumentGroupRecipientsPutRequest(
            recipients=updated, cc=[]
        ).with_document_group_id(dg_id)
        client.send(put_req)

    def _create_embedded_sending_url(self, client, dg_id: str) -> str:
        redirect_url = f"{REDIRECT_BASE_URL}?page=status-page&document_group_id={dg_id}"
        req = DocumentGroupEmbeddedSendingLinkPostRequest(
            redirect_url, 15, "self", "send-invite"
        ).with_document_group_id(dg_id)
        resp = client.send(req).get_response()
        return resp.data["url"]

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

    def _get_document(self, client, document_id: str):
        req = DocumentGetRequest().with_document_id(document_id)
        return client.send(req).get_response()

    def _get_document_group_recipients(self, client, dg_id: str):
        req = DocumentGroupRecipientsGetRequest().with_document_group_id(dg_id)
        return client.send(req).get_response()

    def _download_document_group_file(self, client, dg_id: str) -> str:
        req = DownloadDocumentGroupPostRequest(
            "merged", "no", []
        ).with_document_group_id(dg_id)
        resp = client.send(req).get_response()
        return resp.file_path
