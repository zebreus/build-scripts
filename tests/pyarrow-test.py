import io
import os
import math
import json
import tempfile
import unittest
from datetime import datetime, timezone

import pyarrow as pa
import pyarrow.compute as pc

# Optional modules (skip tests if unavailable)
try:
    import pyarrow.parquet as pq
except Exception:  # pragma: no cover
    pq = None

try:
    import pyarrow.feather as feather
except Exception:  # pragma: no cover
    feather = None

try:
    import pyarrow.csv as csv
except Exception:  # pragma: no cover
    csv = None

try:
    import pyarrow.json as pajson
except Exception:  # pragma: no cover
    pajson = None

try:
    import pyarrow.dataset as ds
except Exception:  # pragma: no cover
    ds = None


class TestPyArrowCore(unittest.TestCase):
    def setUp(self):
        # Primitive arrays
        self.days = pa.array([1, 12, 17, 23, 28], type=pa.int8())
        self.months = pa.array([1, 3, 5, 7, 1], type=pa.int8())
        self.years = pa.array([1990, 2000, 1995, 2000, 1995], type=pa.int16())

        # Table
        self.birthdays = pa.table([self.days, self.months, self.years],
                                  names=["days", "months", "years"])

        # RecordBatch for tensor tests
        self.batch = pa.RecordBatch.from_arrays(
            [pa.array([1, 2, 3, 4], type=pa.int64()),
             pa.array(['foo', 'bar', 'baz', None], type=pa.string()),
             pa.array([True, None, False, True], type=pa.bool_())],
            names=['f0', 'f1', 'f2']
        )

        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

    # ---------- Data types & fields ----------
    def test_data_types_and_fields(self):
        t1 = pa.int32()
        t2 = pa.string()
        t3 = pa.binary()
        t4 = pa.binary(10)
        t5 = pa.timestamp('ms', tz=None)

        self.assertEqual(str(t1), "int32")
        self.assertEqual(str(t4), "fixed_size_binary[10]")
        self.assertEqual(str(t5), "timestamp[ms]")

        f = pa.field("int32_field", t1)
        self.assertEqual(f.name, "int32_field")
        self.assertEqual(f.type, t1)
        self.assertTrue(isinstance(f, pa.Field))

        # Nested
        t_list = pa.list_(t1)
        self.assertIn("list<item: int32>", str(t_list))

        fields = [
            pa.field('s0', t1),
            pa.field('s1', t2),
            pa.field('s2', t4),
            pa.field('s3', t_list),
        ]
        t_struct = pa.struct(fields)
        t_struct_2 = pa.struct([('s0', t1), ('s1', t2), ('s2', t4), ('s3', t_list)])
        self.assertEqual(t_struct, t_struct_2)

    def test_schema_and_mutation(self):
        t1, t2, t4, t_list = pa.int32(), pa.string(), pa.binary(10), pa.list_(pa.int32())
        schema = pa.schema([('field0', t1), ('field1', t2), ('field2', t4), ('field3', t_list)])
        self.assertIsInstance(schema, pa.Schema)
        self.assertEqual(schema.field(0).type, t1)

        updated_field = pa.field('field0_new', pa.int64())
        schema2 = schema.set(0, updated_field)
        self.assertEqual(schema2.field(0).name, 'field0_new')
        self.assertEqual(schema2.field(0).type, pa.int64())

    # ---------- Arrays & scalars ----------
    def test_arrays_scalars_slicing_nulls(self):
        arr = pa.array([1, 2, None, 3])
        self.assertEqual(arr.type, pa.int64())
        self.assertEqual(len(arr), 4)
        self.assertEqual(arr.null_count, 1)
        self.assertEqual(arr[0].as_py(), 1)
        self.assertTrue(arr[2].is_valid is False)

        sl = arr[1:3]
        self.assertEqual(sl.to_pylist(), [2, None])

        # from_pandas semantics for NaN -> null
        import numpy as np
        with self.assertRaises(ValueError):
            pa.array([1, np.nan], type=pa.int64())
        arr_fp = pa.array([1.0, np.nan])
        self.assertTrue(math.isnan(arr_fp[1].as_py()))

    def test_list_and_list_view_arrays(self):
        nested = pa.array([[], None, [1, 2], [None, 1]])
        self.assertTrue(pa.types.is_list(nested.type))
        # ListView is optional across versions; guard
        if hasattr(pa, "list_view"):
            lv = pa.array([[], None, [1, 2], [None, 1]], type=pa.list_view(pa.int64()))
            self.assertIn("list_view<item: int64>", str(lv.type))

            values = [1, 2, 3, 4, 5, 6]
            offsets = [4, 2, 0]
            sizes = [2, 2, 2]
            arr_lv = pa.ListViewArray.from_arrays(offsets, sizes, values)
            self.assertEqual(arr_lv.to_pylist(), [[5, 6], [3, 4], [1, 2]])

    def test_struct_map_union_dictionary_arrays(self):
        # Struct
        ty = pa.struct([('x', pa.int8()), ('y', pa.bool_())])
        s1 = pa.array([{'x': 1, 'y': True}, {'x': 2, 'y': False}], type=ty)
        self.assertEqual(s1.type, ty)
        self.assertEqual(s1.field('x').to_pylist(), [1, 2])

        # Map (explicit type required)
        ty_map = pa.map_(pa.string(), pa.int64())
        data = [[('x', 1), ('y', 0)], [('a', 2), ('b', 45)]]
        m = pa.array(data, type=ty_map)
        self.assertEqual(len(m), 2)
        self.assertTrue(pa.types.is_map(m.type))

        # MapArray from arrays
        m2 = pa.MapArray.from_arrays([0, 2, 3], ['x', 'y', 'z'], [4, 5, 6])
        self.assertEqual(m2.keys.to_pylist(), ["x", "y", "z"])
        self.assertEqual(m2.items.to_pylist(), [4, 5, 6])

        # Union (sparse)
        xs = pa.array([5, 6, 7])
        ys = pa.array([False, False, True])
        types = pa.array([0, 1, 1], type=pa.int8())
        u_sparse = pa.UnionArray.from_sparse(types, [xs, ys])
        self.assertTrue(pa.types.is_union(u_sparse.type))

        # Union (dense)
        xs2 = pa.array([5, 6, 7])
        ys2 = pa.array([False, True])
        types2 = pa.array([0, 1, 1, 0, 0], type=pa.int8())
        offsets = pa.array([0, 0, 1, 1, 2], type=pa.int32())
        u_dense = pa.UnionArray.from_dense(types2, offsets, [xs2, ys2])
        self.assertTrue(pa.types.is_union(u_dense.type))

        # Dictionary
        indices = pa.array([0, 1, 0, 1, 2, 0, None, 2])
        dictionary = pa.array(['foo', 'bar', 'baz'])
        d = pa.DictionaryArray.from_arrays(indices, dictionary)
        self.assertTrue(pa.types.is_dictionary(d.type))
        self.assertEqual(d.dictionary.to_pylist(), ['foo', 'bar', 'baz'])
        self.assertEqual(d.indices.null_count, 1)

    # ---------- RecordBatch, Table, ChunkedArray ----------
    def test_record_batch_and_table(self):
        batch = self.batch
        self.assertEqual(batch.num_rows, 4)
        self.assertEqual(batch.num_columns, 3)
        self.assertEqual(batch[1].to_pylist(), ['foo', 'bar', 'baz', None])

        # Slice
        b2 = batch.slice(1, 3)
        self.assertEqual(b2[1].to_pylist(), ['bar', 'baz', None])

        # Table from batches
        tbl = pa.Table.from_batches([batch] * 5)
        self.assertEqual(tbl.num_rows, 20)
        c0 = tbl[0]
        self.assertIsInstance(c0, pa.ChunkedArray)
        self.assertEqual(c0.num_chunks, 5)
        self.assertEqual(c0.chunk(0).to_pylist(), [1, 2, 3, 4])

        # Concat tables
        tbl2 = pa.concat_tables([tbl, tbl])
        self.assertEqual(tbl2.num_rows, 40)
        self.assertEqual(tbl2[0].num_chunks, 10)

    # ---------- Compute ----------
    def test_compute_functions(self):
        # value_counts over column
        vc = pc.value_counts(self.birthdays["years"])
        # Expect 1990:1, 1995:2, 2000:2 (unordered; sort for stability)
        values = vc.field(0).to_pylist()
        counts = vc.field(1).to_pylist()
        counts_by_val = dict(zip(values, counts))
        self.assertEqual(counts_by_val[1990], 1)
        self.assertEqual(counts_by_val[1995], 2)
        self.assertEqual(counts_by_val[2000], 2)

        # arithmetic
        current_year = datetime.now(timezone.utc).year
        ages = pc.subtract(current_year, self.birthdays["years"])
        self.assertEqual(len(ages), len(self.birthdays))

        # filter + take
        mask = pc.equal(self.birthdays["months"], pa.scalar(1, type=pa.int8()))
        jan_rows = pc.filter(self.birthdays, mask)
        self.assertEqual(jan_rows.num_rows, 2)

    # ---------- Metadata ----------
    def test_schema_and_field_metadata(self):
        tbl = pa.Table.from_batches([self.batch])
        self.assertIsNone(tbl.schema.metadata)

        tbl = tbl.replace_schema_metadata({"f0": "First dose"})
        self.assertEqual(tbl.schema.metadata, {b"f0": b"First dose"})

        field_f1 = tbl.schema.field("f1")
        self.assertIsNone(field_f1.metadata)

        field_f1_meta = field_f1.with_metadata({"f1": "Second dose"})
        self.assertEqual(field_f1_meta.metadata, {b"f1": b"Second dose"})

        # Apply field metadata via cast
        new_schema = pa.schema([
            pa.field('f0', pa.int64(), metadata={"name": "First dose"}),
            pa.field('f1', pa.string(), metadata={"name": "Second dose"}),
            pa.field('f2', pa.bool_())
        ], metadata={"f2": "booster"})
        t2 = tbl.cast(new_schema)
        self.assertEqual(t2.schema.field('f0').metadata, {b"name": b"First dose"})
        self.assertEqual(t2.schema.field('f1').metadata, {b"name": b"Second dose"})
        self.assertEqual(t2.schema.metadata, {b"f2": b"booster"})

    # ---------- RecordBatchReader ----------
    def test_record_batch_reader(self):
        schema = pa.schema([('x', pa.int64())])

        def gen():
            for _ in range(2):
                yield pa.RecordBatch.from_arrays([pa.array([1, 2, 3])], schema=schema)

        reader = pa.RecordBatchReader.from_batches(schema, gen())
        self.assertEqual(reader.schema, schema)
        # iterate ensures batches yield
        batches = list(reader)
        self.assertEqual(len(batches), 2)
        self.assertEqual(batches[0].column(0).to_pylist(), [1, 2, 3])

    # ---------- Tensor conversion ----------
    def test_record_batch_to_tensor(self):
        batch = pa.RecordBatch.from_arrays(
            [pa.array([1, 2, 3, 4, 5], type=pa.uint16()),
             pa.array([10, 20, 30, 40, 50], type=pa.int16())],
            names=['a', 'b']
        )
        tensor = batch.to_tensor()
        arr = tensor.to_numpy()
        self.assertEqual(arr.shape, (5, 2))
        self.assertEqual(arr.tolist(), [[1, 10], [2, 20], [3, 30], [4, 40], [5, 50]])

        # null_to_nan
        batch2 = pa.record_batch(
            [
                pa.array([1, 2, 3, 4, None], type=pa.int32()),
                pa.array([10, 20, 30, 40, None], type=pa.float32()),
            ], names=["a", "b"]
        )
        arr2 = batch2.to_tensor(null_to_nan=True).to_numpy()
        self.assertTrue(math.isnan(arr2[-1, 0]) or arr2[-1, 0] == 0.0)  # impl detail: int -> float with NaN
        self.assertTrue(math.isnan(arr2[-1, 1]))

    # ---------- IPC / Feather / Parquet / CSV / JSON ----------
    def test_ipc_stream_roundtrip(self):
        sink = io.BytesIO()
        with pa.ipc.new_stream(sink, self.batch.schema) as writer:
            writer.write_batch(self.batch)
        buf = sink.getvalue()
        with pa.ipc.open_stream(buf) as reader:
            out = reader.read_all()
        self.assertIsInstance(out, pa.Table)
        self.assertEqual(out.num_rows, 4)

    @unittest.skipIf(feather is None, "pyarrow.feather not available")
    def test_feather_roundtrip(self):
        path = os.path.join(self.tmpdir.name, "tbl.feather")
        feather.write_feather(self.birthdays, path)
        back = feather.read_table(path)
        self.assertTrue(self.birthdays.equals(back))

    @unittest.skipIf(pq is None, "pyarrow.parquet not available")
    def test_parquet_roundtrip(self):
        path = os.path.join(self.tmpdir.name, "birthdays.parquet")
        pq.write_table(self.birthdays, path)
        tbl = pq.read_table(path)
        self.assertTrue(self.birthdays.equals(tbl))

    @unittest.skipIf(csv is None, "pyarrow.csv not available")
    def test_csv_roundtrip(self):
        path = os.path.join(self.tmpdir.name, "simple.csv")
        # Write CSV via Python (small sample)
        rows = ["a,b,c", "1,foo,True", "2,bar,False", "3,,True"]
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(rows))
        table = csv.read_csv(path)
        self.assertEqual(table.num_rows, 3)
        # Write back out
        out_path = os.path.join(self.tmpdir.name, "out.csv")
        csv.write_csv(table, out_path)
        self.assertTrue(os.path.exists(out_path))

    @unittest.skipIf(pajson is None, "pyarrow.json not available")
    def test_json_lines_roundtrip(self):
        path = os.path.join(self.tmpdir.name, "data.jsonl")
        data = [{"x": 1, "y": "a"}, {"x": 2, "y": None}, {"x": 3, "y": "c"}]
        with open(path, "w", encoding="utf-8") as f:
            for row in data:
                f.write(json.dumps(row) + "\n")
        tbl = pajson.read_json(path)
        self.assertEqual(tbl.num_rows, 3)
        # Convert back to json lines via to_pylist for sanity
        pylist = tbl.to_pylist()
        self.assertEqual(len(pylist), 3)
        self.assertIn("x", pylist[0])

    # ---------- Dataset API ----------
    @unittest.skipIf(ds is None or pq is None, "pyarrow.dataset/parquet not available")
    def test_dataset_partitioned_roundtrip(self):
        # Partition by years
        out_dir = os.path.join(self.tmpdir.name, "savedir")
        ds.write_dataset(
            self.birthdays, out_dir, format="parquet",
            partitioning=ds.partitioning(pa.schema([self.birthdays.schema.field("years")]))
        )
        dataset = ds.dataset(out_dir, format="parquet", partitioning=["years"])
        files = sorted(dataset.files)
        # Expect a file per distinct year
        self.assertGreaterEqual(len(files), 3)

        # Lazy scan -> to_batches
        batches = list(dataset.to_batches())
        self.assertGreaterEqual(len(batches), 1)
        # quick compute check on a chunk
        current_year = datetime.now(timezone.utc).year
        for b in batches:
            ages = pc.subtract(current_year, b["years"])
            self.assertEqual(len(ages), b.num_rows)


if __name__ == "__main__":
    unittest.main()