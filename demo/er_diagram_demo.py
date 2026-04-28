"""ErDiagram Demo — generate Mermaid ER diagram from SQLModel entities.

Run:
    uv run python -m demo.er_diagram_demo

This script uses the existing blog demo models (User, Post, Comment)
to demonstrate ErDiagram generation without needing a database.

For the Core API models (Sprint/Task/User), see:
    uv run uvicorn demo.core_api.app:app --port 8001
    then GET /api/er-diagram
"""

from sqlmodel_graphql import ErDiagram
from demo.models import Comment, Post, User


def main():
    print("=" * 60)
    print("ErDiagram Demo — Blog Models (User, Post, Comment)")
    print("=" * 60)

    diagram = ErDiagram.from_sqlmodel([User, Post, Comment])

    # Show discovered entities
    print("\nEntities:")
    for entity in diagram.entities:
        print(f"  {entity.name} (table: {entity.table_name})")
        print(f"    fields: {entity.fields}")
        print(f"    fk_fields: {entity.fk_fields}")
        for rel in entity.relationships:
            print(f"    {rel.relation_type.value}: {rel.name} -> {rel.target} (fk: {rel.fk_field})")

    # Generate Mermaid output
    print("\nMermaid ER Diagram:")
    print("-" * 60)
    print(diagram.to_mermaid())
    print("-" * 60)


if __name__ == "__main__":
    main()
