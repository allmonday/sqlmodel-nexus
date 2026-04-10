"""Check non-id primary key field structure."""

from sqlmodel import Field, SQLModel


class TestBase7(SQLModel):
    pass


class Product(TestBase7, table=True):
    code: str = Field(primary_key=True)
    name: str


# Inspect fields
print("=== Product.code ===")
print("model_fields['code']:", Product.model_fields['code'])
print("type:", type(Product.model_fields['code']))

print("\n=== Product.code properties ===")
for attr in dir(Product.model_fields['code']):
    if attr.startswith('__'):
        continue
    value = getattr(Product.model_fields['code'], attr)
    print(f"{attr}: {value}")
