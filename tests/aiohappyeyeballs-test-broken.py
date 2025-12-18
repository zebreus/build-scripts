# Currently broken, needs further investigation
import asyncio
import socket
import unittest

import aiohappyeyeballs


def _make_addrinfo(host: str, port: int) -> aiohappyeyeballs.AddrInfoType:
    infos = aiohappyeyeballs.addr_to_addr_infos((host, port))
    assert infos and len(infos) == 1
    return infos[0]


async def _start_echo_server(host: str):
    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            # Keep it simple: accept and hold the connection briefly.
            await asyncio.sleep(0.2)
        finally:
            writer.close()
            with contextlib_suppress(Exception):
                await writer.wait_closed()

    # asyncio.start_server picks AF_INET vs AF_INET6 based on host string.
    server = await asyncio.start_server(handle, host=host, port=0)
    sock = server.sockets[0]
    port = sock.getsockname()[1]
    return server, port


class contextlib_suppress:
    """Tiny local replacement for contextlib.suppress to keep this snippet self-contained."""
    def __init__(self, *exc_types):
        self.exc_types = exc_types or (Exception,)

    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc, tb):
        return exc_type is not None and issubclass(exc_type, self.exc_types)


class TestAioHappyEyeballsSync(unittest.TestCase):
    def test_addr_to_addr_infos_ipv4(self):
        infos = aiohappyeyeballs.addr_to_addr_infos(("127.0.0.1", 443))
        self.assertIsInstance(infos, list)
        self.assertEqual(len(infos), 1)
        fam, typ, proto, canon, sockaddr = infos[0]
        self.assertEqual(fam, socket.AF_INET)
        self.assertEqual(typ, socket.SOCK_STREAM)
        self.assertEqual(proto, socket.IPPROTO_TCP)
        self.assertEqual(canon, "")
        self.assertEqual(sockaddr, ("127.0.0.1", 443))

    def test_addr_to_addr_infos_ipv6_variants(self):
        infos2 = aiohappyeyeballs.addr_to_addr_infos(("::1", 443))
        self.assertEqual(infos2[0][0], socket.AF_INET6)
        self.assertEqual(infos2[0][-1], ("::1", 443, 0, 0))

        infos3 = aiohappyeyeballs.addr_to_addr_infos(("::1", 443, 123))
        self.assertEqual(infos3[0][-1], ("::1", 443, 123, 0))

        infos4 = aiohappyeyeballs.addr_to_addr_infos(("::1", 443, 123, 7))
        self.assertEqual(infos4[0][-1], ("::1", 443, 123, 7))

    def test_addr_to_addr_infos_none(self):
        self.assertIsNone(aiohappyeyeballs.addr_to_addr_infos(None))

    def test_pop_addr_infos_interleave_default_1(self):
        v4a = _make_addrinfo("127.0.0.1", 1)
        v4b = _make_addrinfo("127.0.0.2", 2)
        v6a = _make_addrinfo("::1", 3)
        v6b = _make_addrinfo("::2", 4)

        addr_infos = [v4a, v4b, v6a, v6b]
        aiohappyeyeballs.pop_addr_infos_interleave(addr_infos)  # interleave defaults to 1

        # Removes the first occurrence of each family (AF_INET and AF_INET6).
        self.assertNotIn(v4a, addr_infos)
        self.assertNotIn(v6a, addr_infos)
        self.assertIn(v4b, addr_infos)
        self.assertIn(v6b, addr_infos)
        self.assertEqual(len(addr_infos), 2)

    def test_pop_addr_infos_interleave_2(self):
        v4a = _make_addrinfo("127.0.0.1", 1)
        v4b = _make_addrinfo("127.0.0.2", 2)
        v4c = _make_addrinfo("127.0.0.3", 3)
        v6a = _make_addrinfo("::1", 4)
        v6b = _make_addrinfo("::2", 5)

        addr_infos = [v4a, v6a, v4b, v6b, v4c]
        aiohappyeyeballs.pop_addr_infos_interleave(addr_infos, interleave=2)

        # For AF_INET: removes first 2 (v4a, v4b). For AF_INET6: removes first 2 (v6a, v6b).
        self.assertEqual(addr_infos, [v4c])

    def test_remove_addr_infos_exact_match(self):
        v4a = _make_addrinfo("127.0.0.1", 1111)
        v4b = _make_addrinfo("127.0.0.1", 2222)
        addr_infos = [v4a, v4b]
        aiohappyeyeballs.remove_addr_infos(addr_infos, ("127.0.0.1", 1111))
        self.assertEqual(addr_infos, [v4b])

    def test_remove_addr_infos_slow_path_ipv6_normalization(self):
        # Stored address uses compressed IPv6; removal uses expanded form.
        v6 = _make_addrinfo("::1", 3333)
        addr_infos = [v6]
        expanded = ("0:0:0:0:0:0:0:1", 3333, 0, 0)
        aiohappyeyeballs.remove_addr_infos(addr_infos, expanded)
        self.assertEqual(addr_infos, [])

    def test_remove_addr_infos_raises_if_missing(self):
        v4 = _make_addrinfo("127.0.0.1", 4444)
        addr_infos = [v4]
        with self.assertRaises(ValueError):
            aiohappyeyeballs.remove_addr_infos(addr_infos, ("127.0.0.1", 5555))


