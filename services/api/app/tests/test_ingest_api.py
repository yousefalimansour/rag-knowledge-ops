import pytest

pytestmark = pytest.mark.asyncio


async def test_files_endpoint_accepts_txt_and_returns_202_with_job(signed_in, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    from app.api import ingest as ingest_router

    enqueued: list[str] = []

    def dispatcher():
        return lambda job_id: enqueued.append(str(job_id))

    monkeypatch.setattr(ingest_router, "_ingest_dispatcher", dispatcher)

    files = [("files", ("readme.txt", b"first line\n\nsecond paragraph", "text/plain"))]
    r = await signed_in.post("/api/ingest/files", files=files)
    assert r.status_code == 202, r.text
    body = r.json()
    assert len(body["jobs"]) == 1
    assert body["jobs"][0]["status"] == "queued"
    assert enqueued == [body["jobs"][0]["id"]]


async def test_files_endpoint_rejects_unsupported_binary(signed_in, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    from app.api import ingest as ingest_router
    monkeypatch.setattr(ingest_router, "_ingest_dispatcher", lambda: lambda _job_id: None)

    files = [("files", ("blob.bin", b"\x00\xff\xfe\xfd", "application/octet-stream"))]
    r = await signed_in.post("/api/ingest/files", files=files)
    assert r.status_code == 415


async def test_source_endpoint_accepts_slack_payload(signed_in, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    from app.api import ingest as ingest_router
    monkeypatch.setattr(ingest_router, "_ingest_dispatcher", lambda: lambda _job_id: None)

    body = {
        "source": "slack",
        "title": "general thread",
        "payload": {
            "channel": "general",
            "messages": [
                {"user": "a", "ts": "1717084800.000100", "text": "hello"},
                {"user": "b", "ts": "1717084900.000000", "text": "world"},
            ],
        },
    }
    r = await signed_in.post("/api/ingest/source", json=body)
    assert r.status_code == 202, r.text
    assert r.json()["job"]["status"] == "queued"


async def test_source_endpoint_rejects_unknown_source(signed_in):
    r = await signed_in.post(
        "/api/ingest/source",
        json={"source": "wiki", "title": "x", "payload": {}},
    )
    assert r.status_code == 422


async def test_unauth_ingest_returns_401(client):
    r = await client.post(
        "/api/ingest/source",
        json={"source": "slack", "title": "x", "payload": {"messages": []}},
    )
    assert r.status_code == 401
