import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.routes import router

app = FastAPI(title="foodmap route-restaurants API")

_allowed_origins = [
    origin.strip()
    for origin in os.environ.get("FRONTEND_ORIGINS", "http://localhost:3000").split(",")
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["GET"],
    allow_headers=["*"],
)
# 맛집 전체 목록(~3,440건) 응답이 수백 KB에 달해 압축 없이는 전송이 느리다.
app.add_middleware(GZipMiddleware, minimum_size=500)

app.include_router(router)
