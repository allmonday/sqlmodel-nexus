"""Check if Post and Comment have by_id or by_filter attributes."""

from demo.models import Comment, Post, User

print("=== Checking User ===")
print("has by_id:", hasattr(User, "by_id"))
if hasattr(User, "by_id"):
    print("  type:", type(User.by_id))

print("has by_filter:", hasattr(User, "by_filter"))
if hasattr(User, "by_filter"):
    print("  type:", type(User.by_filter))

print("\n=== Checking Post ===")
print("has by_id:", hasattr(Post, "by_id"))
if hasattr(Post, "by_id"):
    print("  type:", type(Post.by_id))
    print("  value:", Post.by_id)

print("has by_filter:", hasattr(Post, "by_filter"))
if hasattr(Post, "by_filter"):
    print("  type:", type(Post.by_filter))
    print("  value:", Post.by_filter)

print("\n=== Checking Comment ===")
print("has by_id:", hasattr(Comment, "by_id"))
if hasattr(Comment, "by_id"):
    print("  type:", type(Comment.by_id))
    print("  value:", Comment.by_id)

print("has by_filter:", hasattr(Comment, "by_filter"))
if hasattr(Comment, "by_filter"):
    print("  type:", type(Comment.by_filter))
    print("  value:", Comment.by_filter)
