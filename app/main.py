import os
import uvicorn
from decouple import config
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi_sqlalchemy import DBSessionMiddleware
from app.core.config import app, Base
from app.db.session import postgresql, session
from app.api.v1.routers import router as api_routes


URL_local = "http://localhost:8000" if config("ENV") == "DEV" \
	else "https://www.olli.com.br"

origins = [
	"http://localhost:5173",
	"http://localhost:8000"
]

app.add_middleware(
	CORSMiddleware,
	allow_origins=origins,
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"]
)
app.add_middleware(
	DBSessionMiddleware,
	db_url=config("DATABASE_URL_DEV") \
		if config("ENV") == "DEV" \
		else config("DATABASE_URL_PROD")
)
app.add_middleware(
	SessionMiddleware,
	secret_key=config("SECRET_KEY"),
	same_site="Lax"
)
app.include_router(api_routes, prefix="/api")

async def create_tables():
	async with postgresql.get_engine().begin() as conn:
		await conn.run_async(Base.metadata.create_all)


@app.on_event("startup")
async def startup():
	await create_tables()

if __name__ == "__main__":
	uvicorn.run(
		"app.main:app",
		host="localhost",
		port="8000",
		log_level="info",
		reload=True
	)
