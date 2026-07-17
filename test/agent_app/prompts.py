from __future__ import annotations

from langchain_core.documents import Document


SEED_DOCUMENTS = [
    Document(
        page_content="""
刘慈欣是中国著名科幻作家，出生于1963年。
他的代表作包括《三体》《球状闪电》《流浪地球》等。
刘慈欣曾凭借《三体》英文版获得雨果奖最佳长篇小说奖。
""".strip(),
        metadata={"source": "liu_cixin_intro", "kind": "seed"},
    ),
    Document(
        page_content="""
《三体》是刘慈欣创作的长篇科幻小说。
《三体》最早于2006年在《科幻世界》杂志连载，单行本首次出版于2008年。
《三体》是“地球往事”三部曲的第一部。
""".strip(),
        metadata={"source": "three_body_intro", "kind": "seed"},
    ),
    Document(
        page_content="""
ADNI 是 Alzheimer's Disease Neuroimaging Initiative 的缩写。
它是一个阿尔茨海默病神经影像学倡议项目，主要用于推动阿尔茨海默病相关研究。
ADNI 数据通常包括 MRI、PET、临床量表、生物标志物和诊断标签等多模态数据。
""".strip(),
        metadata={"source": "adni_intro", "kind": "seed"},
    ),
    Document(
        page_content="""
阿尔茨海默病的英文是 Alzheimer's disease，常缩写为 AD。
它是一种常见的神经退行性疾病，主要表现包括记忆力下降、认知功能减退和日常生活能力下降。
在医学影像研究中，MRI 和 PET 常用于辅助分析阿尔茨海默病相关脑部变化。
""".strip(),
        metadata={"source": "alzheimers_intro", "kind": "seed"},
    ),
    Document(
        page_content="""
MCI 是 Mild Cognitive Impairment 的缩写，中文通常称为轻度认知障碍。
MCI 患者存在认知功能下降，但日常生活能力通常相对保留。
部分 MCI 患者可能进一步进展为阿尔茨海默病，因此 MCI 转 AD 是神经退行性疾病研究中的重要问题。
""".strip(),
        metadata={"source": "mci_intro", "kind": "seed"},
    ),
    Document(
        page_content="""
DiaMond 是一个用于痴呆诊断的多模态视觉 Transformer 模型。
它使用 MRI 和 PET 数据进行多模态融合分析，目标是辅助区分认知正常、轻度认知障碍和痴呆等状态。
在科研 Agent 中，可以将 DiaMond 这类影像模型封装成工具，由 Agent 在需要时调用。
""".strip(),
        metadata={"source": "diamond_intro", "kind": "seed"},
    ),
]


SYSTEM_PROMPT = """
你是一个中文问答机器人，具备以下能力：
1. 会话记忆：可以利用历史对话回答追问。
2. 本地 RAG：可以检索本地知识库中的文档片段。
3. 工具调用：可以使用计算器和预留的 MCP 扩展入口。

规则：
- 事实类、背景类、文档类问题优先使用 rag_search。
- 数学计算优先使用 calculator。
- 如果问题依赖上下文，优先结合历史对话，不要重复追问。
- 回答简洁、准确、中文输出。
- 如果检索不到足够信息，要明确说明不确定，不要编造。
""".strip()

