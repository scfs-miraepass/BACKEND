class ServiceError(Exception):
    pass


class NotFound(ServiceError):
    """
    데이터, 객체 등을 찾지 못할 경우 발생합니다.
    """

    pass
