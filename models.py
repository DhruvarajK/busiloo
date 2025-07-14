from zoneinfo import ZoneInfo
from sqlalchemy import Column, Date, Float, Integer, String, Boolean, ForeignKey, DateTime, Text, Time
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime
from sqlalchemy import Enum as SQLEnum
import enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import MetaData

# Clear existing metadata if any
metadata = MetaData()

# Then define your models using this metadata
Base = declarative_base(metadata=metadata)

class Weekday(enum.Enum):
    monday = 0
    tuesday = 1
    wednesday = 2
    thursday = 3
    friday = 4
    saturday = 5
    sunday = 6


class User(Base):
    __tablename__ = "users"
    __table_args__ = {'extend_existing': True}
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    buses = relationship("Bus", back_populates="owner")
    crowd_submissions = relationship("CrowdSubmission", back_populates="user")
    app_feedback = relationship("AppFeedback", back_populates="user", cascade="all, delete-orphan")
    stop_crowd_reports = relationship("StopCrowdReport", back_populates="reporter", cascade="all, delete-orphan")
    stop_issues = relationship("StopIssue", back_populates="user")

# --- NEW: Enum for Stop Issue Types ---
class StopIssueType(str, enum.Enum):
    """Enumeration for the type of issue being reported for a stop."""
    INCORRECT_LOCATION = "incorrect_location"
    STOP_DAMAGED = "stop_damaged"
    STOP_NAME_INCORRECT = "stop_name_incorrect"
    OTHER = "other"

class KeralaDistrict(enum.Enum):
    Thiruvananthapuram = 1
    Kollam = 2
    Pathanamthitta = 3
    Alappuzha = 4
    Kottayam = 5
    Idukki = 6
    Ernakulam = 7
    Thrissur = 8
    Palakkad = 9
    Malappuram = 10
    Kozhikode = 11
    Wayanad = 12
    Kannur = 13
    Kasaragod = 14
    
    def __str__(self):
        return self.name

