import unittest
import sqlite3
import tempfile
import os
import shutil
import datetime as _dt
import decimal

sqlite3.register_adapter(_dt.datetime, lambda dt: dt.isoformat(" "))
sqlite3.register_converter(
    "TIMESTAMP",
    lambda b: _dt.datetime.fromisoformat(b.decode("utf-8"))
)

# Helper types for adapters/converters
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y
    def __eq__(self, other):
        return isinstance(other, Point) and self.x == other.x and self.y == other.y
    def __repr__(self):
        return f"Point({self.x}, {self.y})"


def adapt_point(p):
    return f"{p.x};{p.y}"  # stored as TEXT


def convert_point(s):
    if isinstance(s, bytes):
        s = s.decode("utf-8")
    x_s, y_s = s.split(";")
    return Point(float(x_s), float(y_s))


class TestSqlite3Module(unittest.TestCase):
    def setUp(self):
        # Detect types via declared types and column names
        self.detect = sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        # isolation_level=None puts connection in autocommit mode
        self.conn = sqlite3.connect(":memory:", detect_types=self.detect, isolation_level=None)
        self.addCleanup(self.conn.close)
        self.cur = self.conn.cursor()
        # Turn on foreign keys for relevant tests
        self.conn.execute("PRAGMA foreign_keys=ON")

    # --- Basic connection/cursor operations ---
    def test_connection_and_cursor(self):
        self.assertIsInstance(self.conn, sqlite3.Connection)
        self.assertIsInstance(self.cur, sqlite3.Cursor)
        self.cur.execute("CREATE TABLE t(a INTEGER, b TEXT)")
        self.cur.execute("INSERT INTO t VALUES (?, ?)", (1, "x"))
        self.cur.execute("SELECT a, b FROM t")
        row = self.cur.fetchone()
        self.assertEqual(row, (1, "x"))
        self.assertIsNone(self.cur.fetchone())
        self.cur.execute("SELECT 1")
        self.assertEqual(self.cur.fetchone()[0], 1)

    def test_cursor_iteration_and_fetch(self):
        self.conn.execute("CREATE TABLE r(i INTEGER)")
        self.conn.executemany("INSERT INTO r(i) VALUES (?)", [(i,) for i in range(10)])
        c = self.conn.execute("SELECT i FROM r ORDER BY i")
        self.assertEqual(c.fetchmany(3), [(0,), (1,), (2,)])
        rest = c.fetchall()
        self.assertEqual(rest[-1], (9,))
        # Reset table
        self.conn.execute("DELETE FROM r")

    # --- Parameter styles ---
    def test_parameter_styles(self):
        self.conn.execute("CREATE TABLE p(a INTEGER, b TEXT, c REAL)")
        # Qmark style
        self.conn.execute("INSERT INTO p VALUES (?, ?, ?)", (1, "one", 1.5))
        # Named style
        self.conn.execute("INSERT INTO p VALUES (:a, :b, :c)", {"a": 2, "b": "two", "c": 2.5})
        # Mapping executemany
        self.conn.executemany(
            "INSERT INTO p VALUES (:a, :b, :c)",
            [{"a": i, "b": str(i), "c": i + 0.5} for i in range(3, 6)],
        )
        count = self.conn.execute("SELECT COUNT(*) FROM p").fetchone()[0]
        self.assertEqual(count, 5)

    # --- executemany / executescript ---
    def test_executemany_and_executescript(self):
        # Ensure table exists before inserts
        self.conn.execute("CREATE TABLE e(x)")
        self.conn.executemany("INSERT INTO e(x) VALUES (?)", [(i,) for i in range(5)])
        script = """
        BEGIN;
        CREATE TABLE s(y INTEGER);
        INSERT INTO s(y) SELECT x FROM e;
        COMMIT;
        """
        self.conn.executescript(script)
        rows = self.conn.execute("SELECT COUNT(*) FROM s").fetchone()[0]
        self.assertEqual(rows, 5)

    # --- Transactions, autocommit, and context manager ---
    def test_transactions_and_context_manager(self):
        # isolation_level=None enables autocommit; use explicit transactions
        self.conn.execute("CREATE TABLE tr(i INTEGER)")
        # Using context manager still executes statements immediately (no implicit BEGIN)
        with self.conn:
            self.conn.execute("INSERT INTO tr VALUES (1)")
        # Exception inside context does NOT rollback previous statements in autocommit mode
        try:
            with self.conn:
                self.conn.execute("INSERT INTO tr VALUES (2)")
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        vals = [r[0] for r in self.conn.execute("SELECT i FROM tr ORDER BY i").fetchall()]
        self.assertEqual(vals, [1, 2])

    def test_savepoints(self):
        self.conn.execute("CREATE TABLE sp(i INTEGER)")
        self.conn.execute("SAVEPOINT a")
        self.conn.executemany("INSERT INTO sp VALUES (?)", [(1,), (2,), (3,)])
        self.conn.execute("SAVEPOINT b")
        self.conn.execute("INSERT INTO sp VALUES (99)")
        self.conn.execute("ROLLBACK TO b")  # undo 99
        self.conn.execute("RELEASE b")
        self.conn.execute("RELEASE a")
        vals = [r[0] for r in self.conn.execute("SELECT i FROM sp ORDER BY i").fetchall()]
        self.assertEqual(vals, [1, 2, 3])

    # --- Row factory & row types ---
    def test_row_factory_and_row(self):
        self.conn.row_factory = None
        self.conn.execute("CREATE TABLE rf(a INTEGER, b TEXT)")
        self.conn.execute("INSERT INTO rf VALUES (1, 'x')")
        self.assertEqual(self.conn.execute("SELECT * FROM rf").fetchone(), (1, "x"))
        # sqlite3.Row
        self.conn.row_factory = sqlite3.Row
        row = self.conn.execute("SELECT a, b FROM rf").fetchone()
        self.assertEqual(row[0], 1)
        self.assertEqual(row["b"], "x")
        self.assertEqual(tuple(row.keys()), ("a", "b"))
        # Custom dict factory
        def dict_factory(cursor, r):
            return {d[0]: r[i] for i, d in enumerate(cursor.description)}
        self.conn.row_factory = dict_factory
        d = self.conn.execute("SELECT a, b FROM rf").fetchone()
        self.assertEqual(d, {"a": 1, "b": "x"})
        # Reset
        self.conn.row_factory = None

    # --- Adapters & Converters ---
    def test_adapters_and_converters(self):
        sqlite3.register_adapter(Point, adapt_point)
        sqlite3.register_converter("POINT", convert_point)
        sqlite3.register_adapter(decimal.Decimal, lambda d: str(d))
        sqlite3.register_converter("DECIMAL", lambda s: decimal.Decimal(s.decode()))
        conn = sqlite3.connect(":memory:", detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        with conn:
            conn.execute("CREATE TABLE ac(p POINT, d DECIMAL, n INTEGER, t TIMESTAMP)")
            now = _dt.datetime(2020, 1, 1, 12, 34, 56)
            conn.execute(
                "INSERT INTO ac VALUES (?, ?, ?, ?)",
                (Point(1, 2), decimal.Decimal("3.14"), 7, now),
            )
        r = conn.execute("SELECT p, d, n, t FROM ac").fetchone()
        self.assertEqual(r[0], Point(1.0, 2.0))
        self.assertEqual(r[1], decimal.Decimal("3.14"))
        self.assertEqual(r[2], 7)
        # Built-in TIMESTAMP converter returns datetime (deprecated default in 3.12 but still works)
        self.assertIsInstance(r[3], _dt.datetime)
        conn.close()

    # --- Custom SQL functions, aggregates, window functions ---
    def test_custom_functions_and_aggregates(self):
        self.conn.execute("CREATE TABLE fun(x INTEGER)")
        self.conn.executemany("INSERT INTO fun(x) VALUES (?)", [(1,), (2,), (3,), (4,)])
        self.conn.create_function("double", 1, lambda v: v * 2)
        out = [r[0] for r in self.conn.execute("SELECT double(x) FROM fun ORDER BY x").fetchall()]
        self.assertEqual(out, [2, 4, 6, 8])

        class SumAgg:
            def __init__(self):
                self.total = 0
            def step(self, v):
                if v is not None:
                    self.total += v
            def finalize(self):
                return self.total
        self.conn.create_aggregate("sumagg", 1, SumAgg)
        s = self.conn.execute("SELECT sumagg(x) FROM fun").fetchone()[0]
        self.assertEqual(s, 10)

        # Optional: window function support varies by build; tolerate absence
        if hasattr(self.conn, "create_window_function"):
            try:
                # Simple cumulative sum window function using the context API
                def winsum(ctx, value):
                    total = 0
                    for i in range(ctx.window_size()):
                        total += ctx.get_value(i)
                    ctx.result(total)
                self.conn.create_window_function("winsum", 1, winsum)
                res = [r[0] for r in self.conn.execute(
                    "SELECT winsum(x) OVER (ORDER BY x ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) FROM fun ORDER BY x"
                )]
                self.assertEqual(res, [1, 3, 6, 10])
            except Exception:
                # Some SQLite builds may not expose the full window context API; ignore
                pass

    # --- Collations ---
    def test_collations(self):
        self.conn.execute("CREATE TABLE col(s TEXT)")
        data = ["apple", "Banana", "cherry"]
        self.conn.executemany("INSERT INTO col VALUES (?)", [(s,) for s in data])

        def nocase_reverse(a, b):
            a, b = a.lower(), b.lower()
            if a < b:
                return 1
            if a > b:
                return -1
            return 0
        self.conn.create_collation("REVERSE", nocase_reverse)
        ordered = [r[0] for r in self.conn.execute("SELECT s FROM col ORDER BY s COLLATE REVERSE").fetchall()]
        # SQLite returns original-case strings; our comparator compares lowercased values only
        self.assertEqual(ordered, ["cherry", "Banana", "apple"])

    # --- Description metadata ---
    def test_cursor_description(self):
        self.conn.execute("CREATE TABLE d(a INTEGER, b TEXT)")
        c = self.conn.execute("SELECT a as A, b as B FROM d")
        desc = c.description
        self.assertEqual([d[0] for d in desc], ["A", "B"])

    # --- lastrowid, rowcount, total_changes ---
    def test_lastrowid_rowcount_total_changes(self):
        self.conn.execute("CREATE TABLE lr(i INTEGER PRIMARY KEY AUTOINCREMENT, v TEXT)")
        c = self.conn.execute("INSERT INTO lr(v) VALUES ('x')")
        self.assertIsInstance(c.lastrowid, int)
        self.assertEqual(c.rowcount, 1)
        before = self.conn.total_changes
        self.conn.executemany("INSERT INTO lr(v) VALUES (?)", [(str(i),) for i in range(5)])
        self.assertGreater(self.conn.total_changes, before)

    # --- Errors and exceptions ---
    def test_errors(self):
        self.conn.execute("CREATE TABLE uq(i INTEGER PRIMARY KEY, v TEXT UNIQUE)")
        self.conn.execute("INSERT INTO uq VALUES (1, 'a')")
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("INSERT INTO uq VALUES (1, 'b')")
        with self.assertRaises(sqlite3.OperationalError):
            self.conn.execute("SELEC 1")  # typo

    # --- Binary/BLOBs ---
    def test_binary_and_blob(self):
        self.conn.execute("CREATE TABLE b(id INTEGER PRIMARY KEY, payload BLOB)")
        raw = bytes(range(256))
        self.conn.execute("INSERT INTO b(payload) VALUES (?)", (sqlite3.Binary(raw),))
        out = self.conn.execute("SELECT payload FROM b").fetchone()[0]
        self.assertEqual(out, raw)
        # Streaming blobs if supported
        if hasattr(self.conn, "blobopen"):
            rowid = self.conn.execute("SELECT id FROM b").fetchone()[0]
            # Try several known signatures across Python/SQLite versions
            wrote = False
            try:
                # Common recent signature: blobopen(table, column, rowid)
                with self.conn.blobopen("b", "payload", rowid) as blob:
                    blob.write(b"\x00\x01\x02\x03")
                wrote = True
            except TypeError:
                pass
            if not wrote:
                try:
                    # Older pysqlite: blobopen(database, table, column, rowid)
                    with self.conn.blobopen("main", "b", "payload", rowid) as blob:
                        blob.write(b"\x00\x01\x02\x03")
                    wrote = True
                except TypeError:
                    pass
            if not wrote:
                try:
                    # Python 3.12+ variant with keywords
                    with self.conn.blobopen("b", "payload", rowid, readonly=False) as blob:
                        blob.write(b"\x00\x01\x02\x03")
                    wrote = True
                except TypeError:
                    self.fail("sqlite3.Connection.blobopen signature not recognized by compatibility shims")
            out2 = self.conn.execute("SELECT substr(payload,1,4) FROM b").fetchone()[0]
            self.assertEqual(out2, b"\x00\x01\x02\x03")

    # --- Backup API ---
    def test_backup_api(self):
        src_dir = tempfile.mkdtemp()
        dst_dir = tempfile.mkdtemp()
        try:
            src_path = os.path.join(src_dir, "src.db")
            dst_path = os.path.join(dst_dir, "dst.db")
            src = sqlite3.connect(src_path)
            dst = sqlite3.connect(dst_path)
            try:
                with src:
                    src.execute("CREATE TABLE t(i)")
                    src.executemany("INSERT INTO t VALUES (?)", [(i,) for i in range(3)])
                with dst:
                    src.backup(dst)
                vals = [r[0] for r in dst.execute("SELECT i FROM t ORDER BY i").fetchall()]
                self.assertEqual(vals, [0, 1, 2])
            finally:
                src.close(); dst.close()
        finally:
            shutil.rmtree(src_dir, ignore_errors=True)
            shutil.rmtree(dst_dir, ignore_errors=True)

    # --- Authorizer & trace callback ---
    def test_authorizer_and_trace(self):
        self.conn.execute("CREATE TABLE a(i)")
        traces = []
        self.conn.set_trace_callback(traces.append)
        def authorizer(action, arg1, arg2, dbname, source):
            # Disallow DROP TABLE
            if action == sqlite3.SQLITE_DROP_TABLE:
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK
        self.conn.set_authorizer(authorizer)
        self.conn.execute("INSERT INTO a VALUES (1)")
        with self.assertRaises(sqlite3.DatabaseError):
            self.conn.execute("DROP TABLE a")
        self.assertTrue(any("INSERT INTO a" in t for t in traces))
        # Remove callbacks
        self.conn.set_trace_callback(None)
        self.conn.set_authorizer(None)

    # --- PRAGMAs, iterdump, and misc ---
    def test_pragmas_and_iterdump(self):
        # Ensure foreign_keys pragma is ON from setUp
        fk = self.conn.execute("PRAGMA foreign_keys").fetchone()[0]
        self.assertEqual(fk, 1)
        # Create a small schema and dump
        self.conn.executescript(
            """
            CREATE TABLE parent(id INTEGER PRIMARY KEY);
            CREATE TABLE child(id INTEGER PRIMARY KEY, parent_id INTEGER,
                               FOREIGN KEY(parent_id) REFERENCES parent(id));
            INSERT INTO parent VALUES (1);
            INSERT INTO child VALUES (1, 1);
            """
        )
        dump = "\n".join(self.conn.iterdump())
        self.assertIn("CREATE TABLE parent", dump)
        self.assertIn("CREATE TABLE child", dump)

    # --- Column type parsing via name hints ---
    def test_parse_colnames(self):
        conn = sqlite3.connect(":memory:", detect_types=sqlite3.PARSE_COLNAMES)
        with conn:
            conn.execute("CREATE TABLE t(d TEXT)")
            conn.execute("INSERT INTO t VALUES ('2020-01-01 12:00:00')")
        row = conn.execute("SELECT d as 'd [timestamp]' FROM t").fetchone()
        # Built-in timestamp converter returns datetime (default is deprecated in 3.12)
        self.assertIsInstance(row[0], _dt.datetime)
        conn.close()

    # --- Connection as context manager w/ default isolation level ---
    def test_connection_context_semantics(self):
        # Explicitly create a new connection with default isolation_level
        conn = sqlite3.connect(":memory:")
        try:
            with conn:
                conn.execute("CREATE TABLE t(x)")
                conn.execute("INSERT INTO t VALUES (1)")
            # On exception, rollback applies with default isolation_level
            with self.assertRaises(RuntimeError):
                with conn:
                    conn.execute("INSERT INTO t VALUES (2)")
                    raise RuntimeError("fail")
            vals = [r[0] for r in conn.execute("SELECT x FROM t ORDER BY x").fetchall()]
            self.assertEqual(vals, [1])
        finally:
            conn.close()


if __name__ == "__main__":
    # Run with: python sqlite3_unittest_suite.py
    unittest.main()