from langchain_core.documents import Document


SYSTEM_PROMPT = """
你是一个中文助手，可以使用本地知识库、计算器和 MCP 工具。

规则：
- 涉及本地资料时，先使用 rag_search。
- 涉及数学计算时，使用 calculator。
- 需要外部工具时，可以先用 mcp_status 检查 MCP 状态。
- 资料不足时明确说明，不要编造。
- 回答简洁、准确，默认使用中文。
""".strip()


SEED_DOCUMENTS = [
    Document(
        page_content="刘慈欣出生于 1963 年，是中国科幻作家。《三体》单行本首次出版于 2008 年。",
        metadata={"source": "内置示例", "kind": "seed"},
    ),
    Document(
        page_content="ADNI 是 Alzheimer's Disease Neuroimaging Initiative 的缩写，数据包括 MRI、PET、临床量表和生物标志物。",
        metadata={"source": "内置示例", "kind": "seed"},
    ),
]
