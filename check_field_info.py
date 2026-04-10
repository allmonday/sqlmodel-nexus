"""Check what's actually in SQLModel's FieldInfo objects."""

from demo.models import Comment, Post, User

# Inspect fields
print("=== User.id ===")
print("model_fields['id']:", User.model_fields['id'])
print("type:", type(User.model_fields['id']))

print("\n=== Post.author_id ===")
print("model_fields['author_id']:", Post.model_fields['author_id'])
print("type:", type(Post.model_fields['author_id']))

print("\n=== Comment.post_id ===")
print("model_fields['post_id']:", Comment.model_fields['post_id'])
print("type:", type(Comment.model_fields['post_id']))


# Check all properties
print("\n=== User.id properties ===")
for attr in dir(User.model_fields['id']):
    if attr.startswith('__'):
        continue
    value = getattr(User.model_fields['id'], attr)
    print(f"{attr}: {value}")

print("\n=== Post.author_id properties ===")
for attr in dir(Post.model_fields['author_id']):
    if attr.startswith('__'):
        continue
    value = getattr(Post.model_fields['author_id'], attr)
    print(f"{attr}: {value}")
