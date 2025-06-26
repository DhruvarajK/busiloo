from pydantic import BaseModel, ConfigDict, EmailStr, Field
from typing import List, Optional
from datetime import datetime, time, date
from enum import Enum

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3)
    email: EmailStr
    password: str = Field(..., min_length=6)

class UserOut(BaseModel):
    id: int
    username: str
    email: EmailStr
    model_config = ConfigDict(from_attributes=True)

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class BusCreate(BaseModel):
    name: str
    registration_no: str
    is_ls: Optional[bool] = False 

class BusOut(BaseModel):
    id: int
    name: str
    registration_no: str
    is_ls: bool 
    model_config = ConfigDict(from_attributes=True)

class StopCreate(BaseModel):
    name: str
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    district: Optional[str] = None
    loc_link: Optional[str] = None

# Schema for updating a stop (input) - all fields are optional
class StopUpdate(BaseModel):
    name: Optional[str] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    district: Optional[str] = None
    loc_link: Optional[str] = None

# Schema for reading/returning a stop (output)
class StopOut(BaseModel):
    id: int
    name: str
    latitude: Optional[str]
    longitude: Optional[str]
    district: Optional[str]
    loc_link: Optional[str]
    created_at: datetime

    # This configuration allows Pydantic to read data from ORM models
    model_config = ConfigDict(from_attributes=True)

class WeekdayEnum(str, Enum):
    monday = "monday"
    tuesday = "tuesday"
    wednesday = "wednesday"
    thursday = "thursday"
    friday = "friday"
    saturday = "saturday"
    sunday = "sunday"

class StopTimeCreate(BaseModel):
    stop_id: int
    arrival_time: time
    sequence: int

class ServiceDayCreate(BaseModel):
    weekday: WeekdayEnum

class TripUpdate(BaseModel):
    departure_time: time
    stop_times: List[StopTimeCreate]
    service_days: Optional[List[ServiceDayCreate]]  # if provided, will replace existing days

class StopTimeOut(BaseModel):
    stop_id: int
    stop_name: str
    arrival_time: time
    sequence: int
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    loc_link: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class ServiceDayOut(BaseModel):
    weekday: WeekdayEnum
    model_config = ConfigDict(from_attributes=True)

class TripOut(BaseModel):
    id: int
    bus_id: int
    route_name: str
    departure_time: time
    direction: str
    stop_times: List[StopTimeOut]
    service_days: List[ServiceDayOut]
    model_config = ConfigDict(from_attributes=True)

class TripCreate(BaseModel):
    bus_id: int
    route_name: str
    departure_time: time
    direction: str
    stop_times: List[StopTimeCreate]
    service_days: List[ServiceDayCreate]

class StopTimeTemplate(BaseModel):
    stop_id: int
    stop_name: str
    latitude: Optional[str]
    longitude: Optional[str]
    sequence: int
    offset_minutes: int

class TripTemplateSummary(BaseModel):
    id: int
    route_name: str
    departure_time: time
    direction: str
    model_config = ConfigDict(from_attributes=True)

class TripTemplateDetail(BaseModel):
    route_name: str
    direction: str
    stop_template: List[StopTimeTemplate]

class ExclusionCreate(BaseModel):
    trip_id: int
    date: date

# Public
class BusSimple(BaseModel):
    id: int
    name: str

class RouteResult(BaseModel):
    bus_id: int
    bus_name: str
    route_name: str
    direction: str
    start_arrival: time
    end_arrival: time

class CrowdSubmissionIn(BaseModel):
    crowd_level: int = Field(..., ge=1, le=3)  # 1=low, 2=medium, 3=high

class CrowdSubmissionOut(BaseModel):
    bus_id: int
    crowd_level: int
    timestamp: datetime
    model_config = ConfigDict(from_attributes=True)

class CrowdPredictionOut(BaseModel):
    bus_id: int
    predicted_level: Optional[int] = None  # None if insufficient data
    description: Optional[str] = None  # e.g., "Low/Medium/High" or "No data"
    based_on_count: int  # number of past submissions used
    recommended_action: Optional[str] = None  # e.g., "Consider an earlier bus" if high

class BusArrival(BaseModel):
    bus_id: int
    bus_name: str
    trip_name: str
    arrival_time: time

class NearbyBusesResponse(BaseModel):
    """The complete response for the nearby buses feature."""
    nearest_stop: StopOut
    arrivals: List[BusArrival]

class AppFeedbackIn(BaseModel):
    category: str = Field(..., min_length=3, max_length=50)
    message: str = Field(..., min_length=10)

class AppFeedbackOut(BaseModel):
    id: int
    category: str
    message: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
    

class TrafficBlockCreate(BaseModel):
    description: str = Field(..., min_length=10)
    severity: int = Field(..., ge=1, le=3)  # 1=low, 2=medium, 3=high
    latitude: float
    longitude: float
    route_name: Optional[str] = None  # Optional route name

class TrafficBlockOut(BaseModel):
    id: int
    description: str
    severity: int
    latitude: float
    longitude: float
    route_name: Optional[str]  # Optional route name
    is_confirmed: bool
    nearest_stop_id: Optional[int]
    reported_time: datetime

    model_config = ConfigDict(from_attributes=True)
    
class TrafficNotificationOut(BaseModel):
    """
    Schema for sending a confirmed traffic notification to the frontend.
    """
    stop_id: int
    stop_sequence: int
    description: str
    average_severity: float
    

class ExclusionCreate(BaseModel):
    trip_id: int
    date: date

class TripBasicInfo(BaseModel):
    """Provides basic trip details for nesting in other schemas."""
    id: int
    route_name: str
    departure_time: time
    direction: str
    model_config = ConfigDict(from_attributes=True)

class ExclusionOut(BaseModel):
    """Schema for returning an exclusion with its trip info."""
    id: int
    date: date
    trip: TripBasicInfo
    model_config = ConfigDict(from_attributes=True)


class RouteFareDetail(BaseModel):
    """Details for a specific bus route found, including its calculated fare."""
    bus_id: int
    bus_name: str
    is_limited_stop: bool
    route_name: str
    direction: str
    departure_time: time
    start_arrival_time: time
    end_arrival_time: time
    calculated_fare: float
    model_config = ConfigDict(from_attributes=True)


class FareCalculationResult(BaseModel):
    """Response model for the fare calculation API."""
    start_stop_name: str
    end_stop_name: str
    distance_km: float
    routes_found: List[RouteFareDetail]