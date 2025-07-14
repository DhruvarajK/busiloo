
from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel, Field,RootModel
from typing import Dict, Any, List, Optional
import enum
from sqlalchemy.orm import joinedload
from datetime import datetime, time, date
from zoneinfo import ZoneInfo
from sqlalchemy import Column, Date, Float, Integer, String, Boolean, ForeignKey, DateTime, Text, Time
from sqlalchemy.orm import relationship
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import MetaData
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from auth import get_admin_user
from database import get_db
from models import Bus, Stop, StopIssue, StopIssueType, Trip, User
import models
import schemas
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import List, Optional
import crud
import models, schemas

templates = Jinja2Templates(directory="templates")
class StopsByDistrict(RootModel[Dict[str, int]]):
    pass 

class AdminStatsResponse(BaseModel):
    total_buses: int = Field(...)
    total_trips: int = Field(...)
    total_users: int = Field(...)
    total_fb: int = Field(...)
    stops_by_district: StopsByDistrict = Field(..., description="Counts of stops per district.")

admin_router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
    responses={404: {"description": "Not found"}},
)



@admin_router.get(
    "/dashboard-stats",
    response_model=AdminStatsResponse,
    summary="Get Admin Dashboard Statistics",
    description="Retrieves total counts of buses and trips, and counts of stops grouped by district for the admin dashboard."
)
def get_admin_dashboard_stats_api(db: Session = Depends(get_db)):

    stats = {}

    try:
        # Total number of buses
        total_buses = db.query(func.count(Bus.id)).scalar()
        stats["total_buses"] = total_buses if total_buses is not None else 0

        # Total number of trips
        total_trips = db.query(func.count(Trip.id)).scalar()
        stats["total_trips"] = total_trips if total_trips is not None else 0
        
        total_users = db.query(func.count(User.id)).scalar()
        stats["total_users"] = total_users if total_users is not None else 0
        
        total_fb = db.query(func.count(models.AppFeedback.id)).scalar()
        stats["total_fb"] = total_fb if total_fb is not None else 0

        # Number of stops by district
        stops_by_district_query = db.query(
            Stop.district,
            func.count(Stop.id)
        ).group_by(Stop.district).all()

        stops_by_district_data = {
            district: count
            for district, count in stops_by_district_query
            if district is not None  # Exclude stops without a district
        }
        # Pydantic expects a dictionary for StopsByDistrict's __root__
        stats["stops_by_district"] = stops_by_district_data

        return AdminStatsResponse(**stats)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while fetching dashboard stats: {e}"
        )
 
@admin_router.get("/issues", response_class=HTMLResponse)
async def read_issues_page(request: Request):
    """Serves the main admin page for managing stop issues."""
    # Pass issue types to the template for the filter dropdown
    return templates.TemplateResponse("admin_stop_issue.html", {
        "request": request, 
        "issue_types": [e.value for e in models.StopIssueType]
    })


@admin_router.get("/admin_buses", response_class=HTMLResponse)
async def list_buses(request: Request):
    return templates.TemplateResponse("admin_buses.html", {
        "request": request, })

# --- API Data Routes ---

@admin_router.get("/api/issues", response_model=List[schemas.StopIssueDetailOut])
def get_all_stop_issues(
    status: Optional[str] = None,
    issue_type: Optional[models.StopIssueType] = None,
    db: Session = Depends(get_db)
):
    """API endpoint to fetch and filter stop issues."""
    issues = crud.get_stop_issues(db, status=status, issue_type=issue_type)
    return issues

@admin_router.get("/api/stops/{stop_id}", response_model=schemas.StopOut)
def get_stop_details_for_fix(stop_id: int, db: Session = Depends(get_db)):
    """API endpoint to get the current data for a single stop."""
    db_stop = crud.get_stop(db, stop_id)
    if not db_stop:
        raise HTTPException(status_code=404, detail="Stop not found")
    return db_stop

@admin_router.put("/api/stops/{stop_id}", response_model=schemas.StopOut)
def fix_stop_and_resolve_issue(
    stop_id: int,
    stop_update: schemas.StopUpdate,
    issue_id_to_resolve: int,
    db: Session = Depends(get_db)
):
    """
    The core endpoint that:
    1. Updates the bus stop with corrected data.
    2. Marks the associated issue as 'resolved'.
    """
    updated_stop = crud.update_stop(db, stop_id, stop_update)
    if not updated_stop:
        raise HTTPException(status_code=404, detail="Stop to update not found")
    
    crud.update_issue_status(db, issue_id_to_resolve, "resolved")
    
    return updated_stop

@admin_router.get(
    "/buses",
    response_model=List[schemas.BusWithTripCount],
    summary="List all buses with trip counts (Admin Only)",
    dependencies=[Depends(get_admin_user)] # Protect this endpoint with admin dependency
)
async def list_buses_with_trip_count(
    db: Session = Depends(get_db),
    search_query: Optional[str] = Query(None, description="Search by bus name or registration number"),
    is_ls: Optional[bool] = Query(None, description="Filter by Limited Stop status")
):
    """
    Retrieves a list of all buses, including their names, registration numbers,
    Limited Stop (LS) status, and the total number of trips associated with each bus.
    Allows filtering by search query on name/registration number and LS status.

    **Requires Admin Authentication.**
    """
    query = db.query(
        Bus.id,
        Bus.name,
        Bus.registration_no,
        Bus.is_ls,
        func.count(Trip.id).label("num_trips")
    ).outerjoin(Trip, Bus.id == Trip.bus_id).group_by(Bus.id)

    if search_query:
        # Case-insensitive search on name or registration number
        query = query.filter(
            (Bus.name.ilike(f"%{search_query}%")) |
            (Bus.registration_no.ilike(f"%{search_query}%"))
        )

    if is_ls is not None:
        query = query.filter(Bus.is_ls == is_ls)

    buses_data = query.all()

    # Convert the results to the Pydantic schema
    # Use a list comprehension to handle the aggregation result
    return [
        schemas.BusWithTripCount(
            id=bus.id,
            name=bus.name,
            registration_no=bus.registration_no,
            is_ls=bus.is_ls,
            num_trips=bus.num_trips
        )
        for bus in buses_data
    ]
    
@admin_router.get("/union-members", response_class=HTMLResponse)
def union_members_page(request: Request):
    """
    Serves the static HTML page. JS inside will call the JSON endpoint.
    """
    return templates.TemplateResponse("admin_union_members.html", {"request": request})


@admin_router.get("/union-members-data", response_class=JSONResponse)
def union_members_data(db: Session = Depends(get_db), _: models.User = Depends(get_admin_user)):
    """
    Returns JSON list of all users with their bus & trip counts.
    """
    users = db.query(models.User).all()
    out = []
    for u in users:
        bus_count = db.query(models.Bus).filter(models.Bus.owner_id == u.id).count()
        trip_count = (
            db.query(models.Trip)
              .join(models.Bus, models.Trip.bus_id == models.Bus.id)
              .filter(models.Bus.owner_id == u.id)
              .count()
        )
        out.append({
            "username":   u.username,
            "email":      u.email,
            "bus_count":  bus_count,
            "trip_count": trip_count,
            "joined_on":  u.created_at.strftime("%Y-%m-%d"),
        })
    return JSONResponse(content=out)