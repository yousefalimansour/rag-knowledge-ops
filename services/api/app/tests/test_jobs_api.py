import pytest

pytestmark = pytest.mark.asyncio


async def test_get_job_returns_404_for_unknown_id(signed_in):
    r = await signed_in.get("/api/jobs/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


async def test_get_job_for_own_job_returns_200(signed_in, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    from app.api import ingest as ingest_router
    monkeypatch.setattr(ingest_router, "_ingest_dispatcher", lambda: lambda _job_id: None)

    files = [("files", ("note.txt", b"hello world", "text/plain"))]
    r = await signed_in.post("/api/ingest/files", files=files)
    assert r.status_code == 202, r.text
    job_id = r.json()["jobs"][0]["id"]

    r = await signed_in.get(f"/api/jobs/{job_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == job_id
    assert body["status"] == "queued"
