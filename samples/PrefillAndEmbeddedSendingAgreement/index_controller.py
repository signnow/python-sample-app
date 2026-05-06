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
from signnow.api.embeddedsending.request.document_embedded_sending_link_post_request import DocumentEmbeddedSendingLinkPostRequest


TEMPLATE_ID = "e30d6e58c82d43f598e365420f3c665a048a7d81"
APP_URL = "http://localhost:8080"
SAMPLE_NAME = "PrefillAndEmbeddedSendingAgreement"


class IndexController(SampleController):
    def handle_get(self, query_params: dict[str, str]) -> Response:
        html_path = Path(__file__).parent / "index.html"
        return HTMLResponse(html_path.read_text())

    def handle_post(self, form_data: dict[str, Any]) -> Response:
        action = form_data.get("action")
        client = SdkFactory.create_api_client()

        if action == "create-embedded-invite":
            name = form_data.get("name")
            link = self._create_embedded_invite_and_return_sending_link(client, name)
            return JSONResponse({"link": link})

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

    def _create_embedded_invite_and_return_sending_link(self, client, name: str) -> str:
        clone_req = CloneTemplatePostRequest().with_template_id(TEMPLATE_ID)
        clone_resp = client.send(clone_req).get_response()
        document_id = clone_resp.id

        self._prefill_fields(client, document_id, name)

        return self._get_embedded_sending_link(client, document_id)

    def _prefill_fields(self, client, document_id: str, name: str) -> None:
        fields = FieldCollection()
        fields.add(Field("Name", name))
        prefill_req = DocumentPrefillPutRequest(fields).with_document_id(document_id)
        client.send(prefill_req)

    def _get_embedded_sending_link(self, client, document_id: str) -> str:
        redirect_url = f"{APP_URL}/samples/{SAMPLE_NAME}?page=download-with-status&document_id={document_id}"
        req = DocumentEmbeddedSendingLinkPostRequest(
            "document", redirect_url, 16, "self"
        ).with_document_id(document_id)
        resp = client.send(req).get_response()
        return resp.data["url"]

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
