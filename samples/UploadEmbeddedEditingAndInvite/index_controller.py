from __future__ import annotations

import datetime
import tempfile
import urllib.parse
from pathlib import Path
from typing import Any

from fastapi import Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from app.sample_interface import SampleController

from signnow.core.exception import SignNowApiException
from signnow.core.factory import SdkFactory
from signnow.api.document.request.document_get_request import DocumentGetRequest
from signnow.api.document.request.document_post_request import DocumentPostRequest
from signnow.api.document.request.document_download_get_request import DocumentDownloadGetRequest
from signnow.api.documentinvite.request.send_invite_post_request import SendInvitePostRequest
from signnow.api.embeddededitor.request.document_embedded_editor_link_post_request import (
    DocumentEmbeddedEditorLinkPostRequest,
)


APP_URL = "http://localhost:8080"
SAMPLE_NAME = "UploadEmbeddedEditingAndInvite"
SENDER_EMAIL = "sender@signnow.com"


class IndexController(SampleController):
    def handle_get(self, query_params: dict[str, str]) -> Response:
        html_path = Path(__file__).parent / "index.html"
        return HTMLResponse(html_path.read_text())

    def handle_post(self, form_data: dict[str, Any]) -> Response:
        action = form_data.get("action")
        client = SdkFactory.create_api_client()

        if action == "upload_and_create_dg":
            return self._upload_and_create_dg(client, form_data)
        if action == "create_embedded_edit":
            return self._create_embedded_edit(client, form_data)
        if action == "create_invite":
            return self._create_invite(client, form_data)
        if action == "invite-status":
            return self._invite_status(client, form_data)
        if action == "download-document":
            return self._download_document(client, form_data)
        if action == "get-recipients":
            return self._get_recipients(client, form_data)
        if action == "add-recipient":
            return self._add_recipient(client, form_data)
        if action == "get-document-roles":
            return self._get_document_roles(client, form_data)

        return JSONResponse({"success": False, "message": "Invalid action"}, status_code=400)

    # --- actions ---

    def _upload_and_create_dg(self, client, form_data: dict[str, Any]) -> Response:
        upload = form_data.get("document_file")
        if upload is None or not hasattr(upload, "read"):
            return JSONResponse({"success": False, "message": "No file uploaded"}, status_code=400)

        filename = getattr(upload, "filename", "document.pdf") or "document.pdf"
        if not filename.lower().endswith(".pdf"):
            return JSONResponse({"success": False, "message": "Only PDF files are allowed"}, status_code=400)

        content_type = getattr(upload, "content_type", "")
        if content_type and content_type != "application/pdf":
            return JSONResponse({"success": False, "message": "Invalid PDF file format"}, status_code=400)

        # Save upload to a temp file ending with .pdf so the SDK receives a real file path
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            content = upload.file.read() if hasattr(upload, "file") else upload.read()
            if len(content) > 50 * 1024 * 1024:
                Path(tmp.name).unlink(missing_ok=True)
                return JSONResponse(
                    {"success": False, "message": "File size too large. Maximum 50MB allowed"},
                    status_code=400,
                )
            tmp.write(content)
            tmp_path = tmp.name

        try:
            req = DocumentPostRequest(file=tmp_path, name=filename)
            resp = client.send(req).get_response()
            document_id = resp.id
        except SignNowApiException as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=500)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        return JSONResponse({
            "success": True,
            "message": "Document uploaded successfully",
            "document_id": document_id,
        })

    def _create_embedded_edit(self, client, form_data: dict[str, Any]) -> Response:
        document_id = form_data.get("document_id")
        if not document_id:
            return JSONResponse({"success": False, "message": "Document ID is required"}, status_code=400)

        redirect_url = (
            f"{APP_URL}/samples/{SAMPLE_NAME}?"
            + urllib.parse.urlencode({"page": "invite-page", "document_id": document_id})
        )
        try:
            req = DocumentEmbeddedEditorLinkPostRequest(
                redirect_uri=redirect_url,
                redirect_target="self",
                link_expiration=15,
            ).with_document_id(document_id)
            resp = client.send(req).get_response()
            edit_link = resp.data.get("url") if isinstance(resp.data, dict) else None
        except SignNowApiException as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=500)

        return JSONResponse({"success": True, "edit_link": edit_link})

    def _create_invite(self, client, form_data: dict[str, Any]) -> Response:
        document_id = form_data.get("document_id")
        signer_email = form_data.get("signer_email")
        signer_name = form_data.get("signer_name")

        if not document_id or not signer_email or not signer_name:
            return JSONResponse(
                {"success": False, "message": "Document ID, signer email and name are required"},
                status_code=400,
            )

        try:
            doc_resp = client.send(
                DocumentGetRequest().with_document_id(document_id)
            ).get_response()

            recipients = self._extract_recipients_from_doc(doc_resp)
            redirect_uri = f"{APP_URL}/samples/{SAMPLE_NAME}?page=status-page&document_id={document_id}"

            to_list: list[dict[str, Any]] = []
            for role in doc_resp.roles or []:
                role_id = role.get("unique_id")
                role_name = role.get("name")
                signing_order = int(role.get("signing_order") or 1)

                # Find a recipient that targets this role
                matched = next((r for r in recipients if r["role_id"] == role_id), None)
                email_to_use = matched["email"] if matched else signer_email
                name_to_use = matched["role"] if matched else signer_name

                to_list.append({
                    "email": email_to_use,
                    "role_id": role_id,
                    "role": role_name,
                    "order": signing_order,
                    "subject": "Document Signing Request - Action Required",
                    "message": f"Dear {name_to_use}, please review and sign the uploaded document.",
                    "redirect_uri": redirect_uri,
                })

            req = SendInvitePostRequest(
                to=to_list,
                from_email=SENDER_EMAIL,
                subject="Document Signing Request - Action Required",
                message=f"Dear {signer_name}, please review and sign the uploaded document.",
            )
            # SendInvitePostRequest does not have with_document_id in its setters listed, but PHP uses it.
            # If the SDK exposes it, call it; otherwise rely on the constructor to carry document_id.
            if hasattr(req, "with_document_id"):
                req = req.with_document_id(document_id)
            client.send(req)
        except SignNowApiException as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=500)

        return JSONResponse({"success": True, "message": "Invite sent successfully"})

    def _invite_status(self, client, form_data: dict[str, Any]) -> Response:
        document_id = form_data.get("document_id")
        try:
            doc_resp = client.send(
                DocumentGetRequest().with_document_id(document_id)
            ).get_response()
        except SignNowApiException as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=500)

        statuses = []
        for invite in doc_resp.field_invites or []:
            updated = invite.get("updated")
            timestamp = ""
            if updated:
                try:
                    timestamp = datetime.datetime.fromtimestamp(int(updated)).strftime("%Y-%m-%d %H:%M:%S")
                except (TypeError, ValueError):
                    timestamp = ""
            statuses.append({
                "name": invite.get("email", ""),
                "timestamp": timestamp,
                "status": invite.get("status", ""),
            })
        return JSONResponse(statuses)

    def _download_document(self, client, form_data: dict[str, Any]) -> Response:
        document_id = form_data.get("document_id")
        try:
            dl_req = (DocumentDownloadGetRequest()
                      .with_document_id(document_id)
                      .with_type("collapsed"))
            if hasattr(dl_req, "with_history"):
                dl_req = dl_req.with_history("no")
            dl_resp = client.send(dl_req).get_response()
            file_path = dl_resp.file_path
        except SignNowApiException as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=500)
        return FileResponse(
            path=file_path,
            media_type="application/pdf",
            filename="final_document.pdf",
        )

    def _get_recipients(self, client, form_data: dict[str, Any]) -> Response:
        document_id = form_data.get("document_id")
        if not document_id:
            return JSONResponse({"success": False, "message": "Document ID is required"}, status_code=400)

        try:
            doc_resp = client.send(
                DocumentGetRequest().with_document_id(document_id)
            ).get_response()
            recipients = self._extract_recipients_from_doc(doc_resp)
        except SignNowApiException as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=500)
        return JSONResponse({"success": True, "recipients": recipients})

    def _add_recipient(self, client, form_data: dict[str, Any]) -> Response:
        document_id = form_data.get("document_id")
        recipient_name = form_data.get("recipient_name")
        recipient_email = form_data.get("recipient_email")
        recipient_role = form_data.get("recipient_role")

        if not all([document_id, recipient_name, recipient_email, recipient_role]):
            return JSONResponse({"success": False, "message": "All fields are required"}, status_code=400)

        try:
            doc_resp = client.send(
                DocumentGetRequest().with_document_id(document_id)
            ).get_response()
            target_role = None
            for role in doc_resp.roles or []:
                if role.get("name") == recipient_role:
                    target_role = role
                    break
            if target_role is None:
                available = ", ".join(r.get("name", "") for r in (doc_resp.roles or []))
                return JSONResponse(
                    {"success": False, "message": f"Role '{recipient_role}' not found in document. Available roles: {available}"},
                    status_code=400,
                )

            redirect_uri = f"{APP_URL}/samples/{SAMPLE_NAME}?page=status-page&document_id={document_id}"
            to_list = [{
                "email": recipient_email,
                "role_id": target_role.get("unique_id"),
                "role": target_role.get("name"),
                "order": int(target_role.get("signing_order") or 1),
                "subject": "Document Signing Request - Action Required",
                "message": f"Dear {recipient_name}, please review and sign the uploaded document.",
                "redirect_uri": redirect_uri,
            }]

            req = SendInvitePostRequest(
                to=to_list,
                from_email=SENDER_EMAIL,
                subject="Document Signing Request - Action Required",
                message=f"Dear {recipient_name}, please review and sign the uploaded document.",
            )
            if hasattr(req, "with_document_id"):
                req = req.with_document_id(document_id)
            client.send(req)
        except SignNowApiException as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=500)

        return JSONResponse({"success": True, "message": "Recipient added and invite sent successfully"})

    def _get_document_roles(self, client, form_data: dict[str, Any]) -> Response:
        document_id = form_data.get("document_id")
        if not document_id:
            return JSONResponse({"success": False, "message": "Document ID is required"}, status_code=400)

        try:
            doc_resp = client.send(
                DocumentGetRequest().with_document_id(document_id)
            ).get_response()
        except SignNowApiException as e:
            return JSONResponse({"success": False, "message": str(e)}, status_code=500)

        roles_data = [{
            "name": r.get("name"),
            "unique_id": r.get("unique_id"),
            "signing_order": r.get("signing_order"),
        } for r in (doc_resp.roles or [])]

        return JSONResponse({"success": True, "roles": roles_data})

    # --- helpers ---

    def _extract_recipients_from_doc(self, doc_resp) -> list[dict[str, Any]]:
        """Extract recipients from document routing_details (matches PHP getDocumentRecipients)."""
        recipients: list[dict[str, Any]] = []
        routing_details = getattr(doc_resp, "routing_details", None) or []
        for routing_detail in routing_details:
            # routing_detail may be a dict with 'data' key, or an object with data attr
            data_collection = (
                routing_detail.get("data") if isinstance(routing_detail, dict)
                else getattr(routing_detail, "data", None)
            ) or []
            for data in data_collection:
                recipients.append({
                    "email": data.get("default_email") if isinstance(data, dict) else getattr(data, "default_email", None),
                    "role": data.get("name") if isinstance(data, dict) else getattr(data, "name", None),
                    "role_id": data.get("role_id") if isinstance(data, dict) else getattr(data, "role_id", None),
                    "signing_order": data.get("signing_order") if isinstance(data, dict) else getattr(data, "signing_order", None),
                    "inviter_role": data.get("inviter_role") if isinstance(data, dict) else getattr(data, "inviter_role", None),
                })
        return recipients
