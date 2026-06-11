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
ROUTES = [{'method': 'GET', 'path': '/.well-known/jwks.json', 'tag': 'Auth', 'operationId': 'authGetWellKnownJwksJson'}, {'method': 'GET', 'path': '/.well-known/oauth-authorization-server', 'tag': 'Auth', 'operationId': 'authGetWellKnownOauthAuthorizationServer'}, {'method': 'GET', 'path': '/.well-known/openid-configuration', 'tag': 'Auth', 'operationId': 'authGetWellKnownOpenidConfiguration'}, {'method': 'GET', 'path': '/api/v1/admin/templates', 'tag': 'Apps', 'operationId': 'appsGetApiV1AdminTemplates'}, {'method': 'POST', 'path': '/api/v1/admin/templates', 'tag': 'Apps', 'operationId': 'appsPostApiV1AdminTemplates'}, {'method': 'GET', 'path': '/api/v1/admin/templates/{templateID}', 'tag': 'Apps', 'operationId': 'appsGetApiV1AdminTemplatesByTemplateID'}, {'method': 'PATCH', 'path': '/api/v1/admin/templates/{templateID}', 'tag': 'Apps', 'operationId': 'appsPatchApiV1AdminTemplatesByTemplateID'}, {'method': 'POST', 'path': '/api/v1/admin/users/{uid}/revoke-all', 'tag': 'Auth', 'operationId': 'authPostApiV1AdminUsersByUidRevokeAll'}, {'method': 'DELETE', 'path': '/api/v1/apps/{appID}', 'tag': 'Apps', 'operationId': 'appsDeleteApiV1AppsByAppID'}, {'method': 'GET', 'path': '/api/v1/apps/{appID}', 'tag': 'Apps', 'operationId': 'appsGetApiV1AppsByAppID'}, {'method': 'PATCH', 'path': '/api/v1/apps/{appID}', 'tag': 'Apps', 'operationId': 'appsPatchApiV1AppsByAppID'}, {'method': 'DELETE', 'path': '/api/v1/apps/{appID}/access', 'tag': 'Apps', 'operationId': 'appsDeleteApiV1AppsByAppIDAccess'}, {'method': 'POST', 'path': '/api/v1/apps/{appID}/access', 'tag': 'Apps', 'operationId': 'appsPostApiV1AppsByAppIDAccess'}, {'method': 'GET', 'path': '/api/v1/apps/{appID}/access/me', 'tag': 'Apps', 'operationId': 'appsGetApiV1AppsByAppIDAccessMe'}, {'method': 'GET', 'path': '/api/v1/apps/{appID}/comments', 'tag': 'Apps', 'operationId': 'appsGetApiV1AppsByAppIDComments'}, {'method': 'POST', 'path': '/api/v1/apps/{appID}/comments', 'tag': 'Apps', 'operationId': 'appsPostApiV1AppsByAppIDComments'}, {'method': 'GET', 'path': '/api/v1/apps/{appID}/deployments', 'tag': 'Deploy', 'operationId': 'deployGetApiV1AppsByAppIDDeployments'}, {'method': 'POST', 'path': '/api/v1/apps/{appID}/deployments', 'tag': 'Deploy', 'operationId': 'deployPostApiV1AppsByAppIDDeployments'}, {'method': 'GET', 'path': '/api/v1/apps/{appID}/deployments/{did}', 'tag': 'Deploy', 'operationId': 'deployGetApiV1AppsByAppIDDeploymentsByDid'}, {'method': 'POST', 'path': '/api/v1/apps/{appID}/deployments/{did}/cancel', 'tag': 'Deploy', 'operationId': 'deployPostApiV1AppsByAppIDDeploymentsByDidCancel'}, {'method': 'POST', 'path': '/api/v1/apps/{appID}/deployments/{did}/rollback', 'tag': 'Deploy', 'operationId': 'deployPostApiV1AppsByAppIDDeploymentsByDidRollback'}, {'method': 'GET', 'path': '/api/v1/apps/{appID}/env-vars', 'tag': 'Apps', 'operationId': 'appsGetApiV1AppsByAppIDEnvVars'}, {'method': 'POST', 'path': '/api/v1/apps/{appID}/env-vars', 'tag': 'Apps', 'operationId': 'appsPostApiV1AppsByAppIDEnvVars'}, {'method': 'DELETE', 'path': '/api/v1/apps/{appID}/env-vars/{key}', 'tag': 'Apps', 'operationId': 'appsDeleteApiV1AppsByAppIDEnvVarsByKey'}, {'method': 'DELETE', 'path': '/api/v1/apps/{appID}/git-connection', 'tag': 'Deploy', 'operationId': 'deployDeleteApiV1AppsByAppIDGitConnection'}, {'method': 'GET', 'path': '/api/v1/apps/{appID}/git-connection', 'tag': 'Deploy', 'operationId': 'deployGetApiV1AppsByAppIDGitConnection'}, {'method': 'PATCH', 'path': '/api/v1/apps/{appID}/git-connection', 'tag': 'Deploy', 'operationId': 'deployPatchApiV1AppsByAppIDGitConnection'}, {'method': 'POST', 'path': '/api/v1/apps/{appID}/git-connection', 'tag': 'Deploy', 'operationId': 'deployPostApiV1AppsByAppIDGitConnection'}, {'method': 'GET', 'path': '/api/v1/apps/{appID}/git/github/install/start', 'tag': 'Deploy', 'operationId': 'deployGetApiV1AppsByAppIDGitGithubInstallStart'}, {'method': 'POST', 'path': '/api/v1/apps/{appID}/icon-dark/upload-url', 'tag': 'Apps', 'operationId': 'appsPostApiV1AppsByAppIDIconDarkUploadUrl'}, {'method': 'POST', 'path': '/api/v1/apps/{appID}/icon/upload-url', 'tag': 'Apps', 'operationId': 'appsPostApiV1AppsByAppIDIconUploadUrl'}, {'method': 'POST', 'path': '/api/v1/apps/{appID}/invitations', 'tag': 'Apps', 'operationId': 'appsPostApiV1AppsByAppIDInvitations'}, {'method': 'DELETE', 'path': '/api/v1/apps/{appID}/invitations/{userID}', 'tag': 'Apps', 'operationId': 'appsDeleteApiV1AppsByAppIDInvitationsByUserID'}, {'method': 'DELETE', 'path': '/api/v1/apps/{appID}/likes', 'tag': 'Apps', 'operationId': 'appsDeleteApiV1AppsByAppIDLikes'}, {'method': 'POST', 'path': '/api/v1/apps/{appID}/likes', 'tag': 'Apps', 'operationId': 'appsPostApiV1AppsByAppIDLikes'}, {'method': 'GET', 'path': '/api/v1/apps/{appID}/likes/me', 'tag': 'Apps', 'operationId': 'appsGetApiV1AppsByAppIDLikesMe'}, {'method': 'GET', 'path': '/api/v1/apps/{appID}/logs', 'tag': 'Deploy', 'operationId': 'deployGetApiV1AppsByAppIDLogs'}, {'method': 'GET', 'path': '/api/v1/apps/{appID}/members', 'tag': 'Apps', 'operationId': 'appsGetApiV1AppsByAppIDMembers'}, {'method': 'POST', 'path': '/api/v1/apps/{appID}/oauth-clients', 'tag': 'Auth', 'operationId': 'authPostApiV1AppsByAppIDOauthClients'}, {'method': 'DELETE', 'path': '/api/v1/apps/{appID}/permanent', 'tag': 'Apps', 'operationId': 'appsDeleteApiV1AppsByAppIDPermanent'}, {'method': 'POST', 'path': '/api/v1/apps/{appID}/resume', 'tag': 'Apps', 'operationId': 'appsPostApiV1AppsByAppIDResume'}, {'method': 'GET', 'path': '/api/v1/apps/{appID}/review-requests', 'tag': 'Apps', 'operationId': 'appsGetApiV1AppsByAppIDReviewRequests'}, {'method': 'POST', 'path': '/api/v1/apps/{appID}/review-requests', 'tag': 'Apps', 'operationId': 'appsPostApiV1AppsByAppIDReviewRequests'}, {'method': 'POST', 'path': '/api/v1/apps/{appID}/suspend', 'tag': 'Apps', 'operationId': 'appsPostApiV1AppsByAppIDSuspend'}, {'method': 'GET', 'path': '/api/v1/apps/{appID}/tables', 'tag': 'Schema', 'operationId': 'schemaGetApiV1AppsByAppIDTables'}, {'method': 'POST', 'path': '/api/v1/apps/{appID}/tables', 'tag': 'Schema', 'operationId': 'schemaPostApiV1AppsByAppIDTables'}, {'method': 'DELETE', 'path': '/api/v1/apps/{appID}/tables/{tableName}', 'tag': 'Schema', 'operationId': 'schemaDeleteApiV1AppsByAppIDTablesByTableName'}, {'method': 'GET', 'path': '/api/v1/apps/{appID}/tables/{tableName}', 'tag': 'Schema', 'operationId': 'schemaGetApiV1AppsByAppIDTablesByTableName'}, {'method': 'POST', 'path': '/api/v1/apps/{appID}/tables/{tableName}/columns', 'tag': 'Schema', 'operationId': 'schemaPostApiV1AppsByAppIDTablesByTableNameColumns'}, {'method': 'DELETE', 'path': '/api/v1/apps/{appID}/tables/{tableName}/columns/{columnName}', 'tag': 'Schema', 'operationId': 'schemaDeleteApiV1AppsByAppIDTablesByTableNameColumnsByColumnName'}, {'method': 'GET', 'path': '/api/v1/apps/{appID}/tables/{tableName}/grants', 'tag': 'Schema', 'operationId': 'schemaGetApiV1AppsByAppIDTablesByTableNameGrants'}, {'method': 'POST', 'path': '/api/v1/apps/{appID}/tables/{tableName}/grants', 'tag': 'Schema', 'operationId': 'schemaPostApiV1AppsByAppIDTablesByTableNameGrants'}, {'method': 'DELETE', 'path': '/api/v1/apps/{appID}/tables/{tableName}/grants/{grantID}', 'tag': 'Schema', 'operationId': 'schemaDeleteApiV1AppsByAppIDTablesByTableNameGrantsByGrantID'}, {'method': 'GET', 'path': '/api/v1/apps/{appID}/tables/{tableName}/rows', 'tag': 'Schema', 'operationId': 'schemaGetApiV1AppsByAppIDTablesByTableNameRows'}, {'method': 'GET', 'path': '/api/v1/apps/{appID}/tables/check-availability', 'tag': 'Schema', 'operationId': 'schemaGetApiV1AppsByAppIDTablesCheckAvailability'}, {'method': 'GET', 'path': '/api/v1/apps/{appID}/tables/column-types', 'tag': 'Schema', 'operationId': 'schemaGetApiV1AppsByAppIDTablesColumnTypes'}, {'method': 'GET', 'path': '/api/v1/apps/discover', 'tag': 'Apps', 'operationId': 'appsGetApiV1AppsDiscover'}, {'method': 'GET', 'path': '/api/v1/apps/search', 'tag': 'Apps', 'operationId': 'appsGetApiV1AppsSearch'}, {'method': 'DELETE', 'path': '/api/v1/comments/{commentID}', 'tag': 'Apps', 'operationId': 'appsDeleteApiV1CommentsByCommentID'}, {'method': 'GET', 'path': '/api/v1/github/accounts', 'tag': 'deploy', 'operationId': 'deployGetApiV1GithubAccounts'}, {'method': 'GET', 'path': '/api/v1/github/installations/{installationID}/repositories', 'tag': 'deploy', 'operationId': 'deployGetApiV1GithubInstallationsByInstallationIDRepositories'}, {'method': 'GET', 'path': '/api/v1/invite-links/{token}', 'tag': 'Tenants', 'operationId': 'tenantsGetApiV1InviteLinksByToken'}, {'method': 'POST', 'path': '/api/v1/invite-links/{token}/accept', 'tag': 'Tenants', 'operationId': 'tenantsPostApiV1InviteLinksByTokenAccept'}, {'method': 'GET', 'path': '/api/v1/me', 'tag': 'Auth', 'operationId': 'authGetApiV1Me'}, {'method': 'GET', 'path': '/api/v1/me/apps/owned', 'tag': 'Apps', 'operationId': 'appsGetApiV1MeAppsOwned'}, {'method': 'GET', 'path': '/api/v1/me/apps/received', 'tag': 'Apps', 'operationId': 'appsGetApiV1MeAppsReceived'}, {'method': 'GET', 'path': '/api/v1/me/apps/workspace', 'tag': 'Apps', 'operationId': 'appsGetApiV1MeAppsWorkspace'}, {'method': 'POST', 'path': '/api/v1/me/invitations/{invitationID}/accept', 'tag': 'Auth', 'operationId': 'authPostApiV1MeInvitationsByInvitationIDAccept'}, {'method': 'GET', 'path': '/api/v1/me/personal-access-tokens', 'tag': 'Schema', 'operationId': 'schemaGetApiV1MePersonalAccessTokens'}, {'method': 'POST', 'path': '/api/v1/me/personal-access-tokens', 'tag': 'Schema', 'operationId': 'schemaPostApiV1MePersonalAccessTokens'}, {'method': 'DELETE', 'path': '/api/v1/me/personal-access-tokens/{patID}', 'tag': 'Schema', 'operationId': 'schemaDeleteApiV1MePersonalAccessTokensByPatID'}, {'method': 'GET', 'path': '/api/v1/oauth-clients/{clientID}', 'tag': 'Auth', 'operationId': 'authGetApiV1OauthClientsByClientID'}, {'method': 'DELETE', 'path': '/api/v1/oauth/clients/{clientID}/grants/me', 'tag': 'Auth', 'operationId': 'authDeleteApiV1OauthClientsByClientIDGrantsMe'}, {'method': 'GET', 'path': '/api/v1/resource-presets', 'tag': 'Apps', 'operationId': 'appsGetApiV1ResourcePresets'}, {'method': 'GET', 'path': '/api/v1/review-requests/{rrID}', 'tag': 'Apps', 'operationId': 'appsGetApiV1ReviewRequestsByRrID'}, {'method': 'POST', 'path': '/api/v1/review-requests/{rrID}/approve', 'tag': 'Apps', 'operationId': 'appsPostApiV1ReviewRequestsByRrIDApprove'}, {'method': 'POST', 'path': '/api/v1/review-requests/{rrID}/reject', 'tag': 'Apps', 'operationId': 'appsPostApiV1ReviewRequestsByRrIDReject'}, {'method': 'GET', 'path': '/api/v1/review-requests/history', 'tag': 'Apps', 'operationId': 'appsGetApiV1ReviewRequestsHistory'}, {'method': 'GET', 'path': '/api/v1/review-requests/pending', 'tag': 'Apps', 'operationId': 'appsGetApiV1ReviewRequestsPending'}, {'method': 'GET', 'path': '/api/v1/templates', 'tag': 'Apps', 'operationId': 'appsGetApiV1Templates'}, {'method': 'GET', 'path': '/api/v1/tenants', 'tag': 'Tenants', 'operationId': 'tenantsGetApiV1Tenants'}, {'method': 'POST', 'path': '/api/v1/tenants', 'tag': 'Tenants', 'operationId': 'tenantsPostApiV1Tenants'}, {'method': 'DELETE', 'path': '/api/v1/tenants/{tenantID}', 'tag': 'Tenants', 'operationId': 'tenantsDeleteApiV1TenantsByTenantID'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}', 'tag': 'Tenants', 'operationId': 'tenantsGetApiV1TenantsByTenantID'}, {'method': 'PATCH', 'path': '/api/v1/tenants/{tenantID}', 'tag': 'Tenants', 'operationId': 'tenantsPatchApiV1TenantsByTenantID'}, {'method': 'POST', 'path': '/api/v1/tenants/{tenantID}/app-bootstraps', 'tag': 'Deploy', 'operationId': 'deployPostApiV1TenantsByTenantIDAppBootstraps'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/app-bootstraps/{bootstrapID}', 'tag': 'Deploy', 'operationId': 'deployGetApiV1TenantsByTenantIDAppBootstrapsByBootstrapID'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/apps', 'tag': 'Apps', 'operationId': 'appsGetApiV1TenantsByTenantIDApps'}, {'method': 'POST', 'path': '/api/v1/tenants/{tenantID}/apps', 'tag': 'Apps', 'operationId': 'appsPostApiV1TenantsByTenantIDApps'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/apps/check-availability', 'tag': 'Apps', 'operationId': 'appsGetApiV1TenantsByTenantIDAppsCheckAvailability'}, {'method': 'POST', 'path': '/api/v1/tenants/{tenantID}/apps/icon/upload-url', 'tag': 'Apps', 'operationId': 'appsPostApiV1TenantsByTenantIDAppsIconUploadUrl'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/audit-events', 'tag': 'Audit', 'operationId': 'auditGetApiV1TenantsByTenantIDAuditEvents'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/audit-events/{eventID}', 'tag': 'Audit', 'operationId': 'auditGetApiV1TenantsByTenantIDAuditEventsByEventID'}, {'method': 'POST', 'path': '/api/v1/tenants/{tenantID}/audit-events/anonymize', 'tag': 'Audit', 'operationId': 'auditPostApiV1TenantsByTenantIDAuditEventsAnonymize'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/audit-events/integrity-check', 'tag': 'Audit', 'operationId': 'auditGetApiV1TenantsByTenantIDAuditEventsIntegrityCheck'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/categories', 'tag': 'Apps', 'operationId': 'appsGetApiV1TenantsByTenantIDCategories'}, {'method': 'POST', 'path': '/api/v1/tenants/{tenantID}/categories', 'tag': 'Apps', 'operationId': 'appsPostApiV1TenantsByTenantIDCategories'}, {'method': 'DELETE', 'path': '/api/v1/tenants/{tenantID}/categories/{categoryID}', 'tag': 'Apps', 'operationId': 'appsDeleteApiV1TenantsByTenantIDCategoriesByCategoryID'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/categories/{categoryID}', 'tag': 'Apps', 'operationId': 'appsGetApiV1TenantsByTenantIDCategoriesByCategoryID'}, {'method': 'PATCH', 'path': '/api/v1/tenants/{tenantID}/categories/{categoryID}', 'tag': 'Apps', 'operationId': 'appsPatchApiV1TenantsByTenantIDCategoriesByCategoryID'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/connectors', 'tag': 'Gateway', 'operationId': 'gatewayGetApiV1TenantsByTenantIDConnectors'}, {'method': 'POST', 'path': '/api/v1/tenants/{tenantID}/connectors', 'tag': 'Gateway', 'operationId': 'gatewayPostApiV1TenantsByTenantIDConnectors'}, {'method': 'DELETE', 'path': '/api/v1/tenants/{tenantID}/connectors/{connectorID}', 'tag': 'Gateway', 'operationId': 'gatewayDeleteApiV1TenantsByTenantIDConnectorsByConnectorID'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/connectors/{connectorID}', 'tag': 'Gateway', 'operationId': 'gatewayGetApiV1TenantsByTenantIDConnectorsByConnectorID'}, {'method': 'PATCH', 'path': '/api/v1/tenants/{tenantID}/connectors/{connectorID}', 'tag': 'Gateway', 'operationId': 'gatewayPatchApiV1TenantsByTenantIDConnectorsByConnectorID'}, {'method': 'POST', 'path': '/api/v1/tenants/{tenantID}/connectors/{connectorID}/test-connection', 'tag': 'Gateway', 'operationId': 'gatewayPostApiV1TenantsByTenantIDConnectorsByConnectorIDTestConnection'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/cost/by-app', 'tag': 'Cost', 'operationId': 'costGetApiV1TenantsByTenantIDCostByApp'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/cost/by-cost-center', 'tag': 'Cost', 'operationId': 'costGetApiV1TenantsByTenantIDCostByCostCenter'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/cost/export', 'tag': 'Cost', 'operationId': 'costGetApiV1TenantsByTenantIDCostExport'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/cost/months', 'tag': 'Cost', 'operationId': 'costGetApiV1TenantsByTenantIDCostMonths'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/cost/summary', 'tag': 'Cost', 'operationId': 'costGetApiV1TenantsByTenantIDCostSummary'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/cost/timeseries', 'tag': 'Cost', 'operationId': 'costGetApiV1TenantsByTenantIDCostTimeseries'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/deployments', 'tag': 'Deploy', 'operationId': 'deployGetApiV1TenantsByTenantIDDeployments'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/discover/apps', 'tag': 'Apps', 'operationId': 'appsGetApiV1TenantsByTenantIDDiscoverApps'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/email-domains', 'tag': 'Tenants', 'operationId': 'tenantsGetApiV1TenantsByTenantIDEmailDomains'}, {'method': 'POST', 'path': '/api/v1/tenants/{tenantID}/email-domains', 'tag': 'Tenants', 'operationId': 'tenantsPostApiV1TenantsByTenantIDEmailDomains'}, {'method': 'DELETE', 'path': '/api/v1/tenants/{tenantID}/email-domains/{domain}', 'tag': 'Tenants', 'operationId': 'tenantsDeleteApiV1TenantsByTenantIDEmailDomainsByDomain'}, {'method': 'POST', 'path': '/api/v1/tenants/{tenantID}/gateway/invoke', 'tag': 'Gateway', 'operationId': 'gatewayPostApiV1TenantsByTenantIDGatewayInvoke'}, {'method': 'POST', 'path': '/api/v1/tenants/{tenantID}/gateway/query', 'tag': 'Gateway', 'operationId': 'gatewayPostApiV1TenantsByTenantIDGatewayQuery'}, {'method': 'POST', 'path': '/api/v1/tenants/{tenantID}/gateway/sessions', 'tag': 'Gateway', 'operationId': 'gatewayPostApiV1TenantsByTenantIDGatewaySessions'}, {'method': 'DELETE', 'path': '/api/v1/tenants/{tenantID}/gateway/sessions/{sessionID}', 'tag': 'Gateway', 'operationId': 'gatewayDeleteApiV1TenantsByTenantIDGatewaySessionsBySessionID'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/grants', 'tag': 'Authorization', 'operationId': 'authorizationGetApiV1TenantsByTenantIDGrants'}, {'method': 'POST', 'path': '/api/v1/tenants/{tenantID}/grants', 'tag': 'Authorization', 'operationId': 'authorizationPostApiV1TenantsByTenantIDGrants'}, {'method': 'DELETE', 'path': '/api/v1/tenants/{tenantID}/grants/{grantID}', 'tag': 'Authorization', 'operationId': 'authorizationDeleteApiV1TenantsByTenantIDGrantsByGrantID'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/grants/{grantID}', 'tag': 'Authorization', 'operationId': 'authorizationGetApiV1TenantsByTenantIDGrantsByGrantID'}, {'method': 'DELETE', 'path': '/api/v1/tenants/{tenantID}/icon', 'tag': 'Tenants', 'operationId': 'tenantsDeleteApiV1TenantsByTenantIDIcon'}, {'method': 'POST', 'path': '/api/v1/tenants/{tenantID}/icon/upload-url', 'tag': 'Tenants', 'operationId': 'tenantsPostApiV1TenantsByTenantIDIconUploadUrl'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/identity-providers', 'tag': 'Auth', 'operationId': 'authGetApiV1TenantsByTenantIDIdentityProviders'}, {'method': 'POST', 'path': '/api/v1/tenants/{tenantID}/identity-providers', 'tag': 'Auth', 'operationId': 'authPostApiV1TenantsByTenantIDIdentityProviders'}, {'method': 'POST', 'path': '/api/v1/tenants/{tenantID}/identity-providers/{providerID}/disable', 'tag': 'Auth', 'operationId': 'authPostApiV1TenantsByTenantIDIdentityProvidersByProviderIDDisable'}, {'method': 'POST', 'path': '/api/v1/tenants/{tenantID}/identity-providers/{providerID}/enable', 'tag': 'Auth', 'operationId': 'authPostApiV1TenantsByTenantIDIdentityProvidersByProviderIDEnable'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/infra/apps/{appID}/usage-series', 'tag': 'Cost', 'operationId': 'costGetApiV1TenantsByTenantIDInfraAppsByAppIDUsageSeries'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/infra/usage', 'tag': 'Cost', 'operationId': 'costGetApiV1TenantsByTenantIDInfraUsage'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/invitations', 'tag': 'Tenants', 'operationId': 'tenantsGetApiV1TenantsByTenantIDInvitations'}, {'method': 'POST', 'path': '/api/v1/tenants/{tenantID}/invitations', 'tag': 'Tenants', 'operationId': 'tenantsPostApiV1TenantsByTenantIDInvitations'}, {'method': 'DELETE', 'path': '/api/v1/tenants/{tenantID}/invitations/{invitationID}', 'tag': 'Tenants', 'operationId': 'tenantsDeleteApiV1TenantsByTenantIDInvitationsByInvitationID'}, {'method': 'POST', 'path': '/api/v1/tenants/{tenantID}/invitations/bulk', 'tag': 'Tenants', 'operationId': 'tenantsPostApiV1TenantsByTenantIDInvitationsBulk'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/invite-links', 'tag': 'Tenants', 'operationId': 'tenantsGetApiV1TenantsByTenantIDInviteLinks'}, {'method': 'POST', 'path': '/api/v1/tenants/{tenantID}/invite-links', 'tag': 'Tenants', 'operationId': 'tenantsPostApiV1TenantsByTenantIDInviteLinks'}, {'method': 'DELETE', 'path': '/api/v1/tenants/{tenantID}/invite-links/{linkID}', 'tag': 'Tenants', 'operationId': 'tenantsDeleteApiV1TenantsByTenantIDInviteLinksByLinkID'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/me/connectors', 'tag': 'Gateway', 'operationId': 'gatewayGetApiV1TenantsByTenantIDMeConnectors'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/me/connectors/{connectorID}/resources', 'tag': 'Gateway', 'operationId': 'gatewayGetApiV1TenantsByTenantIDMeConnectorsByConnectorIDResources'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/me/grants', 'tag': 'Authorization', 'operationId': 'authorizationGetApiV1TenantsByTenantIDMeGrants'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/members', 'tag': 'Tenants', 'operationId': 'tenantsGetApiV1TenantsByTenantIDMembers'}, {'method': 'PATCH', 'path': '/api/v1/tenants/{tenantID}/members/{membershipID}', 'tag': 'Tenants', 'operationId': 'tenantsPatchApiV1TenantsByTenantIDMembersByMembershipID'}, {'method': 'POST', 'path': '/api/v1/tenants/{tenantID}/members/{membershipID}/deactivate', 'tag': 'Tenants', 'operationId': 'tenantsPostApiV1TenantsByTenantIDMembersByMembershipIDDeactivate'}, {'method': 'POST', 'path': '/api/v1/tenants/{tenantID}/members/{membershipID}/reactivate', 'tag': 'Tenants', 'operationId': 'tenantsPostApiV1TenantsByTenantIDMembersByMembershipIDReactivate'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/presets', 'tag': 'Authorization', 'operationId': 'authorizationGetApiV1TenantsByTenantIDPresets'}, {'method': 'POST', 'path': '/api/v1/tenants/{tenantID}/presets', 'tag': 'Authorization', 'operationId': 'authorizationPostApiV1TenantsByTenantIDPresets'}, {'method': 'DELETE', 'path': '/api/v1/tenants/{tenantID}/presets/{presetID}', 'tag': 'Authorization', 'operationId': 'authorizationDeleteApiV1TenantsByTenantIDPresetsByPresetID'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/presets/{presetID}', 'tag': 'Authorization', 'operationId': 'authorizationGetApiV1TenantsByTenantIDPresetsByPresetID'}, {'method': 'PATCH', 'path': '/api/v1/tenants/{tenantID}/presets/{presetID}', 'tag': 'Authorization', 'operationId': 'authorizationPatchApiV1TenantsByTenantIDPresetsByPresetID'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/subjects', 'tag': 'Authorization', 'operationId': 'authorizationGetApiV1TenantsByTenantIDSubjects'}, {'method': 'POST', 'path': '/api/v1/tenants/{tenantID}/subjects', 'tag': 'Authorization', 'operationId': 'authorizationPostApiV1TenantsByTenantIDSubjects'}, {'method': 'GET', 'path': '/api/v1/tenants/{tenantID}/subjects/{subjectID}', 'tag': 'Authorization', 'operationId': 'authorizationGetApiV1TenantsByTenantIDSubjectsBySubjectID'}, {'method': 'GET', 'path': '/api/v1/users/me/apps', 'tag': 'Apps', 'operationId': 'appsGetApiV1UsersMeApps'}, {'method': 'GET', 'path': '/auth/{providerID}/start', 'tag': 'Auth', 'operationId': 'authGetAuthByProviderIDStart'}, {'method': 'GET', 'path': '/auth/github', 'tag': 'identity', 'operationId': 'identityGetAuthGithub'}, {'method': 'GET', 'path': '/auth/github/callback', 'tag': 'identity', 'operationId': 'identityGetAuthGithubCallback'}, {'method': 'GET', 'path': '/auth/google_oauth2/callback', 'tag': 'Auth', 'operationId': 'authGetAuthGoogleOauth2Callback'}, {'method': 'GET', 'path': '/auth/google_oauth2/start', 'tag': 'Auth', 'operationId': 'authGetAuthGoogleOauth2Start'}, {'method': 'POST', 'path': '/auth/logout', 'tag': 'Auth', 'operationId': 'authPostAuthLogout'}, {'method': 'GET', 'path': '/auth/oidc/callback', 'tag': 'Auth', 'operationId': 'authGetAuthOidcCallback'}, {'method': 'GET', 'path': '/auth/providers', 'tag': 'Auth', 'operationId': 'authGetAuthProviders'}, {'method': 'POST', 'path': '/auth/refresh', 'tag': 'Auth', 'operationId': 'authPostAuthRefresh'}, {'method': 'GET', 'path': '/auth/silent/callback', 'tag': 'Auth', 'operationId': 'authGetAuthSilentCallback'}, {'method': 'GET', 'path': '/auth/silent/start', 'tag': 'Auth', 'operationId': 'authGetAuthSilentStart'}, {'method': 'GET', 'path': '/config/public', 'tag': 'Config', 'operationId': 'configGetConfigPublic'}, {'method': 'GET', 'path': '/data/{tenantSlug}/{appSlug}/{table}', 'tag': 'Schema', 'operationId': 'schemaGetDataByTenantSlugByAppSlugByTable'}, {'method': 'POST', 'path': '/data/{tenantSlug}/{appSlug}/{table}', 'tag': 'Schema', 'operationId': 'schemaPostDataByTenantSlugByAppSlugByTable'}, {'method': 'GET', 'path': '/data/{tenantSlug}/{appSlug}/{table}/_count', 'tag': 'Schema', 'operationId': 'schemaGetDataByTenantSlugByAppSlugByTableCount'}, {'method': 'DELETE', 'path': '/data/{tenantSlug}/{appSlug}/{table}/{id}', 'tag': 'Schema', 'operationId': 'schemaDeleteDataByTenantSlugByAppSlugByTableById'}, {'method': 'GET', 'path': '/data/{tenantSlug}/{appSlug}/{table}/{id}', 'tag': 'Schema', 'operationId': 'schemaGetDataByTenantSlugByAppSlugByTableById'}, {'method': 'PATCH', 'path': '/data/{tenantSlug}/{appSlug}/{table}/{id}', 'tag': 'Schema', 'operationId': 'schemaPatchDataByTenantSlugByAppSlugByTableById'}, {'method': 'GET', 'path': '/internal/app-access', 'tag': 'Apps', 'operationId': 'appsGetInternalAppAccess'}, {'method': 'GET', 'path': '/oauth/authorize', 'tag': 'Auth', 'operationId': 'authGetOauthAuthorize'}, {'method': 'POST', 'path': '/oauth/authorize/tenant', 'tag': 'Auth', 'operationId': 'authPostOauthAuthorizeTenant'}, {'method': 'POST', 'path': '/oauth/device_authorization', 'tag': 'Auth', 'operationId': 'authPostOauthDeviceAuthorization'}, {'method': 'POST', 'path': '/oauth/device/authorize', 'tag': 'Auth', 'operationId': 'authPostOauthDeviceAuthorize'}, {'method': 'GET', 'path': '/oauth/device/lookup', 'tag': 'Auth', 'operationId': 'authGetOauthDeviceLookup'}, {'method': 'POST', 'path': '/oauth/register', 'tag': 'Auth', 'operationId': 'authPostOauthRegister'}, {'method': 'POST', 'path': '/oauth/revoke', 'tag': 'Auth', 'operationId': 'authPostOauthRevoke'}, {'method': 'POST', 'path': '/oauth/token', 'tag': 'Auth', 'operationId': 'authPostOauthToken'}, {'method': 'GET', 'path': '/oauth/userinfo', 'tag': 'Auth', 'operationId': 'authGetOauthUserinfo'}, {'method': 'POST', 'path': '/webhooks/github', 'tag': 'Deploy', 'operationId': 'deployPostWebhooksGithub'}]
ERROR_CODES = {
    "action_denied": ErrorInfo("permission_denied", 403, False),
    "action_invalid": ErrorInfo("validation", 400, False),
    "already_accessed": ErrorInfo("conflict", 409, False),
    "already_active": ErrorInfo("conflict", 409, False),
    "already_deleted": ErrorInfo("conflict", 409, False),
    "already_exists": ErrorInfo("conflict", 409, False),
    "already_inactive": ErrorInfo("conflict", 409, False),
    "already_member": ErrorInfo("conflict", 409, False),
    "already_revoked": ErrorInfo("conflict", 409, False),
    "already_settled": ErrorInfo("conflict", 409, False),
    "already_suspended": ErrorInfo("conflict", 409, False),
    "already_terminal": ErrorInfo("conflict", 409, False),
    "app_unavailable": ErrorInfo("conflict", 409, False),
    "bad_request": ErrorInfo("validation", 400, False),
    "cannot_reactivate": ErrorInfo("conflict", 409, False),
    "conflict": ErrorInfo("conflict", 409, False),
    "connector_inactive": ErrorInfo("permission_denied", 403, False),
    "cross_tenant": ErrorInfo("validation", 400, False),
    "domain_blocked": ErrorInfo("precondition_failed", 422, False),
    "domain_taken": ErrorInfo("conflict", 409, False),
    "duplicate": ErrorInfo("validation", 400, False),
    "empty": ErrorInfo("validation", 400, False),
    "expiry_in_past": ErrorInfo("validation", 400, False),
    "forbidden": ErrorInfo("permission_denied", 403, False),
    "grant_already_terminal": ErrorInfo("conflict", 409, False),
    "grant_conflict": ErrorInfo("conflict", 409, False),
    "grant_expired": ErrorInfo("permission_denied", 403, False),
    "grant_revoked": ErrorInfo("permission_denied", 403, False),
    "internal_error": ErrorInfo("internal", 500, False),
    "invalid_expiry": ErrorInfo("validation", 400, False),
    "invalid_format": ErrorInfo("validation", 400, False),
    "invalid_state_transition": ErrorInfo("conflict", 409, False),
    "invalid_value": ErrorInfo("validation", 400, False),
    "invitation_expired": ErrorInfo("not_found", 410, False),
    "kind_engine_mismatch": ErrorInfo("validation", 400, False),
    "last_admin": ErrorInfo("conflict", 409, False),
    "link_invalid": ErrorInfo("not_found", 404, False),
    "no_active_grant": ErrorInfo("not_found", 404, False),
    "not_admin": ErrorInfo("permission_denied", 403, False),
    "not_allowed": ErrorInfo("validation", 400, False),
    "not_deleted": ErrorInfo("conflict", 409, False),
    "not_found": ErrorInfo("not_found", 404, False),
    "not_member": ErrorInfo("permission_denied", 403, False),
    "not_suspended": ErrorInfo("conflict", 409, False),
    "pending_exists": ErrorInfo("conflict", 409, False),
    "permanently_deleted": ErrorInfo("not_found", 410, False),
    "precondition_failed": ErrorInfo("precondition_failed", 412, False),
    "preset_mismatch": ErrorInfo("validation", 400, False),
    "required": ErrorInfo("validation", 400, False),
    "schema_name_taken": ErrorInfo("conflict", 409, False),
    "session_ended": ErrorInfo("unauthenticated", 401, True),
    "session_expired": ErrorInfo("unauthenticated", 401, True),
    "slug_taken": ErrorInfo("conflict", 409, False),
    "temporarily_unavailable": ErrorInfo("unavailable", 429, True),
    "token_expired": ErrorInfo("unauthenticated", 401, True),
    "token_invalid": ErrorInfo("unauthenticated", 401, True),
    "token_missing": ErrorInfo("unauthenticated", 401, True),
    "too_long": ErrorInfo("validation", 400, False),
}
_ROUTE_BY_OP = {r["operationId"]: r for r in ROUTES}
_FORM_ENCODED_OPERATIONS = {"authPostOauthDeviceAuthorization", "authPostOauthRevoke", "authPostOauthToken"}
_OAUTH_RESPONSE_SNAKE_CASE_OPERATIONS = {"authPostOauthDeviceAuthorization", "authPostOauthToken"}
_OAUTH_RESPONSE_SNAKE_KEYS = {"access_token", "token_type", "expires_in", "refresh_token", "id_token", "scope", "resource", "tenant"}

