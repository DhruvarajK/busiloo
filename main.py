
from fastapi import APIRouter, FastAPI, HTTPException, Request, Depends,Query
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from database import engine
import models
import union
from sqlalchemy.orm import Session, aliased
from datetime import datetime
from zoneinfo import ZoneInfo
import database
from public_user import router as public_router
import public_user


models.Base.metadata.create_all(bind=engine)

app = FastAPI()
app.include_router(union.router)
app.include_router(public_router)


# Mount static and templates
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# after templates defined:
public_user.templates = templates  # so the router can use the same templates instance

@app.api_route("/health", methods=["GET", "HEAD"])
async def health_check():
    return {"status": "ok"}

# Example HTML endpoints
@app.get("/register")
def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/dashboard")
def dashboard(request: Request):
    # In practice, redirect after login, include auth check via JS
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/add_bus")
def add_bus_page(request: Request):
    return templates.TemplateResponse("add_bus.html", {"request": request})

@app.get("/add_trip")
def add_trip_page(request: Request):
    return templates.TemplateResponse("add_trip.html", {"request": request})
