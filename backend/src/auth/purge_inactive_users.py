from auth.user_service import user_service

if __name__ == "__main__":
    deleted = user_service.delete_inactive_users_older_than(days=730)
    print(f"Deleted {deleted} inactive users")
