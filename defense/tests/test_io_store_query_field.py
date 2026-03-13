import unittest

from telesafety_defense.io_store import extract_queries


class IOStoreQueryFieldTests(unittest.TestCase):
    def test_extract_queries_uses_explicit_query_field(self):
        data = [
            {"prompt": "a", "final_query": "ignored"},
            {"prompt": "b"},
            {"prompt": None},
        ]
        out = extract_queries(data, query_field="prompt")
        self.assertEqual(out, ["a", "b", ""])

    def test_extract_queries_falls_back_to_legacy_fields(self):
        data = [{"final_query": "q1"}, {"final_prompt": "q2"}, {"rewritten": "q3"}, {}]
        out = extract_queries(data)
        self.assertEqual(out, ["q1", "q2", "q3", ""])


if __name__ == "__main__":
    unittest.main()
