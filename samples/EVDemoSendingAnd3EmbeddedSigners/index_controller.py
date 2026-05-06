from __future__ import annotations

import datetime
import urllib.parse
from pathlib import Path
from typing import Any

from fastapi import Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from app.sample_interface import SampleController

from signnow.core.factory import SdkFactory
from signnow.api.template.request.clone_template_post_request import CloneTemplatePostRequest
from signnow.api.document.request.document_get_request import DocumentGetRequest
from signnow.api.document.request.document_download_get_request import DocumentDownloadGetRequest
from signnow.api.embeddedinvite.request.document_invite_post_request import DocumentInvitePostRequest
from signnow.api.embeddedinvite.request.document_invite_link_post_request import DocumentInviteLinkPostRequest
from signnow.api.documentfield.request.document_prefill_put_request import DocumentPrefillPutRequest
from signnow.api.documentfield.request.data.field import Field
from signnow.api.documentfield.request.data.field_collection import FieldCollection


TEMPLATE_ID = "34009a3d21b5468d86d886cd715658c453335c61"
APP_URL = "http://localhost:8080"
SAMPLE_NAME = "EVDemoSendingAnd3EmbeddedSigners"


class IndexController(SampleController):
    def handle_get(self, query_params: dict[str, str]) -> Response:
        html_path = Path(__file__).parent / "index.html"
        return HTMLResponse(html_path.read_text())

    def handle_post(self, form_data: dict[str, Any]) -> Response:
        action = form_data.get("action")
        client = SdkFactory.create_api_client()

        if action == "start-workflow":
            return self._start_workflow(client, form_data)
        if action == "next-signer":
            return self._next_signer(client, form_data)
        if action == "download":
            return self._download(client, form_data)
        if action == "invite-status":
            return self._invite_status(client, form_data)

        return JSONResponse({"error": "Invalid action"}, status_code=400)

    # --- actions ---

    def _start_workflow(self, client, form_data: dict[str, Any]) -> Response:
        agent_name = form_data.get("agent_name", "")
        agent_email = form_data.get("agent_email", "")
        signer1_name = form_data.get("signer1_name", "")
        signer1_email = form_data.get("signer1_email", "")
        signer2_name = form_data.get("signer2_name", "")
        signer2_email = form_data.get("signer2_email", "")

        clone_resp = client.send(
            CloneTemplatePostRequest().with_template_id(TEMPLATE_ID)
        ).get_response()
        document_id = clone_resp.id

        self._prefill_fields(client, document_id, {
            "Signer 1 Name": signer1_name,
            "Text Field 18": signer1_name,
            "Signer 2 Name": signer2_name,
            "Text Field 19": signer2_name,
        })

        agent_role_id = self._get_role_id(client, document_id, "Contract Preparer")
        signer1_role_id = self._get_role_id(client, document_id, "Recipient 1")
        signer2_role_id = self._get_role_id(client, document_id, "Recipient 2")

        invite_map = self._create_embedded_invites(client, document_id, [
            {"email": agent_email, "role_id": agent_role_id, "order": 1, "name": agent_name},
            {"email": signer1_email, "role_id": signer1_role_id, "order": 2, "name": signer1_name},
            {"email": signer2_email, "role_id": signer2_role_id, "order": 3, "name": signer2_name},
        ])

        agent_invite_id = invite_map[agent_role_id]
        agent_link = self._get_invite_link(
            client, document_id, agent_invite_id,
            self._make_redirect_url(document_id, "signer1"),
        )

        return JSONResponse({
            "document_id": document_id,
            "embedded_link": agent_link,
            "message": "Agent embedded signing link created. Agent can now sign.",
        })

    def _next_signer(self, client, form_data: dict[str, Any]) -> Response:
        document_id = form_data["document_id"]
        role_name = form_data["roleName"]
        redirect_key = "signer2" if role_name == "Recipient 1" else "finish"

        invite_id = self._get_invite_id_for_role_name(client, document_id, role_name)
        signing_link = self._get_invite_link(
            client, document_id, invite_id,
            self._make_redirect_url(document_id, redirect_key),
        )

        return JSONResponse({
            "embedded_link": signing_link,
            "message": f"Embedded link for {role_name} created. Ready for signing.",
        })

    def _download(self, client, form_data: dict[str, Any]) -> Response:
        document_id = form_data["document_id"]
        dl_req = (DocumentDownloadGetRequest()
                  .with_document_id(document_id)
                  .with_type("collapsed"))
        dl_resp = client.send(dl_req).get_response()
        file_path = dl_resp.file_path
        return FileResponse(
            path=file_path,
            media_type="application/pdf",
            filename=Path(file_path).name,
        )

    def _invite_status(self, client, form_data: dict[str, Any]) -> Response:
        document_id = form_data["document_id"]
        doc_resp = client.send(
            DocumentGetRequest().with_document_id(document_id)
        ).get_response()

        statuses = []
        for invite in doc_resp.field_invites or []:
            email_statuses = invite.get("email_statuses") or []
            first = email_statuses[0] if email_statuses else None
            timestamp = ""
            if first and first.get("created_at"):
                timestamp = datetime.datetime.fromtimestamp(
                    int(first["created_at"])
                ).strftime("%Y-%m-%d %H:%M:%S")
            statuses.append({
                "email": invite.get("email", ""),
                "timestamp": timestamp,
                "status": (first or {}).get("status", "Pending"),
            })

        return JSONResponse(statuses)

    # --- helpers ---

    def _prefill_fields(self, client, document_id: str, fields: dict[str, str]) -> None:
        collection = FieldCollection()
        for name, value in fields.items():
            if value:
                collection.add(Field(field_name=name, prefilled_text=value))
        req = DocumentPrefillPutRequest(collection).with_document_id(document_id)
        client.send(req)

    def _get_role_id(self, client, document_id: str, role_name: str) -> str:
        doc_resp = client.send(
            DocumentGetRequest().with_document_id(document_id)
        ).get_response()
        for role in doc_resp.roles or []:
            if role.get("name") == role_name:
                return role["unique_id"]
        raise RuntimeError(f"Role '{role_name}' not found on document {document_id}")

    def _create_embedded_invites(self, client, document_id: str, signers: list[dict]) -> dict[str, str]:
        invite_payload = []
        for s in signers:
            parts = (s.get("name") or "").split()
            first_name = parts[0] if parts else ""
            last_name = parts[1] if len(parts) > 1 else first_name
            invite_payload.append({
                "email": s["email"],
                "role_id": s["role_id"],
                "order": s["order"],
                "auth_method": "none",
                "first_name": first_name,
                "last_name": last_name,
            })
        req = DocumentInvitePostRequest(invite_payload, None).with_document_id(document_id)
        resp = client.send(req).get_response()

        result: dict[str, str] = {}
        for data in resp.data or []:
            role_id = data.get("role_id") or data.get("role_unique_id")
            invite_id = data.get("id")
            if role_id and invite_id:
                result[role_id] = invite_id
        return result

    def _get_invite_link(self, client, document_id: str, invite_id: str, redirect_url: str) -> str:
        link_req = (DocumentInviteLinkPostRequest("none", 15)
                    .with_field_invite_id(invite_id)
                    .with_document_id(document_id))
        resp = client.send(link_req).get_response()
        return resp.data["link"] + "&redirect_uri=" + urllib.parse.quote(redirect_url, safe="")

    def _get_invite_id_for_role_name(self, client, document_id: str, role_name: str) -> str:
        role_id = self._get_role_id(client, document_id, role_name)
        doc_resp = client.send(
            DocumentGetRequest().with_document_id(document_id)
        ).get_response()
        for invite in doc_resp.field_invites or []:
            candidate = invite.get("role_unique_id") or invite.get("role_id")
            if candidate == role_id:
                return invite.get("id") or invite.get("field_invite_unique_id", "")
        raise RuntimeError(f"Invite for role {role_name} not found.")

    def _make_redirect_url(self, document_id: str, next_step: str) -> str:
        return f"{APP_URL}/samples/{SAMPLE_NAME}?document_id={document_id}&step={next_step}"
