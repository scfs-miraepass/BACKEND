"""
Redis Key 레지스트리

프로젝트에서 사용하는 모든 Redis Key(및 Pub/Sub 채널)는 이 파일의 `Keys`에 정의합니다.
Key 문자열을 코드에 직접 작성하지 않고, 아래와 같이 정의된 Key를 호출해 사용합니다.

    key = Keys.User.ITEM(user_id=user.id)       # -> BoundKey("user:item:1101"), TTL 포함
    await client.redis.set(key, value)          # TTL은 Key에 정의된 값이 기본으로 사용됨
    await client.redis.delete_pattern(Keys.Karaoke.USER_PARTY.pattern(karaoke_id=1))

명명 규칙: `{도메인}:{종류}:{파라미터...}`
- 첫 두 구간은 고정 문자열, 이후 구간은 `{파라미터}` 하나씩으로 작성합니다.
- 단, `session:{session_id}`는 기존 로그인 세션 유지를 위해 예외로 기존 형태를 유지합니다.

버전 Key (목록 캐시)
- 자주 무효화되는 목록 캐시는 `{ver}` 파라미터를 가지며, 같은 도메인의 `VERSION` Key 값을 사용합니다.
- 무효화할 때는 패턴 삭제 대신 `bump_version`으로 버전만 올리고, 이전 버전의 캐시는 TTL로 만료되도록 둡니다.
- `VERSION` Key의 TTL은 목록 캐시의 TTL보다 길거나 같아야 합니다. (버전 Key가 만료되어 0부터 다시 시작해도,
  같은 버전 번호를 쓰던 예전 캐시는 이미 만료되어 있도록 보장)

    ver = await client.redis.get_version(Keys.Ranking.VERSION(type="student"))
    key = Keys.Ranking.PAGE(type="student", ver=ver, ...)

전체 목록은 `python tools/cli.py redis-keys` 로 확인할 수 있습니다.
"""

from re import compile
from dataclasses import dataclass, field
from string import Formatter

from .config import settings

MINUTE = 60
HOUR = 60 * MINUTE
DAY = 24 * HOUR

_GLOB_SPECIAL = compile(r"([*?\[\]\\])")


class BoundKey(str):
    """
    파라미터가 모두 채워진 실제 Redis Key.

    `str`을 상속하므로 pipeline, publish, pubsub 등 Redis 원본 API에도 그대로 전달할 수 있습니다.
    """

    ttl: int | None

    def __new__(cls, value: str, ttl: int | None = None):
        obj = super().__new__(cls, value)
        setattr(obj, "ttl", ttl)
        return obj

    def __init__(self, value: str, ttl: int | None = None):
        super().__init__()

    @classmethod
    def unchecked(cls, value: str) -> BoundKey:
        """
        레지스트리를 거치지 않은 임의의 Key를 만듭니다.
        **CLI 등 디버깅 도구에서만 사용합니다.**
        """
        return cls(value)


class KeyPattern(str):
    """`delete_pattern`에 전달하는 glob 패턴"""

    @classmethod
    def unchecked(cls, value: str) -> KeyPattern:
        """
        레지스트리를 거치지 않은 임의의 패턴을 만듭니다.
        **CLI 등 디버깅 도구에서만 사용합니다.**
        """
        return cls(value)


@dataclass(frozen=True, slots=True)
class RedisKey:
    template: str
    ttl: int | None
    """기본 TTL(초). None인 경우 저장 시 TTL을 직접 지정해야 합니다."""
    description: str
    fields: tuple[str, ...] = field(init=False)

    def __post_init__(self):
        names = tuple(name for _, name, _, _ in Formatter().parse(self.template) if name)
        object.__setattr__(self, "fields", names)

    def _check_params(self, params: dict, *, require_all: bool):
        unknown = set(params) - set(self.fields)
        if unknown:
            raise TypeError(f"'{self.template}'에 없는 파라미터입니다: {sorted(unknown)}")
        missing = set(self.fields) - set(params)
        if require_all and missing:
            raise TypeError(f"'{self.template}'에 필요한 파라미터가 없습니다: {sorted(missing)}")

    def __call__(self, **params) -> BoundKey:
        self._check_params(params, require_all=True)
        return BoundKey(self.template.format(**params), self.ttl)

    def pattern(self, **params) -> KeyPattern:
        """
        일부 파라미터만 채운 삭제용 패턴을 만듭니다. 채우지 않은 파라미터는 `*`로 대체됩니다.

        예) `Keys.Karaoke.USER_PARTY.pattern(karaoke_id=1)` -> `karaoke:user_party:1:*`
        """
        self._check_params(params, require_all=False)
        values = {
            name: _GLOB_SPECIAL.sub(r"\\\1", str(params[name])) if name in params else "*" for name in self.fields
        }
        return KeyPattern(self.template.format(**values))


