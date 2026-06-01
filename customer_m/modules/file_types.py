"""file types module."""

from pathlib import Path

from ..config import MODEL_EXTENSIONS

def classify_file(path: Path) -> str:
    lower_name = path.name.lower()
    ext = path.suffix.lower()
    if ext in MODEL_EXTENSIONS:
        return "drawing_model"
    if any(word in lower_name for word in ["purchase order", "po", "订单"]):
        return "po"
    if any(word in lower_name for word in ["内部报价", "成本", "cost"]):
        return "internal_quote"
    if any(word in lower_name for word in ["报价", "quote", "quotation"]):
        return "customer_quote"
    if any(word in lower_name for word in ["方案", "proposal", "solution", "spec"]):
        return "solution"
    if any(word in lower_name for word in ["询价", "rfq", "需求", "requirement"]):
        return "inquiry"
    if any(word in lower_name for word in ["email", "邮件", "微信", "聊天", "meeting"]):
        return "communication"
    if any(word in lower_name for word in ["验收", "fat", "发货", "delivery", "shipment"]):
        return "acceptance_delivery"
    return "other"
