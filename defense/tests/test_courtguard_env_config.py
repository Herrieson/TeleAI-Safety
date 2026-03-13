import os
import unittest

from telesafety_defense.methods.courtguard import CourtGuardDefender


class CourtGuardEnvConfigTests(unittest.TestCase):
    def test_azure_backend_reads_endpoint_and_deployment_from_env(self):
        old_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        old_deployment = os.environ.get("AZURE_OPENAI_DEPLOYMENT")
        try:
            os.environ["AZURE_OPENAI_ENDPOINT"] = "https://example.openai.azure.com"
            os.environ["AZURE_OPENAI_DEPLOYMENT"] = "dep-test"
            defender = CourtGuardDefender(
                detector_backend={
                    "type": "azure_openai",
                    "endpoint_env": "AZURE_OPENAI_ENDPOINT",
                    "deployment_env": "AZURE_OPENAI_DEPLOYMENT",
                    "api_key_env": "AZURE_OPENAI_API_KEY",
                },
                detector_type="direct",
            )
            self.assertEqual(
                defender.detector_backend.endpoint, "https://example.openai.azure.com"
            )
            self.assertEqual(defender.detector_backend.deployment, "dep-test")
        finally:
            if old_endpoint is None:
                os.environ.pop("AZURE_OPENAI_ENDPOINT", None)
            else:
                os.environ["AZURE_OPENAI_ENDPOINT"] = old_endpoint
            if old_deployment is None:
                os.environ.pop("AZURE_OPENAI_DEPLOYMENT", None)
            else:
                os.environ["AZURE_OPENAI_DEPLOYMENT"] = old_deployment


if __name__ == "__main__":
    unittest.main()
