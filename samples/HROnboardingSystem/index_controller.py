from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from app.sample_interface import SampleController

from signnow.core.exception import SignNowApiException
from signnow.core.factory import SdkFactory
from signnow.api.document.request.document_get_request import DocumentGetRequest
from signnow.api.documentfield.request.document_prefill_put_request import DocumentPrefillPutRequest
from signnow.api.documentfield.request.data.field import Field
from signnow.api.documentfield.request.data.field_collection import FieldCollection
from signnow.api.documentgroup.request.document_group_get_request import DocumentGroupGetRequest
from signnow.api.documentgroup.request.document_group_post_request import DocumentGroupPostRequest
from signnow.api.documentgroup.request.download_document_group_post_request import DownloadDocumentGroupPostRequest
from signnow.api.documentgroupinvite.request.group_invite_get_request import GroupInviteGetRequest
from signnow.api.documentgroupinvite.request.group_invite_post_request import GroupInvitePostRequest
from signnow.api.template.request.clone_template_post_request import CloneTemplatePostRequest


USER_EMAIL = "example@example.com"
I9_FORM_TEMPLATE_ID = "940989288b8b4c62a950b908333b5b21efd6a174"
NDA_TEMPLATE_ID = "a4f523d0cb234ffc99b0badc9e6f59111f76abc2"
EMPLOYEE_CONTRACT_TEMPLATE_ID = "1a12d3e00a54457ca1bf7bde5fa37d38ede866ed"

NAME_FIELD = "Name"
TEXT_FIELD_2 = "Text Field 2"
TEXT_FIELD_156 = "Text Field 156"
EMAIL_FIELD = "Email"

