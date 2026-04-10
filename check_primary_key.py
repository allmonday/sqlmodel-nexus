"""Check why Post and Comment don't get by_id queries."""

from demo.models import Comment, Post, User
from sqlmodel_graphql.standard_queries import _get_primary_key_fields

print("=== User ===")
print("model_fields:", list(User.model_fields.keys()))
print("primary keys:", _get_primary_key_fields(User))

print("\n=== Post ===")
print("model_fields:", list(Post.model_fields.keys()))
print("primary keys:", _get_primary_key_fields(Post))

print("\n=== Comment ===")
print("model_fields:", list(Comment.model_fields.keys()))
print("primary keys:", _get_primary_key_fields(Comment))


# Let's see what's in Post.id field
print("\n=== Post.id field ===")
print("Post.id info:", Post.model_fields.get('id'))
if Post.model_fields.get('id'):
    print("  primary_key:", getattr(Post.model_fields['id'], 'primary_key', 'N/A'))
