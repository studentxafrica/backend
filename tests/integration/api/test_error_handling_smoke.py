import pytest

pytestmark = pytest.mark.integration


def test_unknown_route_returns_json_404(client):
    response = client.get("/__pytest_missing_route__")

    assert response.status_code == 404
    payload = response.get_json()
    assert payload is not None
    assert payload["message"] == "Resource not found (404)"

