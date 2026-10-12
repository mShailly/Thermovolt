from contextlib import contextmanager
from pathlib import Path
import os,sqlite3
ROOT=Path(__file__).resolve().parents[1]
POSTGRES=os.environ.get('DATABASE_URL','')
@contextmanager
def connection():
    if POSTGRES:
        import psycopg
        from psycopg.rows import dict_row
        conn=psycopg.connect(POSTGRES,row_factory=dict_row)
    else:
        conn=sqlite3.connect(ROOT/'thermovolt.sqlite');conn.row_factory=sqlite3.Row;conn.execute('PRAGMA foreign_keys=ON')
    try:yield conn;conn.commit()
    except Exception:conn.rollback();raise
    finally:conn.close()
def execute(conn,sql,args=()):return conn.execute(sql.replace('?','%s') if POSTGRES else sql,args)
def initialize():
    filename='postgres.sql' if POSTGRES else 'sqlite.sql'
    with connection() as conn:
        for statement in (ROOT/'sql'/filename).read_text().split(';'):
            if statement.strip():conn.execute(statement)
def fetch(sql,args=()):
    with connection() as conn:return [dict(r) for r in execute(conn,sql,args).fetchall()]
