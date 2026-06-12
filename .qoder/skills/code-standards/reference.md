# 代码规范参考（详细示例）

## MiniMax 嵌入 API 调用

```python
import requests

MINIMAX_EMBEDDING_URL = "https://api.minimax.chat/v1/embeddings"

def embed_texts(texts: list[str], api_key: str, model: str = "embo-01") -> list[list[float]]:
    resp = requests.post(
        MINIMAX_EMBEDDING_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "texts": texts,
            "type": "db",      # 入库和检索都用 "db"
        },
        timeout=60,
    )
    return resp.json()["vectors"]
```

## MiniMax LLM API 调用

```python
from openai import OpenAI

client = OpenAI(api_key=API_KEY, base_url="https://api.minimaxi.com/v1")
response = client.chat.completions.create(
    model="MiniMax-M2.5",
    messages=[{"role": "user", "content": "..."}],
    temperature=0.7,
    max_tokens=2048,
)
```

## SOCKS 代理清除

```python
import os
for _key in ("all_proxy", "ALL_PROXY"):
    os.environ.pop(_key, None)
```

## PDF 解析

```python
import fitz
doc = fitz.open(file_path)
text = "".join(page.get_text() for page in doc)
```

## Word 解析

```python
import docx
doc = docx.Document(file_path)
text = "\n".join(para.text for para in doc.paragraphs if para.text.strip())
```

## FAISS 向量存储

```python
import faiss
import numpy as np

dimension = 1536
index = faiss.IndexFlatIP(dimension)  # 内积 = 归一化后的余弦相似度

vectors = np.array(vectors_list, dtype=np.float32)
norms = np.linalg.norm(vectors, axis=1, keepdims=True)
vectors_normalized = vectors / norms

index.add(vectors_normalized)
```

## SearchReplace 工具使用

- original_text 必须文件中唯一
- 每次操作原始文本总量不超过 600 行
- 修改前先用 Read 确认，不要猜测行号
