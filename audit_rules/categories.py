"""Enums for the Unified Audit Rule Registry.

Each enum represents a distinct axis of classification.
Priority ≠ Severity (Requirement 4).
ExecutionStatus ≠ ResultStatus (Requirement 0.3).
"""

from enum import Enum


# ============================================================
# Category — what area of SEO the rule belongs to
# ============================================================

class Category(str, Enum):
    CRAWL_INDEX = "抓取与索引"
    URL_REDIRECT = "URL 与重定向"
    SITE_ARCH = "站点架构"
    CONTENT_META = "内容与元数据"
    CONTENT_KEYWORD = "内容与关键词"
    CONTENT_QUALITY = "内容质量"
    TECH_PERF = "技术性能"
    MOBILE_UX = "移动体验"
    SECURITY = "安全与 Header"
    STRUCTURED_DATA = "结构化数据"
    INTERNATIONAL = "国际化 / 多语言"
    LINK_ANALYSIS = "链接分析"
    MEDIA = "媒体与富媒体"
    LOG_ANALYSIS = "日志与抓取分析"
    MONITORING = "监控与跟踪"
    WORDPRESS = "WordPress 专项"
    MAINTENANCE = "维护与流程"
    JS_SEO = "JavaScript SEO"
    TRUST_EEAT = "信任与 E-E-A-T"
    ACCESSIBILITY = "用户体验 / Accessibility"
    CONVERSION = "转化与功能"
    RANKING = "排名与竞争"
    INFRA = "基础设施"

    @classmethod
    def from_chinese(cls, name: str) -> "Category":
        for member in cls:
            if member.value == name:
                return member
        raise ValueError(f"Unknown category: {name}")


# ============================================================
# Priority — business importance (NOT severity)
# ============================================================

class Priority(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"

    @classmethod
    def from_str(cls, s: str) -> "Priority":
        mapping = {
            "critical": cls.CRITICAL,
            "high": cls.HIGH,
            "medium": cls.MEDIUM,
            "low": cls.LOW,
        }
        if s.lower() in mapping:
            return mapping[s.lower()]
        raise ValueError(f"Unknown priority: {s}")


# ============================================================
# Severity — technical impact of a finding
# ============================================================

class Severity(str, Enum):
    ERROR = "Error"            # Blocks indexing, ranking, or user experience
    WARNING = "Warning"        # Degrades performance, may impact ranking
    OPPORTUNITY = "Opportunity"  # Improvement opportunity, not currently broken
    INFO = "Info"              # Informational only, no action required

    @classmethod
    def from_str(cls, s: str) -> "Severity":
        mapping = {
            "error": cls.ERROR,
            "warning": cls.WARNING,
            "warn": cls.WARNING,
            "opportunity": cls.OPPORTUNITY,
            "info": cls.INFO,
        }
        key = s.lower().strip()
        if key in mapping:
            return mapping[key]
        raise ValueError(f"Unknown severity: {s}")


# ============================================================
# Scope — what the rule evaluates
# ============================================================

class Scope(str, Enum):
    SITE = "SITE"              # Site-level (robots.txt, sitemap, domain)
    PAGE = "PAGE"              # Per-page (title, meta, H1, status)
    LINK = "LINK"              # Link-level (anchor text, broken outbound)
    RELATIONSHIP = "RELATIONSHIP"  # Cross-page (duplicate content, orphans)
    TEMPLATE = "TEMPLATE"      # Template-level (CWV per template, schema per type)


# ============================================================
# ExecutionStatus — WAS the rule executed? (Requirement 0.3)
# ============================================================

class ExecutionStatus(str, Enum):
    EXECUTED_FULL = "EXECUTED_FULL"          # Rule ran on all eligible pages
    EXECUTED_PARTIAL = "EXECUTED_PARTIAL"    # Rule ran on a sample
    NOT_CHECKED = "NOT_CHECKED"              # Rule was not executed
    NOT_APPLICABLE = "NOT_APPLICABLE"        # Rule does not apply to this site


# ============================================================
# ResultStatus — WHAT was the outcome? (Requirement 0.3)
# ============================================================

class ResultStatus(str, Enum):
    PASS = "PASS"                # All evaluated units passed
    FAIL = "FAIL"                # At least one unit has a critical failure
    WARNING = "WARNING"          # At least one unit has a warning-level issue
    OPPORTUNITY = "OPPORTUNITY"  # Improvement opportunity identified
    INTENTIONAL = "INTENTIONAL"  # Finding is intentional/expected (e.g. deliberate noindex)
    UNKNOWN = "UNKNOWN"          # Rule not executed; outcome unknown


# ============================================================
# ImplStatus — implementation status in the codebase
# ============================================================

class ImplStatus(str, Enum):
    EXISTING_FULL = "EXISTING_FULL"            # Fully implemented
    EXISTING_PARTIAL = "EXISTING_PARTIAL"      # Partially implemented
    NEW_AUTO = "NEW_AUTO"                      # New, can be fully automated
    NEW_EXTERNAL_DATA = "NEW_EXTERNAL_DATA"    # Requires external data source
    NEW_MANUAL = "NEW_MANUAL"                  # Requires human review

    @classmethod
    def from_str(cls, s: str) -> "ImplStatus":
        for member in cls:
            if member.value == s.strip():
                return member
        raise ValueError(f"Unknown impl_status: {s}")


# ============================================================
# DetectionMethod — how the rule detects issues
# ============================================================

class DetectionMethod(str, Enum):
    STATIC_ANALYSIS = "STATIC_ANALYSIS"      # From crawl export data
    HTTP_FETCH = "HTTP_FETCH"                # Requires live HTTP request
    EXTERNAL_API = "EXTERNAL_API"            # Requires external API call
    MANUAL_REVIEW = "MANUAL_REVIEW"          # Requires human review
    COMPOSITE = "COMPOSITE"                  # Combination of methods
    CRAWL_COMPARISON = "CRAWL_COMPARISON"    # Requires two crawl snapshots
    SITE_CHECK = "SITE_CHECK"                # Site-level HTTP check
    OUTPUT_ONLY = "OUTPUT_ONLY"              # Output artifact, not a check

    @classmethod
    def from_str(cls, s: str) -> "DetectionMethod":
        for member in cls:
            if member.value == s.strip():
                return member
        raise ValueError(f"Unknown detection_method: {s}")


# ============================================================
# DataSource — where the data comes from
# ============================================================

class DataSource(str, Enum):
    LIBRECRAWL = "LibreCrawl"
    PAGESPEED = "PageSpeed API"
    GSC = "GSC API"
    GSC_UI = "GSC_UI"
    SEMRUSH = "Semrush API"
    GA4 = "GA4"
    SERVER_LOGS = "Server Logs"
    WORDPRESS_ADMIN = "WordPress Admin"
    MANUAL = "Manual Review"
    EXTERNAL_MONITOR = "External Monitoring Tool"
    NONE = "None"
