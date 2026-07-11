import logging
import os
from sys import stdout
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from typing import Optional

from .config import settings


class CustomFormatter(logging.Formatter):
    """
    로그 레벨과 필드에 따라 색상을 다르게 출력하고,
    고정 너비를 사용하여 가독성을 높인 포맷터 (콘솔용)
    """

    grey = "\x1b[38;20m"
    green = "\x1b[32;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    blue = "\x1b[34;20m"
    cyan = "\x1b[36;20m"
    reset = "\x1b[0m"

    date_fmt = "%Y-%m-%d %H:%M:%S"

    def format(self, record):
        # 레벨별 색상 설정
        level_color = self.grey
        if record.levelno == logging.DEBUG:
            level_color = self.grey
        elif record.levelno == logging.INFO:
            level_color = self.green
        elif record.levelno == logging.WARNING:
            level_color = self.yellow
        elif record.levelno == logging.ERROR:
            level_color = self.red
        elif record.levelno == logging.CRITICAL:
            level_color = self.bold_red

        log_fmt = (
            f"%(asctime)s | {level_color}%(levelname)-8s{self.reset} | {self.cyan}%(name)-30s{self.reset} | %(message)s"
        )

        formatter = logging.Formatter(log_fmt, datefmt=self.date_fmt)
        return formatter.format(record)


class LoggerCore:
    instance = None
    initialized = False
    LOG_DIR = "logs"

    # 로거 캐싱을 위한 딕셔너리
    _loggers: dict[str, logging.Logger] = {}
    _file_handlers: dict[str, logging.Handler] = {}

    # 로거
    global_: logging.Logger = ...
    redis: logging.Logger = ...
    database: logging.Logger = ...
    service_point: logging.Logger = ...
    service_post: logging.Logger = ...

    def __new__(cls, *args, **kwargs):
        if cls.instance is None:
            cls.instance = super().__new__(cls)
        return cls.instance

    def __init__(self):
        cls = type(self)
        if cls.initialized:
            return

        if not os.path.exists(cls.LOG_DIR):
            os.makedirs(cls.LOG_DIR, exist_ok=True)

        for logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error", "fastapi"]:
            self.get_logger(logger_name, filename="server", debug=settings.debug)

        self.get_logger(
            "sqlalchemy.engine",
            filename="database",
            debug=settings.debug,
            default_level=logging.WARNING,
        )
        self.get_logger("sqlalchemy.pool", filename="database", debug=settings.debug)

        cls.global_ = self.get_logger("global", debug=settings.debug)
        cls.redis = self.get_logger("redis", debug=settings.debug)
        cls.database = self.get_logger("database", filename="database", debug=settings.debug)

        cls.service_point = self.get_logger("service.point", filename="service", debug=settings.debug)
        cls.service_post = self.get_logger("service.post", filename="service", debug=settings.debug)

        cls.initialized = True

    @staticmethod
    def _initialize_log_file(path: str):
        """로그 파일이 없으면 생성하고 초기화 메시지를 작성합니다."""
        if not os.path.exists(path):
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(f"====== Log Initialized at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ======\n")
            except PermissionError:
                # 다른 프로세스가 이미 파일을 생성/사용 중인 경우 무시
                pass

    @classmethod
    def _get_file_handler(cls, filename: str) -> logging.Handler:
        """파일 핸들러를 생성하거나 캐시된 핸들러를 반환합니다."""
        log_path = os.path.join(cls.LOG_DIR, f"{filename}.log")

        if log_path in cls._file_handlers:
            return cls._file_handlers[log_path]

        cls._initialize_log_file(log_path)

        file_formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)-40s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # delay=True를 사용하여 파일이 실제로 기록될 때까지 열지 않음 (Windows 파일 잠금 문제 완화)
        file_handler = TimedRotatingFileHandler(
            log_path,
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8",
            delay=True,
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(logging.DEBUG)

        cls._file_handlers[log_path] = file_handler
        return file_handler

    @classmethod
    def get_logger(
        cls,
        name: str = "root",
        *,
        filename: Optional[str] = None,
        debug: bool = False,
        add_stream: bool = True,
        debug_level: int = logging.DEBUG,
        default_level: int = logging.INFO,
    ) -> logging.Logger:
        """
        로거를 생성하거나 가져옵니다.

        Args:
            name: 로거 이름
            filename: 로그 파일 이름 (확장자 제외). None이면 name 사용
            debug: 디버그 모드 여부 (True면 콘솔에도 DEBUG 레벨 출력)
            add_stream: 콘솔 출력 여부

            debug_level: 디버그 모드 활성화시 로그 레벨
            default_level: 디버그 모드 비활성화시 로그 레벨
        """
        if name in cls._loggers:
            return cls._loggers[name]

        if filename is None:
            filename = name

        logger = logging.getLogger(name)

        # 이미 핸들러가 설정된 경우, 기존 핸들러 제거 (재설정을 위해)
        if logger.handlers:
            for handler in logger.handlers[:]:
                logger.removeHandler(handler)

        logger.setLevel(logging.DEBUG)  # 기본 레벨은 DEBUG로 설정하고 핸들러에서 필터링

        # 파일 핸들러 (DEBUG 레벨 이상 모두 기록)
        logger.addHandler(cls._get_file_handler(filename))

        # 전체 로그 파일 핸들러
        logger.addHandler(cls._get_file_handler("global"))

        # 스트림 핸들러 (콘솔용)
        if add_stream:
            stream_handler = logging.StreamHandler(stdout)
            stream_handler.setFormatter(CustomFormatter())
            stream_handler.setLevel(debug_level if debug else default_level)
            logger.addHandler(stream_handler)

        # 전파 방지 (상위 로거로 로그가 중복 전송되는 것 방지)
        logger.propagate = False

        cls._loggers[name] = logger
        return logger
