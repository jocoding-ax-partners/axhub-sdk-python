# Changelog

## v0.9.0 — 2026-07-03

### Added
- `tenants_get_api_v1_tenants_by_tenant_id_members_directory` — `GET /api/v1/tenants/{tenantID}/members/directory`. 활성 멤버 디렉토리(가입 멤버만, email 제외 PII 축소 뷰). 각 행의 `groupId` 로 그룹별 필터가 가능하다. 호출 권한 tenant_member. node 에만 있던 표면을 6개 SDK 로 정렬.

## v0.8.0 — 2026-07-03

### Added
- `tenants_get_api_v1_tenants_by_tenant_id_org_directory` — `GET /api/v1/tenants/{tenantID}/org-directory`. SCIM 사내 조직도 조회: 부서(그룹)→인원 구조, 아직 가입하지 않은 인원 포함(`joined` 플래그로 구분), 표시 이름 없으면 이메일 폴백. 호출 권한 tenant_member.

## v0.7.0 — 2026-07-02

### Removed (developer-surface reduction)
The SDK now exposes only the developer surface (85 operations). 132 operations were removed:
platform admin (templates admin, revoke-all, internal, SCIM, webhooks), tenant/org management
(members, seats, groups, invitations, invite-links, icons, categories, email-domains, identity
providers, tenant create/update/delete), authorization management (grant issuance, presets,
subjects), audit, cost (context removed), review-requests, static-site releases/staging, and all
browser auth / OAuth flows (`/auth/*`, `/oauth/*`) including `authPostOauthToken`.
Auth model: inject an issued PAT or JWT; token exchange happens outside the SDK.
New backend routes are excluded by default until added to `conformance/sdk-allowlist.json`.

### Changed
- Bounded contexts: 9 -> 8 (`cost` removed; `audit` remains registered with no operations). Requests are always JSON (form-encoding path removed).
