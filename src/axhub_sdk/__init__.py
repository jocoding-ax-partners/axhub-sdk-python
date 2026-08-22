from __future__ import annotations
import asyncio, json, re, time, uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping
from urllib import parse, request, error as urlerror

DEFAULT_BASE_URL = "https://api.axhub.ai"
class TokenType(str, Enum): PAT = "pat"; JWT = "jwt"
@dataclass(frozen=True)
class ErrorInfo: category: str; status: int; retryable: bool
class AxHubError(Exception):
    def __init__(self, category: str, code: str, message: str = "", status: int = 0, retryable: bool = False, request_id: str | None = None): super().__init__(message or code); self.category=category; self.code=code; self.status=status; self.retryable=retryable; self.request_id=request_id
ROUTES = [{'method': 'GET', 'path': '/.well-known/jwks.json', 'tag': 'Auth', 'operationId': 'authGetWellKnownJwksJson'}, {'method': 'GET', 'path': '/.well-known/oauth-authorization-server', 'tag': 'Auth', 'operationId': 'authGetWellKnownOauthAuthorizationServer'}, {'method': 'GET', 'path': '/.well-known/openid-configuration', 'tag': 'Auth', 'operationId': 'authGetWellKnownOpenidConfiguration'}, {'method': 'GET', 'path': '/api/v1/access-requests', 'tag': 'Apps', 'operationId': 'appsGetApiV1AccessRequests'}, {'method': 'POST', 'path': '/api/v1/access-requests', 'tag': 'Apps', 'operationId': 'appsPostApiV1AccessRequests'}, {'method': 'PATCH', 'path': '/api/v1/access-requests/{id}/approve', 'tag': 'Apps', 'operationId': 'appsPatchApiV1AccessRequestsByIdApprove'}, {'method': 'PATCH', 'path': '/api/v1/access-requests/{id}/reject', 'tag': 'Apps', 'operationId': 'appsPatchApiV1AccessRequestsByIdReject'}, {'method': 'POST', 'path': '/api/v1/app/mails', 'tag': 'Notifications', 'operationId': 'notificationsPostApiV1AppMails'}, {'method': 'POST', 'path': '/api/v1/app/notifications', 'tag': 'Notifications', 'operationId': 'notificationsPostApiV1AppNotifications'}, {'method': 'DELETE', 'path': '/api/v1/apps/{appID}', 'tag': 'Apps', 'operationId': 'appsDeleteApiV1AppsByAppID'}, {'method': 'GET', 'path': '/api/v1/apps/{appID}', 'tag': 'Apps', 'operationId': 'appsGetApiV1AppsByAppID'}, {'method': 'PATCH', 'path': '/api/v1/apps/{appID}', 'tag': 'Apps', 'operationId': 'appsPatchApiV1AppsByAppID'}, {'method': 'DELETE', 'path': '/api/v1/apps/{appID}/access', 'tag': 'Apps', 'operationId': 'appsDeleteApiV1AppsByAppIDAccess'}, {'method': 'POST', 'path': '/api/v1/apps/{appID}/access', 'tag': 'Apps', 'operationId': 'appsPostApiV1AppsByAppIDAccess'}, {'method': 'GET', 'path': '/api/v1/apps/{appID}/access/me', 'tag': 'Apps', 'operationId': 'appsGetApiV1AppsByAppIDAccessMe'}, {'method': 'POST', 'path': '/api/v1/apps/{appID}/archive', 'tag': 'Apps', 'operationId': 'appsPostApiV1AppsByAppIDArchive'}, {'method': 'GET', 'path': '/api/v1/apps/{appID}/comments', 'tag': 'Apps', 'operationId': 'appsGetApiV1AppsByAppIDComments'}, {'method': 'POST', 'path': '/api/v1/apps/{appID}/comments', 'tag': 'Apps', 'operationId': 'appsPostApiV1AppsByAppIDComments'}, {'method': 'GET', 'path': '/api/v1/apps/{appID}/db/tables', 'tag': 'Schema', 'operationId': 'schemaGetApiV1AppsByAppIDDbTables'}, {'method': 'GET', 'path': '/api/v1/apps/{appID}/db/tables/{table}/rows', 'tag': 'Schema', 'operationId': 'schemaGetApiV1AppsByAppIDDbTablesByTableRows'}, {'method': 'GET', 'path': '/api/v1/apps/{appID}/deployments', 'tag': 'Deploy', 'operationId': 'deployGetApiV1AppsByAppIDDeployments'}, {'method': 'POST', 'path': '/api/v1/apps/{appID}/deployments', 'tag': 'Deploy', 'operationId': 'deployPostApiV1AppsByAppIDDeployments'}, {'method': 'GET', 'path': '/api/v1/apps/{appID}/deployments/{did}', 'tag': 'Deploy', 'operationId': 'deployGetApiV1AppsByAppIDDeploymentsByDid'}, {'method': 'POST', 'path': '/api/v1/apps/{appID}/deployments/{did}/cancel', 'tag': 'Deploy', 'operationId': 'deployPostApiV1AppsByAppIDDeploymentsByDidCancel'}, {'method': 'GET', 'path': '/api/v1/apps/{appID}/deployments/{did}/diagnoses', 'tag': 'Deploy', 'operationId': 'deployGetApiV1AppsByAppIDDeploymentsByDidDiagnoses'}, {'method': 'POST', 'path': '/api/v1/apps/{appID}/deployments/{did}/rollback', 'tag': 'Deploy', 'operationId': 'deployPostApiV1AppsByAppIDDeploymentsByDidRollback'}, {'method': 'GET', 'path': '/api/v1/apps/{appID}/diagnosis', 'tag': 'Deploy', 'operationId': 'deployGetApiV1AppsByAppIDDiagnosis'}, {'method': 'GET', 'path': '/api/v1/apps/{appID}/env-vars', 'tag': 'Apps', 'operationId': 'appsGetApiV1AppsByAppIDEnvVars'}, {'method': 'POST', 'path': '/api/v1/apps/{appID}/env-vars', 'tag': 'Apps', 'operationId': 'appsPostApiV1AppsByAppIDEnvVars'}, {'method': 'PUT', 'path': '/api/v1/apps/{appID}/env-vars/{key}/staging-value', 'tag': 'Apps', 'operationId': 'appsPutApiV1AppsByAppIDEnvVarsByKeyStagingValue'}, {'method': 'DELETE', 'path': '/api/v1/apps/{appID}/git-connection', 'tag': 'Deploy', 'operationId': 'deployDeleteApiV1AppsByAppIDGitConnection'}, {'method': 'GET', 'path': '/api/v1/apps/{appID}/git-connection', 'tag': 'Deploy', 'operationId': 'deployGetApiV1AppsByAppIDGitConnection'}, {'method': 'PATCH', 'path': '/api/v1/apps/{appID}/git-connection', 'tag': 'Deploy', 'operationId': 'deployPatchApiV1AppsByAppIDGitConnection'}, {'method': 'POST', 'path': '/api/v1/apps/{appID}/git-connection', 'tag': 'Deploy', 'operationId': 'deployPostApiV1AppsByAppIDGitConnection'}, {'method': 'POST', 'path': '/api/v1/apps/{appID}/git/github/connect', 'tag': 'Deploy', 'operationId': 'deployPostApiV1AppsByAppIDGitGithubConnect'}, {'method': 'GET', 'path': '/api/v1/apps/{appID}/git/github/install/start', 'tag': 'Deploy', 'operationId': 'deployGetApiV1AppsByAppIDGitGithubInstallStart'}, {'method': 'DELETE', 'path': '/api/v1/apps/{appID}/likes', 'tag': 'Apps', 'operationId': 'appsDeleteApiV1AppsByAppIDLikes'}, {'method': 'POST', 'path': '/api/v1/apps/{appID}/likes', 'tag': 'Apps', 'operationId': 'appsPostApiV1AppsByAppIDLikes'}, {'method': 'GET', 'path': '/api/v1/apps/{appID}/likes/me', 'tag': 'Apps', 'operationId': 'appsGetApiV1AppsByAppIDLikesMe'}, {'method': 'GET', 'path': '/api/v1/apps/{appID}/logs', 'tag': 'Deploy', 'operationId': 'deployGetApiV1AppsByAppIDLogs'}, {'method': 'POST', 'path': '/api/v1/apps/{appID}/oauth-clients', 'tag': 'Auth', 'operationId': 'authPostApiV1AppsByAppIDOauthClients'}, {'method': 'POST', 'path': '/api/v1/apps/{appID}/promotions/{requestID}/retry', 'tag': 'Deploy', 'operationId': 'deployPostApiV1AppsByAppIDPromotionsByRequestIDRetry'}, {'method': 'DELETE', 'path': '/api/v1/apps/{appID}/raw-db', 'tag': 'Apps', 'operationId': 'appsDeleteApiV1AppsByAppIDRawDb'}, {'method': 'POST', 'path': '/api/v1/apps/{appID}/raw-db', 'tag': 'Apps', 'operationId': 'appsPostApiV1AppsByAppIDRawDb'}, {'method': 'GET', 'path': '/api/v1/apps/{appID}/releases', 'tag': 'Deploy', 'operationId': 'deployGetApiV1AppsByAppIDReleases'}, {'method': 'GET', 'path': '/api/v1/apps/{appID}/releases/promote-preflight', 'tag': 'Deploy', 'operationId': 'deployGetApiV1AppsByAppIDReleasesPromotePreflight'}, {'method': 'DELETE', 'path': '/api/v1/apps/{appID}/staging', 'tag': 'Deploy', 'operationId': 'deployDeleteApiV1AppsByAppIDStaging'}, {'method': 'PUT', 'path': '/api/v1/apps/{appID}/staging', 'tag': 'Deploy', 'operationId': 'deployPutApiV1AppsByAppIDStaging'}, {'method': 'GET', 'path': '/api/v1/apps/discover', 'tag': 'Apps', 'operationId': 'appsGetApiV1AppsDiscover'}, {'method': 'GET', 'path': '/api/v1/apps/search', 'tag': 'Apps', 'operationId': 'appsGetApiV1AppsSearch'}, {'method': 'DELETE', 'path': '/api/v1/comments/{commentID}', 'tag': 'Apps', 'operationId': 'appsDeleteApiV1CommentsByCommentID'}, {'method': 'POST', 'path': '/api/v1/git/github/complete', 'tag': 'Deploy', 'operationId': 'deployPostApiV1GitGithubComplete'}, {'method': 'GET', 'path': '/api/v1/github/accounts', 'tag': 'deploy', 'operationId': 'deployGetApiV1GithubAccounts'}, {'method': 'GET', 'path': '/api/v1/github/installations/{installationID}/repositories', 'tag': 'deploy', 'operationId': 'deployGetApiV1GithubInstallationsByInstallationIDRepositories'}, {'method': 'GET', 'path': '/api/v1/me', 'tag': 'Auth', 'operationId': 'authGetApiV1Me'}, {'method': 'GET', 'path': '/api/v1/me/apps/owned', 'tag': 'Apps', 'operationId': 'appsGetApiV1MeAppsOwned'}, {'method': 'GET', 'path': '/api/v1/me/apps/received', 'tag': 'Apps', 'operationId': 'appsGetApiV1MeAppsReceived'}, {'method': 'GET', 'path': '/api/v1/me/apps/workspace', 'tag': 'Apps', 'operationId': 'appsGetApiV1MeAppsWorkspace'}, {'method': 'GET', 'path': '/api/v1/me/notifications', 'tag': 'Notifications', 'operationId': 'notificationsGetApiV1MeNotifications'}, {'method': 'POST', 'path': '/api/v1/me/notifications/{notificationID}/read', 'tag': 'Notifications', 'operationId': 'notificationsPostApiV1MeNotificationsByNotificationIDRead'}, {'method': 'POST', 'path': '/api/v1/me/notifications/read-all', 'tag': 'Notifications', 'operationId': 'notificationsPostApiV1MeNotificationsReadAll'}, {'method': 'GET', 'path': '/api/v1/me/personal-access-tokens', 'tag': 'Schema', 'operationId': 'schemaGetApiV1MePersonalAccessTokens'}, {'method': 'POST', 'path': '/api/v1/me/personal-access-tokens', 'tag': 'Schema', 'operationId': 'schemaPostApiV1MePersonalAccessTokens'}, {'method': 'DELETE', 'path': '/api/v1/me/personal-access-tokens/{patID}', 'tag': 'Schema', 'operationId': 'schemaDeleteApiV1MePersonalAccessTokensByPatID'}, {'method': 'GET', 'path': '/api/v1/oauth-clients/{clientID}', 'tag': 'Auth', 'operationId': 'authGetApiV1OauthClientsByClientID'}, {'method': 'DELETE', 'path': '/api/v1/oauth/clients/{clientID}/grants/me', 'tag': 'Auth', 'operationId': 'authDeleteApiV1OauthClientsByClientIDGrantsMe'}, {'method': 'GET', 'path': '/api/v1/templates', 'tag': 'Apps', 'operationId': 'appsGetApiV1Templates'}, {'method': 'GET', 'path': '/api/v1/tenants', 'tag': 'Tenants', 'operationId': 'tenantsGetApiV1Tenants'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}', 'tag': 'Tenants', 'operationId': 'tenantsGetApiV1TenantsByTenantID'}, {'method': 'POST', 'path': '/api/v1/tenants/{tenantID}/app-bootstraps', 'tag': 'Deploy', 'operationId': 'deployPostApiV1TenantsByTenantIDAppBootstraps'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/app-bootstraps/{bootstrapID}', 'tag': 'Deploy', 'operationId': 'deployGetApiV1TenantsByTenantIDAppBootstrapsByBootstrapID'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/apps', 'tag': 'Apps', 'operationId': 'appsGetApiV1TenantsByTenantIDApps'}, {'method': 'POST', 'path': '/api/v1/tenants/{tenantID}/apps', 'tag': 'Apps', 'operationId': 'appsPostApiV1TenantsByTenantIDApps'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/apps/check-availability', 'tag': 'Apps', 'operationId': 'appsGetApiV1TenantsByTenantIDAppsCheckAvailability'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/connectors', 'tag': 'Gateway', 'operationId': 'gatewayGetApiV1TenantsByTenantIDConnectors'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/connectors/{connectorID}', 'tag': 'Gateway', 'operationId': 'gatewayGetApiV1TenantsByTenantIDConnectorsByConnectorID'}, {'method': 'POST', 'path': '/api/v1/tenants/{tenantID}/connectors/{connectorID}/discover', 'tag': 'Gateway', 'operationId': 'gatewayPostApiV1TenantsByTenantIDConnectorsByConnectorIDDiscover'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/connectors/{connectorID}/resources', 'tag': 'Gateway', 'operationId': 'gatewayGetApiV1TenantsByTenantIDConnectorsByConnectorIDResources'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/deployments', 'tag': 'Deploy', 'operationId': 'deployGetApiV1TenantsByTenantIDDeployments'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/discover/apps', 'tag': 'Apps', 'operationId': 'appsGetApiV1TenantsByTenantIDDiscoverApps'}, {'method': 'POST', 'path': '/api/v1/tenants/{tenantID}/gateway/document-invoke', 'tag': 'Gateway', 'operationId': 'gatewayPostApiV1TenantsByTenantIDGatewayDocumentInvoke'}, {'method': 'POST', 'path': '/api/v1/tenants/{tenantID}/gateway/file-invoke', 'tag': 'Gateway', 'operationId': 'gatewayPostApiV1TenantsByTenantIDGatewayFileInvoke'}, {'method': 'POST', 'path': '/api/v1/tenants/{tenantID}/gateway/invoke', 'tag': 'Gateway', 'operationId': 'gatewayPostApiV1TenantsByTenantIDGatewayInvoke'}, {'method': 'POST', 'path': '/api/v1/tenants/{tenantID}/gateway/query', 'tag': 'Gateway', 'operationId': 'gatewayPostApiV1TenantsByTenantIDGatewayQuery'}, {'method': 'POST', 'path': '/api/v1/tenants/{tenantID}/gateway/sessions', 'tag': 'Gateway', 'operationId': 'gatewayPostApiV1TenantsByTenantIDGatewaySessions'}, {'method': 'DELETE', 'path': '/api/v1/tenants/{tenantID}/gateway/sessions/{sessionID}', 'tag': 'Gateway', 'operationId': 'gatewayDeleteApiV1TenantsByTenantIDGatewaySessionsBySessionID'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/me/connectors', 'tag': 'Gateway', 'operationId': 'gatewayGetApiV1TenantsByTenantIDMeConnectors'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/me/connectors/{connectorID}/resources', 'tag': 'Gateway', 'operationId': 'gatewayGetApiV1TenantsByTenantIDMeConnectorsByConnectorIDResources'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/me/grants', 'tag': 'Authorization', 'operationId': 'authorizationGetApiV1TenantsByTenantIDMeGrants'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/members/directory', 'tag': 'Tenants', 'operationId': 'tenantsGetApiV1TenantsByTenantIDMembersDirectory'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/org-directory', 'tag': 'Tenants', 'operationId': 'tenantsGetApiV1TenantsByTenantIDOrgDirectory'}, {'method': 'GET', 'path': '/api/v1/users/me/apps', 'tag': 'Apps', 'operationId': 'appsGetApiV1UsersMeApps'}, {'method': 'POST', 'path': '/auth/logout', 'tag': 'Auth', 'operationId': 'authPostAuthLogout'}, {'method': 'POST', 'path': '/auth/refresh', 'tag': 'Auth', 'operationId': 'authPostAuthRefresh'}, {'method': 'GET', 'path': '/config/public', 'tag': 'Config', 'operationId': 'configGetConfigPublic'}, {'method': 'GET', 'path': '/oauth/google/callback', 'tag': 'Gateway', 'operationId': 'gatewayGetOauthGoogleCallback'}, {'method': 'GET', 'path': '/oauth/userinfo', 'tag': 'Auth', 'operationId': 'authGetOauthUserinfo'}]
ERROR_CODES = {
    "action_denied": ErrorInfo("permission_denied", 403, False),
    "action_invalid": ErrorInfo("validation", 400, False),
    "ai_key_unavailable": ErrorInfo("unavailable", 503, True),
    "already_accessed": ErrorInfo("conflict", 409, False),
    "already_active": ErrorInfo("conflict", 409, False),
    "already_deleted": ErrorInfo("conflict", 409, False),
    "already_exists": ErrorInfo("conflict", 409, False),
    "already_inactive": ErrorInfo("conflict", 409, False),
    "already_issued": ErrorInfo("conflict", 409, False),
    "already_member": ErrorInfo("conflict", 409, False),
    "already_promoted": ErrorInfo("conflict", 409, False),
    "already_revoked": ErrorInfo("conflict", 409, False),
    "already_settled": ErrorInfo("conflict", 409, False),
    "already_suspended": ErrorInfo("conflict", 409, False),
    "amount_over_limit": ErrorInfo("validation", 400, False),
    "app_archived": ErrorInfo("precondition_failed", 412, False),
    "app_suspended": ErrorInfo("precondition_failed", 412, False),
    "app_unavailable": ErrorInfo("conflict", 409, False),
    "app_unreachable": ErrorInfo("unavailable", 502, True),
    "apps_exist": ErrorInfo("conflict", 409, False),
    "auth_expired": ErrorInfo("unavailable", 503, False),
    "autorecharge_forbidden": ErrorInfo("conflict", 409, False),
    "axrouter_disabled": ErrorInfo("conflict", 409, False),
    "axrouter_link_required": ErrorInfo("precondition_failed", 412, False),
    "backend_unimplemented": ErrorInfo("unavailable", 503, False),
    "backup_in_progress": ErrorInfo("conflict", 409, True),
    "backup_limit_reached": ErrorInfo("conflict", 409, False),
    "backup_not_ready": ErrorInfo("conflict", 409, False),
    "bad_gateway": ErrorInfo("unavailable", 502, True),
    "bad_request": ErrorInfo("validation", 400, False),
    "body_too_large": ErrorInfo("validation", 413, False),
    "build_env_no_override": ErrorInfo("validation", 400, False),
    "business_profile_missing": ErrorInfo("conflict", 409, False),
    "cannot_reactivate": ErrorInfo("conflict", 409, False),
    "card_payment_not_eligible": ErrorInfo("conflict", 409, False),
    "charge_failed": ErrorInfo("payment_required", 402, False),
    "confirm_mismatch": ErrorInfo("validation", 400, False),
    "confirm_required": ErrorInfo("precondition_failed", 412, False),
    "conflict": ErrorInfo("conflict", 409, False),
    "connector_inactive": ErrorInfo("permission_denied", 403, False),
    "connector_probe_failed": ErrorInfo("validation", 400, False),
    "connector_probe_unavailable": ErrorInfo("unavailable", 502, True),
    "connector_quarantined": ErrorInfo("conflict", 409, False),
    "consent_required": ErrorInfo("precondition_failed", 412, False),
    "cross_tenant": ErrorInfo("validation", 400, False),
    "directory_not_ready": ErrorInfo("conflict", 409, True),
    "directory_source_conflict": ErrorInfo("conflict", 409, False),
    "domain_taken": ErrorInfo("conflict", 409, False),
    "duplicate": ErrorInfo("validation", 400, False),
    "egress_blocked": ErrorInfo("validation", 400, False),
    "empty": ErrorInfo("validation", 400, False),
    "exceeds_max": ErrorInfo("conflict", 409, False),
    "expiry_in_past": ErrorInfo("validation", 400, False),
    "exposure_subdomain_conflict": ErrorInfo("conflict", 409, False),
    "feature_disabled": ErrorInfo("permission_denied", 403, False),
    "feature_not_in_plan": ErrorInfo("permission_denied", 403, False),
    "final_visibility_too_wide": ErrorInfo("validation", 400, False),
    "forbidden": ErrorInfo("permission_denied", 403, False),
    "gateway_timeout": ErrorInfo("unavailable", 504, True),
    "git_connection_required": ErrorInfo("precondition_failed", 412, False),
    "github_device_flow_disabled": ErrorInfo("unavailable", 503, False),
    "google_access_denied": ErrorInfo("validation", 400, False),
    "google_domain_taken": ErrorInfo("conflict", 409, False),
    "google_membership_required": ErrorInfo("validation", 400, False),
    "google_not_registered": ErrorInfo("validation", 400, False),
    "grant_already_terminal": ErrorInfo("conflict", 409, False),
    "grant_conflict": ErrorInfo("conflict", 409, False),
    "grant_expired": ErrorInfo("permission_denied", 403, False),
    "grant_revoked": ErrorInfo("permission_denied", 403, False),
    "group_scim_managed": ErrorInfo("conflict", 409, False),
    "insufficient_credit": ErrorInfo("payment_required", 402, False),
    "insufficient_scope": ErrorInfo("permission_denied", 403, False),
    "internal_error": ErrorInfo("internal", 500, False),
    "invalid_auto_recharge": ErrorInfo("validation", 400, False),
    "invalid_credit_policy": ErrorInfo("validation", 400, False),
    "invalid_drive": ErrorInfo("validation", 400, False),
    "invalid_entitlement": ErrorInfo("validation", 400, False),
    "invalid_expiry": ErrorInfo("validation", 400, False),
    "invalid_format": ErrorInfo("validation", 400, False),
    "invalid_manifest": ErrorInfo("validation", 422, False),
    "invalid_oauth_state": ErrorInfo("validation", 400, False),
    "invalid_period": ErrorInfo("validation", 400, False),
    "invalid_source_archive": ErrorInfo("validation", 400, False),
    "invalid_state_transition": ErrorInfo("conflict", 409, False),
    "invalid_target": ErrorInfo("conflict", 409, False),
    "invalid_tls_mode": ErrorInfo("validation", 400, False),
    "invalid_token": ErrorInfo("unauthenticated", 401, False),
    "invalid_value": ErrorInfo("validation", 400, False),
    "invitation_expired": ErrorInfo("not_found", 410, False),
    "invoice_not_available": ErrorInfo("conflict", 409, False),
    "kind_engine_mismatch": ErrorInfo("validation", 400, False),
    "last_admin": ErrorInfo("conflict", 409, False),
    "link_invalid": ErrorInfo("not_found", 404, False),
    "member_inactive": ErrorInfo("permission_denied", 403, False),
    "member_limit_reached": ErrorInfo("conflict", 409, False),
    "no_active_grant": ErrorInfo("not_found", 404, False),
    "no_available_seat": ErrorInfo("conflict", 409, False),
    "no_billing_key": ErrorInfo("payment_required", 402, False),
    "no_payment_method": ErrorInfo("payment_required", 402, False),
    "not_admin": ErrorInfo("permission_denied", 403, False),
    "not_allowed": ErrorInfo("validation", 400, False),
    "not_deleted": ErrorInfo("conflict", 409, False),
    "not_deployed": ErrorInfo("conflict", 409, False),
    "not_found": ErrorInfo("not_found", 404, False),
    "not_manual": ErrorInfo("conflict", 409, False),
    "not_member": ErrorInfo("permission_denied", 403, False),
    "not_metered": ErrorInfo("conflict", 409, False),
    "not_promotable": ErrorInfo("precondition_failed", 412, False),
    "not_suspended": ErrorInfo("conflict", 409, False),
    "oauth_denied": ErrorInfo("validation", 400, False),
    "owner_consent_required": ErrorInfo("permission_denied", 403, False),
    "payload_too_large": ErrorInfo("validation", 413, False),
    "payment_failed": ErrorInfo("payment_required", 402, False),
    "payment_not_paid": ErrorInfo("conflict", 409, False),
    "payment_required": ErrorInfo("payment_required", 402, False),
    "pending_exists": ErrorInfo("conflict", 409, False),
    "pending_review_exists": ErrorInfo("precondition_failed", 412, False),
    "permanently_deleted": ErrorInfo("not_found", 410, False),
    "plan_version_exists": ErrorInfo("conflict", 409, False),
    "policy_in_use": ErrorInfo("conflict", 409, False),
    "precondition_failed": ErrorInfo("precondition_failed", 412, False),
    "preset_in_use": ErrorInfo("conflict", 409, False),
    "preset_mismatch": ErrorInfo("validation", 400, False),
    "preset_not_in_plan": ErrorInfo("payment_required", 402, False),
    "prod_deploy_required": ErrorInfo("precondition_failed", 412, False),
    "promote_in_progress": ErrorInfo("precondition_failed", 412, True),
    "promote_snapshot_missing": ErrorInfo("precondition_failed", 412, False),
    "purge_started": ErrorInfo("conflict", 409, False),
    "query_failed": ErrorInfo("validation", 400, False),
    "quota_exceeded": ErrorInfo("payment_required", 402, False),
    "rate_limited": ErrorInfo("rate_limited", 429, True),
    "raw_db_not_enabled": ErrorInfo("conflict", 409, False),
    "reason_required": ErrorInfo("validation", 400, False),
    "required": ErrorInfo("validation", 400, False),
    "resource_browse_restricted": ErrorInfo("permission_denied", 403, False),
    "resource_quota_exceeded": ErrorInfo("payment_required", 402, False),
    "sales_only": ErrorInfo("permission_denied", 403, False),
    "scan_not_blocked": ErrorInfo("conflict", 409, False),
    "scan_not_errored": ErrorInfo("conflict", 409, False),
    "schema_name_taken": ErrorInfo("conflict", 409, False),
    "scope_out_of_range": ErrorInfo("permission_denied", 403, False),
    "scope_requires_target": ErrorInfo("permission_denied", 403, False),
    "seat_in_use": ErrorInfo("conflict", 409, False),
    "seat_unassigned": ErrorInfo("payment_required", 402, False),
    "seats_not_supported": ErrorInfo("conflict", 409, False),
    "session_ended": ErrorInfo("unauthenticated", 401, True),
    "session_expired": ErrorInfo("unauthenticated", 401, True),
    "site_has_connectors": ErrorInfo("conflict", 409, False),
    "site_offline": ErrorInfo("unavailable", 502, True),
    "slug_brand_protected": ErrorInfo("permission_denied", 403, False),
    "slug_reserved": ErrorInfo("validation", 400, False),
    "slug_taken": ErrorInfo("conflict", 409, False),
    "source_hash_mismatch": ErrorInfo("validation", 400, False),
    "source_input_conflict": ErrorInfo("validation", 400, False),
    "source_too_large": ErrorInfo("validation", 400, False),
    "source_upload_unavailable": ErrorInfo("unavailable", 503, True),
    "spend_cap_reached": ErrorInfo("payment_required", 402, False),
    "staging_already_enabled": ErrorInfo("conflict", 409, False),
    "staging_mismatch": ErrorInfo("precondition_failed", 412, False),
    "staging_namespace_too_long": ErrorInfo("precondition_failed", 412, False),
    "staging_not_enabled": ErrorInfo("precondition_failed", 412, False),
    "staging_required": ErrorInfo("precondition_failed", 412, False),
    "static_release_in_use": ErrorInfo("conflict", 409, False),
    "static_release_not_ready": ErrorInfo("precondition_failed", 412, False),
    "subdomain_conflict": ErrorInfo("conflict", 409, False),
    "subdomain_not_configured": ErrorInfo("precondition_failed", 412, False),
    "subdomain_reserved": ErrorInfo("conflict", 409, False),
    "temporarily_unavailable": ErrorInfo("unavailable", 429, True),
    "tls_config_mismatch": ErrorInfo("validation", 400, False),
    "token_expired": ErrorInfo("unauthenticated", 401, True),
    "token_invalid": ErrorInfo("unauthenticated", 401, True),
    "token_missing": ErrorInfo("unauthenticated", 401, True),
    "too_long": ErrorInfo("validation", 400, False),
    "topup_in_progress": ErrorInfo("conflict", 409, True),
    "unknown_feature_key": ErrorInfo("validation", 400, False),
    "unknown_plan": ErrorInfo("not_found", 404, False),
    "unpaid_balance": ErrorInfo("payment_required", 402, False),
    "unsupported_for_static_app": ErrorInfo("conflict", 409, False),
    "unsupported_target": ErrorInfo("validation", 400, False),
    "verification_failed": ErrorInfo("unauthenticated", 401, False),
    "version_not_approved": ErrorInfo("permission_denied", 403, False),
    "visibility_widen_not_allowed": ErrorInfo("conflict", 409, False),
}
_ROUTE_BY_OP = {r["operationId"]: r for r in ROUTES}

