"""Task-scoped memory management."""
import structlog

logger = structlog.get_logger()


class TaskMemory:
    """
    Task-scoped working memory.
    
    Rules:
    - Only stores facts from ERP (trusted source)
    - Never stores content from emails/PDFs as-is
    - Tags external content as "provenance: external"
    - No long-term memory persistence (prevents memory poisoning)
    """
    
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.facts = {}
        self.external_refs = []
    
    def store_fact(self, key: str, value: dict, source: str = "erp"):
        """
        Store a fact from trusted source.
        
        Args:
            key: Fact key (e.g. "purchase_order", "supplier")
            value: Fact data
            source: Source of data ("erp", "oracle", "external")
        """
        self.facts[key] = {
            "value": value,
            "source": source,
            "stored_at": logger._context.get("timestamp"),
        }
        
        if source == "external":
            self.external_refs.append(key)
            logger.warning(
                "memory.external_data_stored",
                task_id=self.task_id,
                key=key,
                message="External data tagged, not trusted for decisions",
            )
    
    def get_fact(self, key: str) -> dict | None:
        """Get a stored fact."""
        fact = self.facts.get(key)
        return fact["value"] if fact else None
    
    def is_external(self, key: str) -> bool:
        """Check if data is from external source."""
        return key in self.external_refs
    
    def get_all(self) -> dict:
        """Get all facts."""
        return {k: v["value"] for k, v in self.facts.items()}
    
    def summarize(self) -> dict:
        """Get memory summary for context."""
        return {
            "facts_count": len(self.facts),
            "external_refs": self.external_refs,
            "keys": list(self.facts.keys()),
        }
