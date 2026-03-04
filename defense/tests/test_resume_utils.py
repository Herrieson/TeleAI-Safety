import unittest

from telesafety_defense.resume_utils import merge_existing_responses


class ResumeUtilsTests(unittest.TestCase):
    def test_merge_existing_responses_happy_path(self):
        data = [{"q": "a"}, {"q": "b"}]
        existing = [{"q": "a", "final_response": "ra"}, {"q": "b"}]
        merged, restored = merge_existing_responses(data, existing)
        self.assertEqual(restored, 1)
        self.assertEqual(merged[0]["final_response"], "ra")
        self.assertNotIn("final_response", merged[1])

    def test_merge_existing_responses_length_mismatch(self):
        data = [{"q": "a"}]
        existing = [{"q": "a", "final_response": "ra"}, {"q": "b", "final_response": "rb"}]
        merged, restored = merge_existing_responses(data, existing)
        self.assertEqual(restored, 0)
        self.assertEqual(merged, data)

    def test_merge_existing_responses_by_identity_when_reordered(self):
        data = [
            {"final_query": "q2"},
            {"final_query": "q1"},
        ]
        existing = [
            {"final_query": "q1", "final_response": "r1"},
            {"final_query": "q2", "final_response": "r2"},
        ]
        merged, restored = merge_existing_responses(data, existing)
        self.assertEqual(restored, 2)
        self.assertEqual(merged[0]["final_response"], "r2")
        self.assertEqual(merged[1]["final_response"], "r1")


if __name__ == "__main__":
    unittest.main()
