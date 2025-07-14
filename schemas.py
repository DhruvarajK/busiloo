from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_serializer
from typing import List, Literal, Optional, Union
from datetime import datetime, time, date
from enum import Enum

from models import StopIssueType,Weekday,KeralaDistrict

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
    is_admin: bool  
    
class AdminData(BaseModel):
    message: str
    sensitive_data: str

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
    district: Optional[KeralaDistrict] = None  # now uses Enum
    loc_link: Optional[str] = None



class StopUpdate(BaseModel):
    name: Optional[str] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    district: KeralaDistrict
    loc_link: Optional[str] = None


class StopOut(BaseModel):
    id: int
    name: str
    latitude: Optional[str]
    longitude: Optional[str]
    district: KeralaDistrict
    loc_link: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
    
    @model_serializer(when_used="json")
    def serialize_district(self):
        data = self.model_dump()
        if self.district:
            data['district'] = str(self.district) # Convert enum to its string name
        return data


class StopTimeCreate(BaseModel):
    stop_id: int
    arrival_time: time
    sequence: int

class ServiceDayCreate(BaseModel):
    weekday: Weekday

class TripUpdate(BaseModel):
    departure_time: time
    stop_times: List[StopTimeCreate]
    service_days: Optional[List[ServiceDayCreate]]  
    
    

class CrowdReportOut(BaseModel):

    crowd_level: int
    description: Optional[str] = None
    report_time: time

    class Config:
        from_attributes = True

    
class StopTimeOut(BaseModel):
    stop_id: int
    stop_name: str
    arrival_time: time
    sequence: int
    latitude: Optional[str]
    longitude: Optional[str]
    loc_link: Optional[str]
    crowd_report: Optional[CrowdReportOut] = None

    class Config:
        from_attributes = True

class ServiceDayOut(BaseModel):
    weekday: Weekday
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
    crowd_level: int = Field(..., ge=1, le=3) 

class CrowdSubmissionOut(BaseModel):
    bus_id: int
    crowd_level: int
    timestamp: datetime
    model_config = ConfigDict(from_attributes=True)

class CrowdPredictionOut(BaseModel):
    bus_id: int
    predicted_level: Optional[int] = None  
    description: Optional[str] = None  
    based_on_count: int  
    recommended_action: Optional[str] = None  

class BusArrival(BaseModel):
    bus_id: int
    bus_name: str
    trip_name: str
    arrival_time: time

class NearbyBusesResponse(BaseModel):
  
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
    severity: int = Field(..., ge=1, le=3)  
    latitude: float
    longitude: float
    route_name: Optional[str] = None  

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
    
    start_stop_name: str
    end_stop_name: str
    distance_km: float
    routes_found: List[RouteFareDetail]
    

class StopIssueBase(BaseModel):
   
    stop_id: int
    issue_type: StopIssueType
    description: str

class StopIssueCreate(StopIssueBase):
   
    user_id: Optional[int] = None

class StopIssue(StopIssueBase):
   
    id: int
    status: str
    reported_at: datetime
    user_id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)
    


class TransferLeg(BaseModel):
    bus_id: int
    bus_name: str
    route_name: str
    direction: str
    start_stop_name: str
    end_stop_name: str
    departure_time: time
    arrival_time: time

class TransferRouteResult(BaseModel):
    first_leg: TransferLeg
    second_leg: TransferLeg
    transfer_at_stop_name: str
    transfer_wait_time: str
    

class CombinedRouteResponse(BaseModel):
    type: str
    results: Optional[Union[List[RouteResult], List[TransferRouteResult]]] = None
    
    
class StopCrowdReportCreate(BaseModel):
    stop_id: int
    crowd_level: int = Field(..., ge=1, le=3, description="Crowd level: 1=Low, 2=Medium, 3=High")
    report_time: time
    report_weekday: Weekday
    description: Optional[str] = None

    
    model_config = ConfigDict(from_attributes=True)


class StopCrowdReportOut(StopCrowdReportCreate):
    id: int
    reporter_id: int
    reported_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=True,     
    )
    
class StopInfoForIssue(BaseModel):
    """Minimal stop info to be nested in an issue."""
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)

class UserInfoForIssue(BaseModel):
    """Minimal user info for nesting."""
    id: int
    username: str
    model_config = ConfigDict(from_attributes=True)

class StopIssueDetailOut(BaseModel):
    """Detailed schema for displaying an issue in the admin panel."""
    id: int
    issue_type: StopIssueType
    description: str
    status: str
    reported_at: datetime
    stop: StopInfoForIssue  # Nested stop data
    user: Optional[UserInfoForIssue] = None # Reporter can be anonymous
    
    model_config = ConfigDict(from_attributes=True)

class StopIssueUpdate(BaseModel):
    """Schema for updating the status of an issue."""
    status: Literal["reported", "in_progress", "resolved"]
    

class BusWithTripCount(BaseModel):
    id: int
    name: str
    registration_no: str
    is_ls: bool
    num_trips: int
    model_config = ConfigDict(from_attributes=True)