class TestAioHappyEyeballsAsync(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self._servers = []
        self._server_ports = {}

        # IPv4 server is expected to exist.
        s4, p4 = await _start_echo_server("127.0.0.1")
        self._servers.append(s4)
        self._server_ports["v4"] = p4

        # IPv6 server may not be available on all systems.
        try:
            s6, p6 = await _start_echo_server("::1")
        except OSError:
            self._server_ports["v6"] = None
        else:
            self._servers.append(s6)
            self._server_ports["v6"] = p6

    async def asyncTearDown(self):
        for s in self._servers:
            s.close()
            await s.wait_closed()

    async def test_start_connection_success_single_addrinfo_with_socket_factory(self):
        calls = []

        def socket_factory(ai: aiohappyeyeballs.AddrInfoType) -> socket.socket:
            calls.append(ai)
            family, typ, proto, _, _ = ai
            return socket.socket(family, typ, proto)

        addrinfo = _make_addrinfo("127.0.0.1", self._server_ports["v4"])
        sock = await aiohappyeyeballs.start_connection([addrinfo], socket_factory=socket_factory)
        try:
            self.assertIsInstance(sock, socket.socket)
            self.assertTrue(calls, "socket_factory should have been called at least once")
            self.assertEqual(sock.getpeername(), ("127.0.0.1", self._server_ports["v4"]))
        finally:
            sock.close()

    async def test_start_connection_failure_raises(self):
        # Choose a likely-unused port by binding and closing immediately, then attempting connect.
        tmp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tmp.bind(("127.0.0.1", 0))
        unused_port = tmp.getsockname()[1]
        tmp.close()

        addrinfo = _make_addrinfo("127.0.0.1", unused_port)
        with self.assertRaises(OSError):
            await aiohappyeyeballs.start_connection([addrinfo])

    async def test_start_connection_happy_eyeballs_falls_back_to_working_addr(self):
        # First addrinfo should fail quickly; second should succeed.
        tmp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tmp.bind(("127.0.0.1", 0))
        unused_port = tmp.getsockname()[1]
        tmp.close()

        bad = _make_addrinfo("127.0.0.1", unused_port)
        good = _make_addrinfo("127.0.0.1", self._server_ports["v4"])

        sock = await aiohappyeyeballs.start_connection(
            [bad, good],
            happy_eyeballs_delay=0.05,
        )
        try:
            self.assertEqual(sock.getpeername(), ("127.0.0.1", self._server_ports["v4"]))
        finally:
            sock.close()

    async def test_start_connection_with_interleave_and_mixed_families_if_available(self):
        if not self._server_ports.get("v6"):
            self.skipTest("IPv6 (::1) not available on this system")

        # Provide both families; interleave=1 is what start_connection will default to
        # if happy_eyeballs_delay is set and interleave is None.
        v6 = _make_addrinfo("::1", self._server_ports["v6"])
        v4 = _make_addrinfo("127.0.0.1", self._server_ports["v4"])

        sock = await aiohappyeyeballs.start_connection(
            [v6, v4],
            happy_eyeballs_delay=0.01,
            interleave=1,
        )
        try:
            peer = sock.getpeername()
            # Depending on timing, either could win; accept both.
            if isinstance(peer, tuple) and len(peer) >= 2:
                self.assertIn(peer[1], {self._server_ports["v4"], self._server_ports["v6"]})
            else:
                self.fail(f"Unexpected peername: {peer!r}")
        finally:
            sock.close()

    async def test_start_connection_with_local_addr_infos_binds_source_address(self):
        # Bind explicitly to 127.0.0.1 as the local source address (ephemeral port).
        local = aiohappyeyeballs.addr_to_addr_infos(("127.0.0.1", 0))
        remote = [_make_addrinfo("127.0.0.1", self._server_ports["v4"])]

        sock = await aiohappyeyeballs.start_connection(remote, local_addr_infos=local)
        try:
            local_ip = sock.getsockname()[0]
            self.assertEqual(local_ip, "127.0.0.1")
        finally:
            sock.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
