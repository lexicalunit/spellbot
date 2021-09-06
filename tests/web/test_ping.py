class TestWebPing:
    async def test_ping(self, client):
        resp = await client.get("/")
        assert resp.status == 200
        text = await resp.text()
        assert "ok" in text
