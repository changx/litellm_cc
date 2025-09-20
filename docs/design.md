## **LLM API 代理网关：完整设计与实现文档**

### **1. 项目概述**

#### **1.1. 简介**
本文档旨在设计并指导实现一个高性能、可扩展、生产级的智能 LLM API 代理网关。该网关作为客户端与上游 LLM 服务商（如 OpenAI, Anthropic 等）之间的中间层，提供统一的访问入口、精细化的成本控制、账户级预算管理和详细的审计日志。

#### **1.2. 核心需求**

**功能性需求:**
*   **多格式 API 支持**: 必须提供三种独立的、与上游格式兼容的 API 端点：OpenAI Chat Completions, Anthropic Messages, 和 LiteLLM Responses。
*   **账户级预算**: 预算和消费必须在账户（`user_id`）层面进行管理，所有属于同一账户的 API Key 共享同一个预算池。
*   **精细化成本模型**: 系统必须支持为每个 LLM 模型配置独立的成本，包括输入、输出以及缓存读取的 Token 成本。
*   **审计日志**: 必须记录每一次 API 调用的详细信息，包括账户、API Key、成本、Token 用量、请求/响应体等，用于查账和分析。
*   **管理功能**: 必须提供一套内部管理 API，用于创建和管理账户、API Key 及模型成本。

**非功能性需求:**
*   **高并发**: 系统必须能够稳定处理大规模并发请求，特别是在认证和记账环节。
*   **可伸缩性**: 架构必须支持无状态水平扩展，以便通过增加实例数量来应对增长的流量。
*   **高可用性**: 系统应避免单点故障，关键数据存储（数据库）应具备冗余和故障转移能力。
*   **数据一致性**: 在分布式环境下，必须保证预算和计费数据的强一致性。
*   **安全性**: 管理接口和敏感配置必须受到严格保护。

---

### **2. 系统架构**

本系统采用**无状态应用实例 + 外部集中式状态管理**的架构模式，专为云原生环境设计。

*(这是一个示意图，实际流程如下)*

1.  **负载均衡器 (Load Balancer)**: 将传入的客户端请求分发到多个可用的 Proxy 实例之一。
2.  **Proxy 实例 (Stateless FastAPI App)**:
    *   每个实例都是一个独立的、完全无状态的 FastAPI 应用。
    *   实例内部维护一个**本地内存缓存 (Per-instance L1 Cache)**，用于存储频繁访问的认证和账户信息，以实现极致的读取性能。
3.  **MongoDB (Single Source of Truth)**:
    *   作为系统的核心数据库，持久化存储所有账户、API Key、模型成本和使用日志。
    *   是系统中唯一的数据事实来源。
4.  **Redis (Message Bus for Cache Invalidation)**:
    *   不作为主缓存，而是用作一个**发布/订阅 (Pub/Sub) 消息总线**。
    *   当数据在 MongoDB 中发生变更时，通过 Redis 广播消息，通知所有 Proxy 实例使其相关本地缓存失效。

---

### **3. 高并发与可伸缩性设计**

这是本设计的核心，确保系统在生产环境下的性能和稳定性。

#### **3.1. 无状态与水平扩展**
Proxy 实例不存储任何持久化状态。这使得我们可以通过简单地增减实例数量（例如，在 Kubernetes 中调整 Pod 副本数）来轻松应对流量波动，实现无缝的水平扩展。

#### **3.2. 高效的读请求处理 (多级缓存)**
API 调用是主要的读取负载。我们通过一个两级缓存策略来吸收绝大部分压力：
*   **L1 - 本地内存缓存 (In-Memory Cache)**: 使用 `cachetools.TTLCache` 实现。API 请求首先检查此缓存。绝大多数情况下，认证和账户数据会在此命中，耗时在**微秒级**，完全避免了网络 I/O，使单个实例能处理极高的 QPS。
*   **L2 - MongoDB**: 仅当 L1 缓存未命中时（例如，实例重启、缓存过期或数据首次被访问），才会查询 MongoDB。在 `user_id` 和 `api_key` 字段上建立的**数据库索引**确保了即使缓存未命中，查询性能也能维持在毫秒级。

#### **3.3. 高并发写操作的一致性 (原子记账)**
为避免在高并发下因竞争条件导致的记账错误，所有对账户消费额 (`spent_usd`) 的更新**必须**使用 MongoDB 的**原子操作 `$inc`**。
*   **实现**: `db.accounts.update_one({"user_id": ...}, {"$inc": {"spent_usd": cost}})`
*   **保证**: 此操作在数据库层面是原子的，确保了计费的绝对准确性，即使数千个请求同时完成记账。

