from fastapi import FastAPI, APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timedelta
import jwt
import bcrypt
from bson import ObjectId

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# JWT Configuration
SECRET_KEY = os.environ['JWT_SECRET_KEY']
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

app = FastAPI()
api_router = APIRouter(prefix="/api")
security = HTTPBearer()

# ==================== MODELS ====================

class Company(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_code: str  # Unique company identifier
    company_name: str
    password: str  # Hashed
    created_at: datetime = Field(default_factory=datetime.utcnow)

class CompanyCreate(BaseModel):
    company_code: str
    company_name: str
    password: str

class CompanyLogin(BaseModel):
    company_code: str
    password: str

class CompanyResponse(BaseModel):
    id: str
    company_code: str
    company_name: str

class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_id: str  # Link to company
    username: str
    password: str  # Hashed
    role: str  # "admin" or "staff"
    full_name: str
    email: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class UserCreate(BaseModel):
    company_id: str
    username: str
    password: str
    role: str
    full_name: str
    email: Optional[str] = None

class UserLogin(BaseModel):
    company_id: str
    username: str
    password: str

class UserResponse(BaseModel):
    id: str
    company_id: str
    username: str
    role: str
    full_name: str
    email: Optional[str] = None

class QualityCheckItem(BaseModel):
    name: str
    checked: bool = False
    remarks: str = ""

class SizeQuantity(BaseModel):
    size: str
    quantity: int
    packing_ratio: int = 1

class ProductionSlip(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    company_id: str  # Link to company
    production_slip_no: str
    
    # Order & Delivery Details
    client_model: str
    client_name: str
    print_date: datetime = Field(default_factory=datetime.utcnow)
    season: Optional[str] = None
    sample_approval_date: Optional[datetime] = None
    reference_order_no: str
    order_id: str
    batch_no: str
    delivery_date: datetime
    category: str
    gender: str
    
    # Product Specifications
    shoe_type: str
    width_fitting: str
    heel_height: str
    pattern_version: str
    closure_type: str
    construction_type: str
    size_range: str
    last_number_shape: str
    toe_shape: str
    closure_position: str
    
    # Quantity & Size Matrix
    size_quantities: List[SizeQuantity]
    total_quantity: int
    extra_production_buffer: float = 5.0  # percentage
    
    # Shoe Sketch (base64 image)
    shoe_sketch: Optional[str] = None
    
    # Upper Material
    upper_material_type: str
    upper_color: str
    upper_thickness: str
    upper_grade: str
    upper_special_treatment: Optional[str] = None
    upper_supplier_name: str
    lining_material: str
    lining_color: str
    lining_thickness: str
    collar_material: str
    vamp_reinforcement: str
    
    # Sole Details
    sole_type: str
    sole_color: str
    sole_hardness: str
    sole_mold_no: str
    sole_size_matching: str
    sole_weight: str
    sole_supplier: str
    heel_type: str
    heel_shape: str
    heel_height_detail: str
    heel_fixing_method: str
    welt_color: Optional[str] = None
    outsole_pattern_code: str
    
    # Stitching Details
    thread_brand: str
    thread_color_top: str
    thread_color_bottom: str
    thread_size: str
    stitch_type: str
    spi: str  # Stitch Per Inch
    decorative_stitch: Optional[str] = None
    
    # Process Control
    die_number: str
    cutting_method: str
    defect_marking: str
    grain_direction: str
    skiving_details: str
    reinforcement_required: bool
    upper_trimming: str
    upper_inspection_status: str
    last_number: str
    cement_application_type: str
    activation_temperature: str
    curing_time: str
    adhesive_type: str
    adhesive_open_time: str
    sole_attaching_pressure: str
    heat_setting: str
    
    # Finishing & Branding
    edge_ink_color: str
    waxing: str
    insole_branding: str
    final_polish: str
    size_stamping: str
    care_label: str
    edge_polishing: str
    buffing: str
    cleaning: str
    logo_stamping: str
    country_of_origin_stamp: str
    foil_type: str
    
    # Packaging
    special_instructions: Optional[str] = None
    special_instructions_qc: Optional[str] = None
    special_packaging_instructions: Optional[str] = None
    carton_marking_details: str
    remarks: Optional[str] = None
    box_color: str
    pairing_sticker: str
    box_printing: str
    carton_quantity: int
    
    # Quality Control Checklist
    quality_checks: List[QualityCheckItem] = Field(default_factory=lambda: [
        QualityCheckItem(name="Upper Material Quality Check"),
        QualityCheckItem(name="Stitching & Seam Strength Inspection"),
        QualityCheckItem(name="Sole Bonding Strength Test"),
        QualityCheckItem(name="Size & Measurement Verification"),
        QualityCheckItem(name="Color & Finish Consistency Check"),
        QualityCheckItem(name="Logo / Branding Placement Verification"),
        QualityCheckItem(name="Insole & Comfort Padding Inspection"),
        QualityCheckItem(name="Packaging & Label Accuracy Check"),
    ])
    
    # Status Tracking
    status: str = "Pending"  # Pending, In Progress, Quality Check, Completed
    assigned_to: Optional[str] = None  # User ID of assigned staff
    created_by: str  # User ID of creator
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class ProductionSlipCreate(BaseModel):
    client_model: str
    client_name: str
    season: Optional[str] = None
    sample_approval_date: Optional[datetime] = None
    reference_order_no: str
    order_id: str
    batch_no: str
    delivery_date: datetime
    category: str
    gender: str
    shoe_type: str
    width_fitting: str
    heel_height: str
    pattern_version: str
    closure_type: str
    construction_type: str
    size_range: str
    last_number_shape: str
    toe_shape: str
    closure_position: str
    size_quantities: List[SizeQuantity]
    total_quantity: int
    extra_production_buffer: float = 5.0
    shoe_sketch: Optional[str] = None
    upper_material_type: str
    upper_color: str
    upper_thickness: str
    upper_grade: str
    upper_special_treatment: Optional[str] = None
    upper_supplier_name: str
    lining_material: str
    lining_color: str
    lining_thickness: str
    collar_material: str
    vamp_reinforcement: str
    sole_type: str
    sole_color: str
    sole_hardness: str
    sole_mold_no: str
    sole_size_matching: str
    sole_weight: str
    sole_supplier: str
    heel_type: str
    heel_shape: str
    heel_height_detail: str
    heel_fixing_method: str
    welt_color: Optional[str] = None
    outsole_pattern_code: str
    thread_brand: str
    thread_color_top: str
    thread_color_bottom: str
    thread_size: str
    stitch_type: str
    spi: str
    decorative_stitch: Optional[str] = None
    die_number: str
    cutting_method: str
    defect_marking: str
    grain_direction: str
    skiving_details: str
    reinforcement_required: bool
    upper_trimming: str
    upper_inspection_status: str
    last_number: str
    cement_application_type: str
    activation_temperature: str
    curing_time: str
    adhesive_type: str
    adhesive_open_time: str
    sole_attaching_pressure: str
    heat_setting: str
    edge_ink_color: str
    waxing: str
    insole_branding: str
    final_polish: str
    size_stamping: str
    care_label: str
    edge_polishing: str
    buffing: str
    cleaning: str
    logo_stamping: str
    country_of_origin_stamp: str
    foil_type: str
    special_instructions: Optional[str] = None
    special_instructions_qc: Optional[str] = None
    special_packaging_instructions: Optional[str] = None
    carton_marking_details: str
    remarks: Optional[str] = None
    box_color: str
    pairing_sticker: str
    box_printing: str
    carton_quantity: int
    assigned_to: Optional[str] = None

class ProductionSlipUpdate(BaseModel):
    status: Optional[str] = None
    quality_checks: Optional[List[QualityCheckItem]] = None
    assigned_to: Optional[str] = None
    remarks: Optional[str] = None

class StatusUpdate(BaseModel):
    status: str

class QualityCheckUpdate(BaseModel):
    quality_checks: List[QualityCheckItem]

# ==================== HELPER FUNCTIONS ====================

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = credentials.credentials
    payload = decode_token(token)
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user = await db.users.find_one({"id": user_id}, {"password": 0, "_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user

async def get_admin_user(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

def generate_production_slip_no() -> str:
    """Generate a unique production slip number"""
    year = datetime.utcnow().year
    timestamp = datetime.utcnow().strftime("%m%d%H%M%S")
    return f"SPS-{year}-{timestamp}"

# ==================== AUTHENTICATION ROUTES ====================

# Company Authentication
@api_router.post("/company/register")
async def register_company(company_data: CompanyCreate):
    # Check if company code exists
    existing_company = await db.companies.find_one({"company_code": company_data.company_code})
    if existing_company:
        raise HTTPException(status_code=400, detail="Company code already exists")
    
    # Hash password
    hashed_password = hash_password(company_data.password)
    
    # Create company
    company = Company(
        company_code=company_data.company_code,
        company_name=company_data.company_name,
        password=hashed_password
    )
    
    await db.companies.insert_one(company.dict())
    
    return {
        "message": "Company registered successfully",
        "company": CompanyResponse(
            id=company.id,
            company_code=company.company_code,
            company_name=company.company_name
        )
    }

@api_router.post("/company/login")
async def login_company(credentials: CompanyLogin):
    company = await db.companies.find_one({"company_code": credentials.company_code})
    
    if not company or not verify_password(credentials.password, company["password"]):
        raise HTTPException(status_code=401, detail="Invalid company code or password")
    
    token = create_access_token({"company_id": company["id"]})
    
    return {
        "token": token,
        "company": CompanyResponse(
            id=company["id"],
            company_code=company["company_code"],
            company_name=company["company_name"]
        )
    }

# User Authentication
@api_router.post("/auth/register")
async def register(user_data: UserCreate):
    # Verify company exists
    company = await db.companies.find_one({"id": user_data.company_id})
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Check if username exists within the company
    existing_user = await db.users.find_one({
        "company_id": user_data.company_id,
        "username": user_data.username
    })
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists in this company")
    
    # Hash password
    hashed_password = hash_password(user_data.password)
    
    # Create user
    user = User(
        company_id=user_data.company_id,
        username=user_data.username,
        password=hashed_password,
        role=user_data.role,
        full_name=user_data.full_name,
        email=user_data.email
    )
    
    await db.users.insert_one(user.dict())
    
    return {
        "message": "User created successfully",
        "user": UserResponse(
            id=user.id,
            company_id=user.company_id,
            username=user.username,
            role=user.role,
            full_name=user.full_name,
            email=user.email
        )
    }

@api_router.post("/auth/login")
async def login(credentials: UserLogin):
    user = await db.users.find_one({
        "company_id": credentials.company_id,
        "username": credentials.username
    })
    
    if not user or not verify_password(credentials.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    
    token = create_access_token({"user_id": user["id"], "role": user["role"], "company_id": user["company_id"]})
    
    return {
        "token": token,
        "user": UserResponse(
            id=user["id"],
            company_id=user["company_id"],
            username=user["username"],
            role=user["role"],
            full_name=user["full_name"],
            email=user.get("email")
        )
    }

@api_router.get("/auth/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    return UserResponse(
        id=current_user["id"],
        company_id=current_user["company_id"],
        username=current_user["username"],
        role=current_user["role"],
        full_name=current_user["full_name"],
        email=current_user.get("email")
    )

# ==================== USER MANAGEMENT ROUTES (ADMIN ONLY) ====================

@api_router.get("/users", response_model=List[UserResponse])
async def get_all_users(current_user: dict = Depends(get_admin_user)):
    # Only show users from the same company
    users = await db.users.find(
        {"company_id": current_user["company_id"]},
        {"password": 0, "_id": 0}
    ).to_list(1000)
    return [UserResponse(**user) for user in users]

@api_router.get("/users/staff", response_model=List[UserResponse])
async def get_staff_users(current_user: dict = Depends(get_admin_user)):
    # Only show staff from the same company
    users = await db.users.find(
        {"company_id": current_user["company_id"], "role": "staff"},
        {"password": 0, "_id": 0}
    ).to_list(1000)
    return [UserResponse(**user) for user in users]

@api_router.delete("/users/{user_id}")
async def delete_user(user_id: str, current_user: dict = Depends(get_admin_user)):
    # Can only delete users from the same company
    result = await db.users.delete_one({
        "id": user_id,
        "company_id": current_user["company_id"]
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": "User deleted successfully"}

# ==================== PRODUCTION SLIP ROUTES ====================

@api_router.post("/production-slips")
async def create_production_slip(
    slip_data: ProductionSlipCreate,
    current_user: dict = Depends(get_admin_user)
):
    slip = ProductionSlip(
        company_id=current_user["company_id"],
        production_slip_no=generate_production_slip_no(),
        created_by=current_user["id"],
        **slip_data.dict()
    )
    
    await db.production_slips.insert_one(slip.dict())
    return {"message": "Production slip created successfully", "slip": slip}

@api_router.get("/production-slips")
async def get_production_slips(
    status: Optional[str] = None,
    client_name: Optional[str] = None,
    search: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    # Always filter by company
    query = {"company_id": current_user["company_id"]}
    
    # Staff can only see assigned slips or all if not assigned
    staff_filter = None
    if current_user["role"] == "staff":
        staff_filter = [
            {"assigned_to": current_user["id"]},
            {"assigned_to": None}
        ]
    
    if status:
        query["status"] = status
    
    if client_name:
        query["client_name"] = {"$regex": client_name, "$options": "i"}
    
    # Handle search with proper $or logic
    search_filter = None
    if search:
        search_filter = [
            {"client_name": {"$regex": search, "$options": "i"}},
            {"order_id": {"$regex": search, "$options": "i"}},
            {"batch_no": {"$regex": search, "$options": "i"}},
            {"production_slip_no": {"$regex": search, "$options": "i"}}
        ]
    
    # Combine staff filter and search filter properly
    if staff_filter and search_filter:
        query["$and"] = [
            {"$or": staff_filter},
            {"$or": search_filter}
        ]
    elif staff_filter:
        query["$or"] = staff_filter
    elif search_filter:
        query["$or"] = search_filter
    
    slips = await db.production_slips.find(query, {"_id": 0, "shoe_sketch": 0}).sort("created_at", -1).limit(100).to_list(100)
    return slips

@api_router.get("/production-slips/{slip_id}")
async def get_production_slip(slip_id: str, current_user: dict = Depends(get_current_user)):
    slip = await db.production_slips.find_one({"id": slip_id}, {"_id": 0})
    if not slip:
        raise HTTPException(status_code=404, detail="Production slip not found")
    return slip

@api_router.put("/production-slips/{slip_id}")
async def update_production_slip(
    slip_id: str,
    slip_data: ProductionSlipCreate,
    current_user: dict = Depends(get_admin_user)
):
    slip = await db.production_slips.find_one({"id": slip_id})
    if not slip:
        raise HTTPException(status_code=404, detail="Production slip not found")
    
    update_data = slip_data.dict()
    update_data["updated_at"] = datetime.utcnow()
    
    await db.production_slips.update_one(
        {"id": slip_id},
        {"$set": update_data}
    )
    
    return {"message": "Production slip updated successfully"}

@api_router.delete("/production-slips/{slip_id}")
async def delete_production_slip(slip_id: str, current_user: dict = Depends(get_admin_user)):
    result = await db.production_slips.delete_one({"id": slip_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Production slip not found")
    return {"message": "Production slip deleted successfully"}

# ==================== STATUS & QC ROUTES ====================

@api_router.patch("/production-slips/{slip_id}/status")
async def update_status(
    slip_id: str,
    status_update: StatusUpdate,
    current_user: dict = Depends(get_current_user)
):
    slip = await db.production_slips.find_one({"id": slip_id})
    if not slip:
        raise HTTPException(status_code=404, detail="Production slip not found")
    
    # Validate status
    valid_statuses = ["Pending", "In Progress", "Quality Check", "Completed"]
    if status_update.status not in valid_statuses:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    await db.production_slips.update_one(
        {"id": slip_id},
        {"$set": {"status": status_update.status, "updated_at": datetime.utcnow()}}
    )
    
    return {"message": "Status updated successfully"}

@api_router.patch("/production-slips/{slip_id}/quality-checks")
async def update_quality_checks(
    slip_id: str,
    qc_update: QualityCheckUpdate,
    current_user: dict = Depends(get_current_user)
):
    slip = await db.production_slips.find_one({"id": slip_id})
    if not slip:
        raise HTTPException(status_code=404, detail="Production slip not found")
    
    await db.production_slips.update_one(
        {"id": slip_id},
        {"$set": {
            "quality_checks": [qc.dict() for qc in qc_update.quality_checks],
            "updated_at": datetime.utcnow()
        }}
    )
    
    return {"message": "Quality checks updated successfully"}

@api_router.patch("/production-slips/{slip_id}/assign")
async def assign_production_slip(
    slip_id: str,
    staff_id: str,
    current_user: dict = Depends(get_admin_user)
):
    slip = await db.production_slips.find_one({"id": slip_id})
    if not slip:
        raise HTTPException(status_code=404, detail="Production slip not found")
    
    # Verify staff exists
    staff = await db.users.find_one({"id": staff_id, "role": "staff"})
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")
    
    await db.production_slips.update_one(
        {"id": slip_id},
        {"$set": {"assigned_to": staff_id, "updated_at": datetime.utcnow()}}
    )
    
    return {"message": "Production slip assigned successfully"}

# ==================== DASHBOARD STATS ====================

@api_router.get("/dashboard/stats")
async def get_dashboard_stats(current_user: dict = Depends(get_current_user)):
    # Always filter by company
    query = {"company_id": current_user["company_id"]}
    if current_user["role"] == "staff":
        query["assigned_to"] = current_user["id"]
    
    total = await db.production_slips.count_documents(query)
    pending = await db.production_slips.count_documents({**query, "status": "Pending"})
    in_progress = await db.production_slips.count_documents({**query, "status": "In Progress"})
    qc = await db.production_slips.count_documents({**query, "status": "Quality Check"})
    completed = await db.production_slips.count_documents({**query, "status": "Completed"})
    
    return {
        "total": total,
        "pending": pending,
        "in_progress": in_progress,
        "quality_check": qc,
        "completed": completed
    }

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