def _request_id() -> str: return (str(int(time.time()*1000)) + uuid.uuid4().hex)[:26]
def _camel(s: str) -> str:
    parts=s.split('_'); return parts[0]+''.join(p[:1].upper()+p[1:] for p in parts[1:])
def _camelize(v: Any) -> Any:
    if isinstance(v, dict): return {_camel(k): _camelize(x) for k,x in v.items()}
    if isinstance(v, list): return [_camelize(x) for x in v]
    return v
class _NoRedirectHandler(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl): return None
_NO_REDIRECT_OPENER = request.build_opener(_NoRedirectHandler)

class AxHubClient:
    def __init__(self, *, base_url: str = DEFAULT_BASE_URL, token: str | None = None, token_type: TokenType | str | None = None, default_tenant_id: str | None = None, default_tenant_slug: str | None = None):
        self.base_url=base_url.rstrip('/'); self.token=token; self.token_type=TokenType(token_type) if token_type else None; self.default_tenant_id=default_tenant_id; self.default_tenant_slug=default_tenant_slug; self.apps=AppsClient(self)
    def redacted_token(self) -> str: return "" if not self.token else "***REDACTED***"
    def _auth_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.token:
            if self.token_type == TokenType.PAT: headers['X-Api-Key']=self.token
            elif self.token_type == TokenType.JWT: headers['Authorization']='Bearer '+self.token
            else: raise AxHubError('validation','required','tokenType must be explicit')
        return headers
    def _send(self, method: str, url: str, *, data: bytes | None = None, content_type: str | None = None, camelize: bool = True) -> Any:
        """Post-routing transport: auth + redirect policy + response/error normalization.

        Shared by the operation-id `request()` path and the raw-path `request_raw()`
        path. `camelize=False` mirrors the node data transport, which returns row
        bodies and list envelopes verbatim (no snake->camel key rewriting).
        """
        headers={'X-Request-ID': _request_id()}
        if content_type is not None: headers['Content-Type']=content_type
        headers.update(self._auth_headers())
        req=request.Request(url, data=data, headers=headers, method=method)
        try:
            with _NO_REDIRECT_OPENER.open(req, timeout=30) as resp:
                raw=resp.read().decode()
                if not raw.strip():
                    parsed = {}
                else:
                    try:
                        parsed = json.loads(raw)
                    except json.JSONDecodeError:
                        parsed = {"raw": raw}
                if not camelize: return parsed
                return _camelize(parsed)
        except urlerror.HTTPError as e:
            if 300 <= e.code < 400:
                location = e.headers.get("Location") if e.headers else None
                e.close()
                return {"status": e.code, "location": location}
            raw=e.read().decode(); e.close()
            try:
                parsed_error = json.loads(raw)
            except json.JSONDecodeError:
                parsed_error = {}
            err = parsed_error.get('error', parsed_error) if isinstance(parsed_error, dict) else {}
            if not isinstance(err, dict):
                err = {}
            code=err.get('code') or f'http_{e.code}'; info=ERROR_CODES.get(code); category=err.get('category') or (info.category if info else 'unknown')
            retryable = bool(err['retryable']) if 'retryable' in err else bool(info.retryable if info else False)
            raise AxHubError(category, code, err.get('message',''), e.code, retryable, err.get('request_id') or err.get('requestId')) from None
    def request(self, operation_id: str, *, path_params: Mapping[str,str] | None = None, query: Mapping[str,str] | None = None, body: Any = None) -> dict[str, Any]:
        route=_ROUTE_BY_OP[operation_id]; path=route['path'];
        for k,v in (path_params or {}).items(): path=path.replace('{'+k+'}', parse.quote(str(v), safe=''))
        if re.search(r'\{[^}]+\}', path): raise AxHubError('validation','required','missing path parameter')
        url=self.base_url+path
        if query: url += '?' + parse.urlencode(query)
        data=None; content_type=None
        if body is not None:
            data=json.dumps(body).encode(); content_type='application/json'
        return self._send(route['method'], url, data=data, content_type=content_type)

