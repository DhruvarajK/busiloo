import math
from typing import List
from urllib.parse import quote_plus
from fastapi import APIRouter, Request, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from numpy import block
import requests
from sqlalchemy.orm import Session
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from fastapi import Query
from sqlalchemy.orm import aliased
from sqlalchemy import and_, select, exists
import logging
import models, schemas, database
from models import Stop, StopIssue, Trip, ServiceDay, StopTime
from fastapi import BackgroundTasks, Depends, APIRouter
from zoneinfo import ZoneInfo
import overpy
from math import radians, sin, cos, sqrt, atan2
from sqlalchemy import func, and_, select, exists, cast, Float
from sqlalchemy.orm import joinedload


router = APIRouter(prefix="", tags=["public"])
templates = None  # will be set in main

# Use direct Depends for DB

@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})

@router.get("/search_bus", response_class=HTMLResponse)
def search_bus_page(request: Request):
    return templates.TemplateResponse("search_bus.html", {"request": request})

@router.get("/find_route", response_class=HTMLResponse)
def find_route_page(request: Request):
    return templates.TemplateResponse("find_route.html", {"request": request})

@router.get("/api/search_bus", response_model=list[schemas.BusSimple])
def api_search_bus(q: str = Query(..., description="Substring to search bus names"), db: Session = Depends(database.get_db)):
    pattern = f"%{q}%"
    buses = db.query(models.Bus).filter(models.Bus.name.ilike(pattern), models.Bus.is_active == True).order_by(models.Bus.name).limit(20).all()
    return [schemas.BusSimple(id=b.id, name=b.name) for b in buses]


# routers/bus.py (or wherever your router lives)

