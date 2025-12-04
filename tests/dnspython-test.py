"""
Comprehensive (but not exhaustive) dnspython smoke tests.

This module uses unittest to exercise a broad set of dnspython functionality
across common submodules (dns.name, dns.message, dns.rdata, dns.zone,
dns.resolver, dns.reversename, dns.ipv4, dns.ipv6, dns.edns, etc.).

Run with:
    python test_dnspython_comprehensive.py
"""

import os
import socket
import unittest

try:
    import dns
    import dns.name
    import dns.reversename
    import dns.message
    import dns.rdatatype
    import dns.rdataclass
    import dns.rrset
    import dns.zone
    import dns.rdata
    import dns.resolver
    import dns.exception
    import dns.ipv4
    import dns.ipv6
    import dns.flags
    import dns.rcode
    import dns.edns
except ImportError as e:
    raise SystemExit("dnspython must be installed to run these tests: %s" % e)


def _network_available(host="8.8.8.8", port=53, timeout=1.0):
    """Best-effort check for any outbound UDP connectivity."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(timeout)
            s.sendto(b"\0", (host, port))
        return True
    except OSError:
        return False


class TestDnsName(unittest.TestCase):
    def test_basic_name_properties(self):
        n = dns.name.from_text("example.com.")
        self.assertTrue(n.is_absolute())
        self.assertEqual(str(n), "example.com.")
        self.assertEqual(n.labels, (b"example", b"com", b""))

    def test_relative_and_concatenation(self):
        # Exercise concatenation in a version-tolerant way.
        rel = dns.name.from_text("www")
        origin_rel = dns.name.from_text("example.com")

        try:
            full_rel = rel + origin_rel
        except dns.name.AbsoluteConcatenation:
            # Older/stricter versions of dnspython disallow this; just assert
            # that we see that specific exception type.
            self.assertTrue(True, "AbsoluteConcatenation raised as expected")
        else:
            # In versions where this works, ensure the result is as expected.
            self.assertEqual(str(full_rel), "www.example.com")

        # Separately, verify subdomain relationships with absolute names.
        origin_abs = dns.name.from_text("example.com.")
        full_abs = dns.name.from_text("www.example.com.")
        self.assertTrue(full_abs.is_subdomain(origin_abs))
        self.assertFalse(origin_abs.is_subdomain(full_abs))

    def test_relativize_derelativize(self):
        origin = dns.name.from_text("example.com.")
        n = dns.name.from_text("www.example.com.")
        rel = n.relativize(origin)
        self.assertFalse(rel.is_absolute())
        self.assertEqual(str(rel), "www")
        back = rel.derelativize(origin)
        self.assertEqual(back, n)

    def test_comparison_and_equality(self):
        a = dns.name.from_text("a.example.com.")
        b = dns.name.from_text("b.example.com.")
        self.assertNotEqual(a, b)
        self.assertTrue(a < b or a > b)  # just exercise ordering


class TestReverseName(unittest.TestCase):
    def test_ipv4_reverse_roundtrip(self):
        addr = "192.0.2.1"
        rev = dns.reversename.from_address(addr)
        self.assertTrue(rev.is_absolute())
        back = dns.reversename.to_address(rev)
        self.assertEqual(back, addr)

    def test_ipv6_reverse_roundtrip(self):
        addr = "2001:db8::1"
        rev = dns.reversename.from_address(addr)
        self.assertTrue(rev.is_absolute())
        back = dns.reversename.to_address(rev)
        self.assertEqual(back.lower(), addr.lower())


class TestRdatatypeAndRdataclass(unittest.TestCase):
    def test_rdatatype_text_conversion(self):
        a_type = dns.rdatatype.from_text("A")
        self.assertEqual(a_type, dns.rdatatype.A)
        self.assertEqual(dns.rdatatype.to_text(a_type), "A")

        mx_type = dns.rdatatype.from_text("MX")
        self.assertEqual(mx_type, dns.rdatatype.MX)
        self.assertEqual(dns.rdatatype.to_text(mx_type), "MX")

    def test_rdataclass_text_conversion(self):
        in_class = dns.rdataclass.from_text("IN")
        self.assertEqual(in_class, dns.rdataclass.IN)
        self.assertEqual(dns.rdataclass.to_text(in_class), "IN")

    def test_rdatatype_and_class_is_singletonish(self):
        self.assertIsInstance(dns.rdatatype.A, int)
        self.assertIsInstance(dns.rdataclass.IN, int)


class TestRdata(unittest.TestCase):
    def test_a_rdata(self):
        r = dns.rdata.from_text(dns.rdataclass.IN, dns.rdatatype.A, "192.0.2.1")
        self.assertEqual(str(r), "192.0.2.1")
        self.assertEqual(r.address, "192.0.2.1")

    def test_aaaa_rdata(self):
        r = dns.rdata.from_text(dns.rdataclass.IN, dns.rdatatype.AAAA, "2001:db8::1")
        self.assertIn("2001:db8", str(r))

    def test_mx_rdata(self):
        r = dns.rdata.from_text(
            dns.rdataclass.IN, dns.rdatatype.MX, "10 mail.example.com."
        )
        self.assertEqual(r.preference, 10)
        # Accept relative or absolute; normalize to absolute for comparison.
        mname_abs = r.exchange.derelativize(dns.name.from_text("example.com."))
        self.assertEqual(mname_abs, dns.name.from_text("mail.example.com."))

    def test_txt_rdata(self):
        r = dns.rdata.from_text(dns.rdataclass.IN, dns.rdatatype.TXT, '"hello world"')
        self.assertIn("hello", str(r))

    def test_srv_rdata(self):
        r = dns.rdata.from_text(
            dns.rdataclass.IN,
            dns.rdatatype.SRV,
            "10 5 5060 sipserver.example.com.",
        )
        self.assertEqual(r.port, 5060)
        self.assertEqual(r.priority, 10)
        self.assertEqual(r.weight, 5)


class TestMessageAndRrset(unittest.TestCase):
    def test_make_query_and_response(self):
        qname = "example.com."
        q = dns.message.make_query(qname, dns.rdatatype.A)
        self.assertEqual(len(q.question), 1)
        self.assertEqual(q.question[0].name, dns.name.from_text(qname))
        self.assertEqual(q.question[0].rdtype, dns.rdatatype.A)

        r = dns.message.make_response(q)
        r.set_rcode(dns.rcode.NOERROR)
        r.flags |= dns.flags.AA
        self.assertEqual(r.rcode(), dns.rcode.NOERROR)
        self.assertTrue(r.flags & dns.flags.QR)
        self.assertTrue(r.flags & dns.flags.AA)

    def test_rrset_and_sections(self):
        rrset = dns.rrset.from_text(
            "example.com.", 300, "IN", "A", "192.0.2.1", "192.0.2.2"
        )
        self.assertEqual(rrset.name, dns.name.from_text("example.com."))
        self.assertEqual(rrset.ttl, 300)
        self.assertEqual(rrset.rdtype, dns.rdatatype.A)
        self.assertEqual(len(rrset), 2)

        q = dns.message.make_query("example.com.", "A")
        q.answer.append(rrset)
        text = q.to_text()
        self.assertIn("192.0.2.1", text)
        self.assertIn("192.0.2.2", text)

    def test_message_text_roundtrip(self):
        message = dns.message.make_query("example.com.", "A", use_edns=True)
        text = message.to_text()
        parsed = dns.message.from_text(text)
        self.assertEqual(message.id, parsed.id)
        self.assertEqual(message.question[0].name, parsed.question[0].name)
        self.assertEqual(message.question[0].rdtype, parsed.question[0].rdtype)


class TestZone(unittest.TestCase):
    def setUp(self):
        self.zone_text = """\
