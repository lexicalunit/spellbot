import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from os import getenv
from typing import AsyncGenerator, Optional

import aiohttp
import aioredis  # type: ignore
import coloredlogs  # type: ignore
import hupper  # type: ignore
import uvicorn  # type: ignore
from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware  # type: ignore
from fastapi_cache import FastAPICache  # type: ignore
from fastapi_cache.backends.inmemory import InMemoryBackend  # type: ignore
from fastapi_cache.backends.redis import RedisBackend  # type: ignore
from fastapi_cache.coder import Coder  # type: ignore
from fastapi_cache.decorator import cache  # type: ignore
from jose import jwt  # type: ignore
from jose.exceptions import JOSEError  # type: ignore
from pydantic import BaseModel
from sqlalchemy import exc
from sqlalchemy.orm.session import Session
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from spellbot import DEFAULT_DB_URL, get_db_env, get_db_url, get_redis_url
from spellbot.data import Data, Game, Server

logger = logging.getLogger(__name__)
SpellBotData = None

api = FastAPI(root_path="/api")

CACHE_TIMEOUT_SECONDS = 3 * 60  # three minutes
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

SPELLAPI_SECRET_KEY = getenv("SPELLAPI_SECRET_KEY", None)
assert SPELLAPI_SECRET_KEY is not None


def cache_key_builder(
    func,
    namespace: Optional[str] = "",
    request: Request = None,
    response: Response = None,
    *args,
    **kwargs,
) -> str:
    prefix = FastAPICache.get_prefix()
    cache_key = f"{prefix}:{namespace}:{func.__module__}:{func.__name__}:{args}:{kwargs}"
    # if request and (auth := request.headers.get("Authorization")):
    #     cache_key = f"{cache_key}:{auth}"
    return cache_key


class JSONResponseCoder(Coder):
    @classmethod
    def encode(cls, value: bytes):
        return value

    @classmethod
    def decode(cls, value: JSONResponse):
        return json.loads(value.body.decode("utf-8"))


api_cache = cache(
    expire=CACHE_TIMEOUT_SECONDS,
    key_builder=cache_key_builder,
    coder=JSONResponseCoder,
)


class LoginParams(BaseModel):
    discord_access_token: str


class UnauthorizedResponse(BaseModel):
    detail = "Unauthorized"


class NotFoundResponse(BaseModel):
    detail = "Not Found"


# TODO: Factor this out to a library that both spellbot and spellapi can use.
@asynccontextmanager
async def new_session(data: Data) -> AsyncGenerator[Session, None]:
    session = data.Session()
    try:
        yield session
    except exc.SQLAlchemyError as e:
        logger.exception("database error: %s", e)
        session.rollback()
        raise
    finally:
        session.close()


def can_admin(guild: dict) -> bool:
    owner = guild.get("owner", False)
    perms = guild.get("permissions", 0)
    if owner or (perms & 0x00000008) == 0x00000008:
        return True
    return False


