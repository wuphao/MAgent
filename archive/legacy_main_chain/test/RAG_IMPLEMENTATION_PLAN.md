# RAG 深入实现方案

## 1. 目标

本方案用于把当前命令行聊天项目升级成一个结构清晰、可扩展、可评测的 RAG 系统。

RAG 的核心目标不是简单地把整篇文档塞给大模型，而是：

1. 把外部知识文档解析、切分并向量化。
2. 用户提问时，从知识库中检索最相关的片段。
3. 将检索结果作为上下文交给大模型。
4. 让模型基于可靠资料回答，并给出来源。

最终链路如下：

```text
文档 -> 解析 -> 清洗 -> 切分 -> Embedding -> 向量库

用户问题 -> 查询改写 -> 检索 -> 重排 -> 上下文压缩 -> Prompt -> LLM 回答
```

## 2. 推荐目录结构

当前项目可以逐步演进成下面的结构：

```text
agent_app/
  cli.py
  service.py
  settings.py

  rag/
    __init__.py
    models.py              # DocumentChunk、SearchResult 等数据结构
    loaders.py             # txt、md、pdf、docx 文档读取
    splitter.py            # 文本切分策略
    embeddings.py          # embedding 模型封装
    stores.py              # Chroma、Qdrant、pgvector 后端
    retriever.py           # 检索、混合检索、过滤
    reranker.py            # 重排逻辑
    context.py             # 上下文组装和 token 控制
    prompts.py             # RAG prompt 模板
    evaluator.py           # RAG 评测
```

如果项目还比较小，也可以先保持一个 `rag.py`，等功能变多后再拆分。

## 3. 文档入库流程

文档入库负责把原始文件变成可检索的 chunk。

### 3.1 支持的文档类型

第一阶段建议支持：

```text
.txt
.md
.pdf
.docx
.csv
```

不同文件格式对应不同解析方式：

```text
txt/md: 直接 UTF-8 读取
pdf: pypdf 或 pymupdf 提取文本，并保留页码
docx: python-docx 提取段落和标题
csv: 按行或按表格记录转成文本
```

### 3.2 文档清洗

清洗目标是减少噪声，提高检索质量。

常见处理：

```text
去除 BOM
统一换行符
合并过多空行
去除页眉页脚
去除重复空格
保留标题层级
保留页码、文件名、章节名
```

每个 chunk 必须带 metadata：

```python
{
    "doc_id": "...",
    "source": "D:/docs/manual.pdf",
    "file_name": "manual.pdf",
    "page": 12,
    "section": "安装说明",
    "chunk_index": 3,
    "created_at": "2026-08-11T13:00:00"
}
```

## 4. 文本切分策略

切分质量直接决定 RAG 效果。

### 4.1 基础切分

推荐默认参数：

```text
chunk_size: 600-1000 中文字符
chunk_overlap: 80-150 中文字符
```

适合普通文档、说明书、网页文本。

### 4.2 结构化切分

优先按结构切：

```text
Markdown: 按 #、##、### 标题
PDF: 按页码、段落
Word: 按标题、段落
FAQ: 按问答对
代码文档: 按类、函数、标题
```

推荐策略：

```text
先按标题/段落粗切
超过 chunk_size 的块再按字符递归切
切分后保留 section metadata
```

### 4.3 不建议的做法

```text
不要整篇文档一个 chunk
不要每 100 字切一次，太碎会丢上下文
不要丢失来源和页码
不要把不同文档混成一个 chunk
```

## 5. Embedding 设计

Embedding 用于把文本变成向量，方便语义检索。

### 5.1 当前原型

当前项目使用的是本地 hash embedding，优点是：

```text
无需下载模型
无需 API 成本
方便学习 RAG 流程
```

缺点是：

```text
语义理解弱
同义词召回差
复杂中文问题效果有限
```

它适合验证工程链路，不适合作为最终生产方案。

### 5.2 推荐升级模型

本地方案：

```text
bge-m3
nomic-embed-text
m3e
gte-large-zh
```

API 方案：

```text
text-embedding-3-small
text-embedding-3-large
```

学习阶段建议：

```text
Chroma + bge-m3
```

