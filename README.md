# MIRAE PASS BACKEND
---
미래 패스 서비스의 백엔드 시스템

## 🔒 개발 환경설정
---
```bash
# Git clone
git clone https://git.rldn.xyz/scfs.miraepass/backend.git
cd backend

# 필요 라이브러리 설치및 환경 구성
uv sync
uv run pre-commit install
uv run pre-commit run

# 환경변수 설정
cp example.env .env
vi .env

# DATABASE 구성
uv run alembic upgrade head

# 실행
uv run fastapi dev
```

## ✨ 명령어 및 개발 가이드
---
### 데이터베이스 관리
데이터베이스 관리에는 Alembic를 사용합니다.
```bash
# 마이그레이션 생성
uv run alembic revision --autogenerate -m "message"

# 마이그레이션 적용
uv run alembic upgrade head

# 롤백
uv run alembic downgrade -1
```
### 버전 지정
버전의 경우 [pyproject.toml]()에 작성하며. 유의적 버전 규칙을 따릅니다.
```
Major.Minor.Patch
- Major (1.x.x): 기존 기능과 호환되지 않는 큰 변화가 있을 때
- Minor (x.1.x): 새로운 기능이 추가되었지만, 기존 기능은 그대로 잘 작동할 때
- Patch (x.x.1): 단순한 버그 수정이나 성능 개선이 있었을 때
```

## 📦 프로젝트 구조
---
```
alembic                 # alembic 시스템
app
├── core                # 핵심 로직
│   ├── __init__.py
│   ├── config.py       # 환경 변수
│   ├── database.py     # 데이터베이스 엔진
│   ├── dependency.py   # 의존성 설정
│   ├── loggers.py      # 로그 시스템
│   ├── redis.py        # 캐시(Redis) 엔진
│   └── security.py     # 보안 모듈
│
├── router
│   ├── endpoints       # API 엔드포인트
│   │   ├── auth.py     # 인증
│   │   ├── point.py    # 포인트
│   │   └── search.py   # 검색
│   └── __init__.py     # 통합 라우터
│
├── schemas             # SQLAlchemy 모델 및 기타 스키마
│   ├── __init__.py
│   ├── point.py        # 포인트 관련
│   ├── response.py     # 응답 스키마
│   └── users.py        # 유저 관련
│
├── logs                # 시스템 로그 (자동 생성)
│
├── __init__.py
└── main.py             # FastAPI APP
example.env             # 환경변수 예제
```


## 🛠 기술 스택
---
- Framework: FastAPI + Uvicorn
- ORM: SQLAlchemy 2.0 (Async)
- Database: MySQL 8.0, Redis
- Package Management: [UV](https://github.com/astral-sh/uv)