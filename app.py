#!/usr/bin/env python
# coding: utf-8

from fastapi import FastAPI, HTTPException, Depends
import uvicorn
from pydantic import BaseModel
from typing import List
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Text
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, Session

# 初始化数据库
DATABASE_URL = "sqlite:///./smart_home.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 数据库模型
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    house_area = Column(float)  # 添加房屋面积字段，单位比如平方米

class Device(Base):
    __tablename__ = "devices"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    type = Column(String)
    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User")

class SecurityEvent(Base):
    __tablename__ = "security_events"
    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String)
    description = Column(Text)
    device_id = Column(Integer, ForeignKey("devices.id"))
    device = relationship("Device")

class Feedback(Base):
    __tablename__ = "feedback"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    feedback_text = Column(Text)
    user = relationship("User")

Base.metadata.create_all(bind=engine)


# Pydantic 模型
class UserCreate(BaseModel):
    name: str
    email: str
    password: str
    house_area: float = Field(..., gt=0, description="房屋面积（平方米），必须大于 0")

class DeviceCreate(BaseModel):
    name: str
    type: str
    owner_id: int

class SecurityEventCreate(BaseModel):
    event_type: str
    description: str
    device_id: int

class FeedbackCreate(BaseModel):
    user_id: int
    feedback_text: str


# FastAPI 应用
app = FastAPI()

@app.get("/")
async def read_root():
    return {"message": "Welcome to the Smart Home API. Use /api for API endpoint information."}

@app.get("/api")
async def read_api():
    return {"message": "This is the API endpoint"}


# 依赖项
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



# 用户管理
@app.post("/users/", response_model=UserCreate)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = User(
        name=user.name,
        email=user.email,
        password=user.password,
        house_area=user.house_area
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.get("/users/", response_model=List[UserCreate])
def read_users(db: Session = Depends(get_db)):
    return db.query(User).all()


# 设备管理
@app.post("/devices/", response_model=DeviceCreate)
def create_device(device: DeviceCreate, db: Session = Depends(get_db)):
    db_device = Device(name=device.name, type=device.type, owner_id=device.owner_id)
    db.add(db_device)
    db.commit()
    db.refresh(db_device)
    return db_device

@app.get("/devices/", response_model=List[DeviceCreate])
def read_devices(db: Session = Depends(get_db)):
    return db.query(Device).all()


# 安防事件管理
@app.post("/security_events/", response_model=SecurityEventCreate)
def create_security_event(event: SecurityEventCreate, db: Session = Depends(get_db)):
    db_event = SecurityEvent(event_type=event.event_type, description=event.description, device_id=event.device_id)
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event

@app.get("/security_events/", response_model=List[SecurityEventCreate])
def read_security_events(db: Session = Depends(get_db)):
    return db.query(SecurityEvent).all()


# 用户反馈管理
@app.post("/feedback/", response_model=FeedbackCreate)
def create_feedback(feedback: FeedbackCreate, db: Session = Depends(get_db)):
    db_feedback = Feedback(user_id=feedback.user_id, feedback_text=feedback.feedback_text)
    db.add(db_feedback)
    db.commit()
    db.refresh(db_feedback)
    return db_feedback

@app.get("/feedback/", response_model=List[FeedbackCreate])
def read_feedback(db: Session = Depends(get_db)):
    return db.query(Feedback).all()

# 分析不同设备的使用频率和使用时间段
class DeviceUsage(Base):
    __tablename__ = "device_usage"
    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("devices.id"))
    user_id = Column(Integer, ForeignKey("users.id"))  # 关联用户
    usage_start = Column(String)  # 使用开始时间
    usage_end = Column(String)  # 使用结束时间
    duration = Column(Integer)  # 使用时长（秒）
    device = relationship("Device")
    user = relationship("User")

class DeviceUsageCreate(BaseModel):
    device_id: int
    usage_time: str
    duration: int

@app.post("/device_usage/", response_model=DeviceUsageCreate)
def create_device_usage(usage: DeviceUsageCreate, db: Session = Depends(get_db)):
    db_usage = DeviceUsage(
        device_id=usage.device_id,
        usage_time=usage.usage_time,
        duration=usage.duration,
    )
    db.add(db_usage)
    db.commit()
    db.refresh(db_usage)
    return db_usage

from sqlalchemy import func

@app.get("/device_usage/summary/")
def get_device_usage_summary(db: Session = Depends(get_db)):
    usage_summary = (
        db.query(
            Device.name.label("device_name"),
            func.count(DeviceUsage.id).label("usage_count"),
            func.sum(DeviceUsage.duration).label("total_duration"),
        )
        .join(DeviceUsage, Device.id == DeviceUsage.device_id)
        .group_by(Device.id)
        .all()
    )
    return usage_summary

@app.get("/device_usage/time_distribution/")
def get_device_usage_time_distribution(db: Session = Depends(get_db)):
    time_distribution = (
        db.query(
            Device.name.label("device_name"),
            DeviceUsage.usage_time.label("usage_time"),
            func.count(DeviceUsage.id).label("usage_count"),
        )
        .join(DeviceUsage, Device.id == DeviceUsage.device_id)
        .group_by(Device.id, DeviceUsage.usage_time)
        .all()
    )
    return time_distribution

@app.get("/usage_by_house_area/")
def analyze_usage_by_house_area(db: Session = Depends(get_db)):
    # 按房屋面积分段统计设备使用频率
    results = (
        db.query(
            User.house_area,
            Device.name.label("device_name"),
            func.count(DeviceUsage.id).label("usage_count"),
            func.avg(DeviceUsage.duration).label("avg_duration")
        )
        .join(Device, Device.owner_id == User.id)
        .join(DeviceUsage, Device.id == DeviceUsage.device_id)
        .group_by(User.house_area, Device.name)
        .all()
    )
    return results

@app.post("/users/", response_model=UserCreate)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = User(
        name=user.name,
        email=user.email,
        password=user.password,
        house_area=user.house_area
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.get("/users/{user_id}/house_area/")
def get_user_house_area(user_id: int, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"user_id": user_id, "house_area": db_user.house_area}

@app.get("/users/house_areas/")
def get_all_users_house_areas(db: Session = Depends(get_db)):
    users = db.query(User.id, User.name, User.house_area).all()
    return users