# --- Raw DB read facade (typed, read-only) — mirrors Go client.Apps.RawDb() / Node sdk.apps.rawDb.
# Response keys arrive camelCased (request() runs the camelizing transport), so DTOs map camelCase keys.
@dataclass(frozen=True)
class RawDbColumn: name: str; data_type: str; nullable: bool
@dataclass(frozen=True)
class RawDbTable: name: str; managed: bool; columns: list[RawDbColumn]
@dataclass(frozen=True)
class RawDbTableRows: rows: list[dict[str, Any]]; page: int; per_page: int; has_more: bool

def _raw_db_column(d: Mapping[str, Any]) -> RawDbColumn:
    return RawDbColumn(name=str(d.get('name','')), data_type=str(d.get('dataType','')), nullable=bool(d.get('nullable', False)))
def _raw_db_table(d: Mapping[str, Any]) -> RawDbTable:
    cols=d.get('columns') or []
    return RawDbTable(name=str(d.get('name','')), managed=bool(d.get('managed', False)), columns=[_raw_db_column(c) for c in cols if isinstance(c, dict)])

class RawDbClient:
    """Typed, read-only raw-DB facade. Reach it via client.apps.raw_db (mirror of Node sdk.apps.rawDb)."""
    def __init__(self, apps: 'AppsClient'): self._apps=apps
    def tables(self, app_id: str) -> list[RawDbTable]:
        """List the raw DB tables for an app, with typed column metadata.

        A successful call that returns an empty list means the app genuinely has no
        raw DB tables (raw DB not enabled, or zero tables). An authentication or
        permission failure raises AxHubError instead — so an empty list with no
        exception means "empty", not "auth failed".
        """
        if not app_id: raise AxHubError('validation','required','appID is required')
        resp=self._apps._client.request('schemaGetApiV1AppsByAppIDDbTables', path_params={'appID': app_id})
        return [_raw_db_table(t) for t in (resp.get('tables') or []) if isinstance(t, dict)]
    def table_rows(self, app_id: str, table: str, *, per_page: int | None = None, page: int | None = None) -> RawDbTableRows:
        """Read one page of rows from a raw DB table. has_more is a per_page+1 probe; there is no exact total."""
        if not app_id or not table: raise AxHubError('validation','required','appID and table are required')
        query: dict[str, str] = {}
        if per_page is not None: query['per_page']=str(per_page)
        if page is not None: query['page']=str(page)
        resp=self._apps._client.request('schemaGetApiV1AppsByAppIDDbTablesByTableRows', path_params={'appID': app_id, 'table': table}, query=query or None)
        return RawDbTableRows(rows=list(resp.get('rows') or []), page=int(resp.get('page') or 0), per_page=int(resp.get('perPage') or 0), has_more=bool(resp.get('hasMore') or False))

