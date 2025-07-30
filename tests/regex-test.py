import regex
import unittest

class TestRegexModule(unittest.TestCase):

    def test_basic_match(self):
        self.assertTrue(regex.match(r'\d+', '123'))
        self.assertIsNone(regex.match(r'\d+', 'abc'))

    def test_fullmatch(self):
        self.assertIsNotNone(regex.fullmatch(r'\d+', '123'))
        self.assertIsNone(regex.fullmatch(r'\d+', '123a'))

    def test_findall_and_finditer(self):
        self.assertEqual(regex.findall(r'\w+', 'foo bar 123'), ['foo', 'bar', '123'])
        it = regex.finditer(r'\w+', 'foo bar')
        self.assertEqual([m.group(0) for m in it], ['foo', 'bar'])

    def test_named_groups(self):
        m = regex.match(r'(?P<word>\w+)\s(?P<num>\d+)', 'apple 42')
        self.assertEqual(m.group('word'), 'apple')
        self.assertEqual(m.group('num'), '42')

    def test_version_flags(self):
        # Version0: simple set
        self.assertIsNotNone(regex.search(r'(?V0)[a-z]', 'a'))
        # Version1: nested set support
        self.assertIsNotNone(regex.search(r'(?V1)[[a-z]--[aeiou]]', 'b'))

    def test_scoped_flags(self):
        m = regex.match(r'(?i:foo)', 'FOO')
        self.assertIsNotNone(m)

    def test_fuzzy_matching(self):
        m = regex.fullmatch(r'(?:cats|cat){e<=1}', 'cut')
        self.assertTrue(m.fuzzy_counts[2] <= 1)  # max 1 substitution

    def test_posix_matching(self):
        # POSIX mode ensures longest leftmost match
        m = regex.search(r'(?p)one(self)?(selfsufficient)?', 'oneselfsufficient')
        self.assertEqual(m.group(0), 'oneselfsufficient')

    def test_partial_match(self):
        pattern = regex.compile(r'\d{4}')
        self.assertTrue(pattern.fullmatch('123', partial=True).partial)

    def test_unicode_casefolding(self):
        # sharp s casefolded with FULLCASE + IGNORECASE in V1
        m = regex.match(r'(?iV1)strasse', 'straße')
        self.assertIsNotNone(m)

    def test_escape_specials(self):
        self.assertEqual(regex.escape("a+b?c"), r"a\+b\?c")
        self.assertEqual(regex.escape("a b", literal_spaces=True), "a b")

if __name__ == '__main__':
    unittest.main()