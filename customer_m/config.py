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
STATUS_DATE_LABELS = {
    "inquiry": "询价日期",
    "no_equipment_no": "询价日期",
    "clarification": "需求澄清日期",
    "solution_design": "方案设计日期",
    "cost_review": "内部评估日期",
    "internal_quote": "内部报价日期",
    "quoted": "客户报价日期",
    "waiting_feedback": "客户报价日期",
    "po_received": "PO 日期",
    "purchasing": "备料/采购日期",
    "manufacturing": "装配/制作日期",
    "acceptance": "验收/调试日期",
    "shipped": "发货日期",
    "completed": "完成日期",
    "paused": "暂停日期",
    "lost_closed": "关闭日期",
    "historical_entry": "补录日期",
}
STATUS_DATE_FIELD_BY_STATUS = {
    "inquiry": "inquiry_date",
    "no_equipment_no": "inquiry_date",
    "clarification": "inquiry_date",
    "quoted": "quote_date",
    "waiting_feedback": "quote_date",
    "po_received": "po_date",
    "shipped": "actual_ship_date",
    "completed": "actual_ship_date",
}
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