生产轻量服务建议：

```text
Qdrant + bge-m3
```

已有 PostgreSQL 建议：

```text
pgvector + bge-m3
```

## 6. 向量库后端选择

### 6.1 Chroma

适合：

```text
本地学习
Demo
小规模原型
单机实验
```

优点：

```text
安装简单
无需单独启动服务
本地持久化
开发体验好
```

限制：

```text
大规模和多服务并发能力有限
生产权限控制需要额外设计
```

### 6.2 Qdrant

适合：

```text
轻量生产服务
服务化部署
中等规模知识库
需要过滤、payload、API 服务
```

优点：

```text
独立向量数据库
过滤能力强
部署简单
查询性能好
适合 Docker 部署
```

### 6.3 pgvector

适合：

```text
项目已经有 PostgreSQL
希望文档、业务数据、向量存在一个数据库
需要事务和 SQL 查询
```

优点：

```text
和业务系统集成简单
权限、备份、事务沿用 PostgreSQL
减少额外组件
```

限制：

```text
极大规模向量检索性能不如专用向量库
需要维护索引参数
```

## 7. 检索流程

基础检索：

```text
用户问题
-> embedding(query)
-> vector search top_k=4
-> 拼接上下文
-> LLM 回答
```

深入版检索：

```text
用户问题
-> 查询改写
-> 向量检索 top_k=20
-> 关键词检索 top_k=20
-> 合并去重
-> rerank top_n=5
-> 上下文压缩
-> LLM 回答
```

## 8. 查询改写

多轮对话中，用户经常会问：

```text
它怎么安装？
这个多少钱？
上面那个功能支持吗？
```

这些问题脱离历史上下文后无法检索。

因此需要先把问题改写成独立问题：

```text
根据历史对话，将用户的新问题改写成可以独立检索的问题。
只输出改写后的问题。
```

示例：

```text
历史：用户正在询问 ADNI 数据集。
新问题：它包含哪些影像数据？
改写：ADNI 数据集包含哪些影像数据？
```

## 9. 混合检索

只用向量检索容易漏掉精确关键词，例如：

```text
REQ-001
FUN-023
API 名称
配置字段
错误码
人名
产品型号
```

所以生产版建议使用混合检索：

```text
向量检索：解决语义相似
BM25/关键词检索：解决精确匹配
```

合并策略：

```text
vector_results + keyword_results
按 doc_id + chunk_index 去重
根据分数归一化后融合
再进入 rerank
```

## 10. Rerank 重排

第一阶段检索负责召回，rerank 负责排序。

常见流程：

```text
初检 top_k=20
rerank 取 top_n=5
```

可选模型：

```text
bge-reranker
cross-encoder
LLM rerank
```

没有 reranker 时，可以先按向量距离排序。

## 11. 上下文组装

上下文不是越多越好。太多会：

```text
浪费 token
引入噪声
降低回答准确性
增加成本
```

推荐格式：

```text
[资料 1]
来源：manual.pdf
页码：12
标题：安装说明
内容：...

[资料 2]
来源：faq.md
标题：常见问题
内容：...
```

上下文控制：

```text
最多 3-6 个 chunk
总长度控制在 3000-8000 tokens
同一文档相邻 chunk 可以合并
重复内容去重
优先保留来源明确的内容
```

## 12. Prompt 设计

推荐 RAG prompt：

```text
你是一个严谨的知识库问答助手。

规则：
1. 优先根据“本地知识库资料”回答。
2. 如果资料不足，请明确说“知识库中没有足够信息”。
3. 不要编造来源、页码、文档名。
4. 回答要简洁、准确。
5. 关键结论后标注来源。

本地知识库资料：
{context}

用户问题：
{question}
```

回答示例：

```text
ADNI 数据包括 MRI、PET、临床量表和生物标志物。来源：ADNI说明.md
```

## 13. 来源引用

生产级 RAG 必须能追溯来源。

每个结果应保留：

```text
source
page
section
chunk_index
score
```

回答中引用：

```text
根据《产品手册》第 12 页，系统支持 PDF、DOCX 和 TXT 文件。
```

如果没有页码：

