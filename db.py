import os, sqlite3, threading
from config import DB_PATH

DB_LOCK = threading.RLock()
DATABASE_URL = (os.getenv("DATABASE_URL") or "").strip()


def _is_pg(url):
    return url.startswith(("postgres://", "postgresql://"))


if _is_pg(DATABASE_URL):
    import pg8000.dbapi as _pg
    from urllib.parse import urlparse, unquote
    _u = urlparse(DATABASE_URL)
    conn = _pg.connect(
        host=_u.hostname,
        port=_u.port or 5432,
        user=unquote(_u.username or ""),
        password=unquote(_u.password or ""),
        database=(_u.path or "/").lstrip("/") or "neondb",
        ssl_context=True,
    )
    try:
        conn.autocommit = False
    except Exception:
        pass
    BACKEND = "postgres"
else:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    BACKEND = "sqlite"

print("[RCX] db backend:", BACKEND, flush=True)


class CompatRow:
    def __init__(self, src):
        self._src = src
        try:
            self._keys = list(src.keys())
        except Exception:
            self._keys = []

    def __getitem__(self, k):
        if isinstance(k, int):
            return self._src[self._keys[k]]
        return self._src[k]

    def keys(self):
        return self._keys

    def get(self, k, default=None):
        try:
            return self[k]
        except Exception:
            return default


def _translate(sql):
    if BACKEND != "postgres":
        return sql
    s = sql
    if "INSERT OR REPLACE INTO settings" in s:
        s = s.replace(
            "INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)",
            "INSERT INTO settings(key,value) VALUES(%s,%s) "
            "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value"
        )
    elif "INSERT OR REPLACE INTO pending_reqs" in s:
        s = s.replace(
            "INSERT OR REPLACE INTO pending_reqs(user_id,channel_id,ts) VALUES(?,?,?)",
            "INSERT INTO pending_reqs(user_id,channel_id,ts) VALUES(%s,%s,%s) "
            "ON CONFLICT (user_id,channel_id) DO UPDATE SET ts = EXCLUDED.ts"
        )
    s = s.replace("?", "%s")
    return s


def _translate_schema(sql):
    if BACKEND != "postgres":
        return sql
    s = sql
    s = s.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "BIGSERIAL PRIMARY KEY")
    s = s.replace("INTEGER PRIMARY KEY", "BIGINT PRIMARY KEY")
    return s


_RETURNING_TABLES = ("into links", "into clicks", "into channels", "into payments", "into tx")


class CompatCursor:
    def __init__(self, raw_conn):
        # raw_conn is the DB connection. We build a cursor from it.
        self._conn = raw_conn
        self._cur = raw_conn.cursor()
        self._lastrowid = None

    def execute(self, sql, params=()):
        self._lastrowid = None
        t = _translate(sql)
        if BACKEND == "postgres" and t.lstrip().upper().startswith("INSERT"):
            low = t.lower()
            if "returning" not in low and any(tbl in low for tbl in _RETURNING_TABLES):
                t = t.rstrip().rstrip(";") + " RETURNING id"
                self._cur.execute(t, params)
                try:
                    r = self._cur.fetchone()
                    if r is not None:
                        if isinstance(r, dict):
                            self._lastrowid = r.get("id")
                        else:
                            self._lastrowid = r[0]
                except Exception:
                    self._lastrowid = None
                return self
        self._cur.execute(t, params)
        return self

    def executemany(self, sql, seq):
        self._cur.executemany(_translate(sql), seq)
        return self

    def executescript(self, script):
        if BACKEND == "postgres":
            for stmt in _translate_schema(script).split(";"):
                s = stmt.strip()
                if s:
                    self._cur.execute(s)
        else:
            self._cur.executescript(script)
        return self

    def fetchone(self):
        r = self._cur.fetchone()
        if r is None:
            return None
        if BACKEND == "sqlite":
            return r
        cols = [d[0] for d in (self._cur.description or [])]
        d = dict(zip(cols, r)) if cols else {}
        return CompatRow(d)

    def fetchall(self):
        rows = self._cur.fetchall()
        if BACKEND == "sqlite":
            return rows
        cols = [d[0] for d in (self._cur.description or [])]
        return [CompatRow(dict(zip(cols, r))) if cols else CompatRow({}) for r in rows]

    @property
    def lastrowid(self):
        return self._lastrowid


c = CompatCursor(conn)
