from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from app.sample_interface import SampleController

from signnow.core.factory import SdkFactory
from signnow.api.template.request.clone_template_post_request import CloneTemplatePostRequest
from signnow.api.document.request.document_get_request import DocumentGetRequest
from signnow.api.document.request.document_download_get_request import DocumentDownloadGetRequest
from signnow.api.documentfield.request.document_prefill_put_request import DocumentPrefillPutRequest
from signnow.api.documentfield.request.data.field import Field
from signnow.api.documentfield.request.data.field_collection import FieldCollection
from signnow.api.documentinvite.request.send_invite_post_request import SendInvitePostRequest


TEMPLATE_ID = "e30d6e58c82d43f598e365420f3c665a048a7d81"
APP_URL = "http://localhost:8080"
SAMPLE_NAME = "PrefillAndOneClickSendingAgreement"
ROLE_NAME = "Recipient 1"


class IndexController(SampleController):
    def handle_get(self, query_params: dict[str, str]) -> Response:
        html_path = Path(__file__).parent / "index.html"
        return HTMLResponse(html_path.read_text())

    def handle_post(self, form_data: dict[str, Any]) -> Response:
        action = form_data.get("action")
        client = SdkFactory.create_api_client()

        if action == "send-invite":
            name = form_data.get("name")
            email = form_data.get("email")
            document_id = self._send_invite(client, name, email)
            return JSONResponse({"status": "success", "document_id": document_id})

        if action == "invite-status":
            document_id = form_data["document_id"]
            statuses = self._get_document_statuses(client, document_id)
            return JSONResponse(statuses)

        document_id = form_data["document_id"]
        file_path = self._download_document(client, document_id)
        return FileResponse(
            path=file_path,
            media_type="application/pdf",
            filename=Path(file_path).name,
        )

    def _send_invite(self, client, name: str, email: str) -> str:
        clone_req = CloneTemplatePostRequest().with_template_id(TEMPLATE_ID)
        clone_resp = client.send(clone_req).get_response()
        document_id = clone_resp.id

        self._prefill_fields(client, document_id, name)

        role_id = self._get_role_id(client, document_id, ROLE_NAME)

        to = [{
            "email": email,
            "role_id": role_id,
            "role": "signer",
            "order": 1,
            "subject": "Subject",
            "message": "Message",
        }]
        invite_req = SendInvitePostRequest(
            to=to,
            from_email="from@email.com",
            subject="Subject",
            message="Message",
        ).with_document_id(document_id)
        client.send(invite_req)

        return document_id

    def _prefill_fields(self, client, document_id: str, name: str) -> None:
        fields = FieldCollection()
        fields.add(Field("Name", name))
        prefill_req = DocumentPrefillPutRequest(fields).with_document_id(document_id)
        client.send(prefill_req)

    def _get_role_id(self, client, document_id: str, role_name: str) -> str:
        doc_req = DocumentGetRequest().with_document_id(document_id)
        doc_resp = client.send(doc_req).get_response()
        for role in doc_resp.roles or []:
            if role.get("name") == role_name:
                return role["unique_id"]
        raise ValueError("Role not found")

    def _get_document_statuses(self, client, document_id: str) -> dict[str, Any]:
        doc_req = DocumentGetRequest().with_document_id(document_id)
        doc_resp = client.send(doc_req).get_response()
        statuses: dict[str, Any] = {}
        for invite in doc_resp.field_invites or []:
            statuses[invite.get("email")] = {
                "name": invite.get("email"),
                "status": invite.get("status"),
            }
        return statuses

    def _download_document(self, client, document_id: str) -> str:
        dl_req = (DocumentDownloadGetRequest()
                  .with_document_id(document_id)
                  .with_type("collapsed"))
        dl_resp = client.send(dl_req).get_response()
        return dl_resp.file_path
