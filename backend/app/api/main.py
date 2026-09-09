import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.routes import router
from app.db import init_db, make_engine

@asynccontextmanager
async def lifespan(_: FastAPI):
    # suggestions 테이블은 크롤러가 만들지 않으므로 서버가 뜰 때 보장한다. create_all은
    # checkfirst가 기본이라 이미 있는 테이블은 건드리지 않고, 배포 후 수동 작업이 없다.
    # import 시점이 아니라 startup에 두는 이유: 모듈을 import만 하는 테스트가 기본
    # DATABASE_URL로 sqlite 파일을 만들어버리는 부작용을 없애기 위해서다.
    init_db(make_engine())
    yield


app = FastAPI(title="foodmap route-restaurants API", lifespan=lifespan)

_allowed_origins = [
    origin.strip()
    for origin in os.environ.get("FRONTEND_ORIGINS", "http://localhost:3000").split(",")
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    # 건의함 제출(POST)이 추가되면서 GET 전용이 아니게 됐다.
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
# 맛집 전체 목록(~3,440건) 응답이 수백 KB에 달해 압축 없이는 전송이 느리다.
app.add_middleware(GZipMiddleware, minimum_size=500)

app.include_router(router)
