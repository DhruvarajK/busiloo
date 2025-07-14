from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, HTTPException, Response, status, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
import models, schemas, auth, database
from datetime import datetime, date as datecls, timedelta
from typing import Any, List
from schemas import AppFeedbackIn, AppFeedbackOut  
from models import AppFeedback, User  
from database import get_db  
from typing import Optional
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import joinedload
from fastapi.security import OAuth2PasswordRequestForm

router = APIRouter(prefix="/union", tags=["union"])

# Register, login, add bus, add stop, list buses/trips unchanged except modifications noted below

@router.post("/register", response_model=schemas.UserOut)
def register(user_in: schemas.UserCreate, db: Session = Depends(database.get_db)):
    if db.query(models.User).filter((models.User.username == user_in.username) | (models.User.email == user_in.email)).first():
        raise HTTPException(status_code=400, detail="Username or email already registered")
    hashed_pw = auth.get_password_hash(user_in.password)
    user = models.User(username=user_in.username, email=user_in.email, hashed_password=hashed_pw)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user



@router.post("/login", response_model=schemas.Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    user = auth.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    access_token = auth.create_access_token(data={"sub": user.username})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "is_admin": user.username.lower() == "admin"
    }




# Add bus
@router.post("/buses", response_model=schemas.BusOut)
def create_bus(bus_in: schemas.BusCreate, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(database.get_db)):
    # Check if a bus with the given registration number already exists
    if db.query(models.Bus).filter(models.Bus.registration_no == bus_in.registration_no).first():
        raise HTTPException(status_code=400, detail="Bus with this registration number already exists")

    # Create the new bus instance, including the is_ls field
    bus = models.Bus(
        name=bus_in.name,
        registration_no=bus_in.registration_no,
        owner_id=current_user.id,
        is_ls=bus_in.is_ls # Assign the value from the input schema
    )
    db.add(bus)
    db.commit()
    db.refresh(bus)
    return bus




# List/search stops: allow search by name substring
@router.get("/stops", response_model=List[schemas.StopOut])
def list_stops(search: str = Query(None, description="Search stops by name substring"), skip: int = 0, limit: int = 100, db: Session = Depends(database.get_db)):
    query = db.query(models.Stop)
    if search:
        ilike_pattern = f"%{search}%"
        query = query.filter(models.Stop.name.ilike(ilike_pattern))
    stops = query.order_by(models.Stop.name).offset(skip).limit(limit).all()
    return stops


