from fastapi import FastAPI

from app.api.routes import router

app = FastAPI(title="foodmap route-restaurants API")
app.include_router(router)
