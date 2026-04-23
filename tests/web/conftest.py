import pytest
from fastapi.testclient import TestClient

from web.backend.app import create_app
from web.backend.session import get_session


@pytest.fixture(autouse=True)
def clean_session():
    sess = get_session()
    sess._devices.clear()
    sess._filenames.clear()
    yield
    sess._devices.clear()
    sess._filenames.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())
