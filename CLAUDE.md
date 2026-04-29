# CLAUDE.md

## 项目定位

sqlmodel-graphql：从 SQLModel 类自动生成 GraphQL API 的 Python 库。核心能力是 SDL 自动生成 + DataLoader 批量关系加载 + MCP 服务集成。

## 技术栈

- Python >= 3.10
- 核心依赖：sqlmodel, graphql-core, fastapi, aiodataloader
- 可选依赖：fastmcp (MCP 服务)
- 构建工具：hatchling
- 测试：pytest + pytest-asyncio (asyncio_mode=auto)
- Lint：ruff (line-length=100, rules: E/F/I/UP/B)
- 类型检查：mypy (strict)

## 目录结构

```
src/sqlmodel_graphql/       # 主包
├── decorator.py            # @query / @mutation 装饰器
├── handler.py              # GraphQLHandler — 查询执行入口
├── sdl_generator.py        # SQLModel → GraphQL SDL
├── type_converter.py       # Python 类型 → GraphQL 类型
├── query_parser.py         # GraphQL 查询 → FieldSelection 树
├── standard_queries.py     # AutoQueryConfig 自动生成 by_id/by_filter
├── execution/              # 查询执行器
├── loader/                 # DataLoader 关系加载 (registry + factories + pagination)
├── discovery/              # 实体发现
├── mcp/                    # MCP 服务 (simple / multi-app)
└── utils/                  # 工具函数

demo/                       # 演示应用 (User/Post/Comment)
tests/                      # 测试用例
```

## 公共 API

```python
from sqlmodel_graphql import (
    query,                    # 装饰器：标记 GraphQL 查询方法
    mutation,                 # 装饰器：标记 GraphQL 变更方法
    GraphQLHandler,           # 核心：SDL 生成 + 查询执行
    SDLGenerator,             # SDL 生成器（一般不直接使用）
    QueryParser,              # 查询解析器（一般不直接使用）
    FieldSelection,           # 查询解析结果类型
    AutoQueryConfig,          # 自动查询配置
    add_standard_queries,     # 手动注册自动查询
)

# MCP
from sqlmodel_graphql.mcp import (
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
uv run python -m demo.app                        # 启动 demo (GraphQL)
uv run --with fastmcp python -m demo.mcp_server  # 启动 demo (MCP, stdio)
```

## 核心约定

### GraphQL 字段命名规则
`@query`/`@mutation` 方法自动生成字段名：`{EntityName}{MethodName}`
- `User.get_all` → `userGetAll`
- `Post.create` → `postCreate`

### 实体发现规则
- 有 `@query` 或 `@mutation` 的 SQLModel 子类会被自动发现
- 被发现的实体的 Relationship 关联实体也会被递归纳入
- 没有装饰器且没有关系引用的实体不会被纳入 schema

### DataLoader 关系加载
- 逐层批量加载，自动避免 N+1
- 支持 MANYTOONE / ONETOMANY / MANYTOMANY
- 列表关系可启用分页（ROW_NUMBER 窗口函数）

### AutoQueryConfig
启用后为所有实体自动生成 `by_id`（按主键查单个）和 `by_filter`（按字段精确匹配过滤列表）查询。
要求实体有且仅有一个主键字段。

## 常见陷阱

1. **session_factory 必须提供**：否则 DataLoader 无法加载关系数据
2. **列表关系需要 order_by**：分页功能要求 `sa_relationship_kwargs={"order_by": "Entity.column"}`
3. **by_id 只支持单主键**：复合主键实体的 by_id 不会被生成
4. **字段名保持 snake_case**：不会自动转 camelCase
5. **@query/@mutation 方法的第一个参数必须是 cls**：装饰器会将其转为 classmethod
6. **query_meta 参数不出现在 SDL 中**：这是内部机制，不应在 GraphQL 查询中使用
