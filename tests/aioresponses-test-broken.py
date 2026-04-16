# Currently broken, needs further investigation
"""
Comprehensive unittest suite for aioresponses (aiohttp mocking).

Run:
  python -m unittest -q this_file.py
"""

import asyncio
import re
import unittest
from contextlib import asynccontextmanager

import aiohttp
from aiohttp import web
from aiohttp.http_exceptions import HttpProcessingError

from aioresponses import CallbackResult, aioresponses


def _iter_recorded_calls(m):
    """
    Yield (method, url_str, call) for all recorded calls across aioresponses versions.

    Different aioresponses versions store m.requests with keys like:
      - (method, url_str)
      - (method, yarl.URL)
      - or other url-like objects.
    We normalize to (method, str(url)).
    """
    reqs = getattr(m, "requests", {}) or {}
    for key, calls in reqs.items():
        # key often is a tuple (method, url)
        if isinstance(key, tuple) and len(key) >= 2:
            method = str(key[0]).upper()
            url_obj = key[1]
            url_str = str(url_obj)
        else:
            method = "UNKNOWN"
            url_str = str(key)

        for c in calls or []:
            yield method, url_str, c


def _count_calls(m, method: str, url: str) -> int:
    method = method.upper()
    url = str(url)
    return sum(1 for meth, u, _ in _iter_recorded_calls(m) if meth == method and u == url)


def _total_calls(m) -> int:
    reqs = getattr(m, "requests", {}) or {}
    return sum(len(v) for v in reqs.values())


@asynccontextmanager
async def _test_server():
    async def ok_json(request):
        return web.json_response({"ok": True, "path": request.path, "qs": dict(request.query)})

    app = web.Application()
    app.router.add_get("/real", ok_json)
    app.router.add_get("/unmatched", ok_json)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 0)
    await site.start()

    sockets = list(site._server.sockets)  # type: ignore[attr-defined]
    host, port = sockets[0].getsockname()[:2]
    base_url = f"http://{host}:{port}"

    try:
        yield base_url
    finally:
        await runner.cleanup()


class TestAioResponses(unittest.TestCase):
    def test_decorator_basic_get_body_and_assert_called(self):
        @aioresponses()
        def _run(m):
            async def main():
                url = "http://example.test/decorated"
                m.get(url, status=200, body=b"hello")

                async with aiohttp.ClientSession() as session:
                    resp = await session.get(url)
                    self.assertEqual(200, resp.status)
                    self.assertEqual(b"hello", await resp.read())

                m.assert_called_once_with(url)

            asyncio.run(main())

        _run()

    def test_context_manager_payload_json_and_headers(self):
        async def main():
            url = "http://example.test/json"
            with aioresponses() as m:
                m.get(url, payload={"foo": "bar"}, headers={"connection": "keep-alive"})

                async with aiohttp.ClientSession() as session:
                    resp = await session.get(url)
                    self.assertEqual(200, resp.status)
                    self.assertEqual({"foo": "bar"}, await resp.json())
                    self.assertEqual("keep-alive", resp.headers["Connection"])

                m.assert_called_once_with(url)

        asyncio.run(main())

    def test_supported_http_methods_and_call_registry(self):
        """
        Validates that each supported HTTP method is recorded at least once,
        using robust scanning of m.requests across aioresponses versions.
        """
        async def main():
            base = "http://example.test/methods"
            urls = {
                "GET": f"{base}/get",
                "POST": f"{base}/post",
                "PUT": f"{base}/put",
                "PATCH": f"{base}/patch",
                "DELETE": f"{base}/delete",
                "OPTIONS": f"{base}/options",
            }

            with aioresponses() as m:
                m.get(urls["GET"], status=200, body="get-ok")
                m.post(urls["POST"], status=201, payload={"created": True})
                m.put(urls["PUT"], status=202, body=b"put-ok")
                m.patch(urls["PATCH"], status=203, body=b"patch-ok")
                m.delete(urls["DELETE"], status=204, body=b"")
                m.options(urls["OPTIONS"], status=205, body="options-ok")

                async with aiohttp.ClientSession() as session:
                    self.assertEqual(200, (await session.get(urls["GET"])).status)
                    self.assertEqual(201, (await session.post(urls["POST"], json={"ignored": True})).status)
                    self.assertEqual(202, (await session.put(urls["PUT"], data=b"x")).status)
                    self.assertEqual(203, (await session.patch(urls["PATCH"])).status)
                    self.assertEqual(204, (await session.delete(urls["DELETE"])).status)
                    self.assertEqual(205, (await session.options(urls["OPTIONS"])).status)

                # Ensure requests got recorded
                self.assertGreaterEqual(_total_calls(m), 6)

                # Ensure each method+url appears at least once
                for meth, url in urls.items():
                    self.assertGreaterEqual(
                        _count_calls(m, meth, url), 1,
                        msg=f"Expected at least 1 recorded call for {meth} {url}"
                    )

        asyncio.run(main())

    def test_regex_url_matching(self):
        async def main():
            pattern = re.compile(r"^http://example\.test/api\?foo=.*$")
            with aioresponses() as m:
                m.get(pattern, status=200, body="matched")

                async with aiohttp.ClientSession() as session:
                    resp = await session.get("http://example.test/api?foo=bar")
                    self.assertEqual(200, resp.status)
                    self.assertEqual("matched", await resp.text())

        asyncio.run(main())

    def test_multiple_responses_queue_without_repeat(self):
        async def main():
            url = "http://example.test/queue"
            with aioresponses() as m:
                m.get(url, status=500)
                m.get(url, status=200, body="ok-second")

                async with aiohttp.ClientSession() as session:
                    r1 = await session.get(url)
                    r2 = await session.get(url)
                    self.assertEqual(500, r1.status)
                    self.assertEqual(200, r2.status)
                    self.assertEqual("ok-second", await r2.text())

        asyncio.run(main())

    def test_repeat_semantics_returns_same_response_many_times(self):
        async def main():
            url = "http://example.test/repeat"
            with aioresponses() as m:
                m.get(url, status=500, repeat=2)

                async with aiohttp.ClientSession() as session:
                    statuses = []
                    for _ in range(5):
                        r = await session.get(url)
                        statuses.append(r.status)

                self.assertTrue(all(s == 500 for s in statuses), statuses)

        asyncio.run(main())

    def test_redirects_absolute_and_relative(self):
        async def main():
            start = "http://example.test/"
            abs_target = "http://another.test/abs"
            rel_target = "/rel"

            with aioresponses() as m:
                m.get(start, status=307, headers={"Location": abs_target})
                m.get(abs_target, status=200, body="abs-ok")

                async with aiohttp.ClientSession() as session:
                    resp = await session.get(start, allow_redirects=True)
                    self.assertEqual(200, resp.status)
                    self.assertEqual(abs_target, str(resp.url))
                    self.assertEqual("abs-ok", await resp.text())

            with aioresponses() as m:
                m.get(start, status=307, headers={"Location": rel_target})
                m.get("http://example.test/rel", status=200, body="rel-ok")

                async with aiohttp.ClientSession() as session:
                    resp = await session.get(start, allow_redirects=True)
                    self.assertEqual(200, resp.status)
                    self.assertEqual("http://example.test/rel", str(resp.url))
                    self.assertEqual("rel-ok", await resp.text())

        asyncio.run(main())

    def test_raising_exception(self):
        async def main():
            url = "http://example.test/boom"
            with aioresponses() as m:
                m.get(url, exception=HttpProcessingError(code=400, message="bad"))
                async with aiohttp.ClientSession() as session:
                    with self.assertRaises(HttpProcessingError):
                        await session.get(url)

        asyncio.run(main())

    def test_callbacks_sync_and_async(self):
        async def main():
            url_sync = "http://example.test/cb-sync"
            url_async = "http://example.test/cb-async"

            def cb_sync(url, **kwargs):
                return CallbackResult(status=418, body="teapot")

            async def cb_async(url, **kwargs):
                await asyncio.sleep(0)
                return CallbackResult(status=200, payload={"from": "async-callback"})

            with aioresponses() as m:
                m.get(url_sync, callback=cb_sync)
                m.get(url_async, callback=cb_async)

                async with aiohttp.ClientSession() as session:
                    r1 = await session.get(url_sync)
                    self.assertEqual(418, r1.status)
                    self.assertEqual("teapot", await r1.text())

                    r2 = await session.get(url_async)
                    self.assertEqual(200, r2.status)
                    self.assertEqual({"from": "async-callback"}, await r2.json())

        asyncio.run(main())

    def test_passthrough_and_passthrough_unmatched_local_server(self):
        async def main():
            async with _test_server() as base_url:
                real_url = f"{base_url}/real"
                unmatched_url = f"{base_url}/unmatched"
                mocked_url = "http://example.test/mocked"

                with aioresponses(passthrough=[base_url]) as m:
                    m.get(mocked_url, payload={"mocked": True})
                    async with aiohttp.ClientSession() as session:
                        r_real = await session.get(real_url)
                        self.assertEqual(200, r_real.status)
                        self.assertEqual({"ok": True, "path": "/real", "qs": {}}, await r_real.json())

                        r_mocked = await session.get(mocked_url)
                        self.assertEqual(200, r_mocked.status)
                        self.assertEqual({"mocked": True}, await r_mocked.json())

                with aioresponses(passthrough_unmatched=True, passthrough=[base_url]) as m:
                    m.get(mocked_url, status=202, body="only-this-is-mocked")
                    async with aiohttp.ClientSession() as session:
                        r_unmatched = await session.get(unmatched_url)
                        self.assertEqual(200, r_unmatched.status)
                        self.assertEqual({"ok": True, "path": "/unmatched", "qs": {}}, await r_unmatched.json())

                        r_mocked = await session.get(mocked_url)
                        self.assertEqual(202, r_mocked.status)
                        self.assertEqual("only-this-is-mocked", await r_mocked.text())

        asyncio.run(main())


if __name__ == "__main__":
    unittest.main(verbosity=2)
