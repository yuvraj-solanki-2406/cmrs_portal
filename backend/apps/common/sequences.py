from django.db import connection


def next_value(sequence_name: str) -> int:
    """Next value of a PostgreSQL sequence: concurrency-safe, no row lock, gaps possible after rollback."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT nextval(%s)", [sequence_name])
        return cursor.fetchone()[0]
