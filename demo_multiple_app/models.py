"""Multi-app demo models.

This module defines two independent applications:
- BlogApp: User and Post entities
- ShopApp: Product and Order entities

Each application has its own database and independent GraphQL schema.
"""

from typing import Optional

from sqlmodel import Field, Relationship, SQLModel, select

from sqlmodel_graphql import QueryMeta, mutation, query


# =============================================================================
# Blog Application Models
# =============================================================================


class BlogBaseEntity(SQLModel):
    """Base class for Blog application entities."""

    pass


class User(BlogBaseEntity, table=True):
    """User entity in the Blog application."""

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    email: str = Field(unique=True, index=True)

    # Relationships
    posts: list["Post"] = Relationship(back_populates="author")

    @query(name="users", description="Get all users with optional limit")
    async def get_all(
        cls, limit: int = 10, query_meta: QueryMeta | None = None
    ) -> list["User"]:
        """Get all users with optional limit."""
        from .database import get_blog_session

        async with get_blog_session() as session:
            stmt = select(cls).limit(limit)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return list(result.all())

    @query(name="user", description="Get a user by ID")
    async def get_by_id(cls, id: int, query_meta: QueryMeta | None = None) -> Optional["User"]:
        """Get a user by ID."""
        from .database import get_blog_session

        async with get_blog_session() as session:
            stmt = select(cls).where(cls.id == id)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return result.first()

    @mutation(name="create_user", description="Create a new user")
    async def create(cls, name: str, email: str, query_meta: QueryMeta) -> "User":
        """Create a new user."""
        from .database import get_blog_session

        async with get_blog_session() as session:
            user = cls(name=name, email=email)
            session.add(user)
            await session.commit()
            await session.refresh(user)

            # Re-query with query_meta to load relationships
            stmt = select(cls).where(cls.id == user.id)
            stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return result.first()


class Post(BlogBaseEntity, table=True):
    """Post entity in the Blog application."""

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    content: str
    author_id: int = Field(foreign_key="user.id")

    # Relationships
    author: Optional[User] = Relationship(back_populates="posts")

    @query(name="posts", description="Get all posts with optional limit")
    async def get_all(
        cls, limit: int = 10, query_meta: QueryMeta | None = None
    ) -> list["Post"]:
        """Get all posts with optional limit."""
        from .database import get_blog_session

        async with get_blog_session() as session:
            stmt = select(cls).limit(limit)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return list(result.all())

    @query(name="post", description="Get a post by ID")
    async def get_by_id(cls, id: int, query_meta: QueryMeta | None = None) -> Optional["Post"]:
        """Get a post by ID."""
        from .database import get_blog_session

        async with get_blog_session() as session:
            stmt = select(cls).where(cls.id == id)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return result.first()

    @mutation(name="create_post", description="Create a new post")
    async def create(cls, title: str, content: str, author_id: int, query_meta: QueryMeta) -> "Post":
        """Create a new post."""
        from .database import get_blog_session

        async with get_blog_session() as session:
            # Verify author exists
            author = await session.get(User, author_id)
            if not author:
                raise ValueError(f"User with id {author_id} not found")

            post = cls(title=title, content=content, author_id=author_id)
            session.add(post)
            await session.commit()
            await session.refresh(post)

            # Re-query with query_meta to load relationships
            stmt = select(cls).where(cls.id == post.id)
            stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return result.first()


# =============================================================================
# Shop Application Models
# =============================================================================


class ShopBaseEntity(SQLModel):
    """Base class for Shop application entities."""

    pass


