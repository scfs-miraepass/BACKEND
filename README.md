# MIRAE PASS BACKEND
---
미래 패스 서비스의 백엔드 시스템

## ✨ 명령어
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

## 📦 프로젝트 구조
---

### 폴더 구조
```
...
```


## 🛠 기술 스택
---
- Framework: FastAPI + Uvicorn
- ORM: SQLAlchemy 2.0 (Async)
- Database: MySQL 8.0
- Package Management: [UV](https://github.com/astral-sh/uv)