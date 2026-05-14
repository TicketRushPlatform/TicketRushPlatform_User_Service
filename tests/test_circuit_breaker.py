import pytest
import requests

from app.errors import AppError
from app.services.oauth_service import OAuthVerifier, google_oauth_breaker
from tests.conftest import TestConfig


def test_circuit_breaker_demo_opens_after_repeated_failures(client):
    response = client.get("/circuit-breaker/demo?reset=true")
    assert response.status_code == 200
    assert response.get_json()["breaker"]["state"] == "closed"

    for _ in range(3):
        response = client.get("/circuit-breaker/demo?fail=true")
        assert response.status_code == 502

    response = client.get("/circuit-breaker/demo")
    assert response.status_code == 503
    assert response.get_json()["breaker"]["state"] == "open"

    response = client.get("/circuit-breaker/demo?reset=true")
    assert response.status_code == 200
    assert response.get_json()["breaker"]["state"] == "closed"


def test_google_oauth_uses_circuit_breaker_for_provider_failures(monkeypatch):
    google_oauth_breaker.reset()
    calls = {"count": 0}

    def failing_request(*_args, **_kwargs):
        calls["count"] += 1
        raise requests.Timeout("provider timeout")

    monkeypatch.setattr(requests, "request", failing_request)
    verifier = OAuthVerifier(TestConfig())

    for _ in range(3):
        with pytest.raises(AppError) as exc:
            verifier.verify_google({"id_token": "provider-token"})
        assert exc.value.code == "OAUTH_PROVIDER_UNAVAILABLE"
        assert exc.value.status == 503

    with pytest.raises(AppError) as exc:
        verifier.verify_google({"id_token": "provider-token"})

    assert exc.value.code == "OAUTH_PROVIDER_UNAVAILABLE"
    assert exc.value.details["state"] == "open"
    assert calls["count"] == 3
    google_oauth_breaker.reset()
