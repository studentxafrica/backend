import pytest

pytestmark = pytest.mark.integration


def test_health_check_reports_revision(client):
    response = client.get("/healthz")

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ok"
    assert body["revision"]


def test_health_check_reads_revision_from_git_checkout():
    import subprocess

    from app import read_revision

    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    if not head:
        pytest.skip("not running inside a git checkout")

    assert read_revision() == head