class AsyncRawDbClient:
    """Async parallel of RawDbClient. Reach it via async client.apps.raw_db."""
    def __init__(self, apps: 'AsyncAppsClient'): self._apps=apps
    async def tables(self, app_id: str) -> list[RawDbTable]:
        c=self._apps._client; return await c._run(lambda: c._sync.apps.raw_db.tables(app_id))
    async def table_rows(self, app_id: str, table: str, *, per_page: int | None = None, page: int | None = None) -> RawDbTableRows:
        c=self._apps._client; return await c._run(lambda: c._sync.apps.raw_db.table_rows(app_id, table, per_page=per_page, page=page))

class AppsClient:
    def __init__(self, client: AxHubClient): self._client=client; self.raw_db=RawDbClient(self)
    def create(self, body: Mapping[str, Any]) -> dict[str, Any]:
        if not self._client.default_tenant_id: raise AxHubError('tenant_id_required','tenant_id_required','default tenant id is required')
        return self._client.request('appsPostApiV1TenantsByTenantIDApps', path_params={'tenantID': self._client.default_tenant_id}, body=dict(body))
class AsyncAppsClient:
    def __init__(self, client: 'AsyncAxHubClient'): self._client=client; self.raw_db=AsyncRawDbClient(self)
    async def create(self, body: Mapping[str, Any]) -> dict[str, Any]: return await self._client._run(lambda: self._client._sync.apps.create(body))