class Keys:
    class Auth:
        SESSION = RedisKey(
            "session:{session_id}",
            ttl=settings.service.session.expire_seconds,
            description="현재 로그인한 세션 ID(session_id)를 통해 로그인된 유저의 ID를 획득",
        )
        USER_SESSIONS = RedisKey(
            "session:user:{user_id}",
            ttl=settings.service.session.expire_seconds,
            description="유저(user_id)의 로그인 세션 ID 목록",
        )

    class User:
        ITEM = RedisKey("user:item:{user_id}", ttl=settings.service.session.expire_seconds, description="유저 데이터")

    class PointLimit:
        GRANT = RedisKey(
            "point_limit:grant:{user_id}:{week}",
            ttl=None,
            description="교사(user_id)가 해당 주(week; 월요일 시작일)에 사용한 지급/보상 한도",
        )
        STUDENT = RedisKey(
            "point_limit:student:{user_id}:{date}",
            ttl=None,
            description="학생(user_id)이 하루동안(date) 받은 포인트",
        )

    class PointHistory:
        ITEM = RedisKey("point_history:item:{history_id}", ttl=5 * MINUTE, description="포인트 기록(history_id) 데이터")
        COUNT = RedisKey("point_history:count:{user_id}", ttl=DAY, description="유저(user_id)의 포인트 기록 총 개수")
        VERSION = RedisKey(
            "point_history:ver:{user_id}", ttl=HOUR, description="유저(user_id)의 포인트 기록 페이지 캐시 버전"
        )
        PAGE = RedisKey(
            "point_history:page:{user_id}:{ver}:{limit}:{offset}",
            ttl=HOUR,
            description="""
                유저(user_id)의 포인트 기록 페이지
                - ver: 버전
                - limit: 한 페이지당 최대 데이터 개수
                - offset: 현재 페이지 위치
            """,
        )

    class Ranking:
        COUNT = RedisKey("ranking:count:{type}", ttl=5 * MINUTE, description="학생/교사(type) 전체 랭킹 데이터 개수")
        VERSION = RedisKey("ranking:ver:{type}", ttl=HOUR, description="학생/교사(type) 랭킹 페이지 캐시 버전")
        PAGE = RedisKey(
            "ranking:page:{type}:{ver}:{period}:{week}:{limit}:{offset}",
            ttl=5 * MINUTE,
            description="""
                랭킹 데이터
                - type: 교사/학생
                - ver: 버전
                - period: 랭킹 기간을 뜻합니다. (total / weekly)
                - week: all의 경우 일자 상관없는 랭킹, 이며 한 주의 경우 주의 시작일의 ISO 포멧 값
                - limit: 한 페이지당 최대 데이터 개수
                - offset: 현재 페이지 위치
            """,
        )

    class Search:
        USERS = RedisKey(
            "search:users:{query}:{types}",
            ttl=5 * MINUTE,
            description="""
                유저 검색 결과 (유저 ID 목록)
                - query: 검색어
                - types: 타입 필터링이 있는 경우 타입 필터링이 ,으로 구분해 작성됩니다. 없는경우 공란입니다.
            """,
        )

    class Post:
        ITEM = RedisKey("post:item:{post_id}", ttl=DAY, description="게시글(post_id) 데이터")
        COUNT = RedisKey("post:count", ttl=DAY, description="게시글 총 개수")
        VERSION = RedisKey("post:ver", ttl=DAY, description="게시글 목록 페이지 캐시 버전")
        PAGE = RedisKey("post:page:{ver}:{page}:{size}", ttl=DAY, description="게시글 목록 페이지")

    class Quest:
        ITEM = RedisKey("quest:item:{quest_id}", ttl=5 * MINUTE, description="퀘스트(quest_id) 대이터")
        COUNT = RedisKey("quest:count", ttl=5 * MINUTE, description="퀘스트 총 개수")
        VERSION = RedisKey("quest:ver", ttl=HOUR, description="퀘스트 목록 페이지 캐시 버전")
        PAGE = RedisKey("quest:page:{ver}:{limit}:{offset}", ttl=5 * MINUTE, description="퀘스트 목록 페이지")

    class Karaoke:
        ITEM = RedisKey("karaoke:item:{karaoke_id}", ttl=5 * MINUTE, description="노래방(karaoke_id) 경매 데이터")
        LIST = RedisKey("karaoke:list:{date}", ttl=5 * MINUTE, description="date(YYYY-MM-DD) 날의 노래방 경매 목록")
        HIGHEST = RedisKey(
            "karaoke:highest:{karaoke_id}",
            ttl=None,
            description="경매(karaoke_id) 최고 입찰. TTL은 경매 종료 시각 기준으로 자동으로 지정됩니다.",
        )
        BIDS = RedisKey("karaoke:bids:{karaoke_id}", ttl=5 * MINUTE, description="경매(karaoke_id) 입찰 기록")
        USER_PARTY = RedisKey(
            "karaoke:user_party:{karaoke_id}:{user_id}",
            ttl=5 * MINUTE,
            description="경매(karaoke_id)에서 유저(user_id)가 소속된(리더 포함) 파티 ID",
        )
        PARTY = RedisKey("karaoke:party:{party_id}", ttl=DAY, description="노래방(party_id) 파티 데이터")
        PARTY_MEMBERS = RedisKey(
            "karaoke:party_members:{party_id}", ttl=DAY, description="파티(party_id) 멤버 목록 (초대 수락 완료)"
        )
        PARTY_MEMBER = RedisKey(
            "karaoke:party_member:{party_id}:{user_id}",
            ttl=HOUR,
            description="파티(party_id) 멤버(user_id) 데이터 (초대 대기 포함)",
        )
        CHANNEL = RedisKey("karaoke:channel:{karaoke_id}", ttl=None, description="경매 이벤트 Pub/Sub 채널")

    @classmethod
    def all(cls) -> dict[str, RedisKey]:
        """`{도메인}.{이름}` 형태의 이름으로 모든 Key를 반환합니다."""
        result: dict[str, RedisKey] = {}
        for group_name, group in vars(cls).items():
            if not isinstance(group, type):
                continue
            for key_name, key in vars(group).items():
                if isinstance(key, RedisKey):
                    result[f"{group_name}.{key_name}"] = key
        return result


