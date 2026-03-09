import pytest

pytestmark = pytest.mark.integration


def test_api_endpoint_template(client, db_session):
    # Arrange
    # Seed rows with db_session.add(...) and db_session.commit()

    # Act
    response = client.get("/api/v1/replace/with/real/endpoint")

    # Assert
    assert response.status_code == 200
    payload = response.get_json()
    assert payload is not None

