"""Full member-surface DESTRUCTIVE lifecycle against live prod.

1:1 translation of the Go canonical spec
(axhub-sdk-go/live_destructive_lifecycle_test.go). Creates/updates/deletes REAL
resources: opt-in only, disposable fixtures, LIFO cleanup, slug prefix
"sdke2e-python-" so the orchestrator can orphan-sweep. SUCCESS on member-mutable
ops (MUST); TYPED-FAILURE where a precondition is absent (EXPECTFAIL); success
OR allowed typed 4xx where a precondition may be unavailable (TOLERATE).

Admin-sdk-scoped ops (tenant/members/categories/authz/audit/groups/scim/
connectors/static) are intentionally out of scope (ADR-0043).

Wire bodies, operationIds, and path-param keys are the BACKEND CONTRACT — copied
verbatim from the Go spec. Do not rename keys.
"""
import os
import time
import unittest

from axhub_sdk import AxHubClient, AxHubError, TokenType

BASE_URL = os.environ.get("AXHUB_LIVE_BASE_URL") or "https://api.axhub.ai"
TENANT_ID = os.environ.get("AXHUB_LIVE_TENANT_ID") or "cc1e58f1-8e46-4ac7-96c1-190c4cdd5b70"


def _dl_str(m, *keys):
    """First non-empty string among keys (mirrors Go dlStr; responses are camelCased)."""
    for k in keys:
        v = m.get(k)
        if isinstance(v, str) and v:
            return v
    return ""


