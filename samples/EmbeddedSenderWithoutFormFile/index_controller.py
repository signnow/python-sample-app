from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse

from app.sample_interface import SampleController

from signnow.core.factory import SdkFactory
from signnow.api.template.request.clone_template_post_request import CloneTemplatePostRequest
from signnow.api.document.request.document_get_request import DocumentGetRequest
from signnow.api.document.request.document_download_get_request import DocumentDownloadGetRequest
from signnow.api.embeddedsending.request.document_embedded_sending_link_post_request import DocumentEmbeddedSendingLinkPostRequest


TEMPLATE_ID = "76713f00c106425ea8b673c49fd94c0145643c34"
APP_URL = "http://localhost:8080"
SAMPLE_NAME = "EmbeddedSenderWithoutFormFile"


class IndexController(SampleController):
    def handle_get(self, query_params: dict[str, str]) -> Response:
        if query_params.get("page") == "download-with-status":
            html_path = Path(__file__).parent / "index.html"
            return HTMLResponse(html_path.read_text())

        client = SdkFactory.create_api_client()
        link = self._get_embedded_sending_link(client)
        return RedirectResponse(link, status_code=302)

    def handle_post(self, form_data: dict[str, Any]) -> Response:
        action = form_data.get("action")
        client = SdkFactory.create_api_client()
        document_id = form_data["document_id"]

        if action == "invite-status":
            statuses = self._get_document_statuses(client, document_id)
            return JSONResponse(statuses)

        file_path = self._download_document(client, document_id)
        return FileResponse(
            path=file_path,
            media_type="application/pdf",
            filename=Path(file_path).name,
        )

    def _get_embedded_sending_link(self, client) -> str:
        clone_req = CloneTemplatePostRequest().with_template_id(TEMPLATE_ID)
        clone_resp = client.send(clone_req).get_response()
        document_id = clone_resp.id

        redirect_url = f"{APP_URL}/samples/{SAMPLE_NAME}?page=download-with-status&document_id={document_id}"
        req = DocumentEmbeddedSendingLinkPostRequest(
            "document", redirect_url, 16, "self"
        ).with_document_id(document_id)
        resp = client.send(req).get_response()
        return resp.data["url"]

    def _get_document_statuses(self, client, document_id: str) -> list[dict[str, str]]:
        doc_req = DocumentGetRequest().with_document_id(document_id)
        doc_resp = client.send(doc_req).get_response()
        statuses: list[dict[str, str]] = []
        for invite in doc_resp.field_invites or []:
            statuses.append({
                "name": invite.get("email"),
                "status": invite.get("status"),
            })
        return statuses

    def _download_document(self, client, document_id: str) -> str:
        dl_req = (DocumentDownloadGetRequest()
                  .with_document_id(document_id)
                  .with_type("collapsed"))
        dl_resp = client.send(dl_req).get_response()
        return dl_resp.file_path