def _request_id() -> str: return (str(int(time.time()*1000)) + uuid.uuid4().hex)[:26]
def _camel(s: str) -> str:
    parts=s.split('_'); return parts[0]+''.join(p[:1].upper()+p[1:] for p in parts[1:])
def _camelize(v: Any) -> Any:
    if isinstance(v, dict): return {_camel(k): _camelize(x) for k,x in v.items()}
    if isinstance(v, list): return [_camelize(x) for x in v]
    return v
def _camelize_oauth_response(v: Any) -> Any:
    if isinstance(v, dict): return {k if k in _OAUTH_RESPONSE_SNAKE_KEYS else _camel(k): _camelize_oauth_response(x) for k,x in v.items()}
    if isinstance(v, list): return [_camelize_oauth_response(x) for x in v]
    return v
class _NoRedirectHandler(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl): return None
_NO_REDIRECT_OPENER = request.build_opener(_NoRedirectHandler)

def _is_form_encoded(operation_id: str) -> bool: return operation_id in _FORM_ENCODED_OPERATIONS
def _form_body(body: Any) -> bytes:
    if isinstance(body, Mapping):
        return parse.urlencode({str(k): "" if v is None else str(v) for k, v in body.items()}).encode()
    return parse.urlencode({}).encode()

class AxHubClient:
    def __init__(self, *, base_url: str = DEFAULT_BASE_URL, token: str | None = None, token_type: TokenType | str | None = None, default_tenant_id: str | None = None, default_tenant_slug: str | None = None, schema_cache: Any = None):
        self.base_url=base_url.rstrip('/'); self.token=token; self.token_type=TokenType(token_type) if token_type else None; self.default_tenant_id=default_tenant_id; self.default_tenant_slug=default_tenant_slug; self.apps=AppsClient(self); self._schema_cache_opt=schema_cache; self._ergo_data_client=None
    def redacted_token(self) -> str: return "" if not self.token else "***REDACTED***"
    def _auth_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.token:
            if self.token_type == TokenType.PAT: headers['X-Api-Key']=self.token
            elif self.token_type == TokenType.JWT: headers['Authorization']='Bearer '+self.token
            else: raise AxHubError('validation','required','tokenType must be explicit')
        return headers
    def _send(self, method: str, url: str, *, data: bytes | None = None, content_type: str | None = None, camelize: bool = True, snake_keys: bool = False) -> Any:
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
                return _camelize_oauth_response(parsed) if snake_keys else _camelize(parsed)
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
            if _is_form_encoded(operation_id):
                data=_form_body(body); content_type='application/x-www-form-urlencoded'
            else:
                data=json.dumps(body).encode(); content_type='application/json'
        return self._send(route['method'], url, data=data, content_type=content_type, snake_keys=operation_id in _OAUTH_RESPONSE_SNAKE_CASE_OPERATIONS)
    def request_raw(self, method: str, path: str, *, query: Mapping[str, Any] | None = None, body: Any = None, camelize: bool = False) -> Any:
        """Raw-path transport for endpoints with no generated operation-id facade
        (the ergonomic data ring: dynamic CRUD + runtime schema discover).

        `path` is already fully substituted and percent-encoded by the caller.
        Defaults to `camelize=False` to mirror the node data transport: row bodies
        and list envelopes (`has_more`/`per_page`) are returned verbatim.
        """
        url=self.base_url+path
        if query: url += '?' + parse.urlencode(query, doseq=True)
        data=None; content_type=None
        if body is not None:
            data=json.dumps(body).encode(); content_type='application/json'
        return self._send(method, url, data=data, content_type=content_type, camelize=camelize)
