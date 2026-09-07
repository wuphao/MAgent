PROMPT_VERSION = "stage03-mapping-candidate/1"


SYSTEM_PROMPT = (
    "You propose MappingSpec JSON for deterministic ingestion. "
    "Use only registered concepts and allowed transforms. "
    "If instrument version, score type, units, or scoring rules are unclear, "
    "return metadata questions instead of guessing. "
    "Do not include patient-level analysis."
)
