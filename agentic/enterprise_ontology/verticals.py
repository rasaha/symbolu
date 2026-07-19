"""Enterprise organizational verticals."""

from __future__ import annotations

from enum import Enum


class EnterpriseVertical(str, Enum):
    FINANCE = "finance"
    SALES = "sales"
    MARKETING = "marketing"
    IT = "it"
    LEGAL = "legal"
    PROCUREMENT = "procurement"
    HR = "hr"
    SECURITY = "security"
    OPERATIONS = "operations"
    EXECUTIVE = "executive"
    PRIVACY = "privacy"
    PAYROLL = "payroll"
    FACILITIES = "facilities"
    REQUESTING_DEPT = "requesting_department"
