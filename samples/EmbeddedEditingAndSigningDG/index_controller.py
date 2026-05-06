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
from signnow.api.documentgroup.request.document_group_recipients_put_request import DocumentGroupRecipientsPutRequest
from signnow.api.documentgroup.request.download_document_group_post_request import DownloadDocumentGroupPostRequest
from signnow.api.documentgroupinvite.request.group_invite_get_request import GroupInviteGetRequest
from signnow.api.documentgrouptemplate.request.document_group_template_post_request import DocumentGroupTemplatePostRequest
from signnow.api.embeddededitor.request.document_group_embedded_editor_link_post_request import DocumentGroupEmbeddedEditorLinkPostRequest
from signnow.api.embeddedgroupinvite.request.group_invite_post_request import GroupInvitePostRequest as EmbeddedGroupInvitePostRequest
from signnow.api.embeddedgroupinvite.request.group_invite_link_post_request import GroupInviteLinkPostRequest


TEMPLATE_ID = "de45a9a2a6014c2c8ac0a4d9057b17a2108e77e7"
DOCUMENT_GROUP_TEMPLATE_ID = "0d7fb734e962418bad79d8fb80bbdaaf1f8e8cd9"

ROLE_CONTRACT_PREPARER = "Contract Preparer"
ROLE_RECIPIENT_1 = "Recipient 1"
ROLE_RECIPIENT_2 = "Recipient 2"

APP_URL = "http://localhost:8080"
SAMPLE_NAME = "EmbeddedEditingAndSigningDG"
REDIRECT_BASE_URL = f"{APP_URL}/samples/{SAMPLE_NAME}"


