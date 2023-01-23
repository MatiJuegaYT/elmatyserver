#!/usr/bin/env python3

import datetime
import platform
import threading
from math import ceil
from typing import Optional

import uvicorn
from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse, JSONResponse

import context as ctx
from database.db_access import DBAccessLayer
import routers
from config import *
from dfa_filter import DFAFilter
from models import ErrorMessage, ErrorMessageException
from smmwe_lib import *

app = FastAPI()

app.include_router(routers.stage.router)
app.include_router(routers.user.router)

connection_per_minute = 0

start_time = datetime.datetime.now()

if OFFENSIVE_WORDS_FILTER:
    import requests

    # Load DFA filter
    dfa_filter = DFAFilter()
    wordlist = None
    for url in OFFENSIVE_WORDS_LIST:
        wordlist = requests.get(url=url).text.replace("\r", "").split("\n")
    for word in wordlist:
        if len(word) > 1 and len(word.encode("utf-8")) > 2:
            dfa_filter.add(word)
    for url in OFFENSIVE_WORDS_LIST_CN_ONLY:
        wordlist = requests.get(url=url).text.replace("\r", "").split("\n")
        for word in wordlist:
            if len(re.findall(re.compile(r"[A-Za-z]", re.S), word)) == 0:
                if len(word) > 1 and len(word.encode("utf-8")) > 2:
                    dfa_filter.add(word)


@app.on_event("startup")
async def startup_event():
    await ctx.db.create_columns()


@app.get("/")
async def readme_handler() -> RedirectResponse:  # Redirect to Engine Tribe README
    return RedirectResponse("https://web.enginetribe.gq/index.html")


# get server status
@app.get("/server_stats")
async def server_stats() -> dict:
    async with ctx.db.async_session() as session:
        async with session.begin():
            dal = DBAccessLayer(session)
            return {
                "os": platform.platform().replace('-', ' '),
                "python": platform.python_version(),
                "player_count": await dal.get_player_count(),
                "level_count": await dal.get_level_count(),
                "uptime": (datetime.datetime.now() - start_time).seconds,
                "connection_per_minute": connection_per_minute,
            }


@app.exception_handler(ErrorMessageException)
async def error_message_exception_handler(request: Request, exc: ErrorMessageException):
    return JSONResponse(
        status_code=200,
        content={
            "error_type": exc.error_type,
            "message": exc.message,
        },
    )


def timer_function():
    global connection_per_minute
    connection_per_minute = ctx.connection_count
    ctx.connection_count = 0
    threading.Timer(60, timer_function).start()


if __name__ == "__main__":
    threading.Timer(1, timer_function).start()
    uvicorn.run(app, host=HOST, port=PORT, headers=[("Server", "EngineTribe")])
