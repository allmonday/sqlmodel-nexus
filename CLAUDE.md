# CLAUDE.md

## 项目定位

sqlmodel-nexus：从 SQLModel 类自动生成 GraphQL API，并提供 Core API 模式构建用例响应的 Python 库。
- **GraphQL 模式**：SDL 自动生成 + DataLoader 批量关系加载 + MCP 服务集成
- **Core API 模式**：DefineSubset DTO + ErManager + Resolver 模型驱动的响应构建

## 技术栈

- Python >= 3.10
- 核心依赖：sqlmodel, graphql-core, fastapi, aiodataloader
- 可选依赖：fastmcp (MCP 服务)
- 构建工具：hatchling
- 测试：pytest + pytest-asyncio (asyncio_mode=auto)
- Lint：ruff (line-length=100, rules: E/F/I/UP/B, ignore B008)
- 类型检查：mypy (strict)
- 版本：1.0.0

## 目录结构

```
src/sqlmodel_nexus/            # 主包
├── decorator.py               # @query / @mutation 装饰器
├── handler.py                 # GraphQLHandler — 查询执行入口
├── sdl_generator.py           # SQLModel → GraphQL SDL
├── type_converter.py          # Python 类型 → GraphQL 类型
├── query_parser.py            # GraphQL 查询 → FieldSelection 树
├── standard_queries.py        # AutoQueryConfig 自动生成 by_id/by_filter
├── resolver.py                # Resolver — Core API 模型驱动遍历引擎
├── subset.py                  # DefineSubset / SubsetConfig — DTO 生成
├── context.py                 # ExposeAs / SendTo / Collector — 跨层数据流
├── relationship.py            # 自定义（非 ORM）关系定义
├── er_diagram.py              # Mermaid ER 图生成
├── introspection.py           # GraphQL 内省支持
├── graphiql.py                # GraphiQL UI
├── response_builder.py        # 响应构建工具
├── type_service.py            # 类型服务
├── execution/                 # 查询执行器
├── loader/                    # DataLoader 关系加载 (ErManager + factories + pagination)
├── discovery/                 # 实体发现
├── scanning/                  # 方法扫描 (@query/@mutation 发现)
├── mcp/                       # MCP 服务
│   ├── builders/              #   Schema 格式化 + 类型追踪
│   ├── managers/              #   单应用 / 多应用管理器
│   ├── tools/                 #   MCP 工具实现
│   └── types/                 #   配置与错误类型
└── utils/                     # 工具函数

demo/                          # 演示应用
├── app.py                     # GraphQL demo (User/Post/Comment)
├── core_api/                  # Core API demo
├── mcp_server.py              # MCP 多应用 demo
└── mcp_server_simple.py       # MCP 单应用 demo
tests/                         # 测试用例
```

## 公共 API

```python
from sqlmodel_nexus import (
    # 装饰器
    query,                    # 标记 GraphQL 查询方法
    mutation,                 # 标记 GraphQL 变更方法

    # GraphQL 模式核心类
    GraphQLHandler,           # SDL 生成 + 查询执行
    SDLGenerator,             # SDL 生成器（一般不直接使用）
    QueryParser,              # 查询解析器（一般不直接使用）
    FieldSelection,           # 查询解析结果类型
    AutoQueryConfig,          # 自动查询配置
    add_standard_queries,     # 手动注册自动查询

    # Core API 模式
    DefineSubset,             # DTO 基类（从 SQLModel 实体生成 Pydantic 模型）
    SubsetConfig,             # 声明式 DTO 配置
    ErManager,                # 实体关系管理器（DataLoader + Resolver 工厂）
    Loader,                   # resolve_* 方法中声明 DataLoader 依赖

    # 跨层数据流
    ExposeAs,                 # 父→后代上下文暴露
    SendTo,                   # 后代→祖先值收集
    Collector,                # 聚合 SendTo 收集的值

    # 自定义关系 & ER 图
    Relationship,             # 自定义非 ORM 关系定义
    ErDiagram,                # Mermaid ER 图生成
)

# MCP
from sqlmodel_nexus.mcp import (
    config_simple_mcp_server, # 单应用 MCP 服务
    create_mcp_server,        # 多应用 MCP 服务
    AppConfig,                # 应用配置
)
```

