from pathlib import Path
import os
import re

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
STATIC_DIR = BASE_DIR / "static"
DB_PATH = DATA_DIR / "customer_projects.db"
SCHEMA_PATH = BASE_DIR / "mvp-sqlite-schema-v0.2.sql"

AUTH_EMAIL_DOMAIN = os.environ.get("CUSTOMER_AUTH_EMAIL_DOMAIN", "jinxiangsz.com").strip().lower()
AUTH_INITIAL_ADMIN_EMAIL = os.environ.get("CUSTOMER_AUTH_INITIAL_ADMIN_EMAIL", "rongkai@jinxiangsz.com").strip().lower()
AUTH_CODE_TTL_SECONDS = int(os.environ.get("CUSTOMER_AUTH_CODE_TTL_SECONDS", "600"))
AUTH_CODE_RESEND_SECONDS = int(os.environ.get("CUSTOMER_AUTH_CODE_RESEND_SECONDS", "60"))
AUTH_SESSION_DAYS = int(os.environ.get("CUSTOMER_AUTH_SESSION_DAYS", "7"))
AUTH_SECRET = os.environ.get("CUSTOMER_AUTH_SECRET", "local-dev-auth-secret")

SMTP_HOST = os.environ.get("CUSTOMER_SMTP_HOST", "").strip()
SMTP_PORT = int(os.environ.get("CUSTOMER_SMTP_PORT", "465"))
SMTP_SECURITY = os.environ.get("CUSTOMER_SMTP_SECURITY", "ssl").strip().lower()
SMTP_USERNAME = os.environ.get("CUSTOMER_SMTP_USERNAME", "").strip()
SMTP_PASSWORD = os.environ.get("CUSTOMER_SMTP_PASSWORD", "").strip()
SMTP_FROM_EMAIL = os.environ.get("CUSTOMER_SMTP_FROM_EMAIL", SMTP_USERNAME).strip()
SMTP_FROM_NAME = os.environ.get("CUSTOMER_SMTP_FROM_NAME", "项目管理系统").strip()

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

WORKBENCH_AREAS = (
    {"code": "inq", "name": "INQ前期支持"},
    {"code": "wo", "name": "WO执行"},
    {"code": "closed", "name": "已关闭"},
)
WORKBENCH_WORK_PACKAGES = (
    "项目管理",
    "前期方案",
    "报价支持",
    "机械设计",
    "电气设计",
    "BOM/采购",
    "装配",
    "接线",
    "调试",
    "验收",
    "发货",
    "关闭归档",
)
WORKBENCH_TASK_STATUSES = (
    {"code": "not_started", "name": "未开始"},
    {"code": "in_progress", "name": "进行中"},
    {"code": "waiting_info", "name": "等待资料"},
    {"code": "blocked", "name": "阻塞"},
    {"code": "submitted", "name": "已提交"},
    {"code": "rework", "name": "需返工"},
    {"code": "confirmed", "name": "已确认"},
    {"code": "completed", "name": "已完成"},
    {"code": "cancelled", "name": "已取消"},
)
WORKBENCH_DONE_TASK_STATUSES = {"confirmed", "completed", "cancelled"}
WORKBENCH_PHASES = (
    {"code": "inq_intake", "name": "询价录入"},
    {"code": "clarification", "name": "需求澄清"},
    {"code": "rough_solution", "name": "大致方案"},
    {"code": "quote_support", "name": "报价支持"},
    {"code": "waiting_feedback", "name": "等待客户反馈"},
    {"code": "wo_kickoff", "name": "WO启动"},
    {"code": "detailed_design", "name": "细化设计"},
    {"code": "bom_purchase", "name": "BOM/采购"},
    {"code": "assembly", "name": "装配"},
    {"code": "wiring_debug", "name": "接线/调试"},
    {"code": "acceptance_delivery", "name": "验收/发货"},
    {"code": "closed", "name": "关闭"},
)
WORKBENCH_ISSUE_TYPES = (
    "客户资料缺失",
    "内部资源",
    "设计风险",
    "采购风险",
    "交期风险",
    "质量风险",
    "其他",
)
WORKBENCH_ISSUE_SOURCES = ("客户", "内部", "供应商", "其他")
WORKBENCH_ISSUE_SCOPES = (
    {"code": "product", "name": "产品/产线"},
    {"code": "equipment", "name": "当前设备"},
    {"code": "task", "name": "具体任务"},
)
WORKBENCH_ISSUE_SEVERITIES = (
    {"code": "low", "name": "低"},
    {"code": "medium", "name": "中"},
    {"code": "high", "name": "高"},
)
WORKBENCH_ISSUE_STATUSES = (
    {"code": "open", "name": "打开"},
    {"code": "following", "name": "跟进中"},
    {"code": "resolved", "name": "已解决"},
    {"code": "accepted", "name": "已接受风险"},
    {"code": "closed", "name": "已关闭"},
)
WORKBENCH_DELIVERABLE_STATUSES = (
    {"code": "submitted", "name": "待确认"},
    {"code": "confirmed", "name": "已确认"},
    {"code": "rejected", "name": "已驳回"},
)
