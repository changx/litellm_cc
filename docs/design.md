### **LLM API 代理网关：完整设计与实现文档 (修订版)**

### **1. 项目概述**

#### **1.1. 简介**
本文档旨在设计并指导实现一个高性能、可扩展、生产级的智能 LLM API 代理网关。该网关作为客户端与上游 LLM 服务商（OpenAI, Anthropic）之间的中间层，提供统一的访问入口、精细化的成本控制、账户级预算管理和详细的审计日志。

#### **1.2. 核心需求**

**功能性需求:**
*   **多格式 API 支持**: 必须提供与上游格式兼容的 API 端点，明确区分 OpenAI 和 Anthropic 的服务。
*   **账户级预算**: 预算和消费必须在账户（`user_id`）层面进行管理，所有属于同一账户的 API Key 共享同一个预算池。
*   **精细化成本模型**: 系统必须支持为每个 LLM 模型配置独立的成本，包括输入、输出以及缓存读取的 Token 成本。
*   **审计日志**: 必须记录每一次 API 调用的详细信息，包括账户、API Key、成本、Token 用量、请求/响应体等，用于查账和分析。
*   **管理功能**: 必须提供一套内部管理 API，用于创建和管理账户、API Key 及模型成本。

**非功能性需求:**
*   **高并发**: 系统必须能够稳定处理大规模并发请求。
*   **可伸缩性**: 架构必须支持无状态水平扩展。
*   **高可用性**: 关键数据存储（数据库）应具备冗余和故障转移能力。
*   **数据一致性**: 预算和计费数据必须保证强一致性。
*   **安全性**: 管理接口和敏感配置必须受到严格保护。

---

### **2. 系统架构**

本系统采用**无状态应用实例 + 外部集中式状态管理**的架构模式。

1.  **负载均衡器 (Load Balancer)**: 将传入的客户端请求分发到多个可用的 Proxy 实例。
2.  **Proxy 实例 (Stateless FastAPI App)**:
    *   每个实例都是一个独立的、完全无状态的 FastAPI 应用。
    *   实例内部维护一个**本地内存缓存 (Per-instance L1 Cache)**，用于存储认证和账户信息。
3.  **MongoDB (Single Source of Truth)**:
    *   作为系统的核心数据库，持久化存储所有账户、API Key、模型成本和使用日志。
4.  **Redis (Message Bus for Cache Invalidation)**:
    *   用作一个**发布/订阅 (Pub/Sub) 消息总线**。当数据在 MongoDB 中发生变更时，通过 Redis 广播消息，通知所有 Proxy 实例使其相关本地缓存失效。

---

### **3. 高并发与可伸缩性设计**

#### **3.1. 无状态与水平扩展**
Proxy 实例不存储任何持久化状态，允许通过增减实例数量进行无缝的水平扩展。

#### **3.2. 高效的读请求处理 (多级缓存)**
*   **L1 - 本地内存缓存 (In-Memory Cache)**: 使用 `cachetools.TTLCache`。API 请求首先检查此缓存。认证和账户数据在此命中，耗时在微秒级，避免了网络 I/O。
*   **L2 - MongoDB**: 仅当 L1 缓存未命中时查询 MongoDB。在 `user_id` 和 `api_key` 字段上建立的数据库索引确保查询性能维持在毫秒级。

#### **3.3. 高并发写操作的一致性 (原子记账)**
所有对账户消费额 (`spent_usd`) 的更新**必须**使用 MongoDB 的原子操作 `$inc`，确保在高并发下计费的绝对准确性。
*   **实现**: `db.accounts.update_one({"user_id": ...}, {"$inc": {"spent_usd": cost}})`

#### **3.4. 跨实例缓存一致性 (实时失效)**
*   **订阅**: 每个 Proxy 实例在启动时订阅一个 Redis 频道。
*   **发布**: 管理 API 更新 MongoDB 数据后，立即向该频道发布一条失效消息（例如 `{"type": "account", "key": "user-123"}`）。
*   **失效**: 所有实例收到消息后，立即从各自的本地缓存中删除对应的条目。

---

### **4. 数据模型与数据库 Schema**

