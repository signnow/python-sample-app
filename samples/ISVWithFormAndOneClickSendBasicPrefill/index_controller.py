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
from signnow.api.documentgroup.request.download_document_group_post_request import DownloadDocumentGroupPostRequest
from signnow.api.documentgroupinvite.request.group_invite_get_request import GroupInviteGetRequest
from signnow.api.documentgroupinvite.request.group_invite_post_request import GroupInvitePostRequest
from signnow.api.documentgrouptemplate.request.document_group_template_post_request import DocumentGroupTemplatePostRequest


DOCUMENT_GROUP_TEMPLATE_ID = "6e79b9e6f9624984a7f054a7171d1644d0fb9934"
USER_EMAIL = "example@example.com"
NAME_FIELD = "Name"
EMAIL_FIELD = "Email"
APP_URL = "http://localhost:8080"
SAMPLE_NAME = "ISVWithFormAndOneClickSendBasicPrefill"
REDIRECT_BASE_URL = f"{APP_URL}/samples/{SAMPLE_NAME}"


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
        self._update_document_fields(client, dg_id, name, email)
        self._send_invite(client, dg_id, email)

        return JSONResponse({
            "success": True,
            "document_group_id": dg_id,
        })

    def _get_invite_status(self, data: dict[str, Any], client) -> Response:
        dg_id = data["document_group_id"]
        signers = self._get_document_group_signers_status(client, dg_id)
        return JSONResponse(signers)

    def _download_document_group(self, data: dict[str, Any], client) -> Response:
        dg_id = data.get("document_group_id")
        if not dg_id:
            return JSONResponse({
                "success": False,
                "message": "Document group ID is required",
            }, status_code=400)
        file_path = self._download_document_group_file(client, dg_id)
        return FileResponse(
            path=file_path,
            media_type="application/pdf",
            filename=Path(file_path).name,
        )

    def _create_document_group_from_template(self, client) -> str:
        req = DocumentGroupTemplatePostRequest(
            "ISV Form Document Group", "", None
        ).with_template_group_id(DOCUMENT_GROUP_TEMPLATE_ID)
        resp = client.send(req).get_response()
        return resp.data["unique_id"]

    def _update_document_fields(self, client, dg_id: str, name: str, email: str) -> None:
        dg = self._get_document_group(client, dg_id)
        for doc_item in dg.documents or []:
            doc_id = doc_item["id"]
            doc_data = self._get_document(client, doc_id)
            existing_fields = self._extract_field_names(doc_data)

            fields = FieldCollection()
            if NAME_FIELD in existing_fields:
                fields.add(Field(NAME_FIELD, name))
            if EMAIL_FIELD in existing_fields:
                fields.add(Field(EMAIL_FIELD, email))

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

    def _send_invite(self, client, dg_id: str, email: str) -> None:
        dg = self._get_document_group(client, dg_id)
        invite_actions: list[dict[str, Any]] = []
        for doc in dg.documents or []:
            invite_actions.append({
                "email": email,
                "role_name": "Recipient 1",
                "action": "sign",
                "document_id": doc["id"],
                "redirect_uri": f"{REDIRECT_BASE_URL}?page=status-page&document_group_id={dg_id}",
                "redirect_target": "self",
            })

        invite_emails = [{
            "email": email,
            "subject": "Review and sign documents",
            "message": "Please review and sign the documents",
            "expiration_days": 30,
            "reminder": 10,
        }]

        invite_steps = [{
            "order": 1,
            "invite_actions": invite_actions,
            "invite_emails": invite_emails,
        }]

        req = GroupInvitePostRequest(
            invite_steps=invite_steps,
            cc=[],
            sign_as_merged=True,
            client_timestamp=100,
        ).with_document_group_id(dg_id)
        client.send(req)

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