class AsyncAxHubClient:
    apps = None
    def __init__(self, **kwargs: Any): self._sync=AxHubClient(**kwargs); self.apps=AsyncAppsClient(self)
    async def _run(self, fn): return await asyncio.to_thread(fn)
    async def request(self, *args, **kwargs): return await self._run(lambda: self._sync.request(*args, **kwargs))
    def redacted_token(self) -> str: return self._sync.redacted_token()


def _context_name(route: dict[str, str]) -> str:
    tag = route.get("tag", "")
    if tag == "Apps": return "apps"
    if tag in {"Auth", "identity"}: return "identity"
    if tag == "Tenants": return "tenants"
    if tag == "Authorization": return "authz"
    if tag == "Audit": return "audit"
    if tag in {"Gateway", "Config"}: return "gateway"
    if tag == "Schema": return "data"
    if tag in {"Deploy", "deploy"}: return "deployments"
    if tag == "Notifications": return "notifications"
    raise ValueError(f"unmapped route tag: {tag}")
CONTEXT_ROUTES = {name: [r for r in ROUTES if _context_name(r) == name] for name in ['apps', 'identity', 'tenants', 'authz', 'audit', 'gateway', 'data', 'deployments', 'notifications']}

from .operations import install_operations as _install_operations
_install_operations(globals())
