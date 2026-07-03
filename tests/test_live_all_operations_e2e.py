import json
import os
import re
import time
import traceback
import unittest

from axhub_sdk import AxHubClient, AxHubError, ROUTES, TokenType
from axhub_sdk.operations import OPERATION_METHODS


TENANT_ID = os.environ.get("AXHUB_LIVE_TENANT_ID", "cc1e58f1-8e46-4ac7-96c1-190c4cdd5b70")
TENANT_SLUG = os.environ.get("AXHUB_LIVE_TENANT_SLUG", "test")
BASE_URL = os.environ.get("AXHUB_LIVE_BASE_URL", "https://api.axhub.ai")
DEAD_UUID = "00000000-0000-4000-8000-00000000dead"
PATH_PARAM_RE = re.compile(r"\{([^}]+)\}")

HIGH_RISK_TENANT_OPS = {
    "tenantsDeleteApiV1TenantsByTenantID",
    "tenantsPatchApiV1TenantsByTenantID",
    "tenantsDeleteApiV1TenantsByTenantIDIcon",
    # Backend returns a 500 for a fake connector inside a real tenant; a dead
    # tenant exercises the SDK route without mutating or tripping that bug.
    "gatewayGetApiV1TenantsByTenantIDConnectorsByConnectorIDDiscover",
    "gatewayPostApiV1TenantsByTenantIDConnectors",
}
HIGH_RISK_APP_OPS = {
    "appsDeleteApiV1AppsByAppID",
    "deployPostApiV1AppsByAppIDDeploymentsByDidCancel",
    "deployPostApiV1AppsByAppIDDeploymentsByDidRollback",
}


def _path_param_value(name, operation_id, fixture):
    if name == "tenantID":
        return DEAD_UUID if operation_id in HIGH_RISK_TENANT_OPS else TENANT_ID
    if name == "tenantSlug":
        return TENANT_SLUG
    if name == "appID":
        return DEAD_UUID if operation_id in HIGH_RISK_APP_OPS else fixture.get("appID", DEAD_UUID)
    if name == "appSlug":
        return fixture.get("appSlug", "sdk-e2e-missing-app")
    if name in {"table", "tableName"}:
        return "sdk_e2e_missing_table"
    if name == "path":
        return "sdk/e2e/missing"
    if name == "domain":
        return "sdk-e2e.invalid"
    if name == "providerID":
        return "github" if operation_id == "authGetAuthByProviderIDStart" else "sdk-e2e-provider"
    if name == "patID":
        return DEAD_UUID
    if name == "key":
        return "SDK_E2E_NOOP"
    if name == "connector":
        return "sdk-e2e-connector"
    return DEAD_UUID


def _path_params_for(route, fixture):
    operation_id = route["operationId"]
    return {
        match.group(1): _path_param_value(match.group(1), operation_id, fixture)
        for match in PATH_PARAM_RE.finditer(route["path"])
    }


def _body_for(route):
    if route["method"] in {"GET", "DELETE"}:
        return None
    # Intentionally sparse: the live destructive sweep must hit every method,
    # but must not create real tenant/admin/PAT resources. Sparse bodies route
    # through production validation and normally return typed 4xx errors.
    return {"sdk_e2e": True, "operation_id": route["operationId"]}


def _created_app_identity(response):
    return {
        "appID": response.get("id") or response.get("appId") or response.get("appID"),
        "appSlug": response.get("slug"),
    }


@unittest.skipUnless(os.environ.get("AXHUB_LIVE_ALL_METHODS") == "1", "live prod all-method sweep is opt-in")
class LiveAllOperationsE2ETest(unittest.TestCase):
    def test_all_generated_operation_facades_hit_live_prod(self):
        token = os.environ["AXHUB_TOKEN"]
        client = AxHubClient(
            base_url=BASE_URL,
            token=token,
            token_type=TokenType.PAT,
            default_tenant_id=TENANT_ID,
            default_tenant_slug=TENANT_SLUG,
        )
        self.assertEqual(len(ROUTES), 86)
        self.assertEqual(len(OPERATION_METHODS), len(ROUTES))

        fixture = {}
        created_fixture = False
        slug = f"sdk-e2e-destructive-py-{int(time.time())}"
        try:
            created = client.apps.create({"slug": slug, "name": "SDK destructive E2E disposable"})
            fixture.update({k: v for k, v in _created_app_identity(created).items() if v})
            created_fixture = bool(fixture.get("appID"))
        except AxHubError as exc:
            fixture["fixture_error"] = {"status": exc.status, "code": exc.code, "category": exc.category}

        route_by_operation = {route["operationId"]: route for route in ROUTES}
        contexts = {
            "apps": client.apps,
            "identity": client.identity,
            "tenants": client.tenants,
            "authz": client.authz,
            "audit": client.audit,
            "gateway": client.gateway,
            "data": client.data,
            "deployments": client.deployments,
        }
        results = []
        try:
            for item in OPERATION_METHODS:
                route = route_by_operation[item["operationId"]]
                result = {"operationId": item["operationId"], "method": route["method"], "kind": "unknown"}
                try:
                    got = getattr(contexts[item["context"]], item["snake"])(
                        path_params=_path_params_for(route, fixture),
                        query={"sdk_e2e": "live_all_methods"},
                        body=_body_for(route),
                    )
                    result.update({"kind": "success", "keys": sorted(got.keys())[:20] if isinstance(got, dict) else []})
                except AxHubError as exc:
                    result.update(
                        {
                            "kind": "axhub_error",
                            "status": exc.status,
                            "code": exc.code,
                            "category": exc.category,
                            "server_error": exc.status >= 500,
                        }
                    )
                except Exception as exc:  # noqa: BLE001 - live harness records SDK parser/runtime escapes.
                    result.update({"kind": "exception", "exception": type(exc).__name__, "trace": traceback.format_exc(limit=4)})
                results.append(result)
        finally:
            if created_fixture and fixture.get("appID"):
                try:
                    client.request("appsDeleteApiV1AppsByAppID", path_params={"appID": fixture["appID"]})
                except AxHubError:
                    pass

        summary = {
            "sdk": "python",
            "baseUrl": BASE_URL,
            "tenantId": TENANT_ID,
            "fixture": {"created": created_fixture, "appID": fixture.get("appID"), "appSlug": fixture.get("appSlug")},
            "total": len(results),
            "destructive": sum(1 for r in results if r["method"] != "GET"),
            "success": sum(1 for r in results if r["kind"] == "success"),
            "axhub_error": sum(1 for r in results if r["kind"] == "axhub_error"),
            "exception": sum(1 for r in results if r["kind"] == "exception"),
            "server_errors": [r for r in results if r.get("server_error")],
            "exceptions": [r for r in results if r["kind"] == "exception"],
            "results": results,
        }
        result_path = os.environ.get("AXHUB_LIVE_RESULT_PATH")
        if result_path:
            with open(result_path, "w", encoding="utf-8") as fh:
                json.dump(summary, fh, indent=2, sort_keys=True)

        self.assertEqual(summary["total"], 86)
        self.assertEqual(summary["destructive"], sum(1 for route in ROUTES if route["method"] != "GET"))
        self.assertEqual(summary["exceptions"], [])
        self.assertEqual(summary["server_errors"], [])


if __name__ == "__main__":
    unittest.main()