#### **3.4. 跨实例缓存一致性 (实时失效)**
为解决多个实例间本地缓存的数据同步问题，我们采用 Redis Pub/Sub 机制：
*   **订阅**: 每个 Proxy 实例在启动时都会订阅一个 Redis 频道（例如 `cache-invalidation`）。
*   **发布**: 当管理 API 更新了 MongoDB 中的数据（例如，修改了账户预算），该实例会立即向该频道**发布**一条失效消息（例如 `{"type": "account", "key": "user-123"}`）。
*   **失效**: 所有订阅了该频道的实例都会收到此消息，并立即从**各自的本地缓存中删除**对应的条目。这保证了业务规则的变更能在毫秒级内应用到整个集群。

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
        provider: str
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
*(注: `MongoBaseModel`, `BudgetDuration` 等辅助模型需预先定义)*

---

### **5. API Endpoint Specification**

**认证**: 所有 API 均通过 `Authorization: Bearer <api_key>` 请求头进行认证。管理 API 应有额外访问控制。

#### **5.1. 代理接口**
*   **`POST /v1/chat/completions`**
    *   **描述**: 兼容 OpenAI Chat Completions API。
    *   **请求/响应体**: 与 OpenAI 官方 API 格式一致。
*   **`POST /v1/messages`**
    *   **描述**: 兼容 Anthropic Messages API。
    *   **请求/响应体**: 与 Anthropic 官方 API 格式一致。
*   **`POST /v1/responses`**
    *   **描述**: 兼容 LiteLLM Responses API。
    *   **请求/响应体**: 与 LiteLLM Responses API 格式一致。

#### **5.2. 管理接口**
*   **`POST /admin/accounts`**: 创建新账户。
    *   **请求体**: `AccountCreate`
    *   **响应体**: `Account`
*   **`PATCH /admin/accounts/{user_id}`**: 更新账户信息 (预算, 状态等)。
    *   **请求体**: `AccountUpdate`
    *   **响应体**: `Account`
    *   **副作用**: **必须发布** `{"type": "account", "key": "{user_id}"}` 的缓存失效消息。
*   **`POST /admin/keys`**: 创建新 API Key。
    *   **请求体**: `ApiKeyCreate`
    *   **响应体**: `ApiKey`
*   **`PATCH /admin/keys/{api_key}`**: 更新 API Key (状态, 名称等)。
    *   **请求体**: `ApiKeyUpdate`
    *   **响应体**: `ApiKey`
    *   **副作用**: **必须发布** `{"type": "apikey", "key": "{api_key}"}` 的缓存失效消息。
*   **`POST /admin/costs`**: 添加或更新模型成本。
    *   **请求体**: `ModelCostCreate`
    *   **响应体**: `ModelCost`
    *   **副作用**: **必须发布** `{"type": "modelcost", "key": "{model_name}"}` 的缓存失效消息。

---

### **6. 核心逻辑实现细节**

#### **6.1. 认证与授权依赖 (FastAPI Dependency)**
1.  从请求头提取 `api_key` 字符串。
2.  在**本地缓存**中查找 `f"apikey:{api_key}"`。
3.  **缓存命中**: 获取 `ApiKey` 对象，得到 `user_id`。继续在本地缓存查找 `f"account:{user_id}"`。若均命中，则进行预算检查后直接返回 `ApiKey` 和 `Account` 对象。
4.  **缓存未命中**:
    *   查询 **MongoDB** 获取 `ApiKey` 对象。若不存在或 `is_active=False`，抛出 401/403 异常。
    *   使用 `user_id` 查询 **MongoDB** 获取 `Account` 对象。若不存在或 `is_active=False`，抛出 403 异常。
    *   将 `ApiKey` 和 `Account` 对象**填充到本地缓存**中，并设置 TTL (e.g., 1 hour)。
5.  **预算检查**: 比较 `Account.spent_usd` 和 `Account.budget_usd`。若超出预算，抛出 429 异常。
6.  返回 `ApiKey` 和 `Account` 对象供后续使用。

#### **6.2. 成本计算与原子记账**
1.  LLM 调用完成后，从 LiteLLM 的响应中获取 `usage` 和 `_cache_hit` 标志。
2.  获取模型的 `ModelCost` (应同样被缓存)。
3.  根据 `_cache_hit` 标志和公式计算本次调用的 `cost_usd`。
4.  执行 **MongoDB 原子更新**: `db.accounts.update_one({"user_id": ...}, {"$inc": {"spent_usd": cost_usd}})`。
5.  创建 `UsageLog` 对象并异步插入数据库。

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
*   `OPENAI_API_KEY`: 上游 OpenAI Key。
*   `ANTHROPIC_API_KEY`: 上游 Anthropic Key。
*   *(其他 LLM 提供商的 Key)*
*   `ADMIN_API_KEY`: 用于保护管理 API 的超级密钥。

---

### **8. 部署与安全**

*   **部署**: 推荐使用 Docker 容器化应用，并通过 Kubernetes 或类似编排工具进行部署和水平扩展。
*   **数据库**: 生产环境的 MongoDB 必须部署为**副本集 (Replica Set)** 以实现高可用。
*   **安全**:
    *   绝不将任何密钥硬编码在代码中。
    *   管理 API 必须与代理 API 分开，并使用独立的、高强度的密钥进行保护。
    *   考虑在网关层（如 Nginx）添加速率限制和防火墙规则。