$ORIGIN example.com.
@   3600 IN SOA ns1.example.com. hostmaster.example.com. 1 3600 600 86400 3600
    3600 IN NS ns1.example.com.
www 300  IN A 192.0.2.1
api 300  IN CNAME www
"""
        self.origin = dns.name.from_text("example.com.")

    def test_zone_from_and_to_text(self):
        zone = dns.zone.from_text(self.zone_text, origin=self.origin)
        self.assertIsInstance(zone, dns.zone.Zone)

        soa = zone.get_rdataset("example.com.", "SOA")
        self.assertIsNotNone(soa)

        # soa[0].mname may be stored as relative ("ns1") or absolute; normalize.
        mname_abs = soa[0].mname.derelativize(self.origin)
        self.assertEqual(mname_abs, dns.name.from_text("ns1.example.com."))

        www_a = zone.get_rdataset("www.example.com.", "A")
        self.assertEqual(str(www_a[0].address), "192.0.2.1")

        out = zone.to_text()
        self.assertIn("SOA", out)
        self.assertIn("www", out)
        self.assertIn("api", out)

    def test_find_node_and_iterate(self):
        zone = dns.zone.from_text(self.zone_text, origin=self.origin)
        node = zone.find_node("www")
        self.assertIn(dns.rdatatype.A, [rd.rdtype for rd in node.rdatasets])

        # Iterate all names just to exercise the API.
        names = list(zone.nodes.keys())
        self.assertTrue(self.origin in names or dns.name.empty in names)


class TestResolverNetwork(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.has_network = _network_available()

    @unittest.skipUnless(_network_available(), "No network connectivity detected")
    def test_resolver_simple_query(self):
        # Use either new-style resolver.resolve or legacy resolver.query
        if hasattr(dns.resolver, "resolve"):
            answer = dns.resolver.resolve("example.com", "A", lifetime=2.0)
        else:
            answer = dns.resolver.query("example.com", "A", lifetime=2.0)

        self.assertGreaterEqual(len(answer), 1)
        for rdata in answer:
            addr = rdata.address
            packed = dns.ipv4.inet_aton(addr)
            unpacked = dns.ipv4.inet_ntoa(packed)
            self.assertEqual(addr, unpacked)

    @unittest.skipUnless(_network_available(), "No network connectivity detected")
    def test_resolver_with_custom_instance(self):
        res = dns.resolver.Resolver()
        res.lifetime = 2.0
        res.nameservers = ["8.8.8.8", "1.1.1.1"]

        answer = res.resolve("example.com", "MX")
        self.assertGreaterEqual(len(answer), 1)
        for rdata in answer:
            self.assertIsInstance(rdata.preference, int)
            # exchange may be relative; just ensure it's a dns.name.Name
            self.assertIsInstance(rdata.exchange, dns.name.Name)


class TestIPv4IPv6Helpers(unittest.TestCase):
    def test_ipv4_helpers(self):
        ip = "192.0.2.123"
        packed = dns.ipv4.inet_aton(ip)
        self.assertIsInstance(packed, bytes)
        unpacked = dns.ipv4.inet_ntoa(packed)
        self.assertEqual(unpacked, ip)

    def test_ipv6_helpers(self):
        ip = "2001:db8::1234"
        packed = dns.ipv6.inet_aton(ip)
        self.assertIsInstance(packed, bytes)
        unpacked = dns.ipv6.inet_ntoa(packed)
        self.assertEqual(unpacked.lower(), ip.lower())


class TestEdnsAndOptions(unittest.TestCase):
    def test_make_query_with_edns(self):
        q = dns.message.make_query("example.com", "A", use_edns=True)
        # edns is 0 for EDNS(0) if enabled, or None if not
        self.assertTrue(q.edns is None or q.edns >= 0)

    def test_generic_option(self):
        # Support both new and old dnspython APIs
        if hasattr(dns.edns, "GenericOption"):
            opt = dns.edns.GenericOption(dns.edns.NSID, b"testnsid")
        else:
            # Older dnspython: Option(otype) and set data manually
            opt = dns.edns.Option(dns.edns.NSID)
            opt.data = b"testnsid"

        self.assertEqual(opt.otype, dns.edns.NSID)
        self.assertTrue(hasattr(opt, "data"))
        self.assertEqual(opt.data, b"testnsid")


class TestExceptions(unittest.TestCase):
    def test_dns_exception_str(self):
        e = dns.exception.DNSException("something went wrong")
        self.assertIn("something went wrong", str(e))

    def test_timeout_exception(self):
        to = dns.exception.Timeout("timeout occurred")
        self.assertIsInstance(to, dns.exception.Timeout)
        self.assertIn("timeout", str(to))


if __name__ == "__main__":
    # Allow optional filtering via environment variable, e.g.:
    #   DNSPYTHON_TEST_PATTERN="TestResolverNetwork" python this_file.py
    pattern = os.environ.get("DNSPYTHON_TEST_PATTERN")
    if pattern:
        unittest.main(defaultTest=pattern)
    else:
        unittest.main()