def create_access_token(*, data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SPELLAPI_SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


@api.post("/logout")
async def logout():
    response = JSONResponse({})
    response.set_cookie(
        "sessionToken",
        value="",
        httponly=True,
        max_age=0,
    )
    return response


@api.post(
    "/login",
    responses={401: {"model": UnauthorizedResponse}},
    description="""Validates the given Discord access token and logs into the SpellAPI.
                   A JWT token for subsequent API calls will be provided as a set-cookie
                   response header.""",
)
async def login(params: LoginParams):
    headers = {
        "Authorization": f"Bearer {params.discord_access_token}",
        "accept": "application/json",
        "content-type": "application/json",
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(
            "https://discord.com/api/users/@me/guilds",
        ) as resp:
            if resp.status != 200:
                raise HTTPException(
                    status_code=401,
                    detail=f"{resp.status} code from discord.com/api/users/@me/guilds",
                )
            guilds = [
                {
                    "id": guild["id"],
                    "name": guild["name"],
                }
                for guild in await resp.json()
                if isinstance(guild, dict) and can_admin(guild)
            ]

        async with session.get(
            "https://discord.com/api/users/@me",
        ) as resp:
            if resp.status != 200:
                raise HTTPException(
                    status_code=401,
                    detail=f"{resp.status} code from discord.com/api/users/@me",
                )
            me_data = await resp.json()
            username = me_data["username"]

        data = {"guilds": guilds, "username": username}
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(data=data, expires_delta=expires_delta)
        token = jsonable_encoder(access_token)
        response = JSONResponse(data)
        response.set_cookie(
            "sessionToken",
            value=token,
            httponly=True,
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            expires=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
        return response


@api.get(
    "/guild/{guild_id}",
    responses={
        401: {"model": UnauthorizedResponse},
        404: {"model": NotFoundResponse},
    },
    description="""Validates the given Discord access token and logs into the SpellAPI.
                   A JWT token for subsequent API calls will be provided as a set-cookie
                   response header.""",
)
async def guild(guild_id: str, request: Request):
    try:
        token = request.cookies.get("sessionToken")
        if not token:
            raise HTTPException(status_code=401)
        user_session = jwt.decode(token, SPELLAPI_SECRET_KEY, algorithms=[ALGORITHM])
        guilds = user_session.get("guilds") or []
        if all(guild_id != guild_data.get("id") for guild_data in guilds):
            raise HTTPException(status_code=401)
    except JOSEError:
        raise HTTPException(status_code=401)

    async with new_session(SpellBotData) as session:
        server = session.query(Server).filter_by(guild_xid=guild_id).one_or_none()
        games = (
            session.query(Game).filter_by(guild_xid=guild_id, status="started").count()
        )
        if not server:
            raise HTTPException(status_code=404)
        return JSONResponse(
            {
                "serverPrefix": server.prefix,
                "expireTimeMinutes": server.expire,
                "privateLinks": server.links == "private",
                "showSpectateLink": server.show_spectate_link,
                "motdVisibilty": server.motd,
                "powerEnabled": server.power_enabled,
                "tagsEnabled": server.tags_enabled,
                "voiceEnabled": server.create_voice,
                "serverMotd": server.smotd,
                "gamesPlayed": games,
            }
        )


def setup_logging():
    # logging.getLogger("uvicorn").handlers.clear()
    # logging.getLogger("uvicorn.error").handlers.clear()
    # logging.getLogger("uvicorn.access").handlers.clear()

    coloredlogs.install(
        level=logging.INFO,
        fmt="[%(asctime)s][%(name)s][%(levelname)s] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        field_styles={
            "asctime": {"color": "cyan"},
            "hostname": {"color": "magenta"},
            "levelname": {"bold": True, "color": "black"},
            "name": {"color": "blue"},
            "programname": {"color": "cyan"},
            "username": {"color": "yellow"},
        },
        level_styles={
            "debug": {"color": "magenta"},
            "info": {"color": "green"},
            "warning": {"color": "yellow"},
            "error": {"color": "red"},
            "critical": {"color": "red"},
        },
    )


app = FastAPI()


@app.on_event("startup")
async def startup():
    setup_env()
    setup_logging()
    redis_url = get_redis_url()
    if redis_url:
        redis = await aioredis.create_redis_pool(redis_url, encoding="utf8")
        FastAPICache.init(RedisBackend(redis), prefix="fastapi-cache")
    else:
        FastAPICache.init(InMemoryBackend(), prefix="fastapi-cache")


app.mount("/api", api)

# Setup some CORS for development mode (TODO: Make this only happen in dev mode?)
ALLOWED_CORS_ORIGINS = ["http://localhost:3000", "http://localhost:5000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def setup_env():
    # TODO: Factor out all this config/setup to a library that both spellbot and api use.
    database_env = get_db_env("SPELLBOT_DB_URL")
    database_url = get_db_url(database_env, DEFAULT_DB_URL)
    if database_url.startswith("postgres://"):
        # SQLAlchemy 1.4.x removed support for the postgres:// URI scheme
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    global SpellBotData
    SpellBotData = Data(database_url)


def main():
    hupper.start_reloader("spellapi.main")
    # TODO: Identify other things that could change and require a reload...

    # TODO: Use https://github.com/abersheeran/asgi-ratelimit to rate limit API calls?
    uvicorn.run(app, port=getenv("PORT", 5000))


if __name__ == "__main__":
    main()
