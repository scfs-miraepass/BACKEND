# [1.3.0](https://git.rldn.xyz/scfs.miraepass/backend/compare/v1.2.0...v1.3.0) (2026-05-20)


### Bug Fixes

* pydantic 경고 재수정 ([5037dd0](https://git.rldn.xyz/scfs.miraepass/backend/commit/5037dd0713d6204e38bbfa8177484c251e08a833)), closes [#13](https://git.rldn.xyz/scfs.miraepass/backend/issues/13)
* 지급 가능 포인트 소진시 500으로 다시 초기화 되는 형상 해결 ([1037550](https://git.rldn.xyz/scfs.miraepass/backend/commit/10375509eb62fbf5d28bbf8379b1c43b469aa1eb))


### Features

* **point:** 교사, 학생 누적 포인트 순위 추가 ([8fc0a21](https://git.rldn.xyz/scfs.miraepass/backend/commit/8fc0a2196ca8799d397c3714e6b037cfc8eed123)), closes [#18](https://git.rldn.xyz/scfs.miraepass/backend/issues/18)
* **point:** 포인트 조회 Endpoint 권한 검사 추가 ([2dca93c](https://git.rldn.xyz/scfs.miraepass/backend/commit/2dca93c84ee96997e2b2db0dd11ecaeb9598d686)), closes [#17](https://git.rldn.xyz/scfs.miraepass/backend/issues/17)
* **point:** 학생 하루 포인트 지급 한도 추가 ([65c8b0f](https://git.rldn.xyz/scfs.miraepass/backend/commit/65c8b0fd4742c96bbaa5b49f597651448b0a7517)), closes [#19](https://git.rldn.xyz/scfs.miraepass/backend/issues/19)

* **point:** 누적 포인트 추가 ([3221ce7](https://git.rldn.xyz/scfs.miraepass/backend/commit/3221ce71c5804c56b8f5015f0ea54200df327307)), closes [#16](https://git.rldn.xyz/scfs.miraepass/backend/issues/16)
* **point:** 포인트 지급 한도를 조회하는 Endpoint 추가 ([52c2b0b](https://git.rldn.xyz/scfs.miraepass/backend/commit/52c2b0b7e9ff9e3fa0231c455794339eb9e25138))
* **point:** 포인트 지급한도 초기화를 위한 스케줄러 추가 ([39e6c24](https://git.rldn.xyz/scfs.miraepass/backend/commit/39e6c24acd21e00d1a109bd43868f607bb7a2185))


# [1.3.0-dev.3](https://git.rldn.xyz/scfs.miraepass/backend/compare/v1.3.0-dev.2...v1.3.0-dev.3) (2026-05-20)


### Bug Fixes

* pydantic 경고 재수정 ([5037dd0](https://git.rldn.xyz/scfs.miraepass/backend/commit/5037dd0713d6204e38bbfa8177484c251e08a833)), closes [#13](https://git.rldn.xyz/scfs.miraepass/backend/issues/13)
* 지급 가능 포인트 소진시 500으로 다시 초기화 되는 형상 해결 ([1037550](https://git.rldn.xyz/scfs.miraepass/backend/commit/10375509eb62fbf5d28bbf8379b1c43b469aa1eb))

# [1.3.0-dev.2](https://git.rldn.xyz/scfs.miraepass/backend/compare/v1.3.0-dev.1...v1.3.0-dev.2) (2026-05-20)


### Features

* **point:** 포인트 지급 한도를 조회하는 Endpoint 추가 ([52c2b0b](https://git.rldn.xyz/scfs.miraepass/backend/commit/52c2b0b7e9ff9e3fa0231c455794339eb9e25138))
* **point:** 포인트 지급한도 초기화를 위한 스케줄러 추가 ([39e6c24](https://git.rldn.xyz/scfs.miraepass/backend/commit/39e6c24acd21e00d1a109bd43868f607bb7a2185))

# [1.3.0-dev.1](https://git.rldn.xyz/scfs.miraepass/backend/compare/v1.2.0...v1.3.0-dev.1) (2026-05-20)


### Features

* **point:** 누적 포인트 추가 ([3221ce7](https://git.rldn.xyz/scfs.miraepass/backend/commit/3221ce71c5804c56b8f5015f0ea54200df327307)), closes [#16](https://git.rldn.xyz/scfs.miraepass/backend/issues/16)

# [1.2.0](https://git.rldn.xyz/scfs.miraepass/backend/compare/v1.1.0...v1.2.0) (2026-05-19)


### Features

* 학생 지급시 교사 10% 지급에서 교사 동일 지급 ([7911209](https://git.rldn.xyz/scfs.miraepass/backend/commit/791120987ec62f1dab1de3bfa1d19df3c0510fd3))


### Reverts

* Revert "chore(release): 1.1.0 [skip ci]" ([5e05c49](https://git.rldn.xyz/scfs.miraepass/backend/commit/5e05c498e21ba1da56026880f23aa594bcd03163))

# [1.1.0-dev.4](https://git.rldn.xyz/scfs.miraepass/backend/compare/v1.1.0-dev.3...v1.1.0-dev.4) (2026-05-18)


### Bug Fixes

* Redis 캐시 초기화 하는 과정에서 delete에 인수가 잘 못 들어가 있는거 수정 ([83cd756](https://git.rldn.xyz/scfs.miraepass/backend/commit/83cd756cdb6b86c9591eb8194205e3a20c2c1efc))


### Features

* DATABASE 마이그레이셩 재구성 ([3b294d2](https://git.rldn.xyz/scfs.miraepass/backend/commit/3b294d238e5dcaf6a4b405e752c5ce9bb66901e1))
* 교사 포인트 지급 보상? 포인트에 어떤 학생에게 주었는지 까지 표기 ([32c75bb](https://git.rldn.xyz/scfs.miraepass/backend/commit/32c75bb8773b2e18f005129d8486d2d81b334a91))

# [1.1.0-dev.3](https://git.rldn.xyz/scfs.miraepass/backend/compare/v1.1.0-dev.2...v1.1.0-dev.3) (2026-05-18)


### Features

* **point:** 포인트 지급시 교사에게 10% 포인트 지급 ([e17e0f9](https://git.rldn.xyz/scfs.miraepass/backend/commit/e17e0f9e1158f0ac3c16653eccba5b3b5eda8bab)), closes [#12](https://git.rldn.xyz/scfs.miraepass/backend/issues/12)

# [1.1.0-dev.2](https://git.rldn.xyz/scfs.miraepass/backend/compare/v1.1.0-dev.1...v1.1.0-dev.2) (2026-05-02)


### Features

* **POST /admin/point:** 완성 (closes [#9](https://git.rldn.xyz/scfs.miraepass/backend/issues/9), [#10](https://git.rldn.xyz/scfs.miraepass/backend/issues/10)) ([baa67ba](https://git.rldn.xyz/scfs.miraepass/backend/commit/baa67bafb149cbd751744bc9cd265e749ebe414c))

# [1.1.0-dev.1](https://git.rldn.xyz/scfs.miraepass/backend/compare/v1.0.2...v1.1.0-dev.1) (2026-05-02)


### Features

* GET /admin/student 학생 목록 Endpoint 추가 ([369e0cf](https://git.rldn.xyz/scfs.miraepass/backend/commit/369e0cfed2e95aedbd078f5b31d7637b26b469a4))

## [1.0.2](https://git.rldn.xyz/scfs.miraepass/backend/compare/v1.0.1...v1.0.2) (2026-05-02)


### Bug Fixes

* **deploy:** `if [[ "$NEW_VERSION" != *"-dev"* ]]; then` 파트 에러 해결 ([8a1d9fb](https://git.rldn.xyz/scfs.miraepass/backend/commit/8a1d9fba7bd4eedba427a4e45695058d1afb4af7))

## [1.0.1](https://git.rldn.xyz/scfs.miraepass/backend/compare/v1.0.0...v1.0.1) (2026-05-02)


### Bug Fixes

* **deploy:** uv.lock 가 아티펙트로 안넘어가서 uv lock를 따로 해야하는 현상 해결 ([b334d47](https://git.rldn.xyz/scfs.miraepass/backend/commit/b334d4778f0e10ea3140ec211df4d653c0647cd0))

# 1.0.0 (2026-05-02)


### Bug Fixes

* /search Query t 없는거 해결 ([847a50b](https://git.rldn.xyz/scfs.miraepass/backend/commit/847a50b53e92a14394a09ab060b8b97e8b287867))
* **config:** allow_origins를 정상적으로 해석하지 못하던 문제 해결 ([55483ca](https://git.rldn.xyz/scfs.miraepass/backend/commit/55483cab63f8f96dceaf23cc7b362fe352c4d7a7))
* **deploy:** build.env 없음 발생및 name 관련 문제 해결 ([a671e33](https://git.rldn.xyz/scfs.miraepass/backend/commit/a671e33209dfb211628dd62fcfd4613a14304491))
* **deploy:** curl가 없는 문제 해결 ([af26050](https://git.rldn.xyz/scfs.miraepass/backend/commit/af260507b41c11c44d817f1e34514c441caab119))
* redisCore에 ttl 없어서 생기는 버그 해결 ([38e5ec7](https://git.rldn.xyz/scfs.miraepass/backend/commit/38e5ec7204c198d95e8d91d3b3be7b9b342bb74c))
* sqlalchemy.exc.ArgumentError ([28badbc](https://git.rldn.xyz/scfs.miraepass/backend/commit/28badbcff59e7bdb327be026546a64f474ecea8d))
* 기존 임영재 검색시 임영으로 앞에서 부터 해야하는 문제를 해결 (임영재 -> 영재, 여) 등 도 검색 결과에 나옴 ([aab47a5](https://git.rldn.xyz/scfs.miraepass/backend/commit/aab47a547609a854b7ac5849e152aea67fe83842))
* 포인트 결제시 서비스 이름이 들어가지 않는 문제 해결 ([e672c75](https://git.rldn.xyz/scfs.miraepass/backend/commit/e672c753f94f0183e0db3426e3423edd8c958d4a))


### Features

* **0.1.6 Version UP:** 포스트 히스토리 목록 캐시 삭제 추가 ([8e9e315](https://git.rldn.xyz/scfs.miraepass/backend/commit/8e9e315b12afcd9c92ab355e59c6df30bcce963e))
* alembic DB 시스템 추가 ([cdc2c08](https://git.rldn.xyz/scfs.miraepass/backend/commit/cdc2c088e4ee2ae6f909183510f6711720ef188e))
* allow_origins 설정 추가 ([8f6e4e8](https://git.rldn.xyz/scfs.miraepass/backend/commit/8f6e4e8966f07d45db5c1566f72f8d4cf815b5bb))
* check_password_exists시 유저 캐시 ([798dd2c](https://git.rldn.xyz/scfs.miraepass/backend/commit/798dd2ccfe4e8b6574901c5c9ef7254e6724302f))
* Database 엔진 및 기타 환경 설정 추가 ([f7720d3](https://git.rldn.xyz/scfs.miraepass/backend/commit/f7720d322de3dbcf3f0d54130c403e8f07699394))
* DB 연결 안정성을 위한 구성 ([116ddbb](https://git.rldn.xyz/scfs.miraepass/backend/commit/116ddbb5d1c9e7ad0575dce6ef07a8c011fbcb9c))
* FastAPI 기본 구성과 응답 모델 추가 ([3ba3215](https://git.rldn.xyz/scfs.miraepass/backend/commit/3ba32152444366449b7a7482cc9ec1997b9ecc7d))
* loggers add ([1244399](https://git.rldn.xyz/scfs.miraepass/backend/commit/1244399a25c938cefbc0d6a12435ce34e5fef98f))
* **main:** 버전 관리를 위한 X-Server-Version 헤더 추가 (by. gemini) ([2fc7139](https://git.rldn.xyz/scfs.miraepass/backend/commit/2fc71394dc667a7eb9df4257e06e72bb3229a5ae))
* Redis Expire 및 세션 쿠키 path 추가 ([b791f97](https://git.rldn.xyz/scfs.miraepass/backend/commit/b791f970d601cefd9443ea0b126249a63a3ae331))
* **security:** 해시처리 알고리즘 argon2 으로 변경 ([69a2d5a](https://git.rldn.xyz/scfs.miraepass/backend/commit/69a2d5aa4c50f6777107ff3d210bc182aa25a027))
* Users history_type add ([6819364](https://git.rldn.xyz/scfs.miraepass/backend/commit/68193640ad3b2ce4a451e8ec3bd0606ee61da4f1))
* users table model ([f5787c7](https://git.rldn.xyz/scfs.miraepass/backend/commit/f5787c749a9e4e7d2a3d2cf5df0bace45f6af752))
* 교사 포인트 지급시 기록에 선생님 호칭 추가 ([bf11da6](https://git.rldn.xyz/scfs.miraepass/backend/commit/bf11da6070acf39e77aee18246d5fa6ea657bc6f))
* 기본 데이터베이스 관련 환경변수 설정 ([ec93c36](https://git.rldn.xyz/scfs.miraepass/backend/commit/ec93c365d64485e922f5ca8dffadb56599a4a3da))
* 비밀번호 변경 Endpoint와 바밀번호 해시화 ([e52b5aa](https://git.rldn.xyz/scfs.miraepass/backend/commit/e52b5aa971155d70593e4b786199dddfcf625e3c))
* 비밀번호 존재 여부 확인을 위한 Endpoint 추가 ([3cf00c3](https://git.rldn.xyz/scfs.miraepass/backend/commit/3cf00c30ed376a22899d8e5b7835675b2847130c))
* 비밀번호 존재 여부에 유저 타입 검사 추가 ([8e7d75c](https://git.rldn.xyz/scfs.miraepass/backend/commit/8e7d75cbceb45389590de1c6489cbf103bc4cef7))
* 비밀번호 초기 처리 Endpoint 추가 ([033c0b8](https://git.rldn.xyz/scfs.miraepass/backend/commit/033c0b8a5550c48b0bb362929d372a78d87ff715))
* 세션 인증 로직 변경 (by. gemini) ([775ba58](https://git.rldn.xyz/scfs.miraepass/backend/commit/775ba58134c515329d919772e89701ff50e48acc))
* 이름을 기준으로 교사 정보를 가져오는 Endpoint ([8fc73ab](https://git.rldn.xyz/scfs.miraepass/backend/commit/8fc73abd392f4dcd4a4835aa71ae23f6212306c3))
* 통합 검색으로 정리 ([0803122](https://git.rldn.xyz/scfs.miraepass/backend/commit/0803122325e516f2b3d5ab293d78def53285de2d))
* 포인트 기록 종류 추가 ([2c4db3f](https://git.rldn.xyz/scfs.miraepass/backend/commit/2c4db3fee050e12ba3c567593c537e3450f21234))
* 포인트 지급시 검색 캐시도 삭제하도록 변경 ([1db7d80](https://git.rldn.xyz/scfs.miraepass/backend/commit/1db7d800e31bf9cc5f4ef28cc8644745685c1d6a))
* 학생 검색 권한 처리 ([599aac4](https://git.rldn.xyz/scfs.miraepass/backend/commit/599aac4310960a54a2020f0f564a69321592fee3))
