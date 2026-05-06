from __future__ import annotations

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
from signnow.api.documentfield.request.document_prefill_put_request import DocumentPrefillPutRequest
from signnow.api.documentfield.request.data.field import Field
from signnow.api.documentfield.request.data.field_collection import FieldCollection
from signnow.api.embeddedinvite.request.document_invite_post_request import DocumentInvitePostRequest
from signnow.api.embeddedinvite.request.document_invite_link_post_request import DocumentInviteLinkPostRequest


TEMPLATE_ID = "60d8e92f12004fda8985d4574237507e6407530d"
APP_URL = "http://localhost:8080"
SAMPLE_NAME = "EmbeddedSignerWithFormInsurance"
ROLE_NAME = "Recipient 1"


class IndexController(SampleController):
    def handle_get(self, query_params: dict[str, str]) -> Response:
        html_path = Path(__file__).parent / "index.html"
        return HTMLResponse(html_path.read_text())

    def handle_post(self, form_data: dict[str, Any]) -> Response:
        action = form_data.get("action")
        client = SdkFactory.create_api_client()

        if action == "create-embedded-invite":
            full_name = form_data.get("full_name")
            email = form_data.get("email")
            link = self._create_embedded_invite_and_return_signing_link(client, full_name, email)
            return JSONResponse({"link": link})

        document_id = form_data["document_id"]
        file_path = self._download_document(client, document_id)
        return FileResponse(
            path=file_path,
            media_type="application/pdf",
            filename=Path(file_path).name,
        )

    def _create_embedded_invite_and_return_signing_link(self, client, full_name: str, email: str) -> str:
        clone_req = CloneTemplatePostRequest().with_template_id(TEMPLATE_ID)
        clone_resp = client.send(clone_req).get_response()
        document_id = clone_resp.id

        self._prefill_fields(client, document_id, full_name, email)

        role_id = self._get_role_id(client, document_id, ROLE_NAME)

        invites = [{
            "email": email,
            "role_id": role_id,
            "order": 1,
            "auth_method": "none",
        }]
        invite_req = DocumentInvitePostRequest(invites, None).with_document_id(document_id)
        invite_resp = client.send(invite_req).get_response()
        invite_id = invite_resp.data[0]["id"]

        link_req = (DocumentInviteLinkPostRequest("none", 15)
                    .with_field_invite_id(invite_id)
                    .with_document_id(document_id))
        link_resp = client.send(link_req).get_response()
        signing_link = link_resp.data["link"]

        redirect = f"{APP_URL}/samples/{SAMPLE_NAME}?page=download-container&document_id={document_id}"
        return f"{signing_link}&redirect_uri={urllib.parse.quote(redirect, safe='')}"

    def _prefill_fields(self, client, document_id: str, full_name: str, email: str) -> None:
        fields = FieldCollection()
        fields.add(Field("Name", full_name))
        fields.add(Field("Email", email))
        prefill_req = DocumentPrefillPutRequest(fields).with_document_id(document_id)
        client.send(prefill_req)

    def _get_role_id(self, client, document_id: str, role_name: str) -> str:
        doc_req = DocumentGetRequest().with_document_id(document_id)
        doc_resp = client.send(doc_req).get_response()
        for role in doc_resp.roles or []:
            if role.get("name") == role_name:
                return role["unique_id"]
        raise RuntimeError(f"Role '{role_name}' not found on document {document_id}")

    def _download_document(self, client, document_id: str) -> str:
        dl_req = (DocumentDownloadGetRequest()
                  .with_document_id(document_id)
                  .with_type("collapsed"))
        dl_resp = client.send(dl_req).get_response()
        return dl_resp.file_path
