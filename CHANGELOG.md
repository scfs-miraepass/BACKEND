# [1.11.0-dev.2](https://github.com/scfs-miraepass/BACKEND/compare/v1.11.0-dev.1...v1.11.0-dev.2) (2026-09-17)


### Bug Fixes

* 스케줄러 타임존이 UTC 등에 맞춰지던 것을 KST으로 고정 ([9dac36d](https://github.com/scfs-miraepass/BACKEND/commit/9dac36d6bf06969283e330709b12d952e1cf7875))

# [1.11.0-dev.1](https://github.com/scfs-miraepass/BACKEND/compare/v1.10.0...v1.11.0-dev.1) (2026-09-17)


### Bug Fixes

* **core:** date 타입 직렬화 및 enum 경고 해결 ([9a8a787](https://github.com/scfs-miraepass/BACKEND/commit/9a8a787efdbcc6e0ac9266d88bfba3e7c5a5de64))
* **core:** 동시 입찰 레이스 컨디션 수정 및 최종 입찰 조회 기능 추가 ([d5933a0](https://github.com/scfs-miraepass/BACKEND/commit/d5933a09a0b6cfeec17caf8ea302dfc1b9c6d9cd))
* database.session property를 사용하기 위해 async with에 넣을 경우 TypeError가 발생하던 현상 해결 ([3211254](https://github.com/scfs-miraepass/BACKEND/commit/3211254f9e1735035510cbe88549c57dcd82457f))
* DB와 백엔드의 시간대 차이로 경매가 즉시 시작/종료되던 현상 해결 ([61377ec](https://github.com/scfs-miraepass/BACKEND/commit/61377ecbba04c5744baee5f5949594c1709fc9bb))
* **endpoints:** `pydantic.errors.PydanticSchemaGenerationError:` 에러 해결 ([057fa8b](https://github.com/scfs-miraepass/BACKEND/commit/057fa8b106bc7a0cce5194f371c4bfaf9e3c88e7))
* **endpoints:** payload를 참조해서 발생하는 에러 해결 ([e31322c](https://github.com/scfs-miraepass/BACKEND/commit/e31322c2af76be8d7aa2b0addeca2c27b9462597))
* **endpoints:** 경매 생성시, 경매 목록 캐시가 제거가 안돼, 기존 캐시가 응답되는 현상 해결 ([5ed5176](https://github.com/scfs-miraepass/BACKEND/commit/5ed51763da751ee30b645a051922927f80beff3a))
* **karaoke:** final-bid 응답의 created_at에 타임존 오프셋 누락되어 Zod 검증 실패하던 문제 수정 ([17d082e](https://github.com/scfs-miraepass/BACKEND/commit/17d082e4b878e72e3f34836295e66175727d70d0))
* **karaoke:** 상태가 변경되어도, 변경후 남은 시간을 보내주지 않아서 UI에서 00:00 으로 표기되는 현상 해결 ([6479c45](https://github.com/scfs-miraepass/BACKEND/commit/6479c458286f3836bbf0cd58292a3f88fac8ea75))
* **karaoke:** 웹소켓 remaining_time 계산 버그 수정 및 코드 정리 ([227a650](https://github.com/scfs-miraepass/BACKEND/commit/227a65018c47c48fd8bf5ba1999698953e3ff7bd))
* **karaoke:** 입찰 취소 환불 계산이 취소 시점 파티원 기준이라 어긋나던 문제 수정 ([baedad6](https://github.com/scfs-miraepass/BACKEND/commit/baedad602b52c0342bbb67a7bb507c458e564c2a))
* **karaoke:** 캐시 무효화가 누락/오작동하던 곳 수정 ([9be6bcf](https://github.com/scfs-miraepass/BACKEND/commit/9be6bcfed2e275ef53d58ce3f76b6d080b6d138b))
* **karaoke:** 코드 리뷰 지적사항 반영 (권한, 강퇴, 락 범위, 중복 로직) ([386a1bb](https://github.com/scfs-miraepass/BACKEND/commit/386a1bb1b4e492944e036a98525ebe4db516648a))
* **karaoke:** 파티 탈퇴시 DetachedInstanceError로 500 발생하던 문제 수정 ([dc4953d](https://github.com/scfs-miraepass/BACKEND/commit/dc4953d9d1704bea97f98df54734bb176fc67ac0))
* **karaoke:** 프론트에 그대로 노출되는 커스텀 에러 메시지를 한국어로 변경 ([78fd8e0](https://github.com/scfs-miraepass/BACKEND/commit/78fd8e0be0f8bb06fae44589e2395ad781f0b562))
* users 생성시, 검색을 위한 index 초성 처리할 때 로그에 quest 로그로 뜨는거 수정 ([905a47f](https://github.com/scfs-miraepass/BACKEND/commit/905a47fd906c402af4eed1dfe5c3461885627ada))
* **user:** 파티장만 있고 멤버가 없는 파티가 get_party에서 조회되지 않던 문제 해결 ([da61124](https://github.com/scfs-miraepass/BACKEND/commit/da611243fe739f0ab31bdf664c74ee3b01137e22))
* 권한 비트 충돌 수정 및 파티 해산/강퇴 캐시 무효화 지연 해결 ([89da2a5](https://github.com/scfs-miraepass/BACKEND/commit/89da2a5afe8481e71f7e4c8889e4758c9b6bab1e))
* 마이그레이션이 되지 않는 현상 해결 ([6b72b3e](https://github.com/scfs-miraepass/BACKEND/commit/6b72b3e4bb80de16c429e5f1e7fec45d0225cdee))
* 마이그레이션이 되지 않는 현상 해결 ([447dcd7](https://github.com/scfs-miraepass/BACKEND/commit/447dcd7cb2a6351776be2207e3b30ca742fa4595))


### Features

* `ServiceClient.get_karaoke` 추가 ([3f71766](https://github.com/scfs-miraepass/BACKEND/commit/3f7176656dd5588734ee29b55bb78f1beb2bf5a7))
* `예약 경매 삭제 (DELETE /karaoke/{id})` Endpoint ([83309d1](https://github.com/scfs-miraepass/BACKEND/commit/83309d1c3c9cf86ac27deb4fa7c8686b5723c8e6))
* `예약 경매 조회 (GET /karaoke/{id})` Endpoint ([d9618e5](https://github.com/scfs-miraepass/BACKEND/commit/d9618e5b479d0004ad20520255dea4cd8686ace9))
* Core `Karaoke.set_status` 함수 추가 ([65b2a65](https://github.com/scfs-miraepass/BACKEND/commit/65b2a65d9fbd3336d96a5b78be5a748199a97f11))
* Core `KaraokeParty` 객체 기본 베이스 추가 ([0a3f584](https://github.com/scfs-miraepass/BACKEND/commit/0a3f584645b4ada6ef87c92d8e9bc0dca94f4f8b))
* Core `KaraokeParty` 소속 유저와 해산 여부 설정 함수 추가 ([75e2bd4](https://github.com/scfs-miraepass/BACKEND/commit/75e2bd44a6c87ac871b6181b72df34d60dcad34a))
* Core Karaoke 파트 폴더 구조 변경 및 KaraokeBid 기본 코드 추가 ([01ef422](https://github.com/scfs-miraepass/BACKEND/commit/01ef422c0c30c107ec2539c503cc8729007994a2))
* Core Karaoke.delete 추가 ([be0741b](https://github.com/scfs-miraepass/BACKEND/commit/be0741bd0eb98a1b94b68657736c8ef3d3f554b8))
* **core:** `KaraokeMember.get_member` 추가 ([5a4ac7d](https://github.com/scfs-miraepass/BACKEND/commit/5a4ac7dad599fc061da7b48e7da5de66e9adb367))
* **core:** `KaraokeMember.get_party` 추가 ([e998557](https://github.com/scfs-miraepass/BACKEND/commit/e998557b08d7f35f8fc90a523ab23b12cdca38a2))
* **core:** `KaraokeMember.leave` 추가 ([29db7b0](https://github.com/scfs-miraepass/BACKEND/commit/29db7b059f9f0d7b089d30b40ee27f24c3182ce0))
* **core:** User, 대기 중인 파티 초대, `get_karaoke_member` 함수 추가 ([0d3ccbf](https://github.com/scfs-miraepass/BACKEND/commit/0d3ccbfd41d1fca75e0dd6dc8a303977c7baf396))
* **core:** 각 오브젝트 객체에 `get_by_id`을 추가하여 client및 내부에서도 캐시를 이용한 Getting를 할 수 있도록 구성 ([cc0b170](https://github.com/scfs-miraepass/BACKEND/commit/cc0b170b50059f358c0a45f062d1493adbaf39a8))
* **core:** 노래방 경매 시작/종료 자동 처리 스케줄 추가 ([b065ade](https://github.com/scfs-miraepass/BACKEND/commit/b065ade123b42f1c0a94c66ee8288a7e03c48b77))
* **core:** 노래방 파티원 초대/퇴장, `get_member_models` 함수 추가 ([2a506b6](https://github.com/scfs-miraepass/BACKEND/commit/2a506b606f657f3b88dfd30981afa2d629942fc2))
* **core:** 새로운 파티 생성 함수 추가 ([5237034](https://github.com/scfs-miraepass/BACKEND/commit/5237034c921626834507190bf9eab140b3b2361f))
* **core:** 유저가 참여중인(또는 리더인) 파티 가져오는 함수 추가 ([15d6f16](https://github.com/scfs-miraepass/BACKEND/commit/15d6f1696b2f3489f357d1e7693e7716227b42ef))
* **core:** 입찰 취소(KaraokeBid.cancel) 함수 추가 ([dfdca89](https://github.com/scfs-miraepass/BACKEND/commit/dfdca89229977c9df21b81ac5664ec9a22d749fc))
* **core:** 파티 멤버 초대 및 초대 수락/거절 ([ef5eb89](https://github.com/scfs-miraepass/BACKEND/commit/ef5eb8984d073726cfd2d4ba31731b670102a047))
* **core:** 필요한 곳에 노래방 관련 로그 추가 ([acae176](https://github.com/scfs-miraepass/BACKEND/commit/acae17690c0ae36138c7e30cc52de7b2a077e8a2))
* Endpoint 파일 생성 ([10591f0](https://github.com/scfs-miraepass/BACKEND/commit/10591f0dd558475ba861a7de0d525faed04ef3de))
* **endpoints:** 노래방 목록 및 노래방 예약에 최고가 추가 ([a280077](https://github.com/scfs-miraepass/BACKEND/commit/a280077d229bcfea1dce4dac36b58e4324445278))
* **endpoints:** 노래방 예약 경매 입찰, 파티 초대, 초대 응답(수락/거절) Endpoint 추가 ([1144278](https://github.com/scfs-miraepass/BACKEND/commit/11442780a63721c34f00c8b309786f05cc297019))
* **endpoints:** 실시간 통신용 웹 소켓 ([fbfc8c3](https://github.com/scfs-miraepass/BACKEND/commit/fbfc8c38591fedab00f3f8b70dd8837eb838b1a0))
* **endpoints:** 예약 경매 파티 생성 Endpoint ([026961e](https://github.com/scfs-miraepass/BACKEND/commit/026961e485c2e1052dc2776ee1cd40388f515503))
* **endpoints:** 파티 조회/탈퇴/강퇴 Endpoint 추가 및 삭제시 최고 입찰 환불 처리 ([714c877](https://github.com/scfs-miraepass/BACKEND/commit/714c877ccbc236c76bf181c0cd0a0ccc3536146d))
* **endpoints:** 파티장 파티 자진 해산 Endpoint 추가 ([53411f6](https://github.com/scfs-miraepass/BACKEND/commit/53411f6e41776de22916bc80b89764141a2542b8))
* KaraokeBid.party_bidder 제거, party_id 추가 ([47607b6](https://github.com/scfs-miraepass/BACKEND/commit/47607b6f855584b7896ed21ae6ee5af4366e6654))
* KaraokeParty, KaraokeMember 데이터 스키마 추가 ([ef105fc](https://github.com/scfs-miraepass/BACKEND/commit/ef105fcaf2d7fac6075b78c3da1300808613eaf0))
* **karaoke:** 경매 남은시간 sync 브로드캐스트 및 입찰 내역 캐시 파싱 수정 ([149085b](https://github.com/scfs-miraepass/BACKEND/commit/149085b2a37b91e50186580664edbc1ae68252ed))
* **karaoke:** 웹소켓 및 Redis Pub/Sub 로깅 추가 ([045a312](https://github.com/scfs-miraepass/BACKEND/commit/045a31245a6c4f139bb6de48bdd77e8b0b0b834d))
* **karaoke:** 입찰 기록 웹소켓 응답에 입찰자 User 정보 포함, 최신 5건만 전송 ([6ed87b1](https://github.com/scfs-miraepass/BACKEND/commit/6ed87b140d44af6a52f5c96a89ef1744078cb763))
* **karaoke:** 최종 입찰 조회 API에 파티 입찰시 파티 멤버 목록 포함 ([340520b](https://github.com/scfs-miraepass/BACKEND/commit/340520b4a93b7da6f90c22cec2bef5570c6d160c))
* 노래방 경매 생성 Endpoint ([20a2204](https://github.com/scfs-miraepass/BACKEND/commit/20a2204239a3650dc2501e1eef9e79f605c2b6d0))
* 노래방 경매와 관련되 권한들 추가 ([7939f3a](https://github.com/scfs-miraepass/BACKEND/commit/7939f3afb70b0020f22f26facda259cd48ae4f85))
* 노래방 관련 스키마들, Class 이름 복수사로 변경 ([3fb98f4](https://github.com/scfs-miraepass/BACKEND/commit/3fb98f4cf088714f6e4533a81592779870c84fb8))
* 노래방 예약(Karaoke) 데이터 스키마 추가 ([71f5f30](https://github.com/scfs-miraepass/BACKEND/commit/71f5f30d2ce2c07e7ccdf8207ae727f29220d280))
* 노래방 파티 조회 Endpoint 추가 및 초대/입찰 검증 강화 ([f7aa2e8](https://github.com/scfs-miraepass/BACKEND/commit/f7aa2e893e791c68deb4ec0a7c98e3d92148a30f))
* 노래방(Karaoke) 예약 서비스 ([226ab45](https://github.com/scfs-miraepass/BACKEND/commit/226ab45af95cfcc07e7f4d505822f01b3160df2f))
* 예약 경매 목록 조회 (GET /karaoke) Endpoint 완성 ([e7d79d1](https://github.com/scfs-miraepass/BACKEND/commit/e7d79d138d39bb830dcba0d0b61a890df7e7f887))
* 예약 경매 입찰(KaraokeBid) 데이터 스키마 추가 ([24b7f45](https://github.com/scfs-miraepass/BACKEND/commit/24b7f45913b26aec7bdc050c301195f41e79b7a1))
* 입찰 함수(add_bid) 완성 ([d9a9eb5](https://github.com/scfs-miraepass/BACKEND/commit/d9a9eb57d13d2344e25c957ea0fd7aba6b8acdca))
* 포인트 기록 종류에 `노래방 입찰, 입찰 취소` 추가 ([c7e6e16](https://github.com/scfs-miraepass/BACKEND/commit/c7e6e16bef3fd721ceedd887625a6659a0efa293))


### Performance Improvements

* **core:** 멤버 강퇴시 set_dispersed 를 사용하도록 변경 ([e1ec93a](https://github.com/scfs-miraepass/BACKEND/commit/e1ec93ac450f97c694c74ae2eb501cede8ddc8db))
* KaraokeStatus 값 수정 ([1027b25](https://github.com/scfs-miraepass/BACKEND/commit/1027b25bcde236bf78b3f9583f87edfc5e545fc9))

# [1.10.0](https://github.com/scfs-miraepass/BACKEND/compare/v1.9.1...v1.10.0) (2026-08-28)


### Bug Fixes

* 관리자 Endpoint에서 기존 제거된 `clear_search_cache` 를 사용하여 발생하는 오류 해결 ([f84bff7](https://github.com/scfs-miraepass/BACKEND/commit/f84bff724193b16390064db25367c0a1276b262a))
* 실제 포인트 기록에 사용하는 redis key가 달라, 업데이트가 안되는 현상 해결 ([69aaeb6](https://github.com/scfs-miraepass/BACKEND/commit/69aaeb63da784021041b8a34689183c59465e48c))


### Features

* **cli:** 사용자 생성시, 기본 권한까지 추가되도록 처리 ([b565cac](https://github.com/scfs-miraepass/BACKEND/commit/b565cac7b61a2076f01e671a4514f8c021160cdc))
* 데이터베이스 로그 콘솔 표기 환경변수로 따로 분리 ([c77cf0a](https://github.com/scfs-miraepass/BACKEND/commit/c77cf0a8680c43aa42a461e06fc80d8198da2eee))

# [1.10.0-dev.3](https://github.com/scfs-miraepass/BACKEND/compare/v1.10.0-dev.2...v1.10.0-dev.3) (2026-08-28)


### Bug Fixes

* 실제 포인트 기록에 사용하는 redis key가 달라, 업데이트가 안되는 현상 해결 ([69aaeb6](https://github.com/scfs-miraepass/BACKEND/commit/69aaeb63da784021041b8a34689183c59465e48c))

# [1.10.0-dev.2](https://github.com/scfs-miraepass/BACKEND/compare/v1.10.0-dev.1...v1.10.0-dev.2) (2026-08-28)


### Features

* **cli:** 사용자 생성시, 기본 권한까지 추가되도록 처리 ([b565cac](https://github.com/scfs-miraepass/BACKEND/commit/b565cac7b61a2076f01e671a4514f8c021160cdc))

# [1.10.0-dev.1](https://github.com/scfs-miraepass/BACKEND/compare/v1.9.2-dev.1...v1.10.0-dev.1) (2026-08-28)


### Features

* 데이터베이스 로그 콘솔 표기 환경변수로 따로 분리 ([c77cf0a](https://github.com/scfs-miraepass/BACKEND/commit/c77cf0a8680c43aa42a461e06fc80d8198da2eee))

## [1.9.2-dev.1](https://github.com/scfs-miraepass/BACKEND/compare/v1.9.1...v1.9.2-dev.1) (2026-08-18)


### Bug Fixes

* 관리자 Endpoint에서 기존 제거된 `clear_search_cache` 를 사용하여 발생하는 오류 해결 ([f84bff7](https://github.com/scfs-miraepass/BACKEND/commit/f84bff724193b16390064db25367c0a1276b262a))

## [1.9.1](https://github.com/scfs-miraepass/BACKEND/compare/v1.9.0...v1.9.1) (2026-08-18)


### Bug Fixes

* 관리자 Endpoint에서 기존 제거된 `clear_search_cache` 를 사용하여 발생하는 오류 해결 ([#10](https://github.com/scfs-miraepass/BACKEND/issues/10)) ([1e2ab81](https://github.com/scfs-miraepass/BACKEND/commit/1e2ab81cd15f129591d6eafec6b8849e51f4045d))

## [1.9.1-dev.1](https://github.com/scfs-miraepass/BACKEND/compare/v1.9.0...v1.9.1-dev.1) (2026-08-18)


### Bug Fixes

* 관리자 Endpoint에서 기존 제거된 `clear_search_cache` 를 사용하여 발생하는 오류 해결 ([f84bff7](https://github.com/scfs-miraepass/BACKEND/commit/f84bff724193b16390064db25367c0a1276b262a))

# [1.9.0](https://github.com/scfs-miraepass/BACKEND/compare/v1.8.0...v1.9.0) (2026-08-18)


### Bug Fixes

* 관리자 사용자 수정시 에러가 발생하는 현생 해결 ([166033a](https://github.com/scfs-miraepass/BACKEND/commit/166033a3efbcb27cfb61344a7f526b7ef04c027f))


### Features

* 사용자 수정시, 사용자 관련 검색 캐시 삭제 ([5de3237](https://github.com/scfs-miraepass/BACKEND/commit/5de32374d31386fe1e93b9f0b5fccda0b4136536))
* 세부적인 권한 설정 기능 ([#4](https://github.com/scfs-miraepass/BACKEND/issues/4)) ([ee72636](https://github.com/scfs-miraepass/BACKEND/commit/ee72636b85eb2a050e9fe5fb0b52e7191ab472d0)), closes [#3](https://github.com/scfs-miraepass/BACKEND/issues/3)
* 유저 관리 Endpoint ([#9](https://github.com/scfs-miraepass/BACKEND/issues/9)) ([d45d105](https://github.com/scfs-miraepass/BACKEND/commit/d45d1051d6a74bf33dcc407907d754756371910f))
* 특정 포인트를 가져오는 Endpoint 추가 ([bd52263](https://github.com/scfs-miraepass/BACKEND/commit/bd522636a3b8a3fe4fd63d43a41f3a17c771cf92))


### Performance Improvements

* 교사 포인트 지급 제한을 그냥 포인트 지급 제한으로 수정 ([20c890d](https://github.com/scfs-miraepass/BACKEND/commit/20c890d391d2e2c8227a767ca5b9f22aef10353b))
* 유저 처리시 검색 캐시 전체적으로 삭제하는 것으로 변경 ([2842acc](https://github.com/scfs-miraepass/BACKEND/commit/2842acc55b3d9533b0135ff8d594f0cf5fd5a9f0))

# [1.8.0](https://git.rldn.xyz/scfs.miraepass/backend/compare/v1.7.0...v1.8.0) (2026-07-15)


### Bug Fixes

* redis가 정상적으로 초기화 되지 않던 현상 해결 ([46e0358](https://git.rldn.xyz/scfs.miraepass/backend/commit/46e03582a756786ba9c6c21e3269557e9da16ada))
* ServiceCore에서 _payload가 불러와지지 않아 AttributeError가 발생하는 현상 해결 ([47ab770](https://git.rldn.xyz/scfs.miraepass/backend/commit/47ab770ecd02869811e927aa998791c4e4bee26e))
* 서비스 계정 로그인시, 서비스 계정이 아닌 타입의 계정 ID 입력시 에러가 발생하는 현상 해결 ([66875fb](https://git.rldn.xyz/scfs.miraepass/backend/commit/66875fb44024cb477823d37acbcd9ea9abfa6498))
* 스탬프가 정상적으로 되지 않던 현상 및 스탬프 오타 정정 등 ([e928090](https://git.rldn.xyz/scfs.miraepass/backend/commit/e928090db055bcc739a3beebcbbd57492a6ed17b))
* 포인트 지급시 포인트 기록 ID가 정상적으로 로그에 뜨지 않는 현상 해결 ([7300fb3](https://git.rldn.xyz/scfs.miraepass/backend/commit/7300fb3daa8d7d3257993ae72a5d745097b92b12))
* 포인트 지급시 포인트 기록 ID가 정상적으로 로그에 뜨지 않는 현상 해결 ([237e490](https://git.rldn.xyz/scfs.miraepass/backend/commit/237e490c12427fea8503c536c3fa6379af375be3))


### Features

* CLI, ImportUsers Client 작업 ([26ab473](https://git.rldn.xyz/scfs.miraepass/backend/commit/26ab473e7c2d35e69a30cd800a3ed27959da171f))
* Client에서 유저를 가지고 올때, cache를 사용하는 옵션 추가 ([f37e139](https://git.rldn.xyz/scfs.miraepass/backend/commit/f37e139daa7ca793409851ddf91c40bace657eef))
* Client에서 유저를 가지고 올때, lock 옵션 추가 ([186659d](https://git.rldn.xyz/scfs.miraepass/backend/commit/186659da79697e287116e33226d74f46c24ef148))
* **CLI:** 한국어 패치 ([3497b29](https://git.rldn.xyz/scfs.miraepass/backend/commit/3497b297e25df908c19b5ab8bead2198c3639861))
* point API Client 사용 ([99832e9](https://git.rldn.xyz/scfs.miraepass/backend/commit/99832e9c0e906996001871e62a832f41f95fa1fe))
* 검색 API client 적용 ([aa7bde6](https://git.rldn.xyz/scfs.miraepass/backend/commit/aa7bde6a4b2d2e607959bedcb5515b5661eb0422))
* 게시글 API Client 적용 ([b74fe62](https://git.rldn.xyz/scfs.miraepass/backend/commit/b74fe62fe6abb4594916b20ac584c90141a2991c))
* 게시글 객체 기초 및 게시글 삭제, 게시글 생성 ([8f9694f](https://git.rldn.xyz/scfs.miraepass/backend/commit/8f9694fc32b12cf35c66f0d30b588785fe46b325))
* 게시글 내용 데이터 가져오는 함수 추가 ([28e4f3b](https://git.rldn.xyz/scfs.miraepass/backend/commit/28e4f3b200cc012126ac7f940a45b3a0efab92a8))
* 관리자 API client 적용 ([d8fd055](https://git.rldn.xyz/scfs.miraepass/backend/commit/d8fd05596c0e89d3f61f618b9134d25ee319f04f))
* 스템프 시스템 ([928e1b4](https://git.rldn.xyz/scfs.miraepass/backend/commit/928e1b4d72b12ca229b416326803c57faf97db59))
* 아키텍처 변경에 따른 dependency.py 수정 ([e80d780](https://git.rldn.xyz/scfs.miraepass/backend/commit/e80d780af0103aeb153c8a43e96b746d5b0dec77))
* 유저 검색용 처리 로그에 LoggerCore 적용 ([ceda9ae](https://git.rldn.xyz/scfs.miraepass/backend/commit/ceda9ae8b9f9b4e03fbc67fd5d2c0d2a545c58ea))
* 유저 아키텍쳐 기반 구성 및 auth 에 필요한 함수 추가 ([88f910f](https://git.rldn.xyz/scfs.miraepass/backend/commit/88f910f7cb1adba57d3c0f6fe503f6ee7993ba2b))
* 인증 API, 세션 검증 Dep 유저 캐시 수정 ([37428b6](https://git.rldn.xyz/scfs.miraepass/backend/commit/37428b6db4e4669b926483310ea5f4674caade58))
* 퀘스트 API Client 적용 ([9b2db17](https://git.rldn.xyz/scfs.miraepass/backend/commit/9b2db17ea2e66427998c5237f0df4b4c84283fdd))
* 퀘스트 객체 가져오기 함수 추가 ([8d8a317](https://git.rldn.xyz/scfs.miraepass/backend/commit/8d8a3173b5131bf239fa635fcd41f3db7abc36b8))
* 퀘스트 삭제, 수정, 완료 등 관련 함수 추가 ([2281cec](https://git.rldn.xyz/scfs.miraepass/backend/commit/2281cec49c2f233db027beb4ff37acffb17ac457))
* 퀘스트 생성및 퀘스트 객체 생성 ([26f7296](https://git.rldn.xyz/scfs.miraepass/backend/commit/26f72961dcfc242e2301760127c05278676975b3))
* 포인트 기록 추가/삭제 ([44affdc](https://git.rldn.xyz/scfs.miraepass/backend/commit/44affdc83db5922be0cfc747d08e15abd6bca093))
* 포인트 지급/차감 ([8916bab](https://git.rldn.xyz/scfs.miraepass/backend/commit/8916bab06b57b35385e3c1e8cf4e6234b1c05f42))
* 프로젝트 중앙 아키텍처 구성 ([2ca778b](https://git.rldn.xyz/scfs.miraepass/backend/commit/2ca778b39d35da44b79f6d546b9adc59fba849dd))

# [1.7.0](https://git.rldn.xyz/scfs.miraepass/backend/compare/v1.6.1...v1.7.0) (2026-06-25)


### Bug Fixes

* **point:** 관리자계정 포인트 제한시 None 으로 인한 버그 수정 ([6993321](https://git.rldn.xyz/scfs.miraepass/backend/commit/699332155df4633bfb1e7341b83a0765fedae064))


### Features

* **point:** 포인트 교사 랭킹, 관리자 계정 랭킹에서 제외 ([54e4252](https://git.rldn.xyz/scfs.miraepass/backend/commit/54e4252035bc56af81e4269a846e754ad179509d))
* 관리자 계정 포인트 학생 지급이 본인에게 지급하는트 포인트 동일하게 주당 1000 포인트 제한 ([0e33178](https://git.rldn.xyz/scfs.miraepass/backend/commit/0e3317827581d3e5954af3b190239e328223c2a6))

## [1.6.1](https://git.rldn.xyz/scfs.miraepass/backend/compare/v1.6.0...v1.6.1) (2026-06-23)


### Bug Fixes

* **point:** 관리자 권한 유저가 포인트 지급시 제한이 0으로 응답하여, 지급하지 못하는 현상  [skip ci] ([b46b52d](https://git.rldn.xyz/scfs.miraepass/backend/commit/b46b52d841a49ef7a5e73cea4a82fc37d5a51357))

# [1.6.0](https://git.rldn.xyz/scfs.miraepass/backend/compare/v1.5.0...v1.6.0) (2026-06-23)


### Bug Fixes

* **database:** 게시글 관련 스키마 메타데이터에 등록되지 않는 현상 해결 ([ec30bfa](https://git.rldn.xyz/scfs.miraepass/backend/commit/ec30bfa057d3f1d3051fd45430ddb836bc128603))
* 랭크 Endpoint들의 rank 순위가 포함되지 않던 문제 해결 ([9f8d76a](https://git.rldn.xyz/scfs.miraepass/backend/commit/9f8d76a9c55f74c05f4b1b0b4775a3ffd1cdbb3e))
* 아예 실행조차 안되는 현상 해결 ([88b03c5](https://git.rldn.xyz/scfs.miraepass/backend/commit/88b03c5675a57903244a9e924dfdc91169a369c7))


### Features

* **database:** b4da6e37f3a6 마이그레이션 생성 ([6abb057](https://git.rldn.xyz/scfs.miraepass/backend/commit/6abb057b951e5e1ad3cc0aab23a6adb2c0a8b389))
* **point:** 포인트 차감및 지급 Endpoint Body에 기록 메모(지급/차감시 사유) 추가 ([ae2e524](https://git.rldn.xyz/scfs.miraepass/backend/commit/ae2e5247046a1ad2b377ddba04cfdbf221b37892))
* 게시글 시스템 ([4fc9a43](https://git.rldn.xyz/scfs.miraepass/backend/commit/4fc9a4303497b954f063a143c5da6cf5536ecfad))
* 퀘스트 시스템 ([84aeb25](https://git.rldn.xyz/scfs.miraepass/backend/commit/84aeb256942b3cab339937f13fa0c2a5f75b74f1))
* 포인트 limit 관련에 관리자의 경우 항상 0으로 표기하도록 수정 ([b539d5b](https://git.rldn.xyz/scfs.miraepass/backend/commit/b539d5b302d36ac295dfade5ffd9e6344bf6cf75))


### Performance Improvements

* DB 마이그레이션을 고려해 PointHistoryType 검증 자체는 Python 단에서 DB는 String으로 처리 [skip ci] ([dec38fb](https://git.rldn.xyz/scfs.miraepass/backend/commit/dec38fb7a97315c50ec0b4b8fcee660948eb19df))

# [1.5.0](https://git.rldn.xyz/scfs.miraepass/backend/compare/v1.4.3...v1.5.0) (2026-06-01)


### Features

* **point:** 포인트 변화 처리를 위한 x-cached 헤더 추가 ([69b58cd](https://git.rldn.xyz/scfs.miraepass/backend/commit/69b58cdb71f31c1f6cdbd289df76d23c9dc0c733))
* 학생, 교사 포인트 제한 1000으로 변경 ([be8e3d7](https://git.rldn.xyz/scfs.miraepass/backend/commit/be8e3d7431fc5d7e1c4ea353a57c5fcb8bf4c9ac)), closes [#20](https://git.rldn.xyz/scfs.miraepass/backend/issues/20)

## [1.4.3](https://git.rldn.xyz/scfs.miraepass/backend/compare/v1.4.2...v1.4.3) (2026-05-26)


### Bug Fixes

* **ci:** backend 실행 명령어 수정 ([e00da0f](https://git.rldn.xyz/scfs.miraepass/backend/commit/e00da0f89905b8c256aaa3d8070d2d1a2bf8834d))

## [1.4.2](https://git.rldn.xyz/scfs.miraepass/backend/compare/v1.4.1...v1.4.2) (2026-05-26)


### Bug Fixes

* 검색에서 필터가 다름에도 캐시는 동일하게 적용되는 현상 수정 ([fd7b110](https://git.rldn.xyz/scfs.miraepass/backend/commit/fd7b11003b516c0df17f4e65d38522eedf772772))

## [1.4.1](https://git.rldn.xyz/scfs.miraepass/backend/compare/v1.4.0...v1.4.1) (2026-05-22)


### Bug Fixes

* 도커 이미지에 tools포함 하도록 수정 ([8acb4c9](https://git.rldn.xyz/scfs.miraepass/backend/commit/8acb4c9bc0c26d9e73da4d627598cda439b16a3c))

# [1.4.0](https://git.rldn.xyz/scfs.miraepass/backend/compare/v1.3.0...v1.4.0) (2026-05-21)


### Features

* **point:** 교사, 학생 누적 포인트 순위 추가 ([8fc0a21](https://git.rldn.xyz/scfs.miraepass/backend/commit/8fc0a2196ca8799d397c3714e6b037cfc8eed123)), closes [#18](https://git.rldn.xyz/scfs.miraepass/backend/issues/18)
* **point:** 포인트 조회 Endpoint 권한 검사 추가 ([2dca93c](https://git.rldn.xyz/scfs.miraepass/backend/commit/2dca93c84ee96997e2b2db0dd11ecaeb9598d686)), closes [#17](https://git.rldn.xyz/scfs.miraepass/backend/issues/17)
* **point:** 학생 하루 포인트 지급 한도 추가 ([65c8b0f](https://git.rldn.xyz/scfs.miraepass/backend/commit/65c8b0fd4742c96bbaa5b49f597651448b0a7517)), closes [#19](https://git.rldn.xyz/scfs.miraepass/backend/issues/19)

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
