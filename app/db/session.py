import os
from typing import AsyncGenerator 
from contextlib import asynccontextmanager
from fastapi import Depends
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from fastapi import HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from decouple import config


class PostgreSql:
    """
        Classe que agrupa as funções de
        gerenciamento do PostgreSql.
    """

    def __init__(self, user, password, host, port, database):
        """
            Classe que instancia as conexões com
            o serviço PostgreSql.
            PARAMETROS:
                user: Username do PostgreSql;
                password: Senha do PostgreSql;
                host: Ponto de acesso do PostgreSql;
                port: Porta do ponto de acesso do PostgreSql;
                database: Banco de dados do PostgreSql.
        """

        connection = config("DATABASE_URL_DEV") \
                        if config("ENV") == "DEV" \
			else config("DATABASE_URL_PROD")
        self.connection = connection
        self.engine = create_async_engine(self.connection)

    def get_engine(self):
        """
            Obtém a sessão com o PostgreSql
            RETURN:
                Retorna a engine
        """

        return self.engine

    def create_session(self):
        """
            Cria uma sessão com o PostgreSql.
            RETURN:
                Retorna a sessão criada.
        """

        try:
            self.Session = scoped_session(sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            ))
            self.session = self.Session()
            return self.session
        except Exception as error:
            print(f"ERROR: funcion {PostgreSql.create_session.__name__} -> error -> {str(error)}")
            return str(error)

    def close_engine(self):
        """
            Obtém a sessão com o PostgreSql
            RETURN:
                Fecha a engine
        """

        try:
            self.engine.dispose()
        except Exception as error:
            print(f"ERROR: funcion {PostgreSql.close_engine.__name__} -> error -> {str(error)}")


async def upload_image(
    item_id: str,
    model_instance: object,
    column: str,
    session: AsyncSession,
    file: UploadFile = File(...)
):
    query = await session.execute(
        select(
            model_instance
        ).where(
            model_instance.id == item_id
        )
    )
    item = query.scalars().first()

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Data not found"
        )

    image_data = await file.read()

    setattr(
        item, 
        column, 
        image_data
    )

    await session.commit()
    await session.refresh(item)

    return JSONResponse(
        content={
            "message": "Image uploaded successfully"
        }
    )

async_engine = create_async_engine(
    config("DATABASE_URL_DEV") if config("ENV") == "DEV" \
        else config("DATABASE_URL_PROD"),
    echo=True
)

AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            await session.rollback()
            raise e
        finally:
            await session.close()


postgresql = PostgreSql(
    user=config("NAME_DEV") if config("ENV") == "DEV" \
	else config("NAME_PROD"),
    password=config("PASSWORD_DEV") if config("ENV") == "DEV" \
	else config("PASSWORD_PROD"),
    host=config("HOST_DEV") if config("ENV") == "DEV" \
	else config("HOST_PROD"),
    port=5432,
    database=config("DATABASE")
)
session = postgresql.create_session()