@router.get("/api/bus/{bus_id}/current_trip", response_model=schemas.TripOut)
def api_current_trip(bus_id: int, db: Session = Depends(database.get_db)):
    try:
        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        weekday_enum = models.Weekday(now.weekday())
    except Exception:
        logging.exception("Error determining current weekday")
        raise HTTPException(status_code=500, detail="Error determining current weekday")

    try:
        trip = (
            db.query(models.Trip)
            .options(
                joinedload(models.Trip.stop_times).joinedload(models.StopTime.stop),
                joinedload(models.Trip.service_days)
            )
            .join(models.ServiceDay)
            .filter(
                models.Trip.bus_id == bus_id,
                models.ServiceDay.weekday == weekday_enum,
                models.Trip.departure_time <= now.time()
            )
            .order_by(models.Trip.departure_time.desc())
            .first()
        )
        if not trip:
            raise HTTPException(status_code=404, detail="No trip available currently for this bus")

        stop_times_out = []
        for st in sorted(trip.stop_times, key=lambda x: x.sequence):
            stop = st.stop
            stop_times_out.append(
                schemas.StopTimeOut(
                    stop_id=stop.id,
                    stop_name=stop.name,
                    arrival_time=st.arrival_time,
                    sequence=st.sequence,
                    latitude=stop.latitude,
                    longitude=stop.longitude,
                    loc_link=stop.loc_link,       # ← include the new link
                )
            )

        service_days_out = [
            schemas.ServiceDayOut(weekday=sd.weekday.name)
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

    except HTTPException:
        raise
    except Exception:
        logging.exception(f"Error fetching current trip for bus {bus_id}")
        raise HTTPException(status_code=500, detail="Internal error fetching current trip")




@router.get("/redirect_to_current_trip/{bus_id}")
def redirect_to_current_trip(bus_id: int, db: Session = Depends(database.get_db)):
    bus = db.query(models.Bus).filter(models.Bus.id == bus_id).first()
    if not bus:
        raise HTTPException(status_code=404, detail="Bus not found")

    name_enc = quote_plus(bus.name)
    return RedirectResponse(f"/current_trip?bus_id={bus.id}&bus_name={name_enc}")


# Template route: render current_trip.html, expecting bus_id & bus_name as query params
@router.get("/current_trip", response_class=HTMLResponse)
def current_trip_page(request: Request, bus_id: int, bus_name: str):
    # Optionally: you could fetch some data server-side here and pass into template.
    return templates.TemplateResponse(
        "current_trip.html",
        {
            "request": request,
            "bus_id": bus_id,
            "bus_name": bus_name,
        }
    )



logger = logging.getLogger(__name__)



MIN_TRANSFER_MINUTES = 5

@router.get("/api/find_route_results", response_model=schemas.CombinedRouteResponse)
def api_find_route_results(
    start_stop_id: int = Query(..., description="Starting stop ID"),
    end_stop_id: int = Query(..., description="Ending stop ID"),
    db: Session = Depends(database.get_db)
):
    """
    Finds bus routes, prioritizing direct routes. If no direct routes are
    available, it searches for routes with one transfer using a robust
    Python-based connection logic.
    """
    # --- Setup: Time and Date ---
    # Get the current time in the correct timezone
    now_dt = datetime.now(ZoneInfo("Asia/Kolkata"))
    now_time = now_dt.time()
    today_weekday = models.Weekday(now_dt.weekday())
    today_date = now_dt.date()

    # --- 1. First, try to find a direct route (Existing logic) ---
    st_start_direct = aliased(models.StopTime)
    st_end_direct = aliased(models.StopTime)
    
    direct_query = (
        db.query(models.Trip, models.Bus, st_start_direct.arrival_time, st_end_direct.arrival_time)
        .join(models.Bus, models.Bus.id == models.Trip.bus_id)
        .join(st_start_direct, st_start_direct.trip_id == models.Trip.id)
        .join(st_end_direct, st_end_direct.trip_id == models.Trip.id)
        .join(models.ServiceDay, models.ServiceDay.trip_id == models.Trip.id)
        .filter(
            st_start_direct.stop_id == start_stop_id,
            st_end_direct.stop_id == end_stop_id,
            st_start_direct.sequence < st_end_direct.sequence,
            st_start_direct.arrival_time > now_time,
            models.Bus.is_active == True,
            models.ServiceDay.weekday == today_weekday,
            ~models.Trip.exclusions.any(models.Exclusion.date == today_date)
        )
        .order_by(st_start_direct.arrival_time)
    )
    
    direct_results = direct_query.all()

    if direct_results:
        results_data = [
            schemas.RouteResult(
                bus_id=trip.bus.id, bus_name=trip.bus.name, route_name=trip.route_name,
                direction=trip.direction, start_arrival=start_time, end_arrival=end_time
            ) for trip, bus, start_time, end_time in direct_results
        ]
        return schemas.CombinedRouteResponse(type="direct", results=results_data)

    # --- 2. If no direct routes, search for transfer routes (Updated Logic) ---
    
    # Get names for start and end stops for the response schema
    start_stop = db.query(models.Stop).filter(models.Stop.id == start_stop_id).first()
    end_stop = db.query(models.Stop).filter(models.Stop.id == end_stop_id).first()
    if not start_stop or not end_stop:
        return schemas.CombinedRouteResponse(type="none", results=None)

    # STEP A: Find all possible first legs departing from the start stop
    outbound_trips = {}
    st_start = aliased(models.StopTime)
    
    possible_first_leg_trips = (
        db.query(models.Trip, st_start.arrival_time, st_start.sequence)
        .join(models.Bus, models.Bus.id == models.Trip.bus_id)
        .join(models.ServiceDay, models.ServiceDay.trip_id == models.Trip.id)
        .join(st_start, st_start.trip_id == models.Trip.id)
        .filter(
            st_start.stop_id == start_stop_id,
            st_start.arrival_time > now_time,
            models.Bus.is_active == True,
            models.ServiceDay.weekday == today_weekday,
            ~models.Trip.exclusions.any(models.Exclusion.date == today_date)
        ).all()
    )

    for trip, start_time, start_seq in possible_first_leg_trips:
        subsequent_stops = (
            db.query(models.StopTime)
            .filter(models.StopTime.trip_id == trip.id, models.StopTime.sequence > start_seq)
            .all()
        )
        outbound_trips[trip.id] = {
            "trip": trip,
            "start_time": start_time,
            "transfers": {st.stop_id: st.arrival_time for st in subsequent_stops}
        }

    # STEP B: Find all possible second legs arriving at the end stop
    inbound_trips = {}
    st_end = aliased(models.StopTime)
    
    possible_second_leg_trips = (
        db.query(models.Trip, st_end.arrival_time, st_end.sequence)
        .join(models.Bus, models.Bus.id == models.Trip.bus_id)
        .join(models.ServiceDay, models.ServiceDay.trip_id == models.Trip.id)
        .join(st_end, st_end.trip_id == models.Trip.id)
        .filter(
            st_end.stop_id == end_stop_id,
            models.Bus.is_active == True,
            models.ServiceDay.weekday == today_weekday,
            ~models.Trip.exclusions.any(models.Exclusion.date == today_date)
        ).all()
    )
    
    for trip, end_time, end_seq in possible_second_leg_trips:
        preceding_stops = (
            db.query(models.StopTime)
            .filter(models.StopTime.trip_id == trip.id, models.StopTime.sequence < end_seq)
            .all()
        )
        inbound_trips[trip.id] = {
            "trip": trip,
            "end_time": end_time,
            "origins": {st.stop_id: st.arrival_time for st in preceding_stops}
        }
    
    # STEP C: Connect the legs in Python
    valid_transfers = []
    min_transfer_delta = timedelta(minutes=MIN_TRANSFER_MINUTES)
    today = date.today()

    for trip1_id, leg1_data in outbound_trips.items():
        for transfer_stop_id, leg1_arrival_time in leg1_data["transfers"].items():
            for trip2_id, leg2_data in inbound_trips.items():
                if trip1_id == trip2_id: continue

                if transfer_stop_id in leg2_data["origins"]:
                    leg2_departure_time = leg2_data["origins"][transfer_stop_id]
                    
                    arrival_dt = datetime.combine(today, leg1_arrival_time)
                    departure_dt = datetime.combine(today, leg2_departure_time)
                    
                    # The transfer bus must depart AFTER the first bus arrives (+ buffer).
                    # The departure time of the second leg must also be after the current time.
                    if departure_dt > datetime.combine(today, now_time) and departure_dt >= arrival_dt + min_transfer_delta:
                        valid_transfers.append({
                            "leg1_trip": leg1_data["trip"],
                            "leg2_trip": leg2_data["trip"],
                            "leg1_start_time": leg1_data["start_time"],
                            "leg1_arrival_at_transfer": leg1_arrival_time,
                            "leg2_departure_from_transfer": leg2_departure_time,
                            "leg2_end_time": leg2_data["end_time"],
                            "transfer_stop_id": transfer_stop_id
                        })

    if valid_transfers:
        # Sort results by final arrival time
        valid_transfers.sort(key=lambda x: x["leg2_end_time"])

        results_data = []
        all_transfer_stop_ids = {vt['transfer_stop_id'] for vt in valid_transfers}
        transfer_stops_map = {s.id: s for s in db.query(models.Stop).filter(models.Stop.id.in_(all_transfer_stop_ids))}

        for vt in valid_transfers[:5]: # Limit to the best 5 results
            t1 = vt["leg1_trip"]
            t2 = vt["leg2_trip"]
            transfer_stop = transfer_stops_map.get(vt["transfer_stop_id"])
            
            wait_delta = datetime.combine(today, vt["leg2_departure_from_transfer"]) - datetime.combine(today, vt["leg1_arrival_at_transfer"])
            
            leg1 = schemas.TransferLeg(
                bus_id=t1.bus.id, # <-- ADDED
                bus_name=t1.bus.name, 
                route_name=t1.route_name, 
                direction=t1.direction,
                start_stop_name=start_stop.name, 
                end_stop_name=transfer_stop.name,
                departure_time=vt["leg1_start_time"], 
                arrival_time=vt["leg1_arrival_at_transfer"]
            )
            leg2 = schemas.TransferLeg(
                bus_id=t2.bus.id, # <-- ADDED
                bus_name=t2.bus.name, 
                route_name=t2.route_name, 
                direction=t2.direction,
                start_stop_name=transfer_stop.name, 
                end_stop_name=end_stop.name,
                departure_time=vt["leg2_departure_from_transfer"], 
                arrival_time=vt["leg2_end_time"]
            )
            results_data.append(schemas.TransferRouteResult(
                first_leg=leg1, 
                second_leg=leg2,
                transfer_at_stop_name=transfer_stop.name,
                transfer_wait_time=f"{int(wait_delta.total_seconds() // 60)} min"
            ))
            
        return schemas.CombinedRouteResponse(type="transfer", results=results_data)

    # --- 3. If no routes found at all ---
    return schemas.CombinedRouteResponse(type="none", results=None)



@router.post("/api/bus/{bus_id}/submit_crowd", response_model=schemas.CrowdSubmissionOut)
def submit_crowd(bus_id: int, 
                 payload: schemas.CrowdSubmissionIn,
                 db: Session = Depends(database.get_db),
                 
                 ):
    # Verify bus exists and is active
    bus = db.query(models.Bus).filter(models.Bus.id == bus_id, models.Bus.is_active==True).first()
    if not bus:
        raise HTTPException(status_code=404, detail="Bus not found or inactive")
    # Create submission
    current_user=None
    sub = models.CrowdSubmission(
        bus_id=bus_id,
        user_id=current_user.id if current_user else None,
        crowd_level=payload.crowd_level,
        timestamp=datetime.now(ZoneInfo("Asia/Kolkata"))
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return schemas.CrowdSubmissionOut.from_orm(sub)

@router.get("/api/bus/{bus_id}/crowd_prediction", response_model=schemas.CrowdPredictionOut)
def crowd_prediction(bus_id: int, db: Session = Depends(database.get_db)):
    # Find next departure time for this bus today
    now_dt = datetime.now(ZoneInfo("Asia/Kolkata"))
    today_weekday = now_dt.weekday()  # 0=Mon
    # Query upcoming trip departure for bus_id: reuse logic or simply pick earliest stop_time > now
    # For simplicity: find next departure_time of any trip today for this bus

    # First check if bus exists:
    bus = db.query(models.Bus).filter(models.Bus.id==bus_id, models.Bus.is_active==True).first()
    if not bus:
        raise HTTPException(status_code=404, detail="Bus not found or inactive")
    # Find next departure time from Trip table:
    next_time = None
    trip_alias = Trip
    # join ServiceDay to ensure runs today
    next_trip = (
        db.query(Trip)
        .join(ServiceDay, ServiceDay.trip_id == Trip.id)
        .filter(
            Trip.bus_id==bus_id,
            ServiceDay.weekday == models.Weekday(today_weekday),
            Trip.departure_time > now_dt.time()
        )
        .order_by(Trip.departure_time.asc())
        .first()
    )
    if next_trip:
        next_time = next_trip.departure_time
    else:
        # No more trips today; optionally predict tomorrow’s first? For now, return no upcoming
        return schemas.CrowdPredictionOut(
            bus_id=bus_id,
            predicted_level=None,
            description="No upcoming trip today",
            based_on_count=0,
            recommended_action=None
        )

    # Now prediction: look at past submissions for same bus, same weekday, same hour window.
    # E.g., window +/- 1 hour around next_time.hour
    hour = next_time.hour
    # Filter submissions where timestamp in past weeks: same weekday, and hour within [hour-1, hour+1]
    # We assume timestamp stored in UTC? We stored in Asia/Kolkata zone-aware datetime; extract hour in that timezone
    # For simplicity, extract hour from timestamp (which is in UTC? If naive, adjust accordingly). 
    # Here we assume timestamp in UTC but we want local hour: better store timezone-aware. If naive, convert.
    # We'll extract the hour in UTC then adjust? Simpler: store timestamp in UTC, but extract hour in UTC then shift? For now assume timestamp stored in local.
    # Use extract('dow') or compare weekday via datetime functions in Python instead:
    subs = db.query(models.CrowdSubmission).all()
    # Instead, do in Python after fetching a reasonable number, but could do SQL: here simpler is Python filtering:
    history = db.query(models.CrowdSubmission).filter(models.CrowdSubmission.bus_id==bus_id).all()
    filtered = []
    for s in history:
        # convert UTC timestamp to Asia/Kolkata
        ts = s.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo("Asia/Kolkata"))
        else:
            ts = s.timestamp.astimezone(ZoneInfo("Asia/Kolkata"))
        if ts.weekday() == today_weekday and abs(ts.hour - hour) <= 1:
            filtered.append(s.crowd_level)
    count = len(filtered)
    if count >= 5:
        avg = sum(filtered) / count
        # Round to nearest integer 1,2,3
        pred = int(round(avg))
        desc_map = {1: "Low", 2: "Medium", 3: "High"}
        desc = desc_map.get(pred, "Unknown")
        rec = None
        if pred == 3:
            rec = "Crowd likely high; consider earlier bus or alternate route"
        elif pred == 2:
            rec = "Moderate crowd expected"
        else:
            rec = "Likely low crowd"
    else:
        # insufficient data: try broader: same weekday any hour?
        broader = [s for s in history if True and (
            (s.timestamp.tzinfo is None and s.timestamp.weekday()==today_weekday) or 
            (s.timestamp.tzinfo and s.timestamp.astimezone(ZoneInfo("Asia/Kolkata")).weekday()==today_weekday)
        )]
        cb = len(broader)
        if cb >= 5:
            avg = sum(s.crowd_level for s in broader) / cb
            pred = int(round(avg))
            desc_map = {1: "Low", 2: "Medium", 3: "High"}
            desc = desc_map.get(pred, "Unknown")
            rec = None
            if pred == 3:
                rec = "High crowd likely on this bus around this weekday"
            elif pred == 2:
                rec = "Moderate crowd likely"
            else:
                rec = "Likely low crowd"
            count = cb
        else:
            # not enough data at all
            return schemas.CrowdPredictionOut(
                bus_id=bus_id,
                predicted_level=None,
                description="Have a nice Day",
                based_on_count=count,
                recommended_action=None
            )
    return schemas.CrowdPredictionOut(
        bus_id=bus_id,
        predicted_level=pred,
        description=desc,
        based_on_count=count,
        recommended_action=rec
    )



@router.get("/api/nearby_buses", response_model=schemas.NearbyBusesResponse)
def api_nearby_buses(
    lat: float = Query(..., description="User's current latitude"),
    lon: float = Query(..., description="User's current longitude"),
    db: Session = Depends(database.get_db)
):
    """
    Finds the nearest stop to the user's location and lists all upcoming
    bus arrivals at that stop for the current day.
    """
    logger = logging.getLogger(__name__)

    # Find the nearest stop.
    # NOTE: This uses Euclidean distance on lat/lon, which is a simplification.
    # For a production app, consider using a geospatial index or the Haversine formula.
    # We must also cast the latitude/longitude columns from String to Float for the calculation.
    try:
        nearest_stop = db.query(models.Stop).order_by(
            func.sqrt(
                func.pow(cast(models.Stop.latitude, Float) - lat, 2) +
                func.pow(cast(models.Stop.longitude, Float) - lon, 2)
            )
        ).first()
    except Exception as e:
        logger.error(f"Database error while finding the nearest stop: {e}")
        raise HTTPException(status_code=500, detail="Could not process stop locations.")

    if not nearest_stop:
        raise HTTPException(status_code=404, detail="No bus stops could be found in the database.")

    # We found a stop, now get the current time and day to find upcoming buses.
    now_dt = datetime.now(ZoneInfo("Asia/Kolkata"))
    now_time = now_dt.time()
    today_weekday = models.Weekday(now_dt.weekday())
    today_date = now_dt.date()

    # Subquery to filter out trips that have an exclusion for today.
    exclusion_subquery = select(models.Exclusion.id).where(
        and_(
            models.Exclusion.trip_id == models.Trip.id,
            models.Exclusion.date == today_date
        )
    )

    # Query for all upcoming arrivals at the nearest stop.
    try:
        upcoming_arrivals = (
            db.query(
                models.Bus.id.label("bus_id"),
                models.Bus.name.label("bus_name"),
                models.Trip.route_name,
                models.StopTime.arrival_time
            )
            .join(models.Trip, models.Trip.bus_id == models.Bus.id)
            .join(models.StopTime, models.StopTime.trip_id == models.Trip.id)
            .join(models.ServiceDay, models.ServiceDay.trip_id == models.Trip.id)
            .filter(
                models.StopTime.stop_id == nearest_stop.id,
                models.Bus.is_active == True,
                models.ServiceDay.weekday == today_weekday,
                models.StopTime.arrival_time >= now_time,  # Only show buses arriving from now onwards
                ~exists(exclusion_subquery)  # Ensure the trip is not excluded today
            )
            .order_by(models.StopTime.arrival_time)
            .all()
        )
    except Exception as e:
        logger.error(f"Database error while fetching upcoming arrivals: {e}")
        raise HTTPException(status_code=500, detail="Could not retrieve bus arrival times.")

    # Format the results using our Pydantic schemas.
    arrivals_out = [
        schemas.BusArrival(
            bus_id=arrival.bus_id,
            bus_name=arrival.bus_name,
            trip_name=arrival.route_name,
            arrival_time=arrival.arrival_time
        ) for arrival in upcoming_arrivals
    ]


    return schemas.NearbyBusesResponse(
        nearest_stop=schemas.StopOut.from_orm(nearest_stop),
        arrivals=arrivals_out
    )

# Also, add a route to serve the new HTML page.
@router.get("/nearby", response_class=HTMLResponse)
def nearby_page(request: Request):
    return templates.TemplateResponse("nearby.html", {"request": request})


@router.get("/traffic_report", response_class=HTMLResponse)
def nearby_page(request: Request):
    return templates.TemplateResponse("traffic_report.html", {"request": request})






def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth's radius in km
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

def find_nearest_stop(lat, lon, db, max_distance_km=2.0):
    stops = db.query(models.Stop).all()
    nearest_stop = None
    min_distance = float('inf')
    for stop in stops:
        if stop.latitude and stop.longitude:
            distance = haversine(lat, lon, float(stop.latitude), float(stop.longitude))
            if distance < min_distance and distance <= max_distance_km:
                min_distance = distance
                nearest_stop = stop
    return nearest_stop

def is_user_on_road(lat, lon):
    api = overpy.Overpass()
    query = f"""
    [out:json];
    way["highway"](around:50, {lat}, {lon});
    out center;
    """
    try:
        result = api.query(query)
        return len(result.ways) > 0
    except:
        return False

def process_traffic_block_approval(traffic_block_id: int, lat: float, lon: float, db: Session):
    print("bg started")
    try:
        # Check if user is on a road
        on_road = is_user_on_road(lat, lon)
        if not on_road:
            return  # Do not approve if user is not on a road
        
        # Find nearest stop within 1 km
        nearest_stop = find_nearest_stop(lat, lon, db, max_distance_km=1.0)
        
        # Update traffic block
        db_traffic_block = db.query(models.TrafficBlock).filter(models.TrafficBlock.id == traffic_block_id).first()
        if db_traffic_block:
            db_traffic_block.is_confirmed = bool(nearest_stop)  # Approve only if a stop is found
            db_traffic_block.nearest_stop_id = nearest_stop.id if nearest_stop else None
            db.commit()
    except Exception as e:
        print(f"Error processing traffic block {traffic_block_id}: {str(e)}")

@router.post("/api/traffic_blocks/", response_model=schemas.TrafficBlockOut)
def create_traffic_block(
    traffic_block: schemas.TrafficBlockCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(database.get_db)
):
    # Create traffic block with default values
    db_traffic_block = models.TrafficBlock(
        description=traffic_block.description,
        severity=traffic_block.severity,
        latitude=traffic_block.latitude,
        longitude=traffic_block.longitude,
        route_name=traffic_block.route_name,
        is_confirmed=False,
        nearest_stop_id=None,
        reported_time=datetime.now(ZoneInfo("Asia/Kolkata"))
    )
    db.add(db_traffic_block)
    db.commit()
    db.refresh(db_traffic_block)
    
    # Schedule background task to process approval
    background_tasks.add_task(process_traffic_block_approval, db_traffic_block.id, traffic_block.latitude, traffic_block.longitude, db)
    
    return schemas.TrafficBlockOut.from_orm(db_traffic_block)

def get_current_trip_for_bus(db: Session, bus_id: int):
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    weekday_enum = models.Weekday(now.weekday())

    return (
        db.query(models.Trip)
        .options(
            joinedload(models.Trip.stop_times).joinedload(models.StopTime.stop),
        )
        .join(models.ServiceDay)
        .filter(
            models.Trip.bus_id == bus_id,
            models.ServiceDay.weekday == weekday_enum,
            models.Trip.departure_time <= now.time(),
        )
        .order_by(models.Trip.departure_time.desc())
        .first()
    )

@router.get("/api/bus/{bus_id}/traffic_notifications", response_model=List[schemas.TrafficNotificationOut])
def get_traffic_notifications(bus_id: int, db: Session = Depends(database.get_db)):
    """
    Gets confirmed traffic notifications for an active bus trip.
    
    A notification is generated for a stop if:
    1. The bus has not yet passed the stop (based on scheduled time).
    2. More than 3 traffic reports have been made near that stop.
    3. The reports were made within the last hour.
    """
    try:
        # Step 1: Get the current trip for the bus
        current_trip = get_current_trip_for_bus(db, bus_id=bus_id)
        if not current_trip:
            # No active trip, so no notifications to return
            return []

        # Step 2: Define time thresholds
        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        one_hour_ago = now - timedelta(hours=1)
        
        notifications = []

        # Step 3: Iterate through the stops of the current trip, sorted by sequence
        sorted_stop_times = sorted(current_trip.stop_times, key=lambda st: st.sequence)
        
        for stop_time in sorted_stop_times:
            # THIS IS THE FIX: The incorrect strptime() line has been removed.
            # We directly combine the current date with the stop_time.arrival_time object.
            scheduled_arrival_dt = datetime.combine(now.date(), stop_time.arrival_time).replace(tzinfo=ZoneInfo("Asia/Kolkata"))

            # Check if the bus has likely already passed this stop
            if now > scheduled_arrival_dt:
                continue  # Skip to the next stop

            # Step 4: Query for recent, relevant traffic blocks for the current stop
            recent_traffic_reports = (
                db.query(models.TrafficBlock)
                .filter(
                    models.TrafficBlock.nearest_stop_id == stop_time.stop_id,
                    models.TrafficBlock.reported_time >= one_hour_ago,
                )
                .all()
            )
            
            # Step 5: Check if the condition (more than 3 reports) is met
            if len(recent_traffic_reports) > 2:
                total_severity = sum(report.severity for report in recent_traffic_reports)
                average_severity = total_severity / len(recent_traffic_reports)
                
                # Determine traffic level from average severity
                if average_severity < 1.5:
                    severity_level = "Light"
                elif average_severity < 2.5:
                    severity_level = "Moderate"
                else:
                    severity_level = "Heavy"
                
                # Create a dynamic message
                description = f"{severity_level} traffic reported by {len(recent_traffic_reports)} users ahead."

                notification = schemas.TrafficNotificationOut(
                    stop_id=stop_time.stop_id,
                    stop_sequence=stop_time.sequence,
                    description=description,
                    average_severity=round(average_severity, 2),
                )
                notifications.append(notification)

        return notifications

    except Exception as e:
        logging.exception(f"Error fetching traffic notifications for bus {bus_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal error fetching traffic notifications")
   
FARE_STRUCTURES = {
    "ordinary": {
        "min_fare": 10.0,
        "initial_distance_km": 2.5,
        "per_km_rate_paise": 100,  # 1 Rupee per km
    },
    "limited_stop": {  # Assuming Fast Passenger/Limited Stop FP is 'limited_stop'
        "min_fare": 15.0,
        "initial_distance_km": 5.0,
        "per_km_rate_paise": 105,  # 1.05 Rupees per km
    }
}


def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the road distance between two points using the free OSRM API.
    Returns distance in kilometers.
    NOTE: This uses a public demo server, which has usage policies and no uptime guarantee.
    """
    # OSRM API endpoint for the 'route' service
    # Note the coordinate order is {longitude},{latitude}
    url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"
    
    # Parameters to make the response simpler (we only need the distance)
    params = {"overview": "false"}

    try:
        # Make the GET request to the API
        response = requests.get(url, params=params)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

        # Parse the JSON response
        data = response.json()

        # Check if the API returned a valid route ("Ok" code)
        if data["code"] == "Ok":
            # The distance is in the first route's summary, given in meters
            distance_in_meters = data["routes"][0]["distance"]
            
            # Convert meters to kilometers
            distance_in_km = distance_in_meters / 1000
            return distance_in_km
        else:
            print(f"Error from OSRM API: {data.get('message', 'No route found')}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"An error occurred with the network request: {e}")
        return None
    except (KeyError, IndexError):
        print("Error: Could not parse the distance from the API response.")
        return None


# Function to calculate bus fare
def calculate_bus_fare(distance_km: float, is_limited_stop: bool) -> float:
    """
    Calculates the bus fare based on distance and bus type.
    Rounds the fare to the nearest rupee.
    """
    fare_type = "limited_stop" if is_limited_stop else "ordinary"
    fare_config = FARE_STRUCTURES[fare_type]

    min_fare = fare_config["min_fare"]
    initial_distance = fare_config["initial_distance_km"]
    per_km_rate_paise = fare_config["per_km_rate_paise"]

    if distance_km <= initial_distance:
        calculated_fare = min_fare
    else:
        # Calculate fare for distance beyond initial_distance
        additional_distance = distance_km - initial_distance
        additional_fare_paise = additional_distance * per_km_rate_paise
        
        # Convert additional fare to rupees and add to min_fare
        calculated_fare = min_fare + (additional_fare_paise / 100)
    
    # Round to the nearest rupee
    return round(calculated_fare)

   
@router.get("/calculate_fare_page", response_class=HTMLResponse)
def calculate_fare_page(request: Request):
    """
    New endpoint to serve the HTML page for fare calculation.
    """
    return templates.TemplateResponse("calculate_fare.html", {"request": request})
 
    
@router.get("/api/search_stop", response_model=List[schemas.StopOut])
def api_search_stop(q: str = Query(..., description="Substring to search stop names"), db: Session = Depends(database.get_db)):
    """
    API endpoint to search for stops by name.
    """
    pattern = f"%{q}%"
    stops = db.query(models.Stop).filter(models.Stop.name.ilike(pattern)).order_by(models.Stop.name).limit(20).all()
    return [schemas.StopOut.model_validate(s) for s in stops]


@router.get("/api/calculate_fare", response_model=schemas.FareCalculationResult)
def api_calculate_fare(
    start_stop_id: int = Query(..., description="ID of the starting stop"),
    end_stop_id: int = Query(..., description="ID of the ending stop"),
    db: Session = Depends(database.get_db)
):
    """
    Calculates the fare between two stops and lists buses serving that route.
    """
    # 1. Fetch start and end stops
    start_stop = db.query(models.Stop).filter(models.Stop.id == start_stop_id).first()
    end_stop = db.query(models.Stop).filter(models.Stop.id == end_stop_id).first()

    if not start_stop:
        raise HTTPException(status_code=404, detail=f"Start stop with ID {start_stop_id} not found.")
    if not end_stop:
        raise HTTPException(status_code=404, detail=f"End stop with ID {end_stop_id} not found.")

    # Convert lat/long strings to floats
    try:
        start_lat = float(start_stop.latitude)
        start_lon = float(start_stop.longitude)
        end_lat = float(end_stop.latitude)
        end_lon = float(end_stop.longitude)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid latitude or longitude data for stops.")

    # 2. Calculate distance
    distance_km = calculate_distance(start_lat, start_lon, end_lat, end_lon)

    found_routes: List[schemas.RouteFareDetail] = []

    # Aliases for StopTime to distinguish start and end stop times in queries
    StartTimeAlias = aliased(models.StopTime)
    EndTimeAlias = aliased(models.StopTime)

    # 3. Find trips that go from start_stop to end_stop sequentially
    # We need to join Trip with StopTime twice for start and end stops
    # and ensure start_sequence < end_sequence
    trips_on_route = (
        db.query(models.Trip)
        .join(StartTimeAlias, models.Trip.id == StartTimeAlias.trip_id)
        .join(EndTimeAlias, models.Trip.id == EndTimeAlias.trip_id)
        .join(models.Bus, models.Trip.bus_id == models.Bus.id)
        .options(joinedload(models.Trip.bus)) # Eagerly load bus to access is_ls
        .filter(
            StartTimeAlias.stop_id == start_stop_id,
            EndTimeAlias.stop_id == end_stop_id,
            StartTimeAlias.sequence < EndTimeAlias.sequence # Ensure correct sequence
        )
        .all()
    )

    for trip in trips_on_route:
        # Get the arrival times for the specific start and end stops on this trip
        start_stop_time_obj = next((st for st in trip.stop_times if st.stop_id == start_stop_id), None)
        end_stop_time_obj = next((st for st in trip.stop_times if st.stop_id == end_stop_id), None)

        if start_stop_time_obj and end_stop_time_obj:
            # 4. Calculate fare for each bus/trip
            calculated_fare = calculate_bus_fare(distance_km, trip.bus.is_ls)

            found_routes.append(
                schemas.RouteFareDetail(
                    bus_id=trip.bus.id,
                    bus_name=trip.bus.name,
                    is_limited_stop=trip.bus.is_ls,
                    route_name=trip.route_name,
                    direction=trip.direction,
                    departure_time=trip.departure_time,
                    start_arrival_time=start_stop_time_obj.arrival_time,
                    end_arrival_time=end_stop_time_obj.arrival_time,
                    calculated_fare=calculated_fare
                )
            )
    
    return schemas.FareCalculationResult(
        start_stop_name=start_stop.name,
        end_stop_name=end_stop.name,
        distance_km=round(distance_km, 2), # Round distance for display
        routes_found=found_routes
    )


# --- NEW FUNCTION ---
def get_stop_by_name(db: Session, name: str):
    """
    Fetches a single stop by its name.
    It performs a case-insensitive search.
    """
    return db.query(Stop).filter(func.lower(Stop.name) == func.lower(name)).first()


def create_stop_issue(db: Session, issue: schemas.StopIssueCreate) -> schemas.StopIssue:
    """Creates a new stop issue record in the database."""
    db_issue = StopIssue(
        stop_id=issue.stop_id,
        issue_type=issue.issue_type,
        description=issue.description,
        user_id=issue.user_id
    )
    db.add(db_issue)
    db.commit()
    db.refresh(db_issue)
    return db_issue 
    

@router.get("/report-issue-page/{stop_name}", response_class=HTMLResponse)
async def get_report_issue_page_for_stop(
    request: Request, 
    stop_name: str, 
    db: Session = Depends(database.get_db) # Replace Depends() with your get_db dependency
):
    """
    Finds a stop by name and renders the issue reporting page for it.
    This is the endpoint that your href links will point to.
    """
    # Look up the stop in the database using the new CRUD function
    db_stop = get_stop_by_name(db, name=stop_name)

    if not db_stop:
        # You can render a custom 404 template here for a better user experience
        raise HTTPException(status_code=404, detail=f"Stop '{stop_name}' not found")

    # Render the HTML template, passing the stop object to it.
    # The template file should be named 'report_issue.html' in your 'templates' folder.
    return templates.TemplateResponse("report_issue.html", {
        "request": request, 
        "stop": db_stop
    })
    
def get_stop(db: Session, stop_id: int):
    """Fetches a single stop by its ID."""
    return db.query(Stop).filter(Stop.id == stop_id).first()

# --- The endpoint that RECEIVES the form submission ---
# No changes are needed here. The frontend will still send the same JSON payload.
@router.post("/report-issue", response_model=schemas.StopIssue, status_code=201)
def report_issue_for_stop(
    issue: schemas.StopIssueCreate,
    db: Session = Depends(database.get_db) # Replace Depends() with your get_db
):
    """
    Creates a new issue report for a given bus stop.
    """
    # Verify that the stop ID from the form is valid
    db_stop = get_stop(db, stop_id=issue.stop_id)
    if db_stop is None:
        raise HTTPException(status_code=404, detail=f"Stop with ID {issue.stop_id} not found.")

    new_issue = create_stop_issue(db=db, issue=issue)
    return new_issue
