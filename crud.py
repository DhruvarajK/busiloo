from sqlalchemy.orm import Session
import models, schemas, auth
from datetime import datetime
import math

def get_union_by_username(db: Session, username: str):
    return db.query(models.UnionUser).filter(models.UnionUser.username == username).first()

def create_union(db: Session, user: schemas.UnionUserCreate):
    hashed_pwd = auth.get_password_hash(user.password)
    db_user = models.UnionUser(username=user.username, hashed_password=hashed_pwd)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# Bus CRUD

def create_bus(db: Session, union_user: models.UnionUser, bus_in: schemas.BusCreate):
    bus = models.Bus(name=bus_in.name, registration_number=bus_in.registration_number, union_id=union_user.id)
    db.add(bus)
    db.commit()
    db.refresh(bus)
    return bus

# Stop CRUD

def create_stop(db: Session, stop_in: schemas.StopCreate):
    stop = models.Stop(name=stop_in.name, latitude=stop_in.latitude, longitude=stop_in.longitude)
    db.add(stop)
    db.commit()
    db.refresh(stop)
    return stop

# Route CRUD

def create_route(db: Session, route_in: schemas.RouteCreate):
    route = models.Route(name=route_in.name,
                         origin_stop_id=route_in.origin_stop_id,
                         destination_stop_id=route_in.destination_stop_id)
    db.add(route)
    db.commit()
    db.refresh(route)
    return route

def add_route_stop(db: Session, route: models.Route, stop_id: int, sequence: int):
    rs = models.RouteStop(route_id=route.id, stop_id=stop_id, sequence=sequence)
    db.add(rs)
    db.commit()
    return rs

# Trip CRUD

def create_trip(db: Session, trip_in: schemas.TripCreate):
    trip = models.Trip(
        bus_id=trip_in.bus_id,
        route_id=trip_in.route_id,
        direction=trip_in.direction,
        days_of_week=trip_in.days_of_week,
        exception_dates=[d.isoformat() for d in trip_in.exception_dates] if trip_in.exception_dates else [],
        active=True
    )
    db.add(trip)
    db.commit()
    db.refresh(trip)
    # Add TripStops
    for stop_info in trip_in.stops:
        # stop_info: dict with stop_id, sequence, arrival_time string
        tstop = models.TripStop(
            trip_id=trip.id,
            stop_id=stop_info["stop_id"],
            sequence=stop_info["sequence"],
            arrival_time=datetime.strptime(stop_info["arrival_time"], "%H:%M").time()
        )
        db.add(tstop)
    db.commit()
    return trip

# Nearest stops: compute Haversine distance

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000  # meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def get_nearest_stops(db: Session, lat: float, lon: float, limit: int = 5):
    stops = db.query(models.Stop).all()
    result = []
    for s in stops:
        dist = haversine(lat, lon, s.latitude, s.longitude)
        result.append((s, dist))
    result.sort(key=lambda x: x[1])
    return result[:limit]

# Next buses between stops
from datetime import date, datetime, time as dtime

def get_next_buses(db: Session, start_stop_id: int, end_stop_id: int, now_dt: datetime = None):
    if now_dt is None:
        now_dt = datetime.now()
    today = now_dt.date()
    weekday = today.weekday()  # 0=Monday
    # Exclude if today is holiday
    holiday = db.query(models.Holiday).filter(models.Holiday.date == today).first()
    if holiday:
        return []

    # Find all trips that include both stops in correct order
    trips = db.query(models.Trip).filter(models.Trip.active == True).all()
    next_buses = []
    for trip in trips:
        # Check day-of-week and exceptions
        if weekday not in trip.days_of_week:
            continue
        if today.isoformat() in trip.exception_dates:
            continue
        # Get TripStops ordered
        ts_list = sorted(trip.trip_stops, key=lambda x: x.sequence)
        # If reverse direction, order might already reflect reverse
        # Find indices
        indices = {ts.stop_id: ts for ts in ts_list}
        if start_stop_id not in indices or end_stop_id not in indices:
            continue
        start_seq = indices[start_stop_id].sequence
        end_seq = indices[end_stop_id].sequence
        if (trip.direction == 'forward' and start_seq >= end_seq) or (trip.direction == 'reverse' and start_seq >= end_seq):
            # For either direction, sequence must increase from start to end
            continue
        # Scheduled departure time at start stop
        departure_time = indices[start_stop_id].arrival_time
        # If departure_time today already passed
        if now_dt.time() > departure_time:
            continue
        arrival_time = indices[end_stop_id].arrival_time
        # Collect
        next_buses.append({
            'trip_id': trip.id,
            'bus_name': trip.bus.name,
            'departure_time': departure_time.strftime("%H:%M"),
            'arrival_time': arrival_time.strftime("%H:%M"),
            'stops_between': end_seq - start_seq
        })
    # Sort by departure_time
    next_buses.sort(key=lambda x: x['departure_time'])
    return next_buses

# Stop suggestion

def add_stop_suggestion(db: Session, sug):
    suggestion = models.StopSuggestion(
        stop_id=sug.stop_id,
        suggested_latitude=sug.suggested_latitude,
        suggested_longitude=sug.suggested_longitude,
        status="pending"
    )
    db.add(suggestion)
    db.commit()
    db.refresh(suggestion)
    return suggestion