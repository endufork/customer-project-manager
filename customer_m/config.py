from pathlib import Path
import re

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
DB_PATH = DATA_DIR / "customer_projects.db"
SCHEMA_PATH = BASE_DIR / "mvp-sqlite-schema-v0.2.sql"

SINGLE_DEVICE_CONTAINER = "01_独立项目"
PROJECT_GROUP_CONTAINER = "02_客户产品项目"
SHARED_FOLDER_NAME = "00_共享资料"
PROJECT_NATURE_OPTIONS = ("新设备", "老设备改造", "夹具/治具", "备件/耗材", "售后/服务", "纯方案/报价", "其他")
PROJECT_NATURES = set(PROJECT_NATURE_OPTIONS)
STANDARD_PROJECT_FOLDERS = (
    "01_输入资料",
    "02_报价与订单",
    "03_方案与图纸",
    "04_交付与验收",
    "99_其他",
)
CATEGORY_DEFAULT_FOLDERS = {
    "inquiry": "01_输入资料",
    "communication": "01_输入资料",
    "internal_quote": "02_报价与订单",
    "customer_quote": "02_报价与订单",
    "po": "02_报价与订单",
    "solution": "03_方案与图纸",
    "drawing_model": "03_方案与图纸",
    "acceptance_delivery": "04_交付与验收",
    "other": "99_其他",
}
LEGACY_CATEGORY_FOLDERS = {
    "01_询价需求": "inquiry",
    "02_方案资料": "solution",
    "03_内部报价": "internal_quote",
    "04_客户报价": "customer_quote",
    "05_PO订单": "po",
    "06_图纸模型": "drawing_model",
    "07_验收发货": "acceptance_delivery",
    "08_沟通记录": "communication",
    "99_其他": "other",
}
STANDARD_FOLDER_FALLBACK_CATEGORIES = {
    "01_输入资料": "inquiry",
    "03_方案与图纸": "solution",
    "04_交付与验收": "acceptance_delivery",
    "99_其他": "other",
}

EQUIPMENT_NO_RE = re.compile(r"^[A-Za-z0-9_-]+$")
WINDOWS_RESERVED = re.compile(r'[<>:"/\\|?*\x00-\x1F]')
MODEL_EXTENSIONS = {
    ".step",
    ".stp",
    ".sldprt",
    ".sldasm",
    ".dwg",
    ".dxf",
    ".iges",
    ".igs",
    ".x_t",
    ".x_b",
    ".prt",
    ".asm",
}

TEXT_EXTENSIONS = {".txt", ".csv", ".md", ".log"}
