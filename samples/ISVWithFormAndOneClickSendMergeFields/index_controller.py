from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from app.sample_interface import SampleController

from signnow.core.factory import SdkFactory
from signnow.api.document.request.document_get_request import DocumentGetRequest
from signnow.api.document.request.document_put_request import DocumentPutRequest
from signnow.api.documentgroup.request.document_group_get_request import DocumentGroupGetRequest
from signnow.api.documentgroup.request.document_group_recipients_get_request import DocumentGroupRecipientsGetRequest
from signnow.api.documentgroup.request.download_document_group_post_request import DownloadDocumentGroupPostRequest
from signnow.api.documentgroupinvite.request.group_invite_get_request import GroupInviteGetRequest
from signnow.api.documentgroupinvite.request.group_invite_post_request import GroupInvitePostRequest
from signnow.api.documentgrouptemplate.request.document_group_template_post_request import DocumentGroupTemplatePostRequest


DOCUMENT_GROUP_TEMPLATE_ID = "8e36720a436041ea837dc543ec00a3bc3559df45"
USER_EMAIL = "example@example.com"
CUSTOMER_NAME_FIELD = "CustomerName"
COMPANY_NAME_FIELD = "CompanyName"
PREPARE_CONTRACT_ROLE = "Prepare Contract"
CUSTOMER_SIGN_ROLE = "Customer to Sign"
APP_URL = "http://localhost:8080"
SAMPLE_NAME = "ISVWithFormAndOneClickSendMergeFields"
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
        customer_name = data.get("customer_name")
        company_name = data.get("company_name")
        email = data.get("email")

        dg_id = self._create_document_group_from_template(client)
        self._process_merge_fields(client, dg_id, customer_name, company_name)
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

    def _process_merge_fields(self, client, dg_id: str, customer_name: str, company_name: str) -> None:
        dg = self._get_document_group(client, dg_id)
        for doc_item in dg.documents or []:
            doc_id = doc_item["id"]
            doc_data = self._get_document(client, doc_id)

            texts: list[dict[str, Any]] = []
            fields: list[dict[str, Any]] = []

            customer_name_field = None
            company_name_field = None

            for field in doc_data.fields or []:
                field_name = self._extract_field_name(field)
                if field_name == CUSTOMER_NAME_FIELD:
                    customer_name_field = field
                elif field_name == COMPANY_NAME_FIELD:
                    company_name_field = field
                else:
                    if isinstance(field, dict):
                        json_attrs = dict(field.get("json_attributes") or {})
                        json_attrs["type"] = field.get("type", "text")
                        json_attrs["role"] = field.get("role", "")
                        fields.append(json_attrs)

            if customer_name_field is not None:
                coords = self._extract_field_coordinates(customer_name_field)
                texts.append({
                    "x": int(coords.get("x") or 0),
                    "y": int(coords.get("y") or 0),
                    "size": coords.get("size") or 25,
                    "width": int(coords.get("width") or 0),
                    "height": int(coords.get("height") or 0),
                    "subtype": "text",
                    "page_number": coords.get("page_number") or 0,
                    "data": customer_name,
                    "font": "Arial",
                    "line_height": coords.get("size") or 25,
                })

            if company_name_field is not None:
                coords = self._extract_field_coordinates(company_name_field)
                texts.append({
                    "x": int(coords.get("x") or 0),
                    "y": int(coords.get("y") or 0),
                    "size": coords.get("size") or 20,
                    "width": int(coords.get("width") or 0),
                    "height": int(coords.get("height") or 0),
                    "subtype": "text",
                    "page_number": coords.get("page_number") or 0,
                    "data": company_name,
                    "font": "Arial",
                    "line_height": coords.get("size") or 20,
                })

            put_req = DocumentPutRequest(
                fields=None,
                texts=texts,
                document_name="ISV Form Document Group",
                client_timestamp="",
            ).with_document_id(doc_id)
            client.send(put_req)

    def _extract_field_name(self, field) -> str | None:
        if not isinstance(field, dict):
            return None
        json_attrs = field.get("json_attributes")
        if isinstance(json_attrs, dict):
            n = json_attrs.get("name")
            return str(n) if n is not None else None
        return None

    def _extract_field_coordinates(self, field) -> dict[str, Any]:
        coords: dict[str, Any] = {}
        if isinstance(field, dict):
            json_attrs = field.get("json_attributes")
            if isinstance(json_attrs, dict):
                coords["x"] = json_attrs.get("x")
                coords["y"] = json_attrs.get("y")
                coords["width"] = json_attrs.get("width")
                coords["height"] = json_attrs.get("height")
                coords["size"] = json_attrs.get("size")
                coords["page_number"] = json_attrs.get("page_number")
        return coords

    def _send_invite(self, client, dg_id: str, email: str) -> None:
        dg = self._get_document_group(client, dg_id)
        recipients_resp = self._get_document_group_recipients(client, dg_id)
        recipients = recipients_resp.data["recipients"]

        if not recipients:
            return

        invite_actions: list[dict[str, Any]] = []
        invite_emails: list[dict[str, Any]] = []

        for recipient in recipients:
            rname = recipient.get("name")
            email_to_use = email
            if rname == PREPARE_CONTRACT_ROLE:
                email_to_use = email
            elif rname == CUSTOMER_SIGN_ROLE:
                email_to_use = USER_EMAIL

            invite_emails.append({
                "email": email_to_use,
                "subject": "Review and sign documents",
                "message": "Please review and sign the documents",
                "expiration_days": 30,
                "reminder": 10,
            })

            for doc in dg.documents or []:
                invite_actions.append({
                    "email": email_to_use,
                    "role_name": rname,
                    "action": "sign",
                    "document_id": doc["id"],
                    "redirect_uri": f"{REDIRECT_BASE_URL}?page=status-page&document_group_id={dg_id}",
                    "redirect_target": "self",
                })

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
