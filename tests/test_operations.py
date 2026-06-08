import unittest
from axhub_sdk import AxHubClient, ROUTES
from axhub_sdk.operations import OPERATION_METHODS

class OperationsCoverageTest(unittest.TestCase):
    def test_generated_operation_facades_cover_all_routes(self):
        client = AxHubClient(base_url="http://127.0.0.1:1")
        contexts = {
            "apps": client.apps, "identity": client.identity, "tenants": client.tenants, "authz": client.authz,
            "audit": client.audit, "gateway": client.gateway, "cost": client.cost, "data": client.data, "deployments": client.deployments,
        }
        self.assertEqual(len(OPERATION_METHODS), len(ROUTES))
        for item in OPERATION_METHODS:
            self.assertTrue(hasattr(contexts[item["context"]], item["snake"]), item)
            self.assertTrue(hasattr(contexts[item["context"]], item["operationId"]), item)

if __name__ == "__main__": unittest.main()
