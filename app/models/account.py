import traceback
import uuid
from typing import Optional, Any
from datetime import datetime, timezone
from fastapi import (
    HTTPException, 
    UploadFile, 
    File, 
    Form, 
    status,
    Depends
)
import sqlalchemy as db
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from typing_extensions import Annotated
from jose import (
    jwt, 
    JWTError, 
    ExpiredSignatureError
)
from decouple import config
from app.db.session import session as db_session, upload_image
from app.core import (
    verify_password, 
    blacklisted_tokens,
    oauth2_scheme,
    Base
)
from app.db import get_async_session
from app.schemas import AccountInput, TokenData


class AccountModel(Base):
    __tablename__ = "tb_account"

    # Definição das colunas
    id = db.Column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    email = db.Column(db.String(255), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=False)
    profile_picture = db.Column(db.LargeBinary)
    pix_key = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.Date, default=func.now())
    updated_at = db.Column(db.Date, default=func.now(), onupdate=func.now())

    store = relationship(
        "StoreModel", 
        back_populates="account"
    )
    product = relationship(
        "ProductModel", 
        back_populates="account"
    )

    @classmethod
    async def add(
        cls,
        account: AccountInput,
        session: AsyncSession,
        file: Optional[UploadFile] = None
    ):
        from app.core.security import hash_password

        print(f'ACCOUNT OBJ::: {account}')

        password = hash_password(account.password)
        new_account = cls(
            email=account.email,
            password=password,
            pix_key=account.pix_key
        )

        try:
            # Inserir os dados na tabela `AccountModel`
            session.add(new_account)
            await session.commit()

            # Caso a imagem seja fornecida, chamar o método `upload_image`
            if file:
                # file_content = await file.read()
                await upload_image(
                    item_id=str(new_account.id),
                    model_instance=cls,
                    column="profile_picture",
                    file=file,
                    session=session
                )

            await session.refresh(new_account)
            return new_account

        except Exception as error:
            print(error)
            traceback.print_exc()


    @classmethod
    async def get(cls, account_id: str, session: AsyncSession):
        try:
            result = await session.get(cls, account_id)
            if not result:
                raise HTTPException(status_code=404, detail="Account not found")
            return result
        except Exception as error:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=str(error))
        

    @classmethod
    async def update(
        cls,
        account_id: str,
        update_data: dict,
        session: AsyncSession
    ):
        try:
            db_item = await session.get(cls, account_id)
            if not db_item:
                raise HTTPException(status_code=404, detail="Account not found")

            for key, value in update_data.items():
                if hasattr(db_item, key):
                    setattr(db_item, key, value)

            await session.commit()
            await session.refresh(db_item)
            return db_item

        except Exception as error:
            await session.rollback()
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=str(error))
        
    @classmethod
    async def get_password_email(
        cls, 
        email: str, 
        session: AsyncSession
    ):
        # query = cls(
            # AccountModel.password.label("password"),
            # AccountModel.email.label("mail")
        # ).filter(AccountModel.email==email)
        # query = query.all()
        query = await session.execute(
            select(
                cls,
                cls.password.label("password"),
                cls.email.label("email")
            ).where(
                cls.email==email
            )
        )
        result = query.first()
        print(f"RESULT::: {result}")
        try:
            if result:
                # Retorna um dicionário com os campos
                return {
                    "password": result[1],
                    "email": result[2]
                }
        except Exception as error:
            print(error)
            traceback.print_exc()
        finally:
            db_session.close()

    @classmethod
    async def get_user_email(cls, email: str, session: AsyncSession):
        # query = db_session.query(
        #     AccountModel.id.label("id"),
        #     AccountModel.email.label("email"),
        # ).filter(AccountModel.email==email)
        # query = query.all()
        query = await session.execute(
            select(
                cls,
                cls.id.label("id"),
                cls.email.label("email")
            ).where(
                cls.email==email
            )
        )
        result = query.first()
        print(f'RESULTS::: {result}')
        try:
            if result:
                return {
                    "id": result[1],
                    "email": result[2]
                }
        except Exception as error:
            print(error)
            traceback.print_exc()
        finally:
            await db_session.close()


    def dict_columns(query) -> dict:
        return [{
            "id": data[0],
            "email": data[1]
        } for data in query]
    
    @classmethod
    async def authenticate_user(
        cls, 
        email: str, 
        password: str, 
        session: AsyncSession
    ):
        user = await cls.get_password_email(email, session)
        print(f'AUTH USER::: {user}')
        
        if not user or not verify_password(password, user["password"]):
            return None
        
        return user
    
    @classmethod
    async def get_current_user(
        cls, 
        token: str = Depends(oauth2_scheme), 
        session: Any = Depends(get_async_session)
    ):
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

        try:
            # Decodifica o token
            payload = jwt.decode(token, config("SECRET_KEY"), algorithms=[config("ALGORITHM")])
            username: str = payload.get("sub")
            exps: int = payload.get("exp")

            if username is None:
                raise credentials_exception

            if token in blacklisted_tokens:
                raise credentials_exception

            # Verifica se o token expirou
            if exps is None or datetime.fromtimestamp(exps, tz=timezone.utc) < datetime.now(timezone.utc):
                print("Token expirado ou inválido")
                raise credentials_exception

            token_data = TokenData(username=username, expires=exps)

        except ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except JWTError:
            raise credentials_exception

        # Verifica se o usuário existe no banco
        user = await cls.get_user_email(
            email=token_data.username,
            session=session
        )
        print(f'USER CREDENTIALS::: {user}')

        if user is None:
            raise credentials_exception

        return user
    
    async def get_current_user_dep(
        token: str = Depends(oauth2_scheme),
        session: Any = Depends(get_async_session)
    ) -> Any:
        return await AccountModel.get_current_user(token, session)


    @staticmethod
    async def get_current_active_user(
        current_user: Any = Depends(get_current_user_dep)) -> Any:
        if not current_user:
            raise HTTPException(status_code=400, detail="Inactive user")
        return current_user