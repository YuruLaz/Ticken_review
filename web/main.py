"""Server-rendered UI (Jinja2 + htmx). Run from the project root, next to the API:

    uvicorn web.main:app --port 8001 --reload

This file only assembles the app: static files, error handlers and the routers.
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from markupsafe import escape

from web import api
from web.dependencies import LoginRequired
from web.routers import auth, inbox, portal, workspace
from web.templating import templates

app = FastAPI(title="SupportDesk web")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

app.include_router(auth.router)
app.include_router(portal.router)
app.include_router(inbox.router)
app.include_router(workspace.router)


@app.exception_handler(LoginRequired)
async def to_login(request: Request, exc: LoginRequired):
    # A plain redirect inside an htmx request would load the login page into the panel
    # being updated; HX-Redirect makes htmx navigate the whole page instead.
    if request.headers.get("HX-Request"):
        return Response(headers={"HX-Redirect": "/login"})
    return RedirectResponse("/login", status_code=303)


@app.exception_handler(api.ApiError)
async def api_error(request: Request, error: api.ApiError):
    """Any API error a route doesn't handle itself: a readable message instead of a 500 page."""
    if error.status_code == 401:
        return await to_login(request, LoginRequired())
    if request.headers.get("HX-Request"):
        # htmx doesn't swap error responses by default, so this is a 200 with the message,
        # shown in whatever part of the page the request was updating.
        return HTMLResponse(f'<p class="alert error">{escape(str(error))}</p>')
    return templates.TemplateResponse(
        request, "error.html", {"error": str(error)}, status_code=error.status_code
    )