class IndexController(SampleController):
    def handle_get(self, query_params: dict[str, str]) -> Response:
        html_path = Path(__file__).parent / "index.html"
        return HTMLResponse(html_path.read_text())

    def handle_post(self, form_data: dict[str, Any]) -> Response:
        action = form_data.get("action", "")
        client = SdkFactory.create_api_client()

        if action == "submit-signer-info":
            return self._submit_signer_info(form_data, client)
        if action == "create-embedded-invite":
            return self._create_embedded_invite(form_data, client)
        if action == "invite-status":
            dg_id = form_data["document_group_id"]
            statuses = self._get_document_group_signers_status(client, dg_id)
            return JSONResponse(statuses)

        # download-doc-group (default)
        dg_id = form_data["document_group_id"]
        file_path = self._download_document_group_file(client, dg_id)
        return FileResponse(
            path=file_path,
            media_type="application/pdf",
            filename=Path(file_path).name,
        )

    def _submit_signer_info(self, data: dict[str, Any], client) -> Response:
        signer_1_name = data.get("signer_1_name")
        signer_1_email = data.get("signer_1_email")
        signer_2_name = data.get("signer_2_name")
        signer_2_email = data.get("signer_2_email")

        dg_id = self._create_document_group_from_template(client, DOCUMENT_GROUP_TEMPLATE_ID)

        self._prefill_doc_group_fields(client, dg_id, {
            "Signer 1 Name": signer_1_name,
            "Signer 2 Name": signer_2_name,
        })

        self._update_document_group_recipients(client, dg_id, {
            ROLE_RECIPIENT_1: signer_1_email,
            ROLE_RECIPIENT_2: signer_2_email,
        })

        edit_link = self._create_embedded_edit_link(client, dg_id)

        return JSONResponse({
            "document_group_id": dg_id,
            "edit_link": edit_link,
        })

    def _create_embedded_invite(self, data: dict[str, Any], client) -> Response:
        dg_id = data["document_group_id"]
        contract_preparer_email = data.get("contract_preparer_email")

        signing_link = self._create_embedded_invite_link(client, dg_id, contract_preparer_email)

        return JSONResponse({
            "document_group_id": dg_id,
            "signing_link": signing_link,
        })

    def _create_document_group_from_template(self, client, template_id: str) -> str:
        req = DocumentGroupTemplatePostRequest(
            "Embedded Editing & Signing Group", "", None
        ).with_template_group_id(template_id)
        resp = client.send(req).get_response()
        return resp.data["unique_id"]

    def _prefill_doc_group_fields(self, client, dg_id: str, fields_to_fill: dict[str, str]) -> None:
        dg = self._get_document_group(client, dg_id)

        for doc_item in dg.documents or []:
            doc_id = doc_item["id"]
            doc_data = self._get_document(client, doc_id)

            fields = FieldCollection()
            for field in doc_data.fields or []:
                field_name = self._extract_field_name(field)
                if field_name and field_name in fields_to_fill:
                    fields.add(Field(field_name, fields_to_fill[field_name]))

            if len(fields.to_list()) > 0:
                prefill_req = DocumentPrefillPutRequest(fields).with_document_id(doc_id)
                client.send(prefill_req)

    def _update_document_group_recipients(self, client, dg_id: str, recipient_emails: dict[str, str]) -> None:
        resp = self._get_document_group_recipients(client, dg_id)
        current = resp.data["recipients"]

        updated = []
        for recipient in current:
            rname = recipient.get("name")
            email = recipient_emails.get(rname)
            req_docs = []
            for doc in recipient.get("documents", []):
                req_docs.append({
                    "id": doc.get("id"),
                    "role": doc.get("role"),
                    "action": doc.get("action"),
                })
            updated.append({
                "name": rname,
                "email": email,
                "order": recipient.get("order"),
                "documents": req_docs,
            })

        put_req = DocumentGroupRecipientsPutRequest(
            recipients=updated, cc=[]
        ).with_document_group_id(dg_id)
        client.send(put_req)

    def _create_embedded_edit_link(self, client, dg_id: str) -> str:
        redirect_url = f"{REDIRECT_BASE_URL}?page=page2-embedded-sending&document_group_id={dg_id}"
        req = DocumentGroupEmbeddedEditorLinkPostRequest(
            redirect_url, "self", 15
        ).with_document_group_id(dg_id)
        resp = client.send(req).get_response()
        return resp.data["url"]

    def _create_embedded_invite_link(self, client, dg_id: str, contract_preparer_email: str) -> str:
        recipients_resp = self._get_document_group_recipients(client, dg_id)
        recipient1_email = self._find_email_by_role_name(recipients_resp, ROLE_RECIPIENT_1)
        recipient2_email = self._find_email_by_role_name(recipients_resp, ROLE_RECIPIENT_2)

        redirect_url = f"{REDIRECT_BASE_URL}?page=page4-status-download&document_group_id={dg_id}"

        invites: list[dict[str, Any]] = []
        order = 1

        # Contract preparer
        invites.append({
            "order": order,
            "signers": [{
                "email": contract_preparer_email,
                "auth_method": "none",
                "documents": self._build_documents_for_role(client, dg_id, ROLE_CONTRACT_PREPARER),
                "redirect_uri": redirect_url,
                "redirect_target": "self",
            }],
        })
        order += 1

        invites.append({
            "order": order,
            "signers": [{
                "email": recipient1_email,
                "auth_method": "none",
                "documents": self._build_documents_for_role(client, dg_id, ROLE_RECIPIENT_1),
                "redirect_uri": redirect_url,
                "redirect_target": "self",
                "decline_redirect_target": "email",
            }],
        })
        order += 1

        invites.append({
            "order": order,
            "signers": [{
                "email": recipient2_email,
                "auth_method": "none",
                "documents": self._build_documents_for_role(client, dg_id, ROLE_RECIPIENT_2),
                "redirect_uri": redirect_url,
                "redirect_target": "self",
                "decline_redirect_target": "email",
            }],
        })

        invite_req = EmbeddedGroupInvitePostRequest(
            invites=invites,
            sign_as_merged=True,
        ).with_document_group_id(dg_id)
        invite_resp = client.send(invite_req).get_response()

        embedded_invite_id = invite_resp.data["id"]

        link_req = (GroupInviteLinkPostRequest(contract_preparer_email, "none", 30)
                    .with_document_group_id(dg_id)
                    .with_embedded_invite_id(embedded_invite_id))
        link_resp = client.send(link_req).get_response()
        return link_resp.data["link"]

    def _build_documents_for_role(self, client, dg_id: str, role_name: str) -> list[dict[str, Any]]:
        dg = self._get_document_group(client, dg_id)
        docs: list[dict[str, Any]] = []
        for doc in dg.documents or []:
            roles = doc.get("roles") or []
            role_present = role_name in roles
            docs.append({
                "id": doc.get("id"),
                "action": "sign" if role_present else "view",
                "role": role_name,
            })
        return docs

    def _get_document_group_signers_status(self, client, dg_id: str) -> list[dict[str, Any]]:
        dg = self._get_document_group(client, dg_id)
        invite_id = dg.invite_id if hasattr(dg, "invite_id") else None

        status_req = (GroupInviteGetRequest()
                      .with_document_group_id(dg_id)
                      .with_invite_id(invite_id))
        status_resp = client.send(status_req).get_response()

        step_statuses: dict[int, str] = {}
        invite = getattr(status_resp, "invite", None) or {}
        steps = invite.get("steps", []) if isinstance(invite, dict) else []
        for step in steps:
            step_statuses[step.get("order")] = step.get("status")

        recipients_resp = self._get_document_group_recipients(client, dg_id)

        result: list[dict[str, Any]] = []
        for recipient in recipients_resp.data["recipients"]:
            order = recipient.get("order")
            result.append({
                "name": recipient.get("name"),
                "email": recipient.get("email"),
                "order": order,
                "status": step_statuses.get(order, "unknown"),
                "timestamp": None,
            })
        return result

    def _find_email_by_role_name(self, recipients_resp, role_name: str) -> str | None:
        for recipient in recipients_resp.data["recipients"]:
            if recipient.get("name") == role_name:
                return recipient.get("email")
        return None

    def _extract_field_name(self, field) -> str | None:
        if not isinstance(field, dict):
            return None
        json_attrs = field.get("json_attributes") or field.get("jsonAttributes")
        if isinstance(json_attrs, dict):
            n = json_attrs.get("name")
            return str(n) if n is not None else None
        return None

    def _download_document_group_file(self, client, dg_id: str) -> str:
        req = DownloadDocumentGroupPostRequest(
            "merged", "no", []
        ).with_document_group_id(dg_id)
        resp = client.send(req).get_response()
        return resp.file_path

    def _get_document_group(self, client, dg_id: str):
        req = DocumentGroupGetRequest().with_document_group_id(dg_id)
        return client.send(req).get_response()

    def _get_document(self, client, document_id: str):
        req = DocumentGetRequest().with_document_id(document_id)
        return client.send(req).get_response()

    def _get_document_group_recipients(self, client, dg_id: str):
        req = DocumentGroupRecipientsGetRequest().with_document_group_id(dg_id)
        return client.send(req).get_response()