class Stop(Base):
    __tablename__ = "stops"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, index=True)
    latitude = Column(String, nullable=True)
    longitude = Column(String, nullable=True)
    district = Column(SQLEnum(KeralaDistrict, name="kerala_district"), nullable=True, index=True)
    loc_link = Column(String, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    stop_times = relationship("StopTime", back_populates="stop")
    traffic_blocks = relationship("TrafficBlock", back_populates="nearest_stop")
    crowd_reports = relationship("StopCrowdReport", back_populates="stop", cascade="all, delete-orphan")
    issues = relationship("StopIssue", back_populates="stop", cascade="all, delete-orphan")

# --- NEW: StopIssue Model ---
class StopIssue(Base):
    """Represents an issue reported by a user for a specific bus stop."""
    __tablename__ = "stop_issues"
    id = Column(Integer, primary_key=True, index=True)
    stop_id = Column(Integer, ForeignKey("stops.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True) # Optional for anonymous reports
    issue_type = Column(SQLEnum(StopIssueType), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String, default="reported", nullable=False) # e.g., reported, in_progress, resolved
    reported_at = Column(DateTime, default=lambda: datetime.now(ZoneInfo("Asia/Kolkata")))

    stop = relationship("Stop", back_populates="issues")
    user = relationship("User", back_populates="stop_issues")
    
class Bus(Base):
    __tablename__ = "buses"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    registration_no = Column(String, unique=True, index=True, nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    is_ls = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="buses")
    trips = relationship("Trip", back_populates="bus")
    crowd_submissions = relationship("CrowdSubmission", back_populates="bus", cascade="all, delete-orphan")
    bus_exclusions = relationship("BusExclusion", back_populates="bus", cascade="all, delete-orphan") 


class BusExclusion(Base):
    __tablename__ = "bus_exclusions"
    id = Column(Integer, primary_key=True, index=True)
    bus_id = Column(Integer, ForeignKey("buses.id"), nullable=False)
    date = Column(Date, nullable=False)
    
    bus = relationship("Bus", back_populates="bus_exclusions") 




class Trip(Base):
    __tablename__ = "trips"
    id = Column(Integer, primary_key=True, index=True)
    bus_id = Column(Integer, ForeignKey("buses.id"), nullable=False)
    route_name = Column(String, nullable=False, index=True)
    departure_time = Column(Time, nullable=False)
    direction = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    bus = relationship("Bus", back_populates="trips")
    stop_times = relationship("StopTime", back_populates="trip", cascade="all, delete-orphan", order_by="StopTime.sequence")
    service_days = relationship("ServiceDay", back_populates="trip", cascade="all, delete-orphan")
    exclusions = relationship("Exclusion", back_populates="trip", cascade="all, delete-orphan")

class StopTime(Base):
    __tablename__ = "stop_times"
    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False)
    stop_id = Column(Integer, ForeignKey("stops.id"), nullable=False)
    arrival_time = Column(Time, nullable=False)
    sequence = Column(Integer, nullable=False)

    trip = relationship("Trip", back_populates="stop_times")
    stop = relationship("Stop", back_populates="stop_times")

class ServiceDay(Base):
    __tablename__ = "service_days"
    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False)
    weekday = Column(SQLEnum(Weekday), nullable=False)

    trip = relationship("Trip", back_populates="service_days")

class Exclusion(Base):
    __tablename__ = "exclusions"
    id = Column(Integer, primary_key=True, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=False)
    date = Column(Date, nullable=False) # Changed from DateTime to Date

    trip = relationship("Trip", back_populates="exclusions")
    


class CrowdSubmission(Base):
    __tablename__ = "crowd_submissions"
    id = Column(Integer, primary_key=True, index=True)
    bus_id = Column(Integer, ForeignKey("buses.id"), nullable=False)
    # Optionally record user_id if logged-in users:
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # crowd_level: 1=low, 2=medium, 3=high (you can extend)
    crowd_level = Column(Integer, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    bus = relationship("Bus", back_populates="crowd_submissions")
    user = relationship("User", back_populates="crowd_submissions", foreign_keys=[user_id])
    
    
class AppFeedback(Base):
    __tablename__ = "app_feedback"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # optional if not logged in
    category = Column(String, nullable=False)  # e.g. bug, suggestion, question
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(ZoneInfo("Asia/Kolkata")))

    user = relationship("User", back_populates="app_feedback", foreign_keys=[user_id])



class TrafficBlock(Base):
    __tablename__ = "traffic_blocks"
    id = Column(Integer, primary_key=True, index=True)
    description = Column(String, nullable=False)
    severity = Column(Integer, nullable=False)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    route_name = Column(String, nullable=True)
    is_confirmed = Column(Boolean, default=False)
    nearest_stop_id = Column(Integer, ForeignKey("stops.id"), nullable=True)
    reported_time = Column(DateTime, default=lambda: datetime.now(ZoneInfo("Asia/Kolkata")), nullable=False)
    nearest_stop = relationship("Stop", back_populates="traffic_blocks")

class StopCrowdReport(Base):
    """
    Represents a crowd level report for a specific bus stop,
    submitted by a user (union member) for a given time and weekday.
    """
    __tablename__ = "stop_crowd_reports"
    id = Column(Integer, primary_key=True, index=True)
    stop_id = Column(Integer, ForeignKey("stops.id"), nullable=False)
    reporter_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # User who reported the crowd
    crowd_level = Column(Integer, nullable=False)  # e.g., 1=Low, 2=Medium, 3=High
    report_time = Column(Time, nullable=False)  # Time of day the crowd was observed
    report_weekday = Column(SQLEnum(Weekday), nullable=False)  # Day of the week
    description = Column(Text, nullable=True)  # Optional additional details
    reported_at = Column(DateTime, default=lambda: datetime.now(ZoneInfo("Asia/Kolkata"))) # Timestamp of report submission

    stop = relationship("Stop", back_populates="crowd_reports")
    reporter = relationship("User", back_populates="stop_crowd_reports")