class Product(ShopBaseEntity, table=True):
    """Product entity in the Shop application."""

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    price: float = Field(gt=0)
    stock: int = Field(ge=0, default=0)

    # Relationships
    order_items: list["OrderItem"] = Relationship(back_populates="product")

    @query(name="products", description="Get all products with optional limit")
    async def get_all(
        cls, limit: int = 10, query_meta: QueryMeta | None = None
    ) -> list["Product"]:
        """Get all products with optional limit."""
        from .database import get_shop_session

        async with get_shop_session() as session:
            stmt = select(cls).limit(limit)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return list(result.all())

    @query(name="product", description="Get a product by ID")
    async def get_by_id(cls, id: int, query_meta: QueryMeta | None = None) -> Optional["Product"]:
        """Get a product by ID."""
        from .database import get_shop_session

        async with get_shop_session() as session:
            stmt = select(cls).where(cls.id == id)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return result.first()

    @mutation(name="create_product", description="Create a new product")
    async def create(cls, name: str, price: float, stock: int = 0, query_meta: QueryMeta = None) -> "Product":
        """Create a new product."""
        from .database import get_shop_session

        async with get_shop_session() as session:
            product = cls(name=name, price=price, stock=stock)
            session.add(product)
            await session.commit()
            await session.refresh(product)

            # Re-query with query_meta to load relationships
            stmt = select(cls).where(cls.id == product.id)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return result.first()


class Order(ShopBaseEntity, table=True):
    """Order entity in the Shop application."""

    id: Optional[int] = Field(default=None, primary_key=True)
    customer_name: str = Field(index=True)
    total_amount: float = Field(default=0)

    # Relationships
    items: list["OrderItem"] = Relationship(back_populates="order")

    @query(name="orders", description="Get all orders with optional limit")
    async def get_all(
        cls, limit: int = 10, query_meta: QueryMeta | None = None
    ) -> list["Order"]:
        """Get all orders with optional limit."""
        from .database import get_shop_session

        async with get_shop_session() as session:
            stmt = select(cls).limit(limit)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return list(result.all())

    @query(name="order", description="Get an order by ID")
    async def get_by_id(cls, id: int, query_meta: QueryMeta | None = None) -> Optional["Order"]:
        """Get an order by ID."""
        from .database import get_shop_session

        async with get_shop_session() as session:
            stmt = select(cls).where(cls.id == id)
            if query_meta:
                stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return result.first()

    @mutation(name="create_order", description="Create a new order")
    async def create(cls, customer_name: str, query_meta: QueryMeta) -> "Order":
        """Create a new order."""
        from .database import get_shop_session

        async with get_shop_session() as session:
            order = cls(customer_name=customer_name)
            session.add(order)
            await session.commit()
            await session.refresh(order)

            # Re-query with query_meta to load relationships
            stmt = select(cls).where(cls.id == order.id)
            stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return result.first()


class OrderItem(ShopBaseEntity, table=True):
    """OrderItem entity in the Shop application."""

    id: Optional[int] = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="order.id")
    product_id: int = Field(foreign_key="product.id")
    quantity: int = Field(gt=0)
    unit_price: float

    # Relationships
    order: Optional[Order] = Relationship(back_populates="items")
    product: Optional[Product] = Relationship(back_populates="order_items")

    @mutation(name="add_order_item", description="Add an item to an order")
    async def create(
        cls, order_id: int, product_id: int, quantity: int, query_meta: QueryMeta
    ) -> "OrderItem":
        """Add an item to an order."""
        from .database import get_shop_session

        async with get_shop_session() as session:
            # Verify order exists
            order = await session.get(Order, order_id)
            if not order:
                raise ValueError(f"Order with id {order_id} not found")

            # Verify product exists and has enough stock
            product = await session.get(Product, product_id)
            if not product:
                raise ValueError(f"Product with id {product_id} not found")

            if product.stock < quantity:
                raise ValueError(
                    f"Insufficient stock for product {product.name}. "
                    f"Available: {product.stock}, Requested: {quantity}"
                )

            # Create order item
            order_item = cls(
                order_id=order_id,
                product_id=product_id,
                quantity=quantity,
                unit_price=product.price,
            )
            session.add(order_item)

            # Update product stock
            product.stock -= quantity

            # Update order total
            order.total_amount += product.price * quantity

            await session.commit()
            await session.refresh(order_item)

            # Re-query with query_meta to load relationships
            stmt = select(cls).where(cls.id == order_item.id)
            stmt = stmt.options(*query_meta.to_options(cls))
            result = await session.exec(stmt)
            return result.first()
