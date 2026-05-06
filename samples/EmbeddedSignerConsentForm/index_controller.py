from __future__ import annotations

import urllib.parse
from pathlib import Path
from typing import Any

from fastapi import Response
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from app.sample_interface import SampleController
from app.settings import settings

from signnow.core.factory import SdkFactory
from signnow.api.template.request.clone_template_post_request import CloneTemplatePostRequest
from signnow.api.document.request.document_get_request import DocumentGetRequest
from signnow.api.document.request.document_download_get_request import DocumentDownloadGetRequest
from signnow.api.embeddedinvite.request.document_invite_post_request import DocumentInvitePostRequest
from signnow.api.embeddedinvite.request.document_invite_link_post_request import DocumentInviteLinkPostRequest


TEMPLATE_ID = "3d28c78de8ec43ccab81a3e7dde07925cb5a1d29"
APP_URL = "http://localhost:8080"
SAMPLE_NAME = "EmbeddedSignerConsentForm"
ROLE_NAME = "Recipient 1"


class IndexController(SampleController):
    def handle_get(self, query_params: dict[str, str]) -> Response:
        if query_params.get("page") == "download-container":
            html_path = Path(__file__).parent / "index.html"
            return HTMLResponse(html_path.read_text())

        client = SdkFactory.create_api_client()
        link = self._create_invite_and_return_signing_link(client)
        return RedirectResponse(link, status_code=302)

    def handle_post(self, form_data: dict[str, Any]) -> Response:
        document_id = form_data["document_id"]
        client = SdkFactory.create_api_client()
        file_path = self._download_document(client, document_id)
        return FileResponse(
            path=file_path,
            media_type="application/pdf",
            filename=Path(file_path).name,
        )

    def _create_invite_and_return_signing_link(self, client) -> str:
        clone_req = CloneTemplatePostRequest().with_template_id(TEMPLATE_ID)
        clone_resp = client.send(clone_req).get_response()
        document_id = clone_resp.id

        role_id = self._get_role_id(client, document_id, ROLE_NAME)

        invites = [{
            "email": settings.sn_signer_email,
            "role_id": role_id,
            "order": 1,
            "auth_method": "none",
            "first_name": "first name",
            "last_name": "last name",
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
