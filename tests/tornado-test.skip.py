# Skipped because it gets stuck after the test is run
# Confirmed to work on native
import unittest
import tornado.web
import tornado.testing

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.write("Hello, world")


def make_app():
    return tornado.web.Application([
        (r"/", MainHandler),
    ])


class TestTornadoApp(tornado.testing.AsyncHTTPTestCase):
    def get_app(self):
        """Return the Tornado app to be tested."""
        return make_app()

    def test_root_returns_hello_world(self):
        """Test that GET / returns the expected string."""
        response = self.fetch("/")
        self.assertEqual(response.code, 200)
        self.assertEqual(response.body.decode("utf-8"), "Hello, world")

    def test_404_on_invalid_path(self):
        """Test that invalid paths return 404."""
        response = self.fetch("/does-not-exist")
        self.assertEqual(response.code, 404)


if __name__ == "__main__":
    unittest.main()