#### **Collection: `accounts`**
*   **Pydantic Model: `Account`**
    ```python
    class Account(MongoBaseModel):
        user_id: str = Field(..., index=True, unique=True)
        account_name: Optional[str] = None
        budget_usd: float = 0.0
        spent_usd: float = 0.0
        budget_duration: BudgetDuration = BudgetDuration.TOTAL
        is_active: bool = True
        created_at: datetime = Field(default_factory=datetime.utcnow)
        updated_at: datetime = Field(default_factory=datetime.utcnow)
    ```

#### **Collection: `apikeys`**
*   **Pydantic Model: `ApiKey`**
    ```python
    class ApiKey(MongoBaseModel):
        api_key: str = Field(..., unique=True, index=True)
        user_id: str = Field(..., index=True)
        key_name: str
        is_active: bool = True
        allowed_models: Optional[List[str]] = None
        created_at: datetime = Field(default_factory=datetime.utcnow)
        updated_at: datetime = Field(default_factory=datetime.utcnow)
    ```

#### **Collection: `modelcosts`**
*   **Pydantic Model: `ModelCost`**
    ```python
    class ModelCost(MongoBaseModel):
        model_name: str = Field(..., unique=True)
        provider: str # e.g., "openai", "anthropic". Informational only.
        input_cost_per_million_tokens_usd: float
        output_cost_per_million_tokens_usd: float
        cached_read_cost_per_million_tokens_usd: float
        updated_at: datetime = Field(default_factory=datetime.utcnow)
    ```

#### **Collection: `usagelogs`**
*   **Pydantic Model: `UsageLog`**
    ```python
    class UsageLog(MongoBaseModel):
        user_id: str = Field(..., index=True)
        api_key: str = Field(..., index=True)
        model_name: str
        is_cache_hit: bool
        input_tokens: int
        output_tokens: int
        total_tokens: int
        cost_usd: float
        request_endpoint: str
        ip_address: Optional[str] = None
        request_payload: dict
        response_payload: dict
        timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    ```

---

### **5. API Endpoint Specification**

**认证**: 所有 API 均通过 `Authorization: Bearer <api_key>` 请求头进行认证。

#### **5.1. 代理接口**
*   **`POST /v1/chat/completions`**
    *   **描述**: 兼容 OpenAI Chat Completions API。硬编码路由至 OpenAI。
*   **`POST /v1/messages`**
    *   **描述**: 兼容 Anthropic Messages API。硬编码路由至 Anthropic。
*   **`POST /v1/responses`**
    *   **描述**: 兼容 LiteLLM Responses API。硬编码路由至 OpenAI。

#### **5.2. 管理接口**
*   **`POST /admin/accounts`**: 创建新账户。
*   **`PATCH /admin/accounts/{user_id}`**: 更新账户信息。**副作用**: 发布 `account` 缓存失效消息。
*   **`POST /admin/keys`**: 创建新 API Key。
*   **`PATCH /admin/keys/{api_key}`**: 更新 API Key。**副作用**: 发布 `apikey` 缓存失效消息。
*   **`POST /admin/costs`**: 添加或更新模型成本。**副作用**: 发布 `modelcost` 缓存失效消息。

---

### **6. 核心逻辑实现细节**

#### **6.1. 认证与授权依赖 (FastAPI Dependency)**
1.  从请求头提取 `api_key`。
2.  在**本地缓存**中查找 `f"apikey:{api_key}"`。
3.  **缓存命中**: 获取 `ApiKey` 对象，得到 `user_id`。继续在本地缓存查找 `f"account:{user_id}"`。若均命中，则进行预算检查后返回对象。
4.  **缓存未命中**: 查询 **MongoDB** 获取 `ApiKey` 和 `Account` 对象。若不存在或非激活状态，抛出 401/403 异常。将获取的对象填充到本地缓存并设置 TTL。
5.  **预算检查**: 比较 `Account.spent_usd` 和 `Account.budget_usd`。若超出预算，抛出 429 异常。
6.  返回 `ApiKey` 和 `Account` 对象供后续使用。

#### **6.2. 代理请求与上游路由逻辑 (Revised)**
1.  **静态路由**: 上游服务商由 API 端点路径唯一确定。
    *   请求 `.../chat/completions` 或 `.../responses` 时，上游目标为 **OpenAI**。
    *   请求 `.../messages` 时，上游目标为 **Anthropic**。
