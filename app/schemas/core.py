from datetime import datetime
from zoneinfo import ZoneInfo


class ClassProperty:
    def __init__(self, method):
        self.method = method

    def __get__(self, instance, owner):
        return self.method(owner)


class SchemaCore:
    instance = None

    timezone = ZoneInfo("UTC")

    def __new__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance

    @classmethod
    def now(cls) -> datetime:
        """
        DB 서버 시간대를 기준으로 한 현재 시각(timezone-aware)을 반환합니다.

        DB에 저장된 naive datetime(`sync_timezone`으로 시간대를 붙인 값)과 비교할 때는
        반드시 이 함수를 사용해야 합니다. 백엔드 프로세스의 로컬 시간대가 DB 서버와
        다를 수 있어, `datetime.now()`와 직접 비교하면 시차만큼 어긋납니다.
        """
        return datetime.now(cls.timezone)

    @classmethod
    def sync_timezone(cls, _: datetime):
        if _.tzinfo is None:
            # Mysql 기준, DB서버 시간대로 자동 생성시 TZ이 없음 -> TZ 데이터추가
            return _.replace(tzinfo=cls.timezone)
        elif _.utcoffset() != cls.timezone.utcoffset(_.replace(tzinfo=None)):
            # TimeZone이 있지만, 서버와 다른경우
            return _.astimezone(tz=cls.timezone)
        return _
