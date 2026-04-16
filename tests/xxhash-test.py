import unittest
import sys
import xxhash

def b(x):
    """Helper: ensure bytes (utf-8) for inputs; xxhash accepts bytes and often str."""
    if isinstance(x, (bytes, bytearray, memoryview)):
        return bytes(x)
    return str(x).encode("utf-8")


class TestXXHashModule(unittest.TestCase):

    # ---------- Module metadata ----------
    def test_module_versions_present(self):
        self.assertTrue(hasattr(xxhash, "VERSION"))
        self.assertTrue(hasattr(xxhash, "XXHASH_VERSION"))
        self.assertIsInstance(xxhash.VERSION, str)
        self.assertIsInstance(xxhash.XXHASH_VERSION, str)

    # ---------- Core hashlib-ish API (xxh32 / xxh64) ----------
    def test_xxh32_streaming_and_attrs(self):
        h = xxhash.xxh32()
        # empty digest properties
        self.assertEqual(h.digest_size, 4)
        self.assertEqual(h.block_size, 16)

        # update in chunks vs one-shot
        msg1, msg2 = b("Nobody inspects"), b(" the spammish repetition")
        h.update(msg1)
        h.update(msg2)
        d_stream = h.digest()
        d_stream_hex = h.hexdigest()
        d_stream_int = h.intdigest()

        # Known hexdigest from README example
        self.assertEqual(d_stream_hex, "e2293b2f")
        self.assertEqual(d_stream, bytes.fromhex(d_stream_hex))
        self.assertEqual(d_stream_int, int(d_stream_hex, 16))

        # one-shot (constructor with data)
        self.assertEqual(xxhash.xxh32(msg1 + msg2).digest(), d_stream)

        # endianness: digest is big-endian bytes of intdigest
        self.assertEqual(d_stream_int.to_bytes(4, "big"), d_stream)

        # copy() produces same state; reset() clears state
        h2 = h.copy()
        self.assertEqual(h2.digest(), d_stream)
        h.reset()
        self.assertEqual(h.digest(), xxhash.xxh32().digest())

    def test_xxh64_streaming_seed_and_endianness(self):
        # Default seed=0 vs custom seed
        self.assertEqual(
            xxhash.xxh64(b("xxhash")).hexdigest(),
            "32dd38952c4bc720",
        )
        self.assertEqual(
            xxhash.xxh64(b("xxhash"), seed=20141025).hexdigest(),
            "b559b98d844e0635",
        )

        # Streaming with same seed reproduces value
        h = xxhash.xxh64(seed=20141025)
        h.update(b("xxhash"))
        self.assertEqual(h.hexdigest(), "b559b98d844e0635")

        # intdigest roundtrips with digest()/hexdigest()
        dig = h.digest()
        self.assertEqual(len(dig), 8)
        self.assertEqual(h.intdigest().to_bytes(8, "big"), dig)
        self.assertEqual(format(h.intdigest(), "016x"), h.hexdigest())
        self.assertEqual(int(h.hexdigest(), 16), h.intdigest())

    # ---------- Seed overflow semantics ----------
    def test_seed_overflow_xxh32(self):
        msg = b("I want an unsigned 32-bit seed!")
        # seed == 0 and seed == 2**32 are equivalent
        self.assertEqual(
            xxhash.xxh32(msg, seed=0).hexdigest(),
            "f7a35af8",
        )
        self.assertEqual(
            xxhash.xxh32(msg, seed=2**32).hexdigest(),
            "f7a35af8",
        )
        # seed == 1 and seed == 2**32+1 are equivalent
        self.assertEqual(
            xxhash.xxh32(msg, seed=1).hexdigest(),
            "d8d4b4ba",
        )
        self.assertEqual(
            xxhash.xxh32(msg, seed=(2**32) + 1).hexdigest(),
            "d8d4b4ba",
        )

    def test_seed_overflow_xxh64(self):
        msg = b("I want an unsigned 64-bit seed!")
        # seed == 0 and seed == 2**64 are equivalent
        self.assertEqual(
            xxhash.xxh64(msg, seed=0).hexdigest(),
            "d4cb0a70a2b8c7c1",
        )
        self.assertEqual(
            xxhash.xxh64(msg, seed=2**64).hexdigest(),
            "d4cb0a70a2b8c7c1",
        )
        # seed == 1 and seed == 2**64+1 are equivalent
        self.assertEqual(
            xxhash.xxh64(msg, seed=1).hexdigest(),
            "ce5087f12470d961",
        )
        self.assertEqual(
            xxhash.xxh64(msg, seed=(2**64) + 1).hexdigest(),
            "ce5087f12470d961",
        )

    # ---------- One-shot helpers (xxh32/xxh64) ----------
    def test_oneshot_helpers_xxh64_equivalence(self):
        msg = b("a")
        self.assertEqual(xxhash.xxh64(msg).digest(), xxhash.xxh64_digest(msg))
        self.assertEqual(xxhash.xxh64(msg).intdigest(), xxhash.xxh64_intdigest(msg))
        self.assertEqual(xxhash.xxh64(msg).hexdigest(), xxhash.xxh64_hexdigest(msg))

        # With seed
        msg = b("xxhash")
        self.assertEqual(
            xxhash.xxh64_hexdigest(msg, seed=20141025),
            "b559b98d844e0635",
        )
        self.assertEqual(
            xxhash.xxh64_intdigest(msg, seed=20141025),
            13067679811253438005,
        )
        self.assertEqual(
            xxhash.xxh64_digest(msg, seed=20141025),
            bytes.fromhex("b559b98d844e0635"),
        )

    def test_oneshot_helpers_xxh32_exist_and_work(self):
        msg = b("hello world")
        # Smoke: ensure helpers exist and match streaming
        stream = xxhash.xxh32(msg)
        self.assertEqual(stream.digest(), xxhash.xxh32_digest(msg))
        self.assertEqual(stream.intdigest(), xxhash.xxh32_intdigest(msg))
        self.assertEqual(stream.hexdigest(), xxhash.xxh32_hexdigest(msg))

    # ---------- XXH3 / xxh128 (available since v2.0.0) ----------
    def test_xxh3_64_streaming_and_helpers(self):
        if not hasattr(xxhash, "xxh3_64"):
            self.skipTest("xxh3_64 not available in this xxhash build")
        msg = b("XXH3 is fast!")
        h = xxhash.xxh3_64()
        # streaming chunks
        for chunk in (msg[:5], msg[5:]):
            h.update(chunk)
        stream_d = h.digest()
        stream_hex = h.hexdigest()
        stream_int = h.intdigest()

        # sizes and endian
        self.assertEqual(len(stream_d), 8)
        self.assertEqual(stream_int.to_bytes(8, "big"), stream_d)
        self.assertEqual(int(stream_hex, 16), stream_int)

        # oneshot helpers equivalence (with and without seed)
        self.assertEqual(stream_d, xxhash.xxh3_64_digest(msg))
        self.assertEqual(stream_hex, xxhash.xxh3_64_hexdigest(msg))
        self.assertEqual(stream_int, xxhash.xxh3_64_intdigest(msg))

        seeded = xxhash.xxh3_64_hexdigest(msg, seed=123456789)
        self.assertIsInstance(seeded, str)
        self.assertEqual(
            int(seeded, 16),
            xxhash.xxh3_64_intdigest(msg, seed=123456789),
        )

    def test_xxh3_128_streaming_helpers_and_aliases(self):
        # xxh3_128 plus xxh128 aliases
        has_128 = hasattr(xxhash, "xxh3_128")
        has_alias = hasattr(xxhash, "xxh128")
        if not (has_128 or has_alias):
            self.skipTest("xxh3_128 / xxh128 not available in this xxhash build")

        # choose whichever is present, but verify aliases if both are present
        cls_128 = getattr(xxhash, "xxh3_128", None) or getattr(xxhash, "xxh128")
        h = cls_128()
        msg = b("128-bit hashing time")
        h.update(msg[:7])
        h.update(msg[7:])
        d = h.digest()
        hx = h.hexdigest()
        dint = h.intdigest()

        self.assertEqual(len(d), 16)
        self.assertEqual(dint.to_bytes(16, "big"), d)
        self.assertEqual(int(hx, 16), dint)

        # oneshot helpers
        for name in ("xxh3_128_digest", "xxh3_128_hexdigest", "xxh3_128_intdigest"):
            if hasattr(xxhash, name):
                f = getattr(xxhash, name)
                # compare to streaming
                if name.endswith("_digest"):
                    self.assertEqual(d, f(msg))
                elif name.endswith("_hexdigest"):
                    self.assertEqual(hx, f(msg))
                else:
                    self.assertEqual(dint, f(msg))

        # alias helpers (xxh128_*)
        for name in ("xxh128_digest", "xxh128_hexdigest", "xxh128_intdigest"):
            if hasattr(xxhash, name):
                f = getattr(xxhash, name)
                # consistency with xxh3_128 helpers if both exist
                if hasattr(xxhash, name.replace("xxh128", "xxh3_128")):
                    g = getattr(xxhash, name.replace("xxh128", "xxh3_128"))
                    self.assertEqual(f(msg), g(msg))

    # ---------- General consistency & immutability expectations ----------
    def test_update_vs_constructor_equivalence_various(self):
        for algo_name in ("xxh32", "xxh64"):
            algo = getattr(xxhash, algo_name)
            for seed in (0, 1, 2**16 + 3, 2**32 + 5, 2**64 + 7):
                msg = b("The quick brown fox jumps over the lazy dog")
                # streaming
                h = algo(seed=seed)
                for ch in (msg[:10], msg[10:20], msg[20:]):
                    h.update(ch)
                # constructor one-shot
                h2 = algo(msg, seed=seed)
                self.assertEqual(h.digest(), h2.digest())
                self.assertEqual(h.intdigest(), h2.intdigest())
                self.assertEqual(h.hexdigest(), h2.hexdigest())

    def test_copy_is_independent(self):
        h1 = xxhash.xxh64()
        h1.update(b("prefix-"))
        h2 = h1.copy()
        # diverge states
        h1.update(b("A"))
        h2.update(b("B"))
        self.assertNotEqual(h1.digest(), h2.digest())

    def test_reset_clears_state(self):
        h = xxhash.xxh32()
        h.update(b("data"))
        before = h.digest()
        h.reset()
        after = h.digest()
        self.assertNotEqual(before, after)
        self.assertEqual(after, xxhash.xxh32().digest())

    # ---------- Negative / invalid seed should raise (if enforced) ----------
    def test_negative_seed_behavior(self):
        # If implementation enforces non-negative seeds, ValueError/OverflowError should raise.
        # If not enforced, at least ensure it hashes "something" consistently between streaming and one-shot.
        for algo_name, width in (("xxh32", 4), ("xxh64", 8)):
            algo = getattr(xxhash, algo_name)
            msg = b("neg-seed")
            try:
                algo(msg, seed=-1)
            except (ValueError, OverflowError):
                # acceptable: module rejects negative seeds
                continue
            else:
                # acceptable fallback: treat as streaming vs oneshot consistency
                h = algo(seed=-1)
                h.update(msg)
                self.assertEqual(h.hexdigest(), algo(msg, seed=-1).hexdigest())
                self.assertEqual(len(h.digest()), width)

    # ---------- Smoke test for empty input across algorithms ----------
    def test_empty_input_consistency(self):
        algos = [xxhash.xxh32, xxhash.xxh64]
        if hasattr(xxhash, "xxh3_64"):
            algos.append(xxhash.xxh3_64)
        if hasattr(xxhash, "xxh3_128"):
            algos.append(xxhash.xxh3_128)
        for algo in algos:
            h = algo()
            d, hx, dint = h.digest(), h.hexdigest(), h.intdigest()
            # internal consistency
            self.assertEqual(d, dint.to_bytes(len(d), "big"))
            self.assertEqual(int(hx, 16), dint)
            # oneshot helpers (when available)
            name = algo.__name__
            if name in ("xxh32", "xxh64"):
                self.assertEqual(d, getattr(xxhash, f"{name}_digest")(b""))
                self.assertEqual(hx, getattr(xxhash, f"{name}_hexdigest")(b""))
                self.assertEqual(dint, getattr(xxhash, f"{name}_intdigest")(b""))
            elif name == "xxh3_64":
                self.assertEqual(d, xxhash.xxh3_64_digest(b""))
                self.assertEqual(hx, xxhash.xxh3_64_hexdigest(b""))
                self.assertEqual(dint, xxhash.xxh3_64_intdigest(b""))
            elif name == "xxh3_128":
                self.assertEqual(d, xxhash.xxh3_128_digest(b""))
                self.assertEqual(hx, xxhash.xxh3_128_hexdigest(b""))
                self.assertEqual(dint, xxhash.xxh3_128_intdigest(b""))

if __name__ == "__main__":
    runner = unittest.main()