APP_URL = "http://localhost:8080"
SAMPLE_NAME = "HROnboardingSystem"
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

        if action == "create-invite":
            return self._create_invite(form_data, client)
        if action == "invite-status":
            return self._get_invite_status(form_data, client)
        if action == "download-doc-group":
            return self._download_document_group(form_data, client)

        return JSONResponse({
            "success": False,
            "message": f"Invalid action: {action}",
            "available_actions": ["create-invite", "invite-status", "download-doc-group"],
        }, status_code=400)

    def _create_invite(self, data: dict[str, Any], client) -> Response:
        employee_name = data.get("employee_name")
        employee_email = data.get("employee_email")
        hr_manager_email = data.get("hr_manager_email")
        employer_email = data.get("employer_email")
        template_ids = data.get("template_ids")

        if (not employee_name or not employee_email or
                not hr_manager_email or not employer_email or
                not template_ids):
            return JSONResponse({
                "success": False,
                "message": "All fields are required",
            }, status_code=400)

        try:
            dg_id = self._create_document_group(client, template_ids, {
                NAME_FIELD: employee_name,
                TEXT_FIELD_2: employee_name,
                TEXT_FIELD_156: employee_name,
                EMAIL_FIELD: employee_email,
            })

            self._send_invite(client, dg_id, employee_email, hr_manager_email, employer_email)
        except SignNowApiException as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=500)

        return JSONResponse({
            "success": True,
            "document_group_id": dg_id,
        })

    def _get_invite_status(self, data: dict[str, Any], client) -> Response:
        dg_id = data["document_group_id"]
        try:
            status = self._get_document_group_signers_status(client, dg_id)
        except SignNowApiException as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=500)
        return JSONResponse(status)

    def _download_document_group(self, data: dict[str, Any], client) -> Response:
        dg_id = data.get("document_group_id")
        if not dg_id:
            return JSONResponse({
                "success": False,
                "message": "Document group ID is required",
            }, status_code=400)

        try:
            file_path = self._download_document_group_file(client, dg_id)
        except SignNowApiException as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=500)
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

    def _create_document_group(self, client, template_ids: list[str], fields_value: dict[str, str]) -> str:
        document_ids: list[str] = []
        for template_id in template_ids:
            clone_resp = self._create_document_from_template(client, template_id)
            document_ids.append(clone_resp.id)

        for doc_id in document_ids:
            self._prefill_fields(client, doc_id, fields_value)

        dg_req = DocumentGroupPostRequest(document_ids, "HR Onboarding System")
        dg_resp = client.send(dg_req).get_response()
        return dg_resp.id

    def _send_invite(self, client, dg_id: str, employee_email: str, hr_manager_email: str, employer_email: str) -> None:
        dg = self._get_document_group(client, dg_id)

        role_mappings = {
            "Contract Preparer": hr_manager_email,
            "Employee": employee_email,
            "Employer": employer_email,
        }

        invite_actions: list[dict[str, Any]] = []
        invite_emails: list[dict[str, Any]] = []

        for doc in dg.documents or []:
            doc_roles = self._get_document_roles(client, doc["id"])

            for role_name, email in role_mappings.items():
                if role_name in doc_roles:
                    invite_actions.append({
                        "email": email,
                        "role_name": role_name,
                        "action": "sign",
                        "document_id": doc["id"],
                        "redirect_uri": f"{REDIRECT_BASE_URL}?page=status-page&document_group_id={dg_id}",
                        "redirect_target": "self",
                    })
                else:
                    invite_actions.append({
                        "email": email,
                        "role_name": role_name,
                        "action": "view",
                        "document_id": doc["id"],
                    })

        for role_name, email in role_mappings.items():
            invite_emails.append({
                "email": email,
                "subject": "HR Onboarding Documents - Action Required",
                "message": f"Please review and sign the onboarding documents as {role_name}.",
                "expiration_days": 30,
                "reminder": 10,
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

    def _get_document_group_signers_status(self, client, dg_id: str) -> dict[str, Any]:
        dg = self._get_document_group(client, dg_id)
        invite_id = dg.invite_id if hasattr(dg, "invite_id") else None

        if not invite_id:
            return {"status": "pending"}

        status_req = (GroupInviteGetRequest()
                      .with_document_group_id(dg_id)
                      .with_invite_id(invite_id))
        status_resp = client.send(status_req).get_response()

        invite = getattr(status_resp, "invite", None) or {}
        status = invite.get("status") if isinstance(invite, dict) else None
        return {"status": status}

    def _create_document_from_template(self, client, template_id: str):
        req = CloneTemplatePostRequest().with_template_id(template_id)
        return client.send(req).get_response()

    def _prefill_fields(self, client, document_id: str, fields_value: dict[str, str]) -> None:
        doc = self._get_document(client, document_id)
        existing_fields = self._extract_field_names(doc)

        fields = FieldCollection()
        for field_name, field_value in fields_value.items():
            if field_name in existing_fields and field_value:
                fields.add(Field(field_name, field_value))

        if len(fields.to_list()) > 0:
            prefill_req = DocumentPrefillPutRequest(fields).with_document_id(document_id)
            client.send(prefill_req)

    def _get_document_roles(self, client, document_id: str) -> list[str]:
        doc = self._get_document(client, document_id)
        roles: list[str] = []
        for role in doc.roles or []:
            role_name = role.get("name") if isinstance(role, dict) else None
            if role_name and role_name not in roles:
                roles.append(role_name)
        return roles

    def _extract_field_names(self, doc) -> list[str]:
        names: list[str] = []
        for field in doc.fields or []:
            n = self._extract_field_name(field)
            if n is not None:
                names.append(n)
        return names

    def _extract_field_name(self, field) -> str | None:
        if not isinstance(field, dict):
            return None
        json_attrs = field.get("json_attributes") or field.get("jsonAttributes")
        if isinstance(json_attrs, dict):
            n = json_attrs.get("name")
            return str(n) if n is not None else None
        return None

    def _get_document_group(self, client, dg_id: str):
        req = DocumentGroupGetRequest().with_document_group_id(dg_id)
        return client.send(req).get_response()

    def _get_document(self, client, document_id: str):
        req = DocumentGetRequest().with_document_id(document_id)
        return client.send(req).get_response()
