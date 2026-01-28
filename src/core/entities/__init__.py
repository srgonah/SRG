"""Core domain entities."""

from src.core.entities.company_document import (
    CompanyDocument,
    CompanyDocumentType,
)
from src.core.entities.document import (
    Chunk,
    Document,
    DocumentStatus,
    IndexingState,
    Page,
    PageType,
    SearchResult,
)
from src.core.entities.inventory import (
    InventoryItem,
    MovementType,
    StockMovement,
)
from src.core.entities.invoice import (
    ArithmeticCheck,
    ArithmeticCheckContainer,
    AuditIssue,
    AuditResult,
    AuditStatus,
    BankDetails,
    Invoice,
    LineItem,
    ParsingStatus,
    RowType,
)
from src.core.entities.local_sale import (
    LocalSalesInvoice,
    LocalSalesItem,
)
from src.core.entities.material import (
    Material,
    MaterialSynonym,
    OriginConfidence,
)
from src.core.entities.reminder import Reminder
from src.core.entities.session import (
    ChatSession,
    MemoryFact,
    MemoryFactType,
    Message,
    MessageRole,
    MessageType,
    SessionStatus,
)

__all__ = [
    # Invoice entities
    "LineItem",
    "Invoice",
    "AuditResult",
    "AuditIssue",
    "AuditStatus",
    "ArithmeticCheck",
    "ArithmeticCheckContainer",
    "BankDetails",
    "RowType",
    "ParsingStatus",
    # Document entities
    "Document",
    "Page",
    "Chunk",
    "PageType",
    "DocumentStatus",
    "IndexingState",
    "SearchResult",
    # Material entities
    "Material",
    "MaterialSynonym",
    "OriginConfidence",
    # Company document entities
    "CompanyDocument",
    "CompanyDocumentType",
    # Reminder entities
    "Reminder",
    # Inventory entities
    "InventoryItem",
    "StockMovement",
    "MovementType",
    # Local sales entities
    "LocalSalesInvoice",
    "LocalSalesItem",
    # Session entities
    "ChatSession",
    "Message",
    "MemoryFact",
    "MessageRole",
    "MessageType",
    "MemoryFactType",
    "SessionStatus",
]
