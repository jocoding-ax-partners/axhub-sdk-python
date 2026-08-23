# Changelog

## v0.13.0 — 2026-08-23

### Note
- 최초 태그의 발행이 PyPI 업로드 단계에서 실패했다 — `gh-action-pypi-publish` v1.14.0 이 내장한 Twine 이 hatchling 이 찍는 `Metadata-Version: 2.5` 를 몰라 `InvalidDistribution` 으로 거절했다. 액션을 v1.14.2(Twine v7)로 올려 재발행했다. 패키지 내용은 동일하다.

### Fixed
- 에러 카탈로그가 backend 와 3주 벌어져 있던 것을 동기화 (133 → 182). 카탈로그는 응답에 `category`/`retryable` 이 없을 때의 **폴백**이라 조용히 틀린다 — 빠진 코드는 category `unknown` + `retryable=False` 로 떨어져서, 재시도해야 할 실패(`connector_probe_unavailable` 502 등)를 영구 실패로 다루게 된다.
- 죽은 코드 6종 제거 — `synology_invalid_credential`·`synology_probe_failed`·`synology_relay_unreachable` (backend 에서 synology 엔진 철거, 사내망 자원은 사이트 에이전트 터널로 일원화)·`domain_blocked`·`already_terminal`·`invalid_seat_count`.

### Added
- 에러 코드 55종 추가. 게이트웨이 커넥터 표면이 특히 크게 빠져 있었다 — `scope_out_of_range`(폴더 범위 밖 거부)·`connector_probe_unavailable`·`connector_probe_failed`·`connector_quarantined`·`owner_consent_required`·`scope_requires_target`·`invalid_manifest`·`resource_browse_restricted`. 그 밖에 결제·백업·소스업로드·AI 키 계열.
- 회귀 테스트 2종 — 삭제된 코드가 되살아나지 않는지, 재시도 가능 여부(`retryable`)가 뒤집히지 않는지 고정.

### Note
- 이번 동기화는 backend `internal/platform/httpx/codes.go` @ `43193907` 에서 직접 추출했다. 중간 단계인 `axhub-sdk-spec` 저장소는 backend `36d5f38f`(2026-07-30)에 핀되어 있어 그 자체로 낡았고(라우트 +115/−9), 재핀은 node·java·kotlin SDK 와 MCP corpus 까지 함께 움직여야 해서 별도 작업으로 남긴다. 라우트 표면(`ROUTES` 97개)은 이번 릴리스에서 건드리지 않았다.

## v0.12.0 — 2026-07-21

### Added
- 라우트 87→97 — notifications(사용자 알림함 3·앱 발송 2)·access-requests 4·배포별 진단 1 op facade 추가 (backend 8714f5cd re-pin, allowlist 87→97, 신규 notifications context).
- 에러 카탈로그 117→133 — `feature_disabled`·`promote_snapshot_missing`·`rate_limited`·`staging_namespace_too_long` 등 (backend spec 128/133/134 + PR #618).

### Fixed
- 에러 카탈로그 category 오염 교정 — payment 계열 10종의 category 가 Go 식별자 `CategoryPaymentRequired` 문자열로 잘못 들어가던 것을 wire 값 `payment_required` 로 복구.

### Changed
- conformance corpus 45→49 — typed-error 3종(feature_disabled·promote_snapshot_missing·402 payment) + check-availability `reason:"invalid"` 회귀 벡터.

## v0.11.0 — 2026-07-08

### Added
- 에러 카탈로그 106→117 — Google Workspace 조직도 연동(spec 109/113)·디렉터리 단일소스(spec 114) 에러 코드 11종 추가 (`google_domain_taken`, `directory_source_conflict`, `group_scim_managed` 등; backend 73e89024 re-pin).

### Note
- v0.10.0 태그는 소스 버전 bump 누락으로 릴리스 워크플로가 실패해 PyPI 에 발행되지 않았다. 해당 변경(raw DB typed helper, live QA 정렬)은 본 릴리스에 포함되어 발행된다.

## v0.10.0 — 2026-07-08

### Added
- `apps.raw_db.tables()` / `apps.raw_db.table_rows()` — raw DB 조회용 typed helper (read-only introspection). node SDK 와 표면 정렬.

### Changed
- live QA harness 를 현행 route surface 에 정렬.
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