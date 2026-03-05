# SQLModel GraphQL 技术实现原理

本文档详细描述 sqlmodel-graphql 项目的转换逻辑和技术实现原理。

## 目录

1. [项目概述](#项目概述)
2. [核心架构](#核心架构)
3. [模块详解](#模块详解)
4. [数据流转换](#数据流转换)
5. [类型系统](#类型系统)
6. [查询优化机制](#查询优化机制)

---

## 项目概述

sqlmodel-graphql 是一个为 SQLModel 提供 GraphQL 支持的库，主要功能：

- **SDL 生成**：从 SQLModel 类自动生成 GraphQL Schema Definition Language
- **查询执行**：执行 GraphQL 查询并返回结果
- **查询优化**：通过 `QueryMeta` 实现 SQLAlchemy 查询优化，避免 N+1 问题

### 核心设计理念

```
SQLModel Entity  →  GraphQL Schema (SDL)
       ↓                    ↓
   @query/@mutation   →  Query/Mutation Type
       ↓                    ↓
   Python Type Hints →  GraphQL Types
       ↓                    ↓
   QueryMeta         →  SQLAlchemy Options (load_only, selectinload)
```

---

## 核心架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         用户代码层                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ SQLModel    │  │ @query      │  │ @mutation               │ │
│  │ Entity      │  │ decorator   │  │ decorator               │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                        核心处理层                                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ GraphQLHandler  │  │ SDLGenerator    │  │ QueryParser     │ │
│  │ (查询执行)       │  │ (Schema生成)    │  │ (查询解析)       │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
│  ┌─────────────────┐  ┌─────────────────┐                      │
│  │ Introspection   │  │ TypeConverter   │                      │
│  │ Generator       │  │ (类型转换)       │                      │
│  └─────────────────┘  └─────────────────┘                      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                        数据类型层                                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │ QueryMeta       │  │ FieldSelection  │  │ Relationship    │
│  │ (查询元数据)     │  │ (字段选择)       │  │ Selection       │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                        数据库层                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ SQLAlchemy (load_only, selectinload)                        ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

---

## 模块详解

### 1. decorator.py - 装饰器模块

**职责**：将普通方法标记为 GraphQL 查询或变更操作。

#### 转换逻辑

```
Python 方法                    →    GraphQL Field
─────────────────────────────────────────────────────
@query(name='users')           →    Query.users
@mutation(name='createUser')   →    Mutation.createUser
```

#### 实现原理

```python
# 装饰器通过添加属性标记方法
func._graphql_query = True           # 标记为查询
func._graphql_query_name = 'users'   # GraphQL 字段名
func._graphql_query_description = '' # 字段描述

# 自动转换为 classmethod
return classmethod(func)
```

#### 支持的装饰器风格

```python
# 风格1: 无参数
@query
def get_all(cls) -> list['User']: ...

# 风格2: 带名称
@query(name='users')
def get_all(cls) -> list['User']: ...

# 风格3: 带名称和描述
@query(name='users', description='Get all users')
def get_all(cls) -> list['User']: ...
```

---

### 2. type_converter.py - 类型转换器

**职责**：统一处理 Python 类型到 GraphQL 类型的转换逻辑。

#### 核心转换映射

```
Python 类型          →    GraphQL 类型
─────────────────────────────────────────
int                 →    Int
str                 →    String
bool                →    Boolean
float               →    Float
Optional[T]         →    T (nullable)
list[T]             →    [T!]!
Entity类            →    Entity (Object)
Enum类              →    Enum
Mapped[T]           →    T (unwrap)
```

#### 主要方法

| 方法 | 功能 |
|------|------|
| `is_optional()` | 检测是否为 `Optional[T]` |
| `unwrap_optional()` | 解包 `Optional[T]` 获取 `T` |
| `is_list_type()` | 检测是否为 `list[T]` |
| `get_list_inner_type()` | 获取 `list[T]` 中的 `T` |
| `is_mapped_wrapper()` | 检测 SQLAlchemy `Mapped[T]` |
| `is_entity_type()` | 检测是否为实体类型 |
| `is_relationship()` | 检测是否为关系类型 |
| `get_scalar_type_name()` | 获取标量类型名称 |

---

### 3. sdl_generator.py - SDL 生成器

**职责**：从 SQLModel 类生成 GraphQL Schema Definition Language。

#### 生成流程

```
SQLModel Entity
       │
       ├── model_fields → 标量字段
       │      │
       │      └── _field_info_to_graphql() → "fieldName: String!"
       │
       ├── type_hints → 关系字段
       │      │
       │      └── _type_hint_to_graphql() → "posts: [Post!]!"
       │
       └── @query/@mutation 方法
              │
              └── _method_to_graphql_field() → "users(limit: Int): [User!]!"
```

#### 输出示例

```graphql
type User {
  id: Int!
  name: String!
  email: String!
  posts: [Post!]!
}

type Post {
  id: Int!
  title: String!
  content: String!
  author_id: Int!
  author: User
}

type Query {
  users(limit: Int): [User!]!
  user(id: Int!): User
  posts(limit: Int): [Post!]!
}

type Mutation {
  create_user(name: String!, email: String!): User!
}
```

---

### 4. query_parser.py - 查询解析器

**职责**：解析 GraphQL 查询，提取字段选择信息用于查询优化。

#### 解析流程

```
GraphQL Query
       │
       │  parse()
       ↓
┌─────────────────────────────────────┐
│  QueryParser                        │
│  ┌───────────────────────────────┐  │
│  │ 遍历 selection_set            │  │
│  │  ├── 标量字段 → FieldSelection│  │
│  │  └── 关系字段 → 递归解析      │  │
│  └───────────────────────────────┘  │
└─────────────────────────────────────┘
       │
       ↓
{
  'users': QueryMeta(
    fields=[FieldSelection('id'), FieldSelection('name')],
    relationships={
      'posts': RelationshipSelection(
        fields=[FieldSelection('title')],
        relationships={}
      )
    }
  )
}
```

#### 代码示例

```python
query = """
query {
  users {
    id
    name
    posts {
      title
      content
    }
  }
}
"""

parser = QueryParser()
result = parser.parse(query)
# result['users'] 包含 QueryMeta
```

---

### 5. types.py - 数据类型定义

**职责**：定义核心数据结构和 SQLAlchemy 优化转换。

#### 类结构

```
QueryMeta
├── fields: list[FieldSelection]          # 请求的标量字段
├── relationships: dict[str, RelationshipSelection]  # 请求的关系
└── to_options(entity) → list[SQLAlchemy Options]    # 转换方法

FieldSelection
├── name: str       # 字段名
└── alias: str      # GraphQL 别名

RelationshipSelection
├── name: str                        # 关系名
├── fields: list[FieldSelection]     # 关系的字段
└── relationships: dict[...]         # 嵌套关系
```

#### to_options() 转换逻辑

```
QueryMeta                        SQLAlchemy Options
─────────────────────────────────────────────────────
fields: [id, name]          →    load_only(User.id, User.name)

relationships:
  posts:
    fields: [title]         →    selectinload(User.posts)
                                  .options(load_only(Post.title))
```

#### 实现代码

```python
def to_options(self, entity: type[SQLModel]) -> list[Any]:
    options = []

    # 1. 字段选择优化
    if self.fields:
        columns = [getattr(entity, f.name) for f in self.fields]
        # 始终包含主键
        columns.extend(self._get_primary_key_columns(entity))
        options.append(load_only(*columns))

    # 2. 关系加载优化
    for rel_name, rel_selection in self.relationships.items():
        loader = selectinload(getattr(entity, rel_name))
        if rel_selection.fields:
            loader = loader.options(
                load_only(*[getattr(target, f.name) for f in rel_selection.fields])
            )
        options.append(loader)

    return options
```

---

### 6. handler.py - GraphQL 处理器

**职责**：协调各组件，执行 GraphQL 查询。

#### 执行流程

```
GraphQL Query String
         │
         │  execute()
         ↓
┌────────────────────────────────┐
│ 1. 检测是否为内省查询           │
│    (__schema, __type)          │
└────────────────────────────────┘
         │
    ┌────┴────┐
    ↓         ↓
 内省查询    普通查询
    │         │
    │         │
    ↓         ↓
┌────────┐  ┌────────────────────────────┐
│Introsp-│  │ 2. QueryParser.parse()     │
│ection  │  │    提取 QueryMeta          │
│Generator│  └────────────────────────────┘
└────────┘              │
                        ↓
           ┌────────────────────────────┐
           │ 3. 查找对应的 @query 方法   │
           └────────────────────────────┘
                        │
                        ↓
           ┌────────────────────────────┐
           │ 4. 注入 query_meta 参数     │
           │    执行用户方法             │
           └────────────────────────────┘
                        │
                        ↓
           ┌────────────────────────────┐
           │ 5. 序列化结果              │
           │    只包含请求的字段         │
           └────────────────────────────┘
                        │
                        ↓
              GraphQL Response
```

#### 关键代码

```python
async def _execute_query(self, query, variables, operation_name, parsed_meta):
    for definition in document.definitions:
        for selection in definition.selection_set.selections:
            field_name = selection.name.value
            entity, method = self._query_methods[field_name]

            # 构建参数
            args = self._build_arguments(selection, variables, method, entity)

            # 注入 query_meta
            if field_name in parsed_meta:
                args["query_meta"] = parsed_meta[field_name]

            # 执行方法
            result = method(**args)
            if inspect.isawaitable(result):
                result = await result

            # 序列化（只包含请求的字段）
            requested_fields = self._extract_requested_fields(selection)
            data[field_name] = _serialize_value(result, include=requested_fields)
```

---

### 7. introspection.py - 内省生成器

**职责**：生成 GraphQL 内省查询响应，支持 GraphiQL 等工具。

#### 内省数据结构

```python
{
  "__schema": {
    "queryType": {"name": "Query"},
    "mutationType": {"name": "Mutation"},
    "types": [
      # 标量类型
      {"kind": "SCALAR", "name": "Int", ...},
      {"kind": "SCALAR", "name": "String", ...},
      # 枚举类型
      {"kind": "ENUM", "name": "Status", "enumValues": [...]},
      # 对象类型
      {"kind": "OBJECT", "name": "User", "fields": [...]},
      # Query/Mutation 类型
      {"kind": "OBJECT", "name": "Query", "fields": [...]},
    ]
  }
}
```

#### 类型引用结构

```
NON_NULL (required)
└── ofType: LIST
    └── ofType: OBJECT/SCALAR
        └── name: "User" / "Int"
```

示例：
```python
# [User!]! 的内省表示
{
  "kind": "NON_NULL",
  "ofType": {
    "kind": "LIST",
    "ofType": {
      "kind": "NON_NULL",
      "ofType": {"kind": "OBJECT", "name": "User"}
    }
  }
}
```

---

## 数据流转换

### 完整查询流程示例

```
1. 客户端发送查询
─────────────────────────────────────────────────────────────
POST /graphql
{
  "query": "query { users(limit: 2) { id name posts { title } } }"
}

2. GraphQLHandler 接收并解析
─────────────────────────────────────────────────────────────
QueryParser.parse() →
{
  'users': QueryMeta(
    fields=[FieldSelection('id'), FieldSelection('name')],
    relationships={
      'posts': RelationshipSelection(
        fields=[FieldSelection('title')],
        relationships={}
      )
    }
  )
}

3. 查找并执行 @query 方法
─────────────────────────────────────────────────────────────
method = User.get_all  # 被 @query 装饰的方法
args = {'limit': 2, 'query_meta': QueryMeta(...)}

# 用户方法内部
async def get_all(cls, limit: int, query_meta: QueryMeta):
    stmt = select(cls).limit(limit)
    if query_meta:
        stmt = stmt.options(*query_meta.to_options(cls))
    # 生成的 SQL 只查询 id, name，并预加载 posts.title

4. 生成 SQLAlchemy 查询选项
─────────────────────────────────────────────────────────────
query_meta.to_options(User) → [
  load_only(User.id, User.name),
  selectinload(User.posts).options(load_only(Post.title, Post.id))
]

5. 执行数据库查询（优化后）
─────────────────────────────────────────────────────────────
SELECT user.id, user.name FROM user LIMIT 2;
SELECT post.id, post.title FROM post WHERE post.author_id IN (1, 2);

6. 序列化响应
─────────────────────────────────────────────────────────────
_serialize_value(users, include={'id', 'name', 'posts'}) →
{
  "data": {
    "users": [
      {
        "id": 1,
        "name": "Alice",
        "posts": [{"title": "Hello World"}]
      },
      {
        "id": 2,
        "name": "Bob",
        "posts": [{"title": "GraphQL is Great"}]
      }
    ]
  }
}
```

---

## 类型系统

### Python → GraphQL 类型映射

```
┌────────────────────────────────────────────────────────────┐
│ Python 类型                 │ GraphQL 类型                  │
├────────────────────────────────────────────────────────────┤
│ int                        │ Int                          │
│ str                       │ String                       │
│ bool                      │ Boolean                      │
│ float                     │ Float                        │
│ Optional[int]             │ Int                          │
│ list[int]                 │ [Int!]!                      │
│ list[Optional[User]]      │ [User]!                      │
│ User (Entity)             │ User!                        │
│ Optional[User]            │ User                         │
│ list[User]                │ [User!]!                     │
│ Status (Enum)             │ Status!                      │
└────────────────────────────────────────────────────────────┘
```

### 特殊类型处理

#### SQLAlchemy Mapped 包装器

```python
# SQLModel Relationship 字段类型
posts: list["Post"] = Relationship()

# 实际类型提示可能是
# Mapped[list[Post]] 或 list[Post]

# TypeConverter 自动解包 Mapped
if is_mapped_wrapper(type_hint):
    type_hint = unwrap_mapped(type_hint)
```

#### 前向引用 (Forward Reference)

```python
# 字符串形式的前向引用
posts: list["Post"] = Relationship()

# TypeConverter 处理
if isinstance(type_hint, str):
    return type_hint in self._entity_names
```

---

## 查询优化机制

### 问题：N+1 查询

```python
# 未优化的查询
users = await session.exec(select(User))
for user in users:
    # 每次循环都查询一次 posts - N+1 问题！
    posts = await session.exec(select(Post).where(Post.author_id == user.id))
```

### 解决方案：QueryMeta + SQLAlchemy Options

```python
# 优化后的查询
query_meta = QueryMeta(
    fields=[FieldSelection('id'), FieldSelection('name')],
    relationships={
        'posts': RelationshipSelection(fields=[FieldSelection('title')])
    }
)

stmt = select(User).options(*query_meta.to_options(User))
# 生成的选项：
# - load_only(User.id, User.name) - 只查询需要的字段
# - selectinload(User.posts) - 预加载关系，避免 N+1
```

### 优化效果对比

```
未优化 (N+1):
─────────────────────────────────────
SELECT * FROM user LIMIT 10;        -- 1 次
SELECT * FROM post WHERE author_id = 1;  -- 10 次
SELECT * FROM post WHERE author_id = 2;
...
SELECT * FROM post WHERE author_id = 10;
─────────────────────────────────────
总计: 11 次数据库查询

优化后 (QueryMeta):
─────────────────────────────────────
SELECT user.id, user.name FROM user LIMIT 10;  -- 1 次
SELECT post.id, post.title, post.author_id
FROM post WHERE post.author_id IN (1,2,...,10);  -- 1 次
─────────────────────────────────────
总计: 2 次数据库查询
```

---

## 总结

sqlmodel-graphql 通过以下核心技术实现 GraphQL 支持：

1. **装饰器标记**：使用 `@query`/`@mutation` 装饰器声明 GraphQL 操作
2. **类型转换**：`TypeConverter` 统一处理 Python → GraphQL 类型映射
3. **Schema 生成**：`SDLGenerator` 从 SQLModel 类生成 GraphQL SDL
4. **查询解析**：`QueryParser` 从 GraphQL 查询提取 `QueryMeta`
5. **查询优化**：`QueryMeta.to_options()` 生成 SQLAlchemy 优化选项
6. **内省支持**：`IntrospectionGenerator` 支持 GraphiQL 等工具

这种设计实现了：
- **声明式 API**：用户只需关注业务逻辑
- **自动优化**：避免 N+1 查询问题
- **类型安全**：完整的类型映射和验证
- **工具兼容**：支持标准 GraphQL 工具链