2.  **凭证加载**: 根据路由结果，从环境变量加载对应的凭证。
    *   对于 OpenAI: 加载 `OPENAI_API_KEY` 和 `OPENAI_BASE_URL`。
    *   对于 Anthropic: 加载 `ANTHROPIC_API_KEY` 和 `ANTHROPIC_BASE_URL`。
3.  **参数透传**: 客户端请求体中的所有参数（`model`, `messages`, `stream`, etc.）将通过 `**kwargs` 方式原封不动地传递给 `litellm.acompletion`。
4.  **调用 LiteLLM**:
    ```python
    # 伪代码 - OpenAI 路由
    response = await litellm.acompletion(
        **client_request_body,
        api_key=os.getenv("OPENAI_API_KEY"),
        api_base=os.getenv("OPENAI_BASE_URL")
    )
    ```

#### **6.3. 流式响应处理 (Streaming)**
系统必须正确处理 `stream=True` 的请求以保证计费准确。
1.  在代理逻辑中检查请求体是否包含 `"stream": True`。
2.  若为流式请求，必须使用 FastAPI 的 `StreamingResponse` 返回。
3.  `litellm.acompletion(..., stream=True)` 返回一个异步生成器。系统需要创建一个包装生成器，将数据块 `yield` 给 `StreamingResponse`。
4.  在包装生成器的 `finally` 块中，**必须**从流结束后的 LiteLLM 响应对象中提取 `usage` 信息，然后执行成本计算和原子记账。这确保了即使连接中断，只要流正常结束，记账就会发生。

#### **6.4. 成本计算与原子记账**
1.  **获取用量**:
    *   **非流式**: 直接从 `litellm.acompletion` 返回的 `ModelResponse` 对象中获取 `usage` 属性和 `_cache_hit` 标志。
    *   **流式**: 在 `finally` 块中从响应对象获取 `usage`。
2.  **查询成本**: 从客户端请求体中获取 `model` 名称，查询 `modelcosts` 缓存/数据库以获取其成本配置。
3.  **计算成本**: 根据用量、成本配置和缓存状态计算 `cost_usd`。
4.  **原子记账**: 执行 `db.accounts.update_one({"user_id": ...}, {"$inc": {"spent_usd": cost_usd}})`。
5.  **异步日志**: 创建 `UsageLog` 对象并异步插入数据库。

---

### **7. 技术栈与环境配置**

#### **7.1. 技术栈**
*   **Python**: 3.10+
*   **Web**: FastAPI
*   **LLM Proxy**: LiteLLM
*   **DB Driver**: Motor (Async MongoDB Driver)
*   **Cache**: cachetools
*   **Message Bus**: redis-py (async)
*   **Data Validation**: Pydantic

#### **7.2. 环境变量**
应用启动必须配置以下环境变量：
*   `MONGO_URI`: MongoDB 连接字符串。
*   `MONGO_DB_NAME`: 数据库名称。
*   `REDIS_URL`: Redis 连接字符串。
*   `ADMIN_API_KEY`: 用于保护管理 API 的密钥。
*   `OPENAI_API_KEY`: 上游 OpenAI Key。
*   `OPENAI_BASE_URL`: 上游 OpenAI API 的 Base URL。
*   `ANTHROPIC_API_KEY`: 上游 Anthropic Key。
*   `ANTHROPIC_BASE_URL`: 上游 Anthropic API 的 Base URL。

---

### **8. 部署与安全**

*   **部署**: 使用 Docker 容器化，通过 Kubernetes 等工具进行部署和水平扩展。
*   **数据库**: 生产环境的 MongoDB 必须部署为副本集 (Replica Set) 以实现高可用。
*   **错误处理**: 实现一个 FastAPI 全局异常处理器，用于捕获 `litellm` 的上游异常（如 `RateLimitError`, `APIError`），并将其映射为标准的 HTTP 错误码返回给客户端。
*   **安全**:
    *   绝不将任何密钥硬编码在代码中。
    *   管理 API 使用独立的、高强度的密钥进行保护，并考虑增加 IP 白名单。