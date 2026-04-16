import unittest

_IMPORT_ERROR = None
try:
    import yarl
    from yarl import URL
except Exception as e:  # pragma: no cover
    yarl = None
    URL = None
    _IMPORT_ERROR = e


@unittest.skipIf(yarl is None, f"yarl is not importable: {_IMPORT_ERROR!r}")
class TestYarlURL(unittest.TestCase):
    def test_constructor_and_basic_str(self):
        u = URL("http://user:pass@example.com:8042/over/there?name=ferret#nose")
        self.assertEqual(u.scheme, "http")
        self.assertEqual(u.user, "user")
        self.assertEqual(u.password, "pass")
        self.assertEqual(u.host, "example.com")
        self.assertEqual(u.port, 8042)
        self.assertEqual(u.explicit_port, 8042)
        self.assertEqual(u.path, "/over/there")
        self.assertEqual(u.query_string, "name=ferret")
        self.assertEqual(u.fragment, "nose")
        self.assertTrue(u.absolute)

        # Immutability: operations return new objects
        u2 = u.with_scheme("https")
        self.assertIsNot(u, u2)
        self.assertEqual(str(u), "http://user:pass@example.com:8042/over/there?name=ferret#nose")
        self.assertEqual(str(u2), "https://user:pass@example.com:8042/over/there?name=ferret#nose")

        # Relative URL basics
        r = URL("page.html?x=1#frag")
        self.assertFalse(r.absolute)
        self.assertEqual(r.scheme, "")
        self.assertIsNone(r.host)
        self.assertIsNone(r.port)
        self.assertEqual(r.path, "page.html")
        self.assertEqual(r.query_string, "x=1")
        self.assertEqual(r.fragment, "frag")

    def test_idna_and_percent_encoding_and_human_repr(self):
        u = URL("http://εμπορικόσήμα.eu/шлях/這裡")
        s = str(u)
        self.assertIn("http://", s)
        self.assertIn("xn--", s)  # IDNA host
        self.assertIn("%D1%88%D0%BB%D1%8F%D1%85", s)  # шлях
        self.assertIn("%E9%80%99%E8%A3%A1", s)        # 這裡

        hr = u.human_repr()
        self.assertIn("εμπορικόσήμα.eu", hr)
        self.assertIn("/шлях/這裡", hr)

        # Already-encoded host should not be modified
        u2 = URL("http://xn--jxagkqfkduily1i.eu")
        self.assertEqual(str(u2), "http://xn--jxagkqfkduily1i.eu")

    def test_encoded_flag_does_not_auto_encode(self):
        # encoded=True treats input as already-encoded
        u = URL("http://example.com/%D1%88%D0%BB%D1%8F%D1%85", encoded=True)
        self.assertEqual(u.raw_path, "/%D1%88%D0%BB%D1%8F%D1%85")
        self.assertEqual(u.path, "/шлях")

        # encoded=False (default) encodes non-ascii automatically
        u2 = URL("http://example.com/шлях", encoded=False)
        self.assertEqual(u2.raw_path, "/%D1%88%D0%BB%D1%8F%D1%85")
        self.assertEqual(u2.path, "/шлях")

    def test_user_password_raw_and_decoded(self):
        u = URL("http://довбуш:пароль@example.com/path")
        self.assertEqual(u.user, "довбуш")
        self.assertEqual(u.password, "пароль")
        self.assertIn("%D0%B4%D0%BE%D0%B2%D0%B1%D1%83%D1%88", u.raw_user)
        self.assertIn("%D0%BF%D0%B0%D1%80%D0%BE%D0%BB%D1%8C", u.raw_password)

        # with_user(None) clears both user/password
        u2 = u.with_user(None)
        self.assertIsNone(u2.user)
        self.assertIsNone(u2.password)
        self.assertEqual(str(u2), "http://example.com/path")

        # with_password(None) clears password only
        u3 = u.with_password(None)
        self.assertEqual(u3.user, "довбуш")
        self.assertIsNone(u3.password)

    def test_host_variants_ipv6_and_subcomponents(self):
        u = URL("http://Example.COM./path")
        self.assertEqual(u.host, "example.com.")  # stored lowercased
        if hasattr(u, "host_port_subcomponent"):
            self.assertEqual(u.host_port_subcomponent, "example.com")  # trailing dot stripped

        v6 = URL("http://[::1]/")
        self.assertEqual(v6.host, "::1")
        if hasattr(v6, "host_subcomponent"):
            self.assertEqual(v6.host_subcomponent, "[::1]")
        if hasattr(v6, "host_port_subcomponent"):
            self.assertEqual(v6.host_port_subcomponent, "[::1]")

    def test_authority_and_raw_authority(self):
        u = URL("http://john:pass@хост.домен:8000/path")
        self.assertEqual(u.authority, "john:pass@хост.домен:8000")
        if hasattr(u, "raw_authority"):
            self.assertIn("john:pass@", u.raw_authority)
            self.assertIn("xn--", u.raw_authority)
            self.assertTrue(u.raw_authority.endswith(":8000"))

    def test_path_parts_name_suffixes(self):
        u = URL("http://example.com/path/to.tar.gz")
        self.assertEqual(u.parts, ("/", "path", "to.tar.gz"))
        self.assertEqual(u.name, "to.tar.gz")
        self.assertEqual(u.suffix, ".gz")
        self.assertEqual(u.suffixes, (".tar", ".gz"))

        # Trailing slash -> empty name
        u2 = URL("http://example.com/path/")
        self.assertEqual(u2.name, "")

        # raw_* variants
        u3 = URL("http://example.com/шлях.тут.ось")
        self.assertTrue(u3.raw_name.startswith("%"))
        self.assertEqual(u3.suffixes, (".тут", ".ось"))
        self.assertTrue(all(s.startswith(".%") for s in u3.raw_suffixes))

    def test_path_qs_raw_path_qs_and_query_proxy(self):
        u = URL("http://example.com/path/to?a1=a&a2=b")
        self.assertEqual(u.path_qs, "/path/to?a1=a&a2=b")
        self.assertEqual(u.raw_path_qs, "/path/to?a1=a&a2=b")
        self.assertEqual(u.query["a1"], "a")
        self.assertEqual(u.query["a2"], "b")

        u2 = URL("http://example.com/path?ключ=знач")
        self.assertEqual(u2.query_string, "ключ=знач")
        self.assertIn("%D0%BA%D0%BB%D1%8E%D1%87=%D0%B7%D0%BD%D0%B0%D1%87", u2.raw_query_string)
        self.assertEqual(u2.query["ключ"], "знач")

    def test_path_safe_distinguishes_encoded_slash(self):
        u = URL("http://example.com/a%2Fb/%252F")
        # path decodes %2F into "/" (so it looks like a separator)
        self.assertEqual(u.path, "/a/b/%2F")
        # path_safe keeps %2F and %25 encoded
        if hasattr(u, "path_safe"):
            self.assertEqual(u.path_safe, "/a%2Fb/%252F")

    def test_build_and_validation(self):
        self.assertEqual(str(URL.build()), "")
        self.assertEqual(str(URL.build(scheme="http", host="example.com")), "http://example.com")
        self.assertEqual(
            str(URL.build(scheme="http", host="example.com", query={"a": "b"})),
            "http://example.com/?a=b",
        )
        self.assertEqual(
            str(URL.build(scheme="http", host="example.com", query_string="a=b")),
            "http://example.com/?a=b",
        )

        with self.assertRaises(ValueError):
            URL.build(scheme="http", host="example.com", query={"a": "b"}, query_string="a=b")

    def test_with_modifiers(self):
        base = URL("http://user:pass@example.com:8080/path/to?x=1#frag")

        self.assertEqual(str(base.with_scheme("https")), "https://user:pass@example.com:8080/path/to?x=1#frag")
        self.assertEqual(str(base.with_user("new")), "http://new:pass@example.com:8080/path/to?x=1#frag")
        self.assertEqual(
            str(base.with_password("пароль")),
            "http://user:%D0%BF%D0%B0%D1%80%D0%BE%D0%BB%D1%8C@example.com:8080/path/to?x=1#frag",
        )
        self.assertEqual(str(base.with_host("python.org")), "http://user:pass@python.org:8080/path/to?x=1#frag")
        self.assertEqual(str(base.with_port(9999)), "http://user:pass@example.com:9999/path/to?x=1#frag")
        self.assertEqual(str(base.with_port(None)), "http://user:pass@example.com/path/to?x=1#frag")

        # with_path cleanup; keep_query/keep_fragment added in 1.18
        p = base.with_path("/new/path")
        self.assertEqual(str(p), "http://user:pass@example.com:8080/new/path")
        if "keep_query" in URL.with_path.__code__.co_varnames:
            p2 = base.with_path("/new/path", keep_query=True, keep_fragment=True)
            self.assertEqual(str(p2), "http://user:pass@example.com:8080/new/path?x=1#frag")

        # with_fragment
        self.assertEqual(str(base.with_fragment("anchor")), "http://user:pass@example.com:8080/path/to?x=1#anchor")
        self.assertEqual(str(base.with_fragment(None)), "http://user:pass@example.com:8080/path/to?x=1")

        # with_name / with_suffix cleanup; keep_* added in 1.18
        n = base.with_name("newname")
        self.assertEqual(str(n), "http://user:pass@example.com:8080/path/newname")
        s = base.with_suffix(".doc")
        self.assertEqual(str(s), "http://user:pass@example.com:8080/path/to.doc")
        if "keep_query" in URL.with_name.__code__.co_varnames:
            n2 = base.with_name("newname", keep_query=True, keep_fragment=True)
            self.assertEqual(str(n2), "http://user:pass@example.com:8080/path/newname?x=1#frag")

    def test_query_mutations_with_update_extend_and_percent_operator(self):
        u = URL("http://example.com/path?a=b&b=1")

        # with_query replaces everything
        self.assertEqual(str(u.with_query("c=d")), "http://example.com/path?c=d")
        self.assertEqual(str(u.with_query({"c": "d"})), "http://example.com/path?c=d")
        self.assertEqual(str(u.with_query({"c": [1, 2]})), "http://example.com/path?c=1&c=2")
        self.assertEqual(str(u.with_query(None)), "http://example.com/path")

        # update_query merges/replaces keys
        self.assertEqual(str(u.update_query({"c": "d"})), "http://example.com/path?a=b&b=1&c=d")
        self.assertEqual(str(u.update_query(b="2")), "http://example.com/path?a=b&b=2")
        self.assertEqual(str(u.update_query("c=d&c=f")), "http://example.com/path?a=b&b=1&c=d&c=f")
        self.assertEqual(str(u % {"c": "d"}), "http://example.com/path?a=b&b=1&c=d")

        # extend_query keeps duplicates
        u2 = URL("http://example.com/path?a=b&c=e&c=f")
        ext = u2.extend_query(c="d")
        self.assertEqual(str(ext), "http://example.com/path?a=b&c=e&c=f&c=d")
        self.assertIs(u2.extend_query(None), u2)

        # without_query_params
        if hasattr(u, "without_query_params"):
            w = u.without_query_params("a", "missing")
            self.assertEqual(str(w), "http://example.com/path?b=1")

    def test_parent_origin_relative_and_joinpath_div(self):
        u = URL("http://example.com/path/to?arg=1#frag")

        self.assertEqual(str(u.parent), "http://example.com/path")
        self.assertEqual(str(u.origin()), "http://example.com")
        self.assertEqual(str(u.relative()), "/path/to?arg=1#frag")

        # / operator (truediv)
        u2 = URL("http://example.com/path?arg#frag") / "to/subpath"
        self.assertEqual(str(u2), "http://example.com/path/to/subpath")
        self.assertEqual(u2.parts, ("/", "path", "to", "subpath"))

        # joinpath with multiple args
        u3 = URL("http://example.com/path?arg#frag").joinpath("to", "subpath")
        self.assertEqual(str(u3), "http://example.com/path/to/subpath")

        # joinpath encoded=True (caller provides already-encoded tokens)
        u4 = URL("http://example.com/path").joinpath("%D1%81%D1%8E%D0%B4%D0%B8", encoded=True)
        self.assertEqual(str(u4), "http://example.com/path/%D1%81%D1%8E%D0%B4%D0%B8")
        self.assertEqual(u4.path, "/path/сюди")

    def test_join_rules(self):
        base = URL("http://example.com/path/index.html")
        self.assertEqual(str(base.join(URL("page.html"))), "http://example.com/path/page.html")
        self.assertEqual(str(base.join(URL("//python.org/page.html"))), "http://python.org/page.html")
        self.assertEqual(str(base.join(URL("http://other.example/a"))), "http://other.example/a")

    def test_default_port_and_explicit_port(self):
        u = URL("http://example.com")
        self.assertEqual(u.port, 80)
        self.assertIsNone(u.explicit_port)
        self.assertTrue(u.is_default_port())

        u2 = URL("http://example.com:80")
        self.assertEqual(u2.port, 80)
        self.assertEqual(u2.explicit_port, 80)
        self.assertTrue(u2.is_default_port())

        u3 = URL("http://example.com:8080")
        self.assertEqual(u3.port, 8080)
        self.assertFalse(u3.is_default_port())

        r = URL("/path/to")
        self.assertIsNone(r.port)
        self.assertFalse(r.is_default_port())

    def test_equality_hash_and_repr(self):
        u1 = URL("http://example.com/path?a=1#x")
        u2 = URL("http://example.com/path?a=1#x")
        self.assertEqual(u1, u2)
        self.assertEqual(hash(u1), hash(u2))
        self.assertIn("URL(", repr(u1))
        self.assertNotEqual(URL("http://example.com"), URL("https://example.com"))

    def test_cache_helpers(self):
        info1 = yarl.cache_info()
        self.assertIsInstance(info1, dict)
        for k in ("idna_encode", "idna_decode", "encode_host"):
            self.assertIn(k, info1)

        yarl.cache_clear()
        info2 = yarl.cache_info()
        self.assertIsInstance(info2, dict)

        yarl.cache_configure(idna_encode_size=256, idna_decode_size=256, encode_host_size=512)

    def test_invalid_operations(self):
        # Changing host on relative URL is not allowed
        r = URL("path/to")
        with self.assertRaises(Exception):
            r.with_host("example.com")


if __name__ == "__main__":
    unittest.main(verbosity=2)
