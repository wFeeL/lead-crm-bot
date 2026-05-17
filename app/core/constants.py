from enum import StrEnum


class UserRole(StrEnum):
    CLIENT = "client"
    MANAGER = "manager"
    ADMIN = "admin"
    OWNER = "owner"


class LeadStatus(StrEnum):
    NEW = "new"
    CONTACTED = "contacted"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"
    DONE = "done"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class LeadPriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class QuestionType(StrEnum):
    TEXT = "text"
    LONG_TEXT = "long_text"
    PHONE = "phone"
    EMAIL = "email"
    CHOICE = "choice"
    MULTI_CHOICE = "multi_choice"
    FILE = "file"
    PHOTO = "photo"
    DATE = "date"
    TIME = "time"
    NUMBER = "number"


class FileType(StrEnum):
    PHOTO = "photo"
    DOCUMENT = "document"


class LeadEventType(StrEnum):
    LEAD_CREATED = "lead_created"
    STATUS_CHANGED = "status_changed"
    ADMIN_ASSIGNED = "admin_assigned"
    COMMENT_ADDED = "comment_added"
    FILE_UPLOADED = "file_uploaded"
    CLIENT_CANCELLED = "client_cancelled"


ALLOWED_STATUS_TRANSITIONS: dict[LeadStatus, set[LeadStatus]] = {
    LeadStatus.NEW: {
        LeadStatus.CONTACTED,
        LeadStatus.IN_PROGRESS,
        LeadStatus.REJECTED,
        LeadStatus.CANCELLED,
    },
    LeadStatus.CONTACTED: {
        LeadStatus.IN_PROGRESS,
        LeadStatus.WAITING,
        LeadStatus.DONE,
        LeadStatus.REJECTED,
        LeadStatus.CANCELLED,
    },
    LeadStatus.IN_PROGRESS: {
        LeadStatus.CONTACTED,
        LeadStatus.WAITING,
        LeadStatus.DONE,
        LeadStatus.REJECTED,
        LeadStatus.CANCELLED,
    },
    LeadStatus.WAITING: {
        LeadStatus.CONTACTED,
        LeadStatus.IN_PROGRESS,
        LeadStatus.DONE,
        LeadStatus.REJECTED,
        LeadStatus.CANCELLED,
    },
    LeadStatus.DONE: set(),
    LeadStatus.REJECTED: set(),
    LeadStatus.CANCELLED: set(),
}


STATUS_TITLES: dict[str, str] = {
    LeadStatus.NEW: "Новая",
    LeadStatus.CONTACTED: "Связались",
    LeadStatus.IN_PROGRESS: "В работе",
    LeadStatus.WAITING: "Ждем клиента",
    LeadStatus.DONE: "Завершена",
    LeadStatus.REJECTED: "Отклонена",
    LeadStatus.CANCELLED: "Отменена",
}


STATUS_EMOJIS: dict[str, str] = {
    LeadStatus.NEW: "🆕",
    LeadStatus.CONTACTED: "📞",
    LeadStatus.IN_PROGRESS: "🛠",
    LeadStatus.WAITING: "⏳",
    LeadStatus.DONE: "✅",
    LeadStatus.REJECTED: "❌",
    LeadStatus.CANCELLED: "🚫",
}


ACTIVE_STATUSES = {LeadStatus.NEW, LeadStatus.CONTACTED, LeadStatus.IN_PROGRESS, LeadStatus.WAITING}
CLOSED_STATUSES = {LeadStatus.DONE, LeadStatus.REJECTED, LeadStatus.CANCELLED}
