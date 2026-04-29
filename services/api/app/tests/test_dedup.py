import pytest

pytestmark = pytest.mark.asyncio


async def test_duplicate_file_dedups_to_existing_doc(signed_in, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    from app.api import ingest as ingest_router
    monkeypatch.setattr(ingest_router, "_ingest_dispatcher", lambda: lambda _job_id: None)

    raw = b"hello world from a tiny test file"
    files = [("files", ("note.txt", raw, "text/plain"))]
    r1 = await signed_in.post("/api/ingest/files", files=files)
    assert r1.status_code == 202, r1.text
    j1 = r1.json()["jobs"][0]
    assert j1["deduplicated"] is False

    r2 = await signed_in.post("/api/ingest/files", files=files)
    assert r2.status_code == 202
    j2 = r2.json()["jobs"][0]
    assert j2["deduplicated"] is True
    assert j2["document_id"] == j1["document_id"]


async def test_changed_content_same_title_creates_new_version(signed_in, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    from app.api import ingest as ingest_router
    monkeypatch.setattr(ingest_router, "_ingest_dispatcher", lambda: lambda _job_id: None)

    files_v1 = [("files", ("policy.txt", b"version one body", "text/plain"))]
    files_v2 = [("files", ("policy.txt", b"version two body - changed", "text/plain"))]

    r1 = await signed_in.post("/api/ingest/files", files=files_v1)
    r2 = await signed_in.post("/api/ingest/files", files=files_v2)
    assert r1.status_code == 202 and r2.status_code == 202

    listing = await signed_in.get("/api/docs?q=policy")
    assert listing.status_code == 200
    items = listing.json()["items"]
    versions = sorted(d["version"] for d in items)
    assert versions == [1, 2]
