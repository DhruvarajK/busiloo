
import random
import string

from fastapi import APIRouter, FastAPI, HTTPException, Request, Depends,Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import auth
from database import engine
import models
import schemas
from sqlalchemy.orm import Session, aliased
from datetime import datetime
from zoneinfo import ZoneInfo
import database
import public_user,admin,union

models.Base.metadata.create_all(bind=engine)

app = FastAPI()
app.include_router(union.router)
app.include_router(public_user.router)
app.include_router(admin.admin_router)

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
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/api/admin/data", response_model=schemas.AdminData) # 
def get_admin_data(current_user: models.User = Depends(auth.get_admin_user)):
    # Because of Depends(auth.get_admin_user), this code will only run
    # if the user is authenticated AND is an admin.
    characters = string.ascii_letters + string.digits
    random_code = ''.join(random.choices(characters, k=6))

    return {
        "message": f"Welcome Admin {current_user.username}!",
        "sensitive_data": random_code
    }


@app.get("/admin/dashboard")
def admin_dashboard(request: Request):
    return templates.TemplateResponse("admin_dashboard.html", {"request": request})

@app.get("/add_bus")
def add_bus_page(request: Request):
    return templates.TemplateResponse("add_bus.html", {"request": request})

@app.get("/manifest.json")
def manifest():
    return FileResponse("manifest.json", media_type="application/manifest+json")

@app.get("/service-worker.js")
def sw():
    return FileResponse("service-worker.js", media_type="application/javascript")

@app.get("/add_trip")
def add_trip_page(request: Request):
    return templates.TemplateResponse("add_trip.html", {"request": request})
