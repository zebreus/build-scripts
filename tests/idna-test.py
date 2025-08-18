import unittest
import idna
import idna.codec
from idna.core import InvalidCodepoint

class TestIDNAModule(unittest.TestCase):

    def test_encode_decode_basic(self):
        domain = "ドメイン.テスト"
        encoded = idna.encode(domain)
        self.assertEqual(encoded, b'xn--eckwd4c7c.xn--zckzah')
        decoded = idna.decode(encoded)
        self.assertEqual(decoded, domain)

    def test_alabel_ulabel(self):
        label = "测试"
        alabel = idna.alabel(label)
        self.assertEqual(alabel, b'xn--0zwm56d')
        ulabel = idna.ulabel(alabel)
        self.assertEqual(ulabel, label)

    def test_codec_encode_decode(self):
        domain = "домен.испытание"
        encoded = domain.encode("idna2008")
        self.assertEqual(encoded, b'xn--d1acufc.xn--80akhbyknj4f')
        decoded = encoded.decode("idna2008")
        self.assertEqual(decoded, domain)

    def test_invalid_codepoint(self):
        with self.assertRaises(InvalidCodepoint):
            idna.encode("Königsgäßchen")

    def test_uts46_processing(self):
        domain = "Königsgäßchen"
        encoded = idna.encode(domain, uts46=True)
        self.assertEqual(encoded, b'xn--knigsgchen-b4a3dun')
        decoded = idna.decode(encoded)
        self.assertEqual(decoded, "königsgäßchen")

    def test_uts46_transitional(self):
        domain = "Königsgäßchen"
        encoded = idna.encode(domain, uts46=True, transitional=True)
        self.assertTrue(encoded.startswith(b'xn--knigsg'))
        # Transitional mode maps ß to 'ss', so result differs
        self.assertIn(b'ss', encoded)

if __name__ == "__main__":
    unittest.main()