## 开发命令

```bash
uv run pytest                                    # 运行测试
uv run ruff check src/ tests/                    # Lint 检查
uv run ruff check --fix src/ tests/              # Lint 修复
uv run mypy src/                                 # 类型检查
uv run python -m demo.app                        # 启动 GraphQL demo
uv run uvicorn demo.core_api.app:app --port 8001 # 启动 Core API demo
uv run --with fastmcp python -m demo.mcp_server  # 启动 MCP demo (stdio)
```

## 核心约定

### GraphQL 模式

#### 字段命名规则
`@query`/`@mutation` 方法自动生成字段名：`{entityName}{MethodName}`
- `User.get_all` → `userGetAll`
- `Post.create` → `postCreate`

#### 实体发现规则
- 有 `@query` 或 `@mutation` 的 SQLModel 子类会被自动发现
- 被发现的实体的 Relationship 关联实体也会被递归纳入
- 没有装饰器且没有关系引用的实体不会被纳入 schema

#### DataLoader 关系加载
- 逐层批量加载，自动避免 N+1
- 支持 MANYTOONE / ONETOMANY / MANYTOMANY
- 列表关系可启用分页（ROW_NUMBER 窗口函数）

#### AutoQueryConfig
启用后为所有实体自动生成 `by_id`（按主键查单个）和 `by_filter`（按字段精确匹配过滤列表）查询。
要求实体有且仅有一个主键字段。

### Core API 模式

#### DefineSubset 规则
- `__subset__` 接受元组 `(Entity, ('field1', 'field2'))` 或 `SubsetConfig` 对象
- FK 字段自动隐藏（`exclude=True`），但内部仍可在 `resolve_*` 中访问
- 关系字段声明在类体中（非 `__subset__`），类型必须是 DTO 类型，不能直接用 SQLModel 实体

#### Resolver 执行顺序
1. 执行所有 `resolve_*` 方法（加载关系数据）
2. 遍历已有的对象字段
3. 执行所有 `post_*` 方法（计算派生字段）
4. 收集 SendTo 值到祖先的 Collector

#### Implicit Auto-Loading
当以下条件全部满足时，Resolver 自动加载关系字段（无需手写 `resolve_*`）：
- 字段没有对应的 `resolve_*` 方法
- 字段是额外字段（不在 `__subset__` 定义中）
- 字段名匹配已注册的 ORM/自定义关系
- 字段类型是 BaseModel DTO 且与关系目标实体兼容

## 常见陷阱

### GraphQL 模式
1. **session_factory 必须提供**：否则 DataLoader 无法加载关系数据
2. **列表关系需要 order_by**：分页功能要求 `sa_relationship_kwargs={"order_by": "Entity.column"}`
3. **by_id 只支持单主键**：复合主键实体的 by_id 不会被生成
4. **字段名保持 snake_case**：不会自动转 camelCase
5. **@query/@mutation 方法的第一个参数必须是 cls**：装饰器会将其转为 classmethod
6. **query_meta 参数不出现在 SDL 中**：这是内部机制，不应在 GraphQL 查询中使用

### Core API 模式
7. **DTO 字段类型禁止用 SQLModel 实体**：`author: User | None` 会报 TypeError，必须用 `author: UserDTO | None`
8. **resolve_* 先于 post_***：post_* 中可以安全读取 resolve_* 赋值的字段
9. **Loader 依赖名必须匹配关系名**：`Loader('author')` 要求 ErManager 中有名为 `author` 的关系
10. **ErManager 的 base 和 entities 互斥**：不能同时传两个参数