def _validate_registry():
    """
    Key 정의 오류(형식 위반, 다른 Key와 겹칠 수 있는 템플릿)를 서버 시작 시점에 확인합니다.
    두 템플릿이 같은 실제 Key를 만들 수 있으면 캐시가 섞이거나 패턴 삭제 범위가 겹치므로 허용하지 않습니다.
    """
    segments: dict[str, list[str | None]] = {}
    for name, key in Keys.all().items():
        parsed: list[str | None] = []
        for segment in key.template.split(":"):
            if segment.startswith("{") and segment.endswith("}") and segment[1:-1] in key.fields:
                parsed.append(None)  # 파라미터 구간
            elif "{" in segment or "}" in segment or not segment:
                raise ValueError(f"{name}: 구간에는 고정 문자열 또는 파라미터 하나만 올 수 있습니다. ({key.template})")
            else:
                parsed.append(segment)
        if parsed[0] is None:
            raise ValueError(f"{name}: 첫 구간은 도메인 이름이어야 합니다. ({key.template})")
        if len(set(key.fields)) != len(key.fields):
            raise ValueError(f"{name}: 파라미터 이름이 중복됩니다. ({key.template})")
        segments[name] = parsed

    # 버전 Key를 사용하는 목록 캐시는 같은 도메인에 충분한 TTL을 가진 VERSION Key가 있어야 합니다.
    for group_name, group in vars(Keys).items():
        if not isinstance(group, type):
            continue
        for key_name, key in vars(group).items():
            if not isinstance(key, RedisKey) or "ver" not in key.fields:
                continue
            version = getattr(group, "VERSION", None)
            if not isinstance(version, RedisKey) or version.ttl is None or key.ttl is None or version.ttl < key.ttl:
                raise ValueError(f"{group_name}.{key_name}: VERSION Key가 없거나 TTL이 목록 캐시보다 짧습니다.")

    names = list(segments)
    for i, a in enumerate(names):
        for b in names[i + 1 :]:
            sa, sb = segments[a], segments[b]
            if len(sa) == len(sb) and all(x is None or y is None or x == y for x, y in zip(sa, sb, strict=True)):
                raise ValueError(f"{a}와 {b}의 Key가 겹칠 수 있습니다. ({Keys.all()[a].template})")


_validate_registry()
