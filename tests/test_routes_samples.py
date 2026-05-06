import importlib
import pytest
from app.sample_interface import SampleController


SAMPLES = [
    "EVDemoSendingAnd3EmbeddedSigners",
    "EmbeddedEditingAndSigningDG",
    "EmbeddedSenderWithFormAndFirstSigner",
    "EmbeddedSenderWithFormCreditLoanAgreement",
    "EmbeddedSenderWithFormDG",
    "EmbeddedSenderWithFormDGAdjunct",
    "EmbeddedSenderWithFormDGConstr",
    "EmbeddedSenderWithoutFormFile",
    "EmbeddedSignerConsentForm",
    "EmbeddedSignerConsumerServices",
    "EmbeddedSignerPatientIntakeForm",
    "EmbeddedSignerWithFormInsurance",
    "HROnboardingSystem",
    "ISVWithFormAndOneClickSendBasicPrefill",
    "ISVWithFormAndOneClickSendMergeFields",
    "MedicalInsuranceClaimForm",
    "PrefillAndEmbeddedSendingAgreement",
    "PrefillAndOneClickSendingAgreement",
    "UploadEmbeddedEditingAndInvite",
    "UploadEmbeddedSender",
]


@pytest.mark.parametrize("name", SAMPLES)
def test_sample_module_loads(name):
    module = importlib.import_module(f"samples.{name}.index_controller")
    assert hasattr(module, "IndexController")
    assert issubclass(module.IndexController, SampleController)


def test_all_samples_have_folder_and_html():
    import os
    samples_dir = os.path.join(os.path.dirname(__file__), "..", "samples")
    for name in SAMPLES:
        folder = os.path.join(samples_dir, name)
        assert os.path.isdir(folder), f"Missing folder for {name}"
        assert os.path.isfile(os.path.join(folder, "__init__.py")), f"Missing __init__.py for {name}"
        assert os.path.isfile(os.path.join(folder, "index_controller.py")), f"Missing controller for {name}"
        assert os.path.isfile(os.path.join(folder, "index.html")), f"Missing index.html for {name}"