# Exclude trip
@router.post("/trips/exclude", response_model=schemas.ExclusionCreate)
def exclude_trip(excl_in: schemas.ExclusionCreate, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(database.get_db)):
    trip = db.query(models.Trip).join(models.Bus).filter(models.Trip.id == excl_in.trip_id, models.Bus.owner_id == current_user.id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found or unauthorized")
    exclusion = models.Exclusion(trip_id=excl_in.trip_id, date=excl_in.date)
    db.add(exclusion)
    db.commit()
    return excl_in

# List user's buses
@router.get("/buses", response_model=List[schemas.BusOut])
def get_user_buses(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(database.get_db)):
    buses = db.query(models.Bus).filter(models.Bus.owner_id == current_user.id).order_by(models.Bus.name).all()
    return buses


@router.post("/trips", response_model=schemas.TripOut)
def create_trip(
    trip_in: schemas.TripCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    """
    Creates a new trip entry, associating it with a bus, service days,
    and stop times.
    """
    # 1. Verify bus ownership
    # Ensure the bus exists and belongs to the current authenticated user.
    bus = (
        db.query(models.Bus)
          .filter(models.Bus.id == trip_in.bus_id,
                  models.Bus.owner_id == current_user.id)
          .first()
    )
    if not bus:
        raise HTTPException(status_code=404, detail="Bus not found or unauthorized")

    # 2. Create Trip
    # Instantiate a new Trip object with basic details.
    trip = models.Trip(
        bus_id=trip_in.bus_id,
        route_name=trip_in.route_name,
        departure_time=trip_in.departure_time,
        direction=trip_in.direction, # Corrected: Was trip.direction, should be trip_in.direction
    )
    db.add(trip)
    db.flush()  # Flush to get the trip.id, which is needed for related objects

    # 3. Service days
    # Iterate through the provided service days. Since sd.weekday is already
    # expected to be a Weekday enum member (parsed by Pydantic),
    # we can directly use it.
    for sd in trip_in.service_days:
        # Pydantic should handle the conversion from incoming integer to Weekday enum.
        # So, sd.weekday should already be a Weekday enum member here.
        db.add(models.ServiceDay(trip_id=trip.id, weekday=sd.weekday))

    # 4. Stop times
    # Iterate through the provided stop times, verify each stop exists,
    # and add the StopTime entries to the database.
    for st in trip_in.stop_times:
        stop = db.query(models.Stop).get(st.stop_id)
        if not stop:
            raise HTTPException(status_code=404, detail=f"Stop id {st.stop_id} not found")

        db.add(models.StopTime(
            trip_id=trip.id,
            stop_id=st.stop_id,
            arrival_time=st.arrival_time,
            sequence=st.sequence,
        ))

    db.commit() # Commit all changes to the database

    # 5. Reload with Stop relationships
    # Reload the trip object to include its related stop_times and service_days
    # with their respective relationships (e.g., Stop details for StopTime).
    trip = (
        db.query(models.Trip)
          .options(
              joinedload(models.Trip.stop_times)
                 .joinedload(models.StopTime.stop), # Load related Stop for each StopTime
              joinedload(models.Trip.service_days) # Load related ServiceDays
          )
          .filter(models.Trip.id == trip.id)
          .one()
    )

    # 6. Serialize including stop.latitude/etc from the joined Stop
    # Prepare the output data structure, extracting necessary details
    # from the loaded relationships.
    stop_times_out = [
        schemas.StopTimeOut(
            stop_id=st.stop_id,
            stop_name=st.stop.name,           # from related Stop
            arrival_time=st.arrival_time,
            sequence=st.sequence,
            latitude=st.stop.latitude,        # now pulled from Stop
            longitude=st.stop.longitude,
            loc_link=st.stop.loc_link
        )
        for st in sorted(trip.stop_times, key=lambda x: x.sequence)
    ]
    service_days_out = [
        schemas.ServiceDayOut(weekday=sd.weekday.value) # ***CHANGED: Use .value to get integer***
        for sd in trip.service_days
    ]

    # Return the fully structured TripOut response.
    return schemas.TripOut(
        id=trip.id,
        bus_id=trip.bus_id,
        route_name=trip.route_name,
        departure_time=trip.departure_time,
        direction=trip.direction,
        stop_times=stop_times_out,
        service_days=service_days_out
    )


# Similarly, when returning trips in GET endpoints, manually map:
@router.get("/buses/{bus_id}/trips", response_model=List[schemas.TripOut])
def get_bus_trips(
    bus_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    bus = (
        db.query(models.Bus)
        .filter(models.Bus.id == bus_id, models.Bus.owner_id == current_user.id)
        .first()
    )
    if not bus:
        raise HTTPException(status_code=404, detail="Bus not found or unauthorized")

    result: List[schemas.TripOut] = []
    for trip in bus.trips:
        # Force‐load relationships (if lazy)
        trip.stop_times  
        trip.service_days

        # Build StopTimeOut, pulling in name, coords and a link
        stop_times_out = []
        for st in sorted(trip.stop_times, key=lambda x: x.sequence):
            stop = st.stop  # your Stop ORM instance
            loc_link = None
            if stop.latitude and stop.longitude:
                loc_link = (
                    f"https://www.google.com/maps/search/"
                    f"?api=1&query={stop.latitude},{stop.longitude}"
                )

            stop_times_out.append(
                schemas.StopTimeOut(
                    stop_id=st.stop_id,
                    stop_name=stop.name,
                    arrival_time=st.arrival_time,
                    sequence=st.sequence,
                    latitude=stop.latitude,
                    longitude=stop.longitude,
                    loc_link=loc_link,
                )
            )

        service_days_out = [
            schemas.ServiceDayOut(weekday=sd.weekday.value) for sd in trip.service_days
        ]

        result.append(
            schemas.TripOut(
                id=trip.id,
                bus_id=trip.bus_id,
                route_name=trip.route_name,
                departure_time=trip.departure_time,
                direction=trip.direction,
                stop_times=stop_times_out,
                service_days=service_days_out,
            )
        )

    return result


# Trip template endpoints
@router.get("/trips/templates/names", response_model=List[str])
def get_route_names(current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(database.get_db)):
    # Return distinct route names from trips of this user or globally? For reuse across unions, return global distinct names
    names = db.query(models.Trip.route_name).distinct().order_by(models.Trip.route_name).all()
    return [n[0] for n in names]

@router.get("/trips/templates", response_model=List[schemas.TripTemplateSummary])
def get_trip_templates(route_name: str = Query(..., description="Route name to filter templates"), direction: str = Query(None, description="Optional direction filter"), db: Session = Depends(database.get_db)):
    query = db.query(models.Trip).filter(models.Trip.route_name == route_name)
    if direction:
        query = query.filter(models.Trip.direction == direction)
    trips = query.order_by(models.Trip.departure_time).all()
    return trips

@router.get("/trips/templates/{template_id}", response_model=schemas.TripTemplateDetail)
def get_trip_template_detail(template_id: int, db: Session = Depends(database.get_db)):
    trip = db.query(models.Trip).filter(models.Trip.id == template_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Template trip not found")
    # Compute offsets in minutes relative to departure_time
    dep = datetime.combine(datetime.utcnow().date(), trip.departure_time)
    stop_templates = []
    for st in sorted(trip.stop_times, key=lambda x: x.sequence):
        arr = datetime.combine(datetime.utcnow().date(), st.arrival_time)
        offset = int((arr - dep).total_seconds() // 60)
        stop_templates.append(schemas.StopTimeTemplate(
            stop_id=st.stop_id,
            stop_name=st.stop.name,
            latitude=st.stop.latitude,
            longitude=st.stop.longitude,
            sequence=st.sequence,
            offset_minutes=offset
        ))
    return schemas.TripTemplateDetail(
        route_name=trip.route_name,
        direction=trip.direction,
        stop_template=stop_templates
    )
    
    

@router.get("/trips/{trip_id}", response_model=schemas.TripOut)
def get_trip_detail(trip_id: int, current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(database.get_db)):
    # Verify ownership: join Bus and eager load stop_times and their associated stops
    trip = (
        db.query(models.Trip)
        .join(models.Bus)
        .filter(models.Trip.id == trip_id, models.Bus.owner_id == current_user.id)
        .options(
            joinedload(models.Trip.stop_times)
                .joinedload(models.StopTime.stop), # This line is crucial for loading stop details
            joinedload(models.Trip.service_days)
        )
        .first()
    )
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found or unauthorized")

    # Serialize
    stop_times_out = []
    for st in sorted(trip.stop_times, key=lambda x: x.sequence):
        stop = st.stop # Access the related Stop object
        loc_link = None
        if stop.latitude and stop.longitude:
            loc_link = (
                f"https://www.google.com/maps/search/"
                f"?api=1&query={stop.latitude},{stop.longitude}"
            )
        stop_times_out.append(
            schemas.StopTimeOut(
                stop_id=st.stop_id,
                stop_name=stop.name,          # Populate stop_name from the related Stop
                arrival_time=st.arrival_time,
                sequence=st.sequence,
                latitude=stop.latitude,       # Populate latitude from the related Stop
                longitude=stop.longitude,     # Populate longitude from the related Stop
                loc_link=loc_link             # Populate loc_link
            )
        )

    service_days_out = [
        schemas.ServiceDayOut(weekday=sd.weekday.value)
        for sd in trip.service_days
    ]
    return schemas.TripOut(
        id=trip.id,
        bus_id=trip.bus_id,
        route_name=trip.route_name,
        departure_time=trip.departure_time,
        direction=trip.direction,
        stop_times=stop_times_out,
        service_days=service_days_out
    )
    
@router.put("/trips/{trip_id}", response_model=schemas.TripOut)
def update_trip_times(
    trip_id: int,
    trip_upd: schemas.TripUpdate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    # Verify ownership
    trip = db.query(models.Trip).join(models.Bus).filter(models.Trip.id == trip_id, models.Bus.owner_id == current_user.id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found or unauthorized")

    # Update departure_time
    trip.departure_time = trip_upd.departure_time

    # Optionally update service_days if provided
    if trip_upd.service_days is not None:
        # Delete existing
        db.query(models.ServiceDay).filter(models.ServiceDay.trip_id == trip.id).delete()
        # Add new
        for sd in trip_upd.service_days:
            try:
                weekday_enum = models.Weekday(sd.weekday)
            except KeyError:
                raise HTTPException(status_code=400, detail=f"Invalid weekday: {sd.weekday}")
            db.add(models.ServiceDay(trip_id=trip.id, weekday=weekday_enum))

    # Update stop_times: delete existing, then recreate
    # Note: ensure atomic replacement
    db.query(models.StopTime).filter(models.StopTime.trip_id == trip.id).delete()
    for st in trip_upd.stop_times:
        # Validate stop exists
        stop = db.query(models.Stop).filter(models.Stop.id == st.stop_id).first()
        if not stop:
            raise HTTPException(status_code=404, detail=f"Stop id {st.stop_id} not found")
        new_st = models.StopTime(
            trip_id=trip.id,
            stop_id=st.stop_id,
            arrival_time=st.arrival_time,
            sequence=st.sequence
        )
        db.add(new_st)

    db.commit()

    trip = (
        db.query(models.Trip)
        .filter(models.Trip.id == trip.id) # Use trip.id after refresh
        .options(
            joinedload(models.Trip.stop_times)
                .joinedload(models.StopTime.stop), # Crucial for loading stop details
            joinedload(models.Trip.service_days)
        )
        .one() # Use .one() as you expect a single result based on ID
    )

    # Serialize response
    stop_times_out = []
    for st in sorted(trip.stop_times, key=lambda x: x.sequence):
        stop = st.stop # Access the related Stop object
        loc_link = None
        if stop.latitude and stop.longitude:
            loc_link = (
                f"https://www.google.com/maps/search/"
                f"?api=1&query={stop.latitude},{stop.longitude}"
            )
        stop_times_out.append(
            schemas.StopTimeOut(
                stop_id=st.stop_id,
                stop_name=stop.name,          # Populate stop_name from the related Stop
                arrival_time=st.arrival_time,
                sequence=st.sequence,
                latitude=stop.latitude,       # Populate latitude from the related Stop
                longitude=stop.longitude,     # Populate longitude from the related Stop
                loc_link=loc_link             # Populate loc_link
            )
        )
    service_days_out = [
        schemas.ServiceDayOut(weekday=sd.weekday.value)
        for sd in trip.service_days
    ]

    return schemas.TripOut(
        id=trip.id,
        bus_id=trip.bus_id,
        route_name=trip.route_name,
        departure_time=trip.departure_time,
        direction=trip.direction,
        stop_times=stop_times_out,
        service_days=service_days_out
    )
    



@router.post("/api/app_feedback", response_model=AppFeedbackOut)
def submit_app_feedback(
    payload: AppFeedbackIn,
    db: Session = Depends(get_db),
    current_user: Optional[Any] = None
):
    fb = AppFeedback(
        user_id=current_user.id if current_user else None,
        category=payload.category,
        message=payload.message,
        created_at=datetime.now(ZoneInfo("Asia/Kolkata"))
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return AppFeedbackOut.model_validate(fb)



templates = Jinja2Templates(directory="templates")

@router.get("/app_feedback", response_class=HTMLResponse)
def app_feedback_page(request: Request):
    return templates.TemplateResponse("app_feedback.html", {"request": request})

@router.get("/exclusion", response_class=HTMLResponse)
def app_feedback_page(request: Request):
    return templates.TemplateResponse("exclusion.html", {"request": request})

@router.get("/add_stop", response_class=HTMLResponse)
def app_feedback_page(request: Request):
    return templates.TemplateResponse("add_stop.html", {"request": request})



@router.post("/exclusions", response_model=schemas.ExclusionOut, status_code=status.HTTP_201_CREATED)
def create_trip_exclusion(
    excl_in: schemas.ExclusionCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    """
    Mark a specific trip as not running on a given date.
    The user must own the bus associated with the trip.
    """
    # 1. Verify that the trip exists and the user owns it.
    trip = db.query(models.Trip).join(models.Bus).filter(
        models.Trip.id == excl_in.trip_id,
        models.Bus.owner_id == current_user.id
    ).first()

    if not trip:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Trip not found or you do not have permission to modify it."
        )

    # 2. Check if an exclusion for this trip on this date already exists.
    existing_exclusion = db.query(models.Exclusion).filter(
        models.Exclusion.trip_id == excl_in.trip_id,
        models.Exclusion.date == excl_in.date
    ).first()

    if existing_exclusion:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"This trip is already excluded on {excl_in.date}."
        )

    # 3. Create and save the new exclusion.
    exclusion = models.Exclusion(trip_id=excl_in.trip_id, date=excl_in.date)
    db.add(exclusion)
    db.commit()
    db.refresh(exclusion)
    
    # 4. The `ExclusionOut` schema needs the `trip` relationship to be loaded.
    # The refresh and SQLAlchemy's relationship loading handle this.
    return exclusion

@router.get("/exclusions", response_model=List[schemas.ExclusionOut])
def get_user_exclusions(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    """
    Get a list of all trip exclusions created by the current user.
    """
    exclusions = (
        db.query(models.Exclusion)
        .join(models.Exclusion.trip)
        .join(models.Trip.bus)
        .filter(models.Bus.owner_id == current_user.id)
        .options(joinedload(models.Exclusion.trip)) # Eager load trip details
        .order_by(models.Exclusion.date.desc())
        .all()
    )
    return exclusions

@router.delete("/exclusions/{exclusion_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trip_exclusion(
    exclusion_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    """
    Delete a trip exclusion. The user must own the bus associated with the trip.
    """
    # 1. Find the exclusion and verify ownership via the trip and bus.
    exclusion = (
        db.query(models.Exclusion)
        .join(models.Exclusion.trip)
        .join(models.Trip.bus)
        .filter(
            models.Exclusion.id == exclusion_id,
            models.Bus.owner_id == current_user.id
        )
        .first()
    )

    # 2. If it doesn't exist or doesn't belong to the user, raise 404.
    if not exclusion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exclusion not found or you do not have permission to delete it."
        )

    # 3. Delete the exclusion.
    db.delete(exclusion)
    db.commit()

    # 4. Return nothing, as indicated by the 204 status code.
    return

@router.get("/", response_model=List[schemas.TripBasicInfo])
def search_trips(
    search_query: Optional[str] = Query(None, min_length=2, description="Search trip by route name"),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db)
):
    """
    Search for trips based on route name, owned by the current user's bus.
    """
    query = db.query(models.Trip).join(models.Bus).filter(
        models.Bus.owner_id == current_user.id
    )

    if search_query:
        # Use ilike for case-insensitive search if using PostgreSQL, otherwise use like
        query = query.filter(func.lower(models.Trip.route_name).like(f"%{search_query.lower()}%"))
        # For SQLite or MySQL, use: query = query.filter(models.Trip.route_name.like(f"%{search_query}%"))

    # Limit the number of results to prevent overwhelming the client
    trips = query.limit(10).all()
    return trips


@router.post("/stops", response_model=schemas.StopOut, status_code=status.HTTP_201_CREATED)
def create_stop(
    stop_in: schemas.StopCreate, 
    db: Session = Depends(database.get_db), 
    current_user: models.User = Depends(auth.get_current_user)
):
    """
    Create a new stop. Only authenticated users can perform this action.
    - Checks if a stop with the same name already exists to prevent duplicates.
    """
    db_stop = db.query(models.Stop).filter(models.Stop.name == stop_in.name).first()
    if db_stop:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stop with name '{stop_in.name}' already exists."
        )

    new_stop = models.Stop(**stop_in.model_dump())
    
    db.add(new_stop)
    db.commit()
    db.refresh(new_stop)
    
    return new_stop




# GET /union/stops/{stop_id} - Get a single stop by ID
@router.get("/stops/{stop_id}", response_model=schemas.StopOut)
def get_stop_by_id(
    stop_id: int, 
    db: Session = Depends(database.get_db)
):
    """
    Retrieve a single stop by its ID.
    """
    stop = db.query(models.Stop).filter(models.Stop.id == stop_id).first()
    if not stop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stop with id {stop_id} not found"
        )
    return stop




# PUT /union/stops/{stop_id} - Update an existing stop
@router.put("/stops/{stop_id}", response_model=schemas.StopOut)
def update_stop(
    stop_id: int, 
    stop_update: schemas.StopUpdate, 
    db: Session = Depends(database.get_db), 
    current_user: models.User = Depends(auth.get_current_user)
):
    """
    Update an existing stop. Only authenticated users can perform this action.
    - Finds the stop by ID.
    - Updates only the fields provided in the request body.
    """
    stop_query = db.query(models.Stop).filter(models.Stop.id == stop_id)
    db_stop = stop_query.first()

    if not db_stop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stop with id {stop_id} not found"
        )

    # Get the update data, excluding unset fields to avoid overwriting with null
    update_data = stop_update.model_dump(exclude_unset=True)
    
    stop_query.update(update_data, synchronize_session=False)
    db.commit()
    db.refresh(db_stop)
    
    return db_stop

# DELETE /union/stops/{stop_id} - Delete a stop
@router.delete("/stops/{stop_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_stop(
    stop_id: int, 
    db: Session = Depends(database.get_db), 
    current_user: models.User = Depends(auth.get_current_user)
):
    """
    Delete a stop by its ID. Only authenticated users can perform this action.
    - Finds the stop and deletes it.
    - Returns 204 No Content on successful deletion.
    """
    stop_to_delete = db.query(models.Stop).filter(models.Stop.id == stop_id).first()

    if not stop_to_delete:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stop with id {stop_id} not found"
        )
    
    db.delete(stop_to_delete)
    db.commit()
    
    # Return a response with a 204 status code, which has no body
    return Response(status_code=status.HTTP_204_NO_CONTENT)

# In your main router file (e.g., main.py)

@router.get("/submit-stop-crowd-report", response_class=HTMLResponse)
async def get_stop_crowd_report_form(request: Request):
    """
    Renders the HTML page for users to submit a crowd report for a bus stop.
    """
    return templates.TemplateResponse("submit_stop_crowd_report.html", {"request": request})


@router.post(
    "/stops/crowd_reports",
    response_model=schemas.StopCrowdReportOut,
    status_code=status.HTTP_201_CREATED
)
def create_stop_crowd_report(
    report_in: schemas.StopCrowdReportCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    stop = db.query(models.Stop).get(report_in.stop_id)
    if not stop:
        raise HTTPException(404, "Stop not found")

    new_report = models.StopCrowdReport(
        stop_id       = report_in.stop_id,
        reporter_id   = current_user.id,
        crowd_level   = report_in.crowd_level,
        report_time   = report_in.report_time,
        report_weekday= report_in.report_weekday,
        description   = report_in.description,
        reported_at   = datetime.now(ZoneInfo("Asia/Kolkata"))
    )
    db.add(new_report)
    db.commit()
    db.refresh(new_report)

    # This ensures Pydantic serialization runs, applying use_enum_values
    return schemas.StopCrowdReportOut.model_validate(new_report)
