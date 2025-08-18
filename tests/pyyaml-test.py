import unittest
import yaml

class TestPyYAML(unittest.TestCase):
    def setUp(self):
        self.yaml_str = """
        name: ChatGPT
        version: 5
        features:
          - nlp
          - reasoning
          - coding
        """
        self.data = {
            "name": "ChatGPT",
            "version": 5,
            "features": ["nlp", "reasoning", "coding"],
        }

    def test_safe_load(self):
        """safe_load parses YAML into correct Python types."""
        result = yaml.safe_load(self.yaml_str)
        self.assertEqual(result, self.data)

    def test_load_with_cloader(self):
        """load using CLoader if available, otherwise Python Loader."""
        try:
            from yaml import CLoader as Loader
        except ImportError:
            from yaml import Loader
        result = yaml.load(self.yaml_str, Loader=Loader)
        self.assertEqual(result["name"], "ChatGPT")
        self.assertIn("reasoning", result["features"])

    def test_dump_and_load_roundtrip(self):
        """dump then safe_load reproduces the original data."""
        dumped = yaml.dump(self.data, Dumper=yaml.SafeDumper)
        loaded = yaml.safe_load(dumped)
        self.assertEqual(loaded, self.data)

    def test_custom_object_dump_and_load(self):
        """Serialize/deserialize a custom object via SafeDumper/SafeLoader."""

        class Example:
            def __init__(self, value):
                self.value = value
            def __eq__(self, other):
                return isinstance(other, Example) and self.value == other.value

        # Representer for dumping with SafeDumper
        def example_representer(dumper, obj):
            return dumper.represent_mapping("!Example", {"value": obj.value})

        # Constructor for loading with SafeLoader
        def example_constructor(loader, node):
            mapping = loader.construct_mapping(node)
            return Example(mapping["value"])

        # Register with the SAFE classes explicitly
        yaml.add_representer(Example, example_representer, Dumper=yaml.SafeDumper)
        yaml.add_constructor("!Example", example_constructor, Loader=yaml.SafeLoader)

        obj = Example(42)
        dumped = yaml.dump(obj, Dumper=yaml.SafeDumper)
        loaded = yaml.safe_load(dumped)
        self.assertEqual(obj, loaded)

    def test_invalid_yaml_raises(self):
        """Invalid YAML should raise a YAMLError."""
        bad = "key: [unclosed list"
        with self.assertRaises(yaml.YAMLError):
            yaml.safe_load(bad)

if __name__ == "__main__":
    unittest.main()