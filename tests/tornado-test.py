import os
import io
import json
import unittest
import tempfile

import tornado.ioloop
import tornado.web
import tornado.websocket
import tornado.httpclient
import tornado.testing
import tornado.gen
from tornado.testing import AsyncHTTPTestCase
from tornado.web import HTTPError, URLSpec
from tornado.ioloop import PeriodicCallback
from tornado.locks import Event


# ---------------------------
# Application / Handlers
# ---------------------------

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("OK")


class EchoHandler(tornado.web.RequestHandler):
    def get(self):
        self.write(self.get_argument("q", ""))

    def post(self):
        if self.request.headers.get("Content-Type", "").startswith("application/json"):
            data = json.loads(self.request.body or b"{}")
            self.write({"got": data})
        else:
            self.write(self.request.body)


class JSONHandler(tornado.web.RequestHandler):
    def get(self):
        self.set_header("Content-Type", "application/json")
        self.write({"hello": "world", "ok": True})


class AsyncHandler(tornado.web.RequestHandler):
    async def get(self):
        # Async handler – exercised via self.fetch()
        await tornado.gen.sleep(0.01)
        self.write("async-done")


class RaiseErrorHandler(tornado.web.RequestHandler):
    def get(self):
        raise HTTPError(400, reason="bad things")


class SetCookieHandler(tornado.web.RequestHandler):
    def get(self):
        self.set_secure_cookie("flavor", "choco")
        self.write("cookie-set")


class GetCookieHandler(tornado.web.RequestHandler):
    def get(self):
        val = self.get_secure_cookie("flavor")
        self.write((val or b"").decode() or "none")


class NamedHandler(tornado.web.RequestHandler):
    def get(self, id):
        self.write(f"named:{id}")


class UploadHandler(tornado.web.RequestHandler):
    async def post(self):
        files = self.request.files.get("file", [])
        name = self.get_body_argument("name", default="")
        sizes = [len(f["body"]) for f in files]
        self.write({"name": name, "sizes": sizes})


class WebSocketEcho(tornado.websocket.WebSocketHandler):
    def check_origin(self, origin):
        return True  # allow all in tests

    def open(self):
        self.write_message("ws-open")

    def on_message(self, message):
        self.write_message(f"echo:{message}")


def make_app(static_path):
    return tornado.web.Application(
        [
            (r"/", MainHandler),
            (r"/echo", EchoHandler),
            (r"/json", JSONHandler),
            (r"/async", AsyncHandler),
            (r"/error", RaiseErrorHandler),
            (r"/set_cookie", SetCookieHandler),
            (r"/get_cookie", GetCookieHandler),
            (r"/upload", UploadHandler),
            URLSpec(r"/named/(?P<id>\d+)", NamedHandler, name="named"),
            (r"/redirect", tornado.web.RedirectHandler, {"url": "/"}),
            (r"/static/(.*)", tornado.web.StaticFileHandler, {"path": static_path}),
            (r"/ws", WebSocketEcho),
        ],
        debug=False,  # avoid autoreload noise
        cookie_secret="__very_secret_for_tests__",  # required for secure cookies
        static_url_prefix="/static/",
        xsrf_cookies=False,
    )


# ---------------------------
# Test Case
# ---------------------------

class TestTornadoComprehensive(AsyncHTTPTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls.static_dir = cls._tmpdir.name
        with open(os.path.join(cls.static_dir, "hello.txt"), "w", encoding="utf-8") as f:
            f.write("static-hello")

    @classmethod
    def tearDownClass(cls):
        try:
            cls._tmpdir.cleanup()
        finally:
            super().tearDownClass()

    def get_app(self):
        return make_app(self.static_dir)

    # ---- Basic HTTP + routing

    def test_root_ok(self):
        r = self.fetch("/")
        self.assertEqual(r.code, 200)
        self.assertEqual(r.body.decode(), "OK")

    def test_404(self):
        r = self.fetch("/nope")
        self.assertEqual(r.code, 404)

    def test_echo_query_and_post_bytes(self):
        r = self.fetch("/echo?q=hello")
        self.assertEqual(r.code, 200)
        self.assertEqual(r.body.decode(), "hello")

        r2 = self.fetch("/echo", method="POST", body=b"abc123")
        self.assertEqual(r2.code, 200)
        self.assertEqual(r2.body, b"abc123")

    def test_json(self):
        r = self.fetch("/json")
        self.assertEqual(r.code, 200)
        ct = r.headers.get("Content-Type", "")
        # Allow charset, e.g. "application/json; charset=UTF-8"
        self.assertTrue(ct.startswith("application/json"))
        payload = json.loads(r.body.decode())
        self.assertEqual(payload, {"hello": "world", "ok": True})

    def test_post_json_body(self):
        # Use self.fetch so we stay on the same IOLoop as the test server
        r = self.fetch(
            "/echo",
            method="POST",
            headers={"Content-Type": "application/json"},
            body=json.dumps({"x": 1}).encode(),
        )
        self.assertEqual(r.code, 200)
        self.assertEqual(json.loads(r.body.decode()), {"got": {"x": 1}})

    def test_error_status(self):
        r = self.fetch("/error")
        self.assertEqual(r.code, 400)
        self.assertIn("bad things", r.body.decode())

    def test_redirect(self):
        r = self.fetch("/redirect", follow_redirects=False)
        self.assertIn(r.code, (301, 302, 303, 307, 308))
        self.assertEqual(r.headers["Location"], "/")

        r2 = self.fetch("/redirect", follow_redirects=True)
        self.assertEqual(r2.code, 200)
        self.assertEqual(r2.body.decode(), "OK")

    # ---- Cookies

    def test_secure_cookies_roundtrip(self):
        r1 = self.fetch("/set_cookie")
        self.assertEqual(r1.code, 200)
        self.assertIn("Set-Cookie", r1.headers)

        cookie_header = r1.headers.get("Set-Cookie")
        r2 = self.fetch("/get_cookie", headers={"Cookie": cookie_header})
        self.assertEqual(r2.code, 200)
        self.assertEqual(r2.body.decode(), "choco")

    # ---- Static files

    def test_static_file_served(self):
        r = self.fetch("/static/hello.txt")
        self.assertEqual(r.code, 200)
        self.assertEqual(r.body.decode(), "static-hello")

    # ---- reverse_url & named routes

    def test_reverse_url(self):
        path = self._app.reverse_url("named", "42")
        self.assertEqual(path, "/named/42")
        r = self.fetch(path)
        self.assertEqual(r.code, 200)
        self.assertEqual(r.body.decode(), "named:42")

    # ---- Async handler (just via fetch)

    def test_async_handler(self):
        r = self.fetch("/async")
        self.assertEqual(r.code, 200)
        self.assertEqual(r.body.decode(), "async-done")

    # ---- File upload (multipart/form-data)

    def test_multipart_upload(self):
        boundary = "---------------------------TESTBOUNDARY"
        body = io.BytesIO()

        def write_part(disposition, content, content_type=None, filename=None):
            body.write(f"--{boundary}\r\n".encode())
            disp = f'form-data; name="{disposition}"'
            if filename:
                disp += f'; filename="{filename}"'
            body.write(f"Content-Disposition: {disp}\r\n".encode())
            if content_type:
                body.write(f"Content-Type: {content_type}\r\n".encode())
            body.write(b"\r\n")
            body.write(content if isinstance(content, (bytes, bytearray)) else content.encode())
            body.write(b"\r\n")

        write_part("name", "sample")
        write_part("file", b"abc", content_type="application/octet-stream", filename="a.bin")
        write_part("file", b"abcdef", content_type="application/octet-stream", filename="b.bin")
        body.write(f"--{boundary}--\r\n".encode())
        body_bytes = body.getvalue()

        r = self.fetch(
            "/upload",
            method="POST",
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            body=body_bytes,
        )
        self.assertEqual(r.code, 200)
        data = json.loads(r.body.decode())
        self.assertEqual(data["name"], "sample")
        self.assertEqual(sorted(data["sizes"]), [3, 6])

    # ---- WebSocket (using self.io_loop.run_sync)

    def test_websocket_echo(self):
        from tornado.websocket import websocket_connect

        async def run():
            url = self.get_url("/ws").replace("http://", "ws://")
            conn = await websocket_connect(url)
            try:
                msg = await conn.read_message()
                assert msg == "ws-open"
                await conn.write_message("hi")
                msg2 = await conn.read_message()
                assert msg2 == "echo:hi"
            finally:
                conn.close()

        self.io_loop.run_sync(run)

    # ---- AsyncHTTPClient explicitly

    def test_async_http_client_direct(self):
        async def run():
            client = tornado.httpclient.AsyncHTTPClient()
            try:
                return await client.fetch(self.get_url("/echo?q=xyz"))
            finally:
                client.close()

        r = self.io_loop.run_sync(run)
        self.assertEqual(r.code, 200)
        self.assertEqual(r.body.decode(), "xyz")

    # ---- IOLoop scheduling & PeriodicCallback + Event

    def test_ioloop_call_later_and_periodic(self):
        loop = self.io_loop
        called = []
        evt = Event()

        def later_cb():
            called.append("later")
            evt.set()

        loop.call_later(0.01, later_cb)
        loop.run_sync(evt.wait)
        self.assertIn("later", called)

        pc_evt = Event()
        count = {"n": 0}

        def pc_cb():
            count["n"] += 1
            if count["n"] >= 2 and not pc_evt.is_set():
                pc_evt.set()

        pc = PeriodicCallback(pc_cb, 5)
        pc.start()
        try:
            loop.run_sync(pc_evt.wait)
        finally:
            pc.stop()
        self.assertGreaterEqual(count["n"], 2)


# ---------------------------
# Main
# ---------------------------

if __name__ == "__main__":
    import sys
    sys.argv = [sys.argv[0]]
    unittest.main()