class AppsClient:
    def __init__(self, client: AxHubClient): self._client=client
    def create(self, body: Mapping[str, Any]) -> dict[str, Any]:
        if not self._client.default_tenant_id: raise AxHubError('tenant_id_required','tenant_id_required','default tenant id is required')
        return self._client.request('appsPostApiV1TenantsByTenantIDApps', path_params={'tenantID': self._client.default_tenant_id}, body=dict(body))
class AsyncAppsClient:
    def __init__(self, client: 'AsyncAxHubClient'): self._client=client
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
    if tag == "Cost": return "cost"
    if tag == "Schema": return "data"
    if tag in {"Deploy", "deploy"}: return "deployments"
    raise ValueError(f"unmapped route tag: {tag}")
CONTEXT_ROUTES = {name: [r for r in ROUTES if _context_name(r) == name] for name in ['apps', 'identity', 'tenants', 'authz', 'audit', 'gateway', 'cost', 'data', 'deployments']}

from .operations import install_operations as _install_operations
_install_operations(globals())


# --- Ergonomic data layer fluent surface (mirrors node sdk.tenant().app().data) ---
# `client.data` stays the operation-id route-table OperationContextClient (the
# conformance vectors + e2e tests depend on it). The ergonomic data layer is
# reached only through the tenant/app fluent chain, exactly as in node.
class _AppScope:
    def __init__(self, data: Any, tenant_slug: str, app_slug: str):
        # `data` is the single per-client DataClient (memoized on AxHubClient),
        # so its schema cache persists across every tenant().app() chain — node parity.
        self.data = data.scoped(tenant_slug).app(app_slug)


