# docker run --rm -it --name some-clickhouse -e CLICKHOUSE_DB=mydatabase -e CLICKHOUSE_USER=myuser -e CLICKHOUSE_DEFAULT_ACCESS_MANAGEMENT=1 -e CLICKHOUSE_PASSWORD=mypassword -p 8123:8123 -p 9003:9000/tcp clickhouse/clickhouse-server
#
# Test is working on native, but fails to connect to clickhouse in wasix

import os
import io
import csv
import uuid
import time
import json
import math
import tempfile
import unittest
from datetime import datetime, timedelta

# --- Optional deps (tests will skip gracefully if missing) ---
import pandas as pd  # noqa: F401

HAS_NUMPY = True
import numpy as np  # noqa: F401
HAS_PANDAS = True
try:
    import pyarrow as pa  # noqa: F401
    HAS_ARROW = True
except Exception:
    HAS_ARROW = False

# --- Driver under test ---
import clickhouse_connect
from clickhouse_connect.driver.external import ExternalData
from clickhouse_connect.driver.exceptions import ClickHouseError

# QuerySummary exists in newer versions. We’ll import if available but not rely on it.
try:
    from clickhouse_connect.driver.summary import QuerySummary
except Exception:  # older versions
    QuerySummary = None


def _summary_to_dict(sumobj):
    """Normalize QuerySummary/dict to dict for assertions."""
    if sumobj is None:
        return {}
    if hasattr(sumobj, "to_dict"):
        try:
            return sumobj.to_dict()
        except Exception:
            pass
    if isinstance(sumobj, dict):
        return sumobj
    # Fallback: best-effort attribute scrape
    out = {}
    for name in ("read_rows", "read_bytes", "written_rows", "written_bytes", "query_id", "elapsed"):
        if hasattr(sumobj, name):
            out[name] = getattr(sumobj, name)
    return out