@unittest.skipUnless(
    os.environ.get("AXHUB_LIVE_DESTRUCTIVE") == "1",
    "destructive live prod lifecycle is opt-in (set AXHUB_LIVE_DESTRUCTIVE=1)",
)
class LiveDestructiveLifecycleTest(unittest.TestCase):
    def test_full_member_surface_destructive_lifecycle_hits_prod(self):
        token = os.environ.get("AXHUB_TOKEN")
        if not token:
            self.skipTest("AXHUB_TOKEN required")

        client = AxHubClient(
            base_url=BASE_URL,
            token=token,
            token_type=TokenType.PAT,
            default_tenant_id=TENANT_ID,
        )
        # ponytail: no analog to Go's 240s ctx deadline; SDK hardcodes 30s/request.

        suffix = str(time.time_ns())
        app_slug = "sdke2e-python-" + suffix
        table_name = "items" + suffix[-8:]

        # must: member-mutable op that MUST succeed (Go t.Fatalf -> abort; addCleanup still runs).
        def must(label, op_id, pp=None, body=None):
            try:
                res = client.request(op_id, path_params=pp, body=body)
                print(f"  {label}: ok")
                return res
            except AxHubError as exc:
                self.fail(f"MUST {label} ({op_id}): status={exc.status} code={exc.code} msg={exc}")

        # tolerate: accept success OR a typed AxHubError with allowed 4xx; anything
        # else (5xx/transport/other) is recorded non-fatally (Go t.Errorf).
        def tolerate(label, op_id, pp=None, body=None, allowed=()):
            with self.subTest(kind="tolerate", label=label, op=op_id):
                try:
                    client.request(op_id, path_params=pp, body=body)
                    print(f"  {label}: ok (success)")
                except AxHubError as exc:
                    self.assertIn(
                        exc.status, allowed,
                        f"TOLERATE {label} ({op_id}): status {exc.status} not in {allowed} ({exc.code})",
                    )
                    print(f"  {label}: ok (tolerated {exc.status})")

        # expectFail: precondition genuinely unavailable -> MUST be a typed 4xx.
        def expect_fail(label, op_id, pp=None, body=None, allowed=()):
            with self.subTest(kind="expectfail", label=label, op=op_id):
                try:
                    client.request(op_id, path_params=pp, body=body)
                except AxHubError as exc:
                    self.assertIn(
                        exc.status, allowed,
                        f"EXPECTFAIL {label} ({op_id}): status {exc.status} not in {allowed} ({exc.code})",
                    )
                    print(f"  {label}: ok (expected-fail {exc.status})")
                else:
                    self.fail(f"EXPECTFAIL {label} ({op_id}): expected typed failure, got success")

        # --- identity: userId (grant principal + row owner) ---
        me = must("me", "authGetApiV1Me")
        user_id = _dl_str(me, "id", "userId", "userID", "user_id")
        if not user_id:
            u = me.get("user")
            if isinstance(u, dict):
                user_id = _dl_str(u, "id", "userId", "userID", "user_id")
        if not user_id:
            self.fail(f"me: could not resolve user id from {sorted(me.keys())}")

        # --- app create (+ cleanup registered immediately) ---
        app_res = must(
            "create app", "appsPostApiV1TenantsByTenantIDApps",
            {"tenantID": TENANT_ID},
            {"slug": app_slug, "name": "SDK destructive E2E " + suffix, "description": "sdke2e disposable"},
        )
        app_id = _dl_str(app_res, "id", "appId", "appID")
        if not app_id:
            self.fail(f"create app: no id in response {sorted(app_res.keys())}")

        def _cleanup_app(app_id=app_id):
            # best-effort idempotent: ignore 404/409/410 from already-deleted app.
            for op in ("appsDeleteApiV1AppsByAppID", "appsDeleteApiV1AppsByAppIDPermanent"):
                try:
                    client.request(op, path_params={"appID": app_id})
                except AxHubError:
                    pass

        self.addCleanup(_cleanup_app)

        # --- app update ---
        must("update app", "appsPatchApiV1AppsByAppID", {"appID": app_id},
             {"name": "SDK destructive E2E " + suffix + " renamed"})

        # --- env vars ---
        must("set env var", "appsPostApiV1AppsByAppIDEnvVars", {"appID": app_id},
             {"key": "SDK_E2E_SECRET", "value": "sekret-" + suffix})
        must("delete env var", "appsDeleteApiV1AppsByAppIDEnvVarsByKey",
             {"appID": app_id, "key": "SDK_E2E_SECRET"})

        # --- comments ---
        c_res = must("add comment", "appsPostApiV1AppsByAppIDComments", {"appID": app_id},
                     {"body": "sdke2e comment " + suffix})
        comment_id = _dl_str(c_res, "id", "commentId", "commentID")
        if comment_id:
            must("delete comment", "appsDeleteApiV1CommentsByCommentID", {"commentID": comment_id})

        # --- likes (idempotent) ---
        must("like", "appsPostApiV1AppsByAppIDLikes", {"appID": app_id}, {})
        must("unlike", "appsDeleteApiV1AppsByAppIDLikes", {"appID": app_id})

        # --- icon upload url (signed URL; body key uncertain -> tolerate) ---
        tolerate("icon upload url", "appsPostApiV1AppsByAppIDIconUploadUrl", {"appID": app_id},
                 {"content_type": "image/png"}, allowed=(400, 404, 422))

        # --- raw-db (node MISSES; body contract uncertain -> tolerate POST + DELETE; app is disposable) ---
        tolerate("raw-db exec", "appsPostApiV1AppsByAppIDRawDb", {"appID": app_id},
                 {"sql": "select 1"}, allowed=(400, 403, 404, 409, 422, 501))
        tolerate("raw-db reset", "appsDeleteApiV1AppsByAppIDRawDb", {"appID": app_id},
                 allowed=(400, 403, 404, 409, 422, 501))

        # --- oauth client (clientSecret surfaced once) ---
        oc_res = must("create oauth client", "authPostApiV1AppsByAppIDOauthClients", {"appID": app_id}, {
            "name": "SDK E2E OAuth " + suffix,
            "type": "confidential",
            "token_endpoint_auth_method": "client_secret_post",
            "redirect_uris": ["https://example.com/callback"],
            "allowed_scopes": ["read"],
            "allowed_grant_types": ["authorization_code", "refresh_token"],
        })
        with self.subTest("oauth client fields"):
            self.assertTrue(_dl_str(oc_res, "clientId", "client_id", "id"),
                            f"oauth client: missing clientId in {sorted(oc_res.keys())}")
            self.assertTrue(_dl_str(oc_res, "clientSecret", "client_secret"),
                            f"oauth client: missing clientSecret in {sorted(oc_res.keys())}")

        # --- PAT lifecycle (account-scoped: explicit revoke, survives app deletion) ---
        pat_res = must("issue PAT", "schemaPostApiV1MePersonalAccessTokens", None,
                       {"name": "SDK E2E " + suffix, "expires_in_days": 1})
        pat_id = _dl_str(pat_res, "id", "patId", "patID")
        if pat_id:
            def _cleanup_pat(pat_id=pat_id):
                # best-effort idempotent: ignore 404/409/410 from already-revoked PAT.
                try:
                    client.request("schemaDeleteApiV1MePersonalAccessTokensByPatID",
                                   path_params={"patID": pat_id})
                except AxHubError:
                    pass

            self.addCleanup(_cleanup_pat)
            with self.subTest("pat rawToken"):
                self.assertTrue(_dl_str(pat_res, "rawToken", "raw_token"),
                                f"issue PAT: missing rawToken in {sorted(pat_res.keys())}")
            must("revoke PAT", "schemaDeleteApiV1MePersonalAccessTokensByPatID", {"patID": pat_id})

        # --- publication: submit -> reject ; submit -> approve -> back to private (invite_only, never public) ---
        p1 = must("submit publication#1", "appsPostApiV1AppsByAppIDReviewRequests", {"appID": app_id},
                  {"reason": "sdke2e reject " + suffix, "requested_visibility": "invite_only"})
        rr1 = _dl_str(p1, "id", "reviewRequestId", "rrId")
        if rr1:
            must("reject publication#1", "appsPostApiV1ReviewRequestsByRrIDReject", {"rrID": rr1},
                 {"comment": "sdke2e cleanup rejection"})
        p2 = must("submit publication#2", "appsPostApiV1AppsByAppIDReviewRequests", {"appID": app_id},
                  {"reason": "sdke2e approve " + suffix, "requested_visibility": "invite_only"})
        rr2 = _dl_str(p2, "id", "reviewRequestId", "rrId")
        if rr2:
            must("approve publication#2", "appsPostApiV1ReviewRequestsByRrIDApprove", {"rrID": rr2},
                 {"comment": "sdke2e transient approval"})
            # unpublish equivalent: return app to private
            tolerate("unpublish (visibility->private)", "appsPatchApiV1AppsByAppID", {"appID": app_id},
                     {"visibility": "private"}, allowed=(400, 404, 409))

        # --- TYPED-FAILURE: preconditions genuinely unavailable ---
        expect_fail("deployment create (no commit)", "deployPostApiV1AppsByAppIDDeployments", {"appID": app_id},
                    {"commit_sha": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0"}, allowed=(400, 404, 409, 412))
        expect_fail("git connect (no install)", "deployPostApiV1AppsByAppIDGitGithubConnect", {"appID": app_id},
                    {"repo_full_name": "jocoding/sdke2e-nonexistent", "branch": "main", "installation_id": 0},
                    allowed=(400, 403, 404, 409))
        tolerate("access grant (self)", "appsPostApiV1AppsByAppIDAccess", {"appID": app_id}, {},
                 allowed=(400, 403, 409))

        # --- explicit teardown (cleanup stack also covers on failure) ---
        must("delete app", "appsDeleteApiV1AppsByAppID", {"appID": app_id})
        must("permanent delete app", "appsDeleteApiV1AppsByAppIDPermanent", {"appID": app_id})
        print(f"destructive lifecycle OK (app={app_slug})")


if __name__ == "__main__":
    unittest.main()
