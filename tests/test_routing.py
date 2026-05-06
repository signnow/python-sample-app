import pytest
from app.routing import load_controller, is_valid_sample_name


@pytest.mark.parametrize("name,expected", [
    ("EmbeddedSignerConsentForm", True),
    ("HR_Onboarding_123", True),
    ("a", True),
    ("", False),
    ("has-dash", False),
    ("with.dot", False),
    ("has space", False),
    ("../etc/passwd", False),
    ("slash/name", False),
])
def test_is_valid_sample_name(name, expected):
    assert is_valid_sample_name(name) is expected


def test_load_controller_rejects_invalid_name():
    assert load_controller("../etc/passwd") is None
    assert load_controller("has-dash") is None


def test_load_controller_returns_none_for_unknown_module():
    assert load_controller("DefinitelyDoesNotExist") is None


from fastapi.testclient import TestClient
from app.main import app


def test_root_returns_404():
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 404
    assert "text/html" in resp.headers["content-type"]


def test_unknown_sample_returns_404():
    client = TestClient(app)
    resp = client.get("/samples/DefinitelyDoesNotExist")
    assert resp.status_code == 404


def test_invalid_name_returns_404():
    client = TestClient(app)
    resp = client.get("/samples/has-dash")
    assert resp.status_code == 404
    resp2 = client.get("/samples/with.dot")
    assert resp2.status_code == 404


def test_static_css_is_served():
    client = TestClient(app)
    resp = client.get("/css/bootstrap.min.css")
    assert resp.status_code == 200


def test_static_img_is_served():
    client = TestClient(app)
    resp = client.get("/img/sign-now.png")
    assert resp.status_code == 200


def test_samples_index_html():
    client = TestClient(app)
    resp = client.get("/samples")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    # Every known sample should appear in the HTML index
    for name in [
        "EmbeddedSignerConsentForm",
        "UploadEmbeddedEditingAndInvite",
        "EVDemoSendingAnd3EmbeddedSigners",
    ]:
        assert name in resp.text


def test_api_samples_returns_json_list():
    client = TestClient(app)
    resp = client.get("/api/samples")
    assert resp.status_code == 200
    data = resp.json()
    assert "samples" in data
    assert isinstance(data["samples"], list)
    assert len(data["samples"]) == 20
    assert "EmbeddedSignerConsentForm" in data["samples"]
    # Alphabetically sorted
    assert data["samples"] == sorted(data["samples"])
