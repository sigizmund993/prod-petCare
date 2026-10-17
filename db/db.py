from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

pool: ConnectionPool | None = None


def connect(dsn: str) -> ConnectionPool:
    global pool
    pool = ConnectionPool(dsn, kwargs={"row_factory": dict_row}, open=True)
    pool.wait()
    return pool


def close() -> None:
    if pool is not None:
        pool.close()
