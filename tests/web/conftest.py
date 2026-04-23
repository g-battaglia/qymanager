import pytest
from fastapi.testclient import TestClient

from web.backend.app import create_app
from web.backend.session import get_session


@pytest.fixture(autouse=True)
def clean_session():
    get_session()._devices.clear()
    yield
    get_session()._devices.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())