class _TenantScope:
    def __init__(self, data: Any, tenant_slug: str):
        self._data = data
        self._tenant_slug = tenant_slug

    def app(self, app_slug: str) -> _AppScope:
        return _AppScope(self._data, self._tenant_slug, app_slug)


def _ergo_data(self: 'AxHubClient'):
    """The single per-client ergonomic DataClient, lazily memoized so the
    schema cache (TTL/negative-TTL/LRU) survives across tenant().app() chains
    (mirrors node, where `data` is one per-SDK DataClient)."""
    existing = getattr(self, '_ergo_data_client', None)
    if existing is None:
        from .data import DataClient
        existing = DataClient(self, schema_cache=getattr(self, '_schema_cache_opt', None))
        self._ergo_data_client = existing
    return existing


def _tenant(self: 'AxHubClient', tenant_slug: str) -> _TenantScope:
    return _TenantScope(self.ergo_data(), tenant_slug)


AxHubClient.ergo_data = _ergo_data
AxHubClient.tenant = _tenant


def _async_tenant(self: 'AsyncAxHubClient', tenant_slug: str) -> _TenantScope:
    # Sync-backed data layer; async wrapper exposes the same fluent surface.
    return _TenantScope(self._sync.ergo_data(), tenant_slug)


AsyncAxHubClient.tenant = _async_tenant