```text
根据 docs/import.md 的“文件导入”章节，系统支持批量上传。
```

## 14. 数据更新

文档更新不能简单重复入库。

推荐设计：

```text
doc_id = 文件路径 + 文件内容 hash
chunk_id = doc_id + chunk_index
```

入库前检查：

```text
文件不存在于知识库 -> 新增
文件内容未变化 -> 跳过
文件内容变化 -> 删除旧 chunk，写入新 chunk
```

## 15. 权限控制

如果未来支持多用户，必须在检索时加权限过滤。

metadata 示例：

```python
{
    "tenant_id": "company_a",
    "user_id": "u001",
    "project_id": "p001",
    "visibility": "private"
}
```

检索时必须带过滤条件：

```text
tenant_id = 当前租户
project_id in 用户可访问项目
```

## 16. 评测方案

没有评测，就无法判断 RAG 是否真的变好了。

建议准备一个 `eval/questions.jsonl`：

```json
{"question": "ADNI 包含哪些影像数据？", "expected_sources": ["adni.md"], "expected_keywords": ["MRI", "PET"]}
{"question": "系统支持哪些文件格式？", "expected_sources": ["manual.md"], "expected_keywords": ["PDF", "DOCX", "TXT"]}
```

评测指标：

```text
Recall@K: 正确文档是否被检索到
MRR: 正确文档排序是否靠前
Answer Faithfulness: 回答是否忠于资料
Citation Accuracy: 引用来源是否正确
No-answer Accuracy: 资料不足时是否拒答
```

## 17. 日志与可观测性

每次 RAG 查询建议记录：

```text
原始问题
改写后的问题
检索到的 chunk
检索分数
rerank 分数
最终上下文
最终回答
耗时
模型名称
```

这样方便定位问题：

```text
是没召回？
是召回了但排序错？
是上下文太长？
是模型没有遵守资料？
```

## 18. 当前项目落地路线

### 阶段 1：当前已完成的原型

```text
DeepSeek chat
Chroma 本地向量库
本地 hash embedding
/add 文档入库
/search 检索
chat 自动注入 RAG 上下文
```

### 阶段 2：提升检索质量

建议改动：

```text
把 hash embedding 替换为真实 embedding 模型
增加 Markdown/PDF/DOCX loader
保留页码和标题 metadata
优化 chunk 切分
增加来源引用
```

推荐：

```text
本地 embedding: bge-m3
向量库: Chroma
```

### 阶段 3：接近生产

建议改动：

```text
切换 Qdrant 或 pgvector
增加文档增量更新
增加混合检索
增加 reranker
增加 RAG 评测集
增加日志
```

### 阶段 4：生产化

建议改动：

```text
权限过滤
多租户隔离
后台入库任务
失败重试
监控和告警
检索质量仪表盘
定期评测
```

## 19. 推荐优先级

最值得优先做的不是换向量库，而是：

```text
1. 换成真实 embedding 模型
2. 做好文档切分和 metadata
3. 做来源引用
4. 做评测集
5. 再考虑 Qdrant 或 pgvector
```

原因是：很多 RAG 效果差，并不是向量库的问题，而是切分、embedding、metadata、检索策略和 prompt 没做好。

## 20. 免费使用说明

这三个后端都可以免费自托管使用：

```text
Chroma: 本地运行免费
Qdrant: 开源自托管免费
pgvector: PostgreSQL 扩展开源免费
```

可能收费的场景：

```text
Chroma Cloud
Qdrant Cloud
云数据库 PostgreSQL
API embedding 模型
API LLM 调用
服务器、磁盘、带宽资源
```

所以准确说：

```text
软件本身可以免费使用。
如果使用云托管服务或 API 模型，会产生服务费用。
```

## 21. 推荐最终架构

学习阶段：

```text
DeepSeek + Chroma + bge-m3
```

轻量生产：

```text
DeepSeek + Qdrant + bge-m3 + reranker
```

已有 PostgreSQL：

```text
DeepSeek + pgvector + bge-m3 + SQL metadata filter
```

生产级 RAG 的关键不是某一个组件，而是完整闭环：

```text
高质量入库
可靠检索
明确引用
可评测
可观测
可迭代
```
