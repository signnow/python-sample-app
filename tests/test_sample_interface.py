import pytest
from fastapi.responses import PlainTextResponse
from app.sample_interface import SampleController


def test_abstract_class_cannot_be_instantiated():
    with pytest.raises(TypeError):
        SampleController()  # type: ignore


def test_concrete_subclass_works():
    class MyCtrl(SampleController):
        def handle_get(self, query_params):
            return PlainTextResponse("get")

        def handle_post(self, form_data):
            return PlainTextResponse("post")

    c = MyCtrl()
    assert c.handle_get({}).body == b"get"
    assert c.handle_post({}).body == b"post"


def test_missing_methods_raise():
    class Incomplete(SampleController):
        pass

    with pytest.raises(TypeError):
        Incomplete()  # type: ignore