class ClickHouseConnectComprehensiveTest(unittest.TestCase):
    """
    Comprehensive integration test suite for clickhouse-connect.

    Assumes local ClickHouse HTTP at:
      host=localhost, port=8123, user=myuser, password=mypassword, database=mydatabase
    """

    @classmethod
    def setUpClass(cls):
        cls.host = 'localhost'
        cls.port = 8123
        cls.user = 'myuser'
        cls.password = 'mypassword'
        cls.database = 'mydatabase'

        cls.client = clickhouse_connect.get_client(
            host=cls.host,
            port=cls.port,
            username=cls.user,
            password=cls.password,
            database=cls.database,
            client_name='ch_connect_test/1.0',
            connect_timeout=10,
            send_receive_timeout=60,
        )

        cls.sfx = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
        cls._tables = []

        cls.server_version = getattr(cls.client, 'server_version', '0.0.0')
        def parse_ver(v):
            parts = v.split('.')[0:3]
            try:
                return tuple(int(x) for x in parts)
            except Exception:
                return (0, 0, 0)
        cls.server_ver_tuple = parse_ver(cls.server_version)

        tz = cls.client.command('SELECT timezone()')
        assert isinstance(tz, str)

    @classmethod
    def tearDownClass(cls):
        for tbl in cls._tables:
            try:
                cls.client.command(f"DROP TABLE IF EXISTS {tbl}")
            except Exception:
                pass

    @classmethod
    def _register_table(cls, full_table_name):
        cls._tables.append(full_table_name)

    def _mk_table(self, ddl_sql, table_name):
        self.client.command(ddl_sql)
        self.__class__._register_table(table_name)

    # ---------- Tests ----------

    def test_001_command_create_insert_select_basic(self):
        tbl = f"{self.database}.kv_{self.sfx}"
        ddl = f"""
        CREATE TABLE {tbl}
        (
            key UInt32,
            value String,
            metric Float64,
            created DateTime DEFAULT now()
        )
        ENGINE MergeTree
        ORDER BY key
        """
        self._mk_table(ddl, tbl)

        data = [
            [1, 'alpha', 3.14],
            [2, 'beta', -2.5],
        ]
        summary = self.client.insert(tbl, data, column_names=['key', 'value', 'metric'])

        # Accept either QuerySummary or dict
        sd = _summary_to_dict(summary)
        self.assertTrue('written_rows' in sd or hasattr(summary, 'written_rows'))

        qr = self.client.query(f"SELECT key, value, metric FROM {tbl} ORDER BY key")
        self.assertEqual(qr.column_names, ('key', 'value', 'metric'))
        self.assertEqual(qr.first_row, (1, 'alpha', 3.14))
        self.assertEqual(qr.first_item, {'key': 1, 'value': 'alpha', 'metric': 3.14})
        self.assertEqual(qr.result_rows[-1], (2, 'beta', -2.5))

        # Summary may be QuerySummary in newer versions; normalize
        qsd = _summary_to_dict(qr.summary)
        self.assertIsInstance(qsd, dict)

    def test_002_parameter_binding_server_and_client(self):
        res = self.client.query(
            "SELECT {v:UInt32} AS x, {s:String} AS y",
            parameters={'v': 123, 's': "a string with 'quote"}
        ).first_item
        self.assertEqual(res['x'], 123)
        self.assertEqual(res['y'], "a string with 'quote")

        now = datetime(2022, 10, 1, 15, 20, 5)
        res2 = self.client.query(
            "SELECT %(v1)s AS dt, %(v2)s AS s",
            parameters={'v1': now, 'v2': "hello ' world"}
        ).first_item
        self.assertEqual(str(res2['dt']), '2022-10-01 15:20:05')
        self.assertEqual(res2['s'], "hello ' world")

    def test_003_column_oriented_insert_and_select(self):
        tbl = f"{self.database}.kv_col_{self.sfx}"
        ddl = f"""
        CREATE TABLE {tbl}
        (
            key UInt32,
            txt String
        )
        ENGINE MergeTree
        ORDER BY key
        """
        self._mk_table(ddl, tbl)

        data_columns = [
            [10, 20, 30, 40],
            ['a', 'b', 'c', 'd']
        ]
        self.client.insert(tbl, data_columns, column_names=['key', 'txt'], column_oriented=True)
        qr = self.client.query(f"SELECT key, txt FROM {tbl} ORDER BY key")
        self.assertEqual(qr.result_rows, [(10, 'a'), (20, 'b'), (30, 'c'), (40, 'd')])

    @unittest.skipUnless(HAS_PANDAS, "pandas not installed")
    def test_004_insert_df_and_query_df(self):
        import pandas as pd
        tbl = f"{self.database}.kv_df_{self.sfx}"
        ddl = f"""
        CREATE TABLE {tbl}
        (
            id UInt32,
            name String
        )
        ENGINE MergeTree
        ORDER BY id
        """
        self._mk_table(ddl, tbl)

        df = pd.DataFrame({'id': [1, 2, 3], 'name': ['x', 'y', 'z']})
        self.client.insert_df(tbl, df)
        out = self.client.query_df(f"SELECT * FROM {tbl} ORDER BY id")
        self.assertEqual(list(out['name']), ['x', 'y', 'z'])

    @unittest.skipUnless(HAS_ARROW, "pyarrow not installed")
    def test_005_insert_arrow_and_query_arrow(self):
        import pyarrow as pa
        tbl = f"{self.database}.kv_arrow_{self.sfx}"
        ddl = f"""
        CREATE TABLE {tbl}
        (
            id UInt32,
            label String
        )
        ENGINE MergeTree
        ORDER BY id
        """
        self._mk_table(ddl, tbl)

        arr_id = pa.array([11, 12, 13], type=pa.uint32())
        arr_label = pa.array(['L1', 'L2', 'L3'])
        at = pa.Table.from_arrays([arr_id, arr_label], names=['id', 'label'])
        self.client.insert_arrow(tbl, at)
        t = self.client.query_arrow(f"SELECT * FROM {tbl} ORDER BY id")
        self.assertEqual(t.to_pydict()['label'], ['L1', 'L2', 'L3'])

    def test_006_streaming_queries(self):
        with self.client.query_row_block_stream("SELECT number, number+1 AS nxt FROM system.numbers LIMIT 5") as stream:
            blocks = list(stream)
        flat = [row for block in blocks for row in block]
        self.assertEqual(flat, [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)])

        with self.client.query_rows_stream("SELECT number FROM system.numbers LIMIT 3") as stream:
            rows = list(stream)
        self.assertEqual(rows, [(0,), (1,), (2,)])

        with self.client.query_column_block_stream("SELECT number, toString(number) FROM system.numbers LIMIT 3") as cstream:
            cblocks = list(cstream)
        self.assertEqual(len(cblocks[0]), 2)

    @unittest.skipUnless(HAS_NUMPY, "numpy not installed")
    def test_007_np_query_and_stream(self):
        import numpy as np
        arr = self.client.query_np("SELECT number, number*2 FROM system.numbers LIMIT 4")

        # Accept both orientations across driver versions:
        if arr.shape == (2, 4):  # (cols, rows)
            nums = arr[0]
            doubles = arr[1]
        elif arr.shape == (4, 2):  # (rows, cols)
            nums = arr[:, 0]
            doubles = arr[:, 1]
        else:
            self.fail(f"Unexpected NumPy array shape {arr.shape}")

        self.assertTrue(np.array_equal(np.asarray(nums), np.array([0, 1, 2, 3])))
        self.assertTrue(np.array_equal(np.asarray(doubles), np.array([0, 2, 4, 6])))

        # Stream: just ensure we get numpy arrays back
        with self.client.query_np_stream("SELECT number FROM system.numbers LIMIT 5") as nps:
            parts = list(nps)
        self.assertTrue(all(hasattr(p, 'shape') for p in parts))

    @unittest.skipUnless(HAS_PANDAS, "pandas not installed")
    def test_008_df_stream(self):
        with self.client.query_df_stream("SELECT number AS n FROM system.numbers LIMIT 4") as dfs:
            chunks = list(dfs)
        self.assertTrue(len(chunks) >= 1)
        self.assertIn('n', chunks[0].columns)

    @unittest.skipUnless(HAS_ARROW, "pyarrow not installed")
    def test_009_arrow_stream(self):
        with self.client.query_arrow_stream("SELECT number FROM system.numbers LIMIT 3") as ars:
            batches = list(ars)
        self.assertTrue(len(batches) >= 1)

    def test_010_raw_query_and_stream(self):
        # Raw bytes (TSV by default)
        raw = self.client.raw_query("SELECT 'a'\tAS c UNION ALL SELECT 'b' AS c ORDER BY c")
        self.assertIsInstance(raw, (bytes, bytearray))
        self.assertIn(b"a", raw)

        # Raw stream WITH header so we can assert on 'number'
        with self.client.raw_stream("SELECT number FROM system.numbers LIMIT 3", fmt="CSVWithNames") as rstream:
            chunks = list(rstream)
        combined = b"".join(chunks)
        self.assertIn(b'number', combined)  # header present with CSVWithNames
        self.assertIn(b'0', combined)

    def test_011_raw_insert_tsv(self):
        tbl = f"{self.database}.raw_tsv_{self.sfx}"
        ddl = f"""
        CREATE TABLE {tbl}
        (
            id UInt32,
            name String
        )
        ENGINE MergeTree
        ORDER BY id
        """
        self._mk_table(ddl, tbl)

        buf = io.StringIO()
        w = csv.writer(buf, delimiter='\t', lineterminator='\n', quoting=csv.QUOTE_MINIMAL)
        w.writerow(['id', 'name'])
        w.writerow([1, 'A'])
        w.writerow([2, 'B'])
        payload = buf.getvalue().encode('utf-8')

        summary = self.client.raw_insert(tbl, column_names=['id', 'name'], insert_block=payload, fmt='TabSeparatedWithNames')

        # Handle QuerySummary or dict
        sd = _summary_to_dict(summary)
        self.assertTrue(('written_rows' in sd and sd['written_rows'] >= 2) or getattr(summary, 'written_rows', 0) >= 2)

        cnt = self.client.command(f"SELECT count() FROM {tbl}")
        self.assertEqual(cnt, 2)

    def test_012_insert_file_csv(self):
        from clickhouse_connect.driver.tools import insert_file
        tbl = f"{self.database}.kv_file_{self.sfx}"
        ddl = f"""
        CREATE TABLE {tbl}
        (
            id UInt32,
            label String
        )
        ENGINE MergeTree
        ORDER BY id
        """
        self._mk_table(ddl, tbl)

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.csv')
        try:
            with open(tmp.name, 'w', newline='') as f:
                w = csv.writer(f)
                w.writerow(['id', 'label'])
                w.writerow([101, 'one'])
                w.writerow([102, 'two'])
            insert_file(self.client, tbl, tmp.name)
            res = self.client.query(f"SELECT * FROM {tbl} ORDER BY id").result_rows
            self.assertEqual(res, [(101, 'one'), (102, 'two')])
        finally:
            try:
                os.unlink(tmp.name)
            except Exception:
                pass

    def test_013_external_data(self):
        data = "x,s\n1,aa\n2,bb\n3,cc\n"
        ext = ExternalData(
            data=data.encode('utf-8'),
            fmt='CSV',
            structure=['x UInt32', 's String'],
            file_name='exttab'
        )
        total = self.client.query("SELECT sum(x) AS sm FROM exttab", external_data=ext).first_item['sm']
        self.assertEqual(total, 6)

    def test_014_query_and_column_formats(self):
        u = uuid.uuid4()
        item = self.client.query("SELECT {u:UUID} AS u", parameters={'u': str(u)}, query_formats={'UUID': 'string'}).first_item
        self.assertEqual(item['u'], str(u))

        item2 = self.client.query(
            "SELECT toIPv4('68.61.4.254') AS ip",
            column_formats={'ip': 'string'}
        ).first_item
        self.assertEqual(item2['ip'], '68.61.4.254')

    def test_015_query_context_reuse(self):
        tbl = f"{self.database}.ctx_{self.sfx}"
        ddl = f"""
        CREATE TABLE {tbl}
        (
            k UInt32,
            v String
        )
        ENGINE MergeTree
        ORDER BY k
        """
        self._mk_table(ddl, tbl)
        self.client.insert(tbl, [[1, 'one'], [2, 'two'], [3, 'three']], column_names=['k', 'v'])

        qc = self.client.create_query_context(
            query=f"SELECT v FROM {tbl} WHERE k = {{kk:UInt32}}",
            parameters={'kk': 1},
        )
        r1 = self.client.query(context=qc).first_item['v']
        self.assertEqual(r1, 'one')
        qc.set_parameter('kk', 3)
        r3 = self.client.query(context=qc).first_item['v']
        self.assertEqual(r3, 'three')

    def test_016_insert_context_reuse(self):
        tbl = f"{self.database}.ictx_{self.sfx}"
        ddl = f"""
        CREATE TABLE {tbl}
        (
            id UInt32,
            a String,
            b String
        )
        ENGINE MergeTree
        ORDER BY id
        """
        self._mk_table(ddl, tbl)
        data1 = [[1, 'v1', 'v2'], [2, 'v3', 'v4']]
        ic = self.client.create_insert_context(table=tbl, data=data1, column_names=['id', 'a', 'b'])
        self.client.insert(context=ic)
        data2 = [[3, 'v5', 'v6'], [4, 'v7', 'v8']]
        ic.data = data2
        self.client.insert(context=ic)
        cnt = self.client.command(f"SELECT count() FROM {tbl}")
        self.assertEqual(cnt, 4)

    def test_017_settings_and_summary(self):
        qr = self.client.query(
            "SELECT number FROM system.numbers LIMIT 10",
            settings={'wait_end_of_query': 1}
        )
        sdict = _summary_to_dict(qr.summary)
        self.assertTrue(isinstance(sdict, dict))
        self.assertIn('read_rows', json.dumps(sdict))

    def test_018_error_handling(self):
        with self.assertRaises(ClickHouseError):
            self.client.query("SELLECT 1")

    def test_019_use_database_flag(self):
        res1 = self.client.command("SELECT 1")
        self.assertEqual(res1, 1)
        res2 = self.client.command("SELECT 2", use_database=False)
        self.assertEqual(res2, 2)

    def test_020_query_limit_and_retries(self):
        qr = self.client.query("SELECT number FROM system.numbers LIMIT 3")
        self.assertEqual(len(qr.result_rows), 3)

    def test_021_dt64_param_note(self):
        item = self.client.query("SELECT toDateTime64('2025-01-01 00:00:00', 3) AS ts").first_item
        self.assertIn('ts', item)


if __name__ == '__main__':
    unittest.main(verbosity=2)