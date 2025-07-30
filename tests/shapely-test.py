import unittest
from shapely import Point, LineString, LinearRing, Polygon, MultiPoint, MultiLineString, MultiPolygon, box
from shapely.ops import unary_union
from shapely.geometry import GeometryCollection


class TestShapelyBasics(unittest.TestCase):

    def test_point(self):
        p = Point(1, 2)
        self.assertEqual(p.x, 1)
        self.assertEqual(p.y, 2)
        self.assertTrue(p.is_valid)
        self.assertEqual(p.geom_type, 'Point')
        self.assertEqual(p.area, 0.0)

    def test_linestring(self):
        line = LineString([(0, 0), (1, 1)])
        self.assertAlmostEqual(line.length, 1.41421, places=4)
        self.assertTrue(line.is_simple)
        self.assertEqual(line.geom_type, 'LineString')
        self.assertEqual(len(line.coords), 2)

    def test_linearring(self):
        ring = LinearRing([(0, 0), (1, 1), (1, 0)])
        self.assertTrue(ring.is_ring)
        self.assertEqual(len(ring.coords), 4)
        self.assertEqual(ring.length, 3.414213562373095)

    def test_polygon(self):
        poly = Polygon([(0, 0), (1, 0), (1, 1), (0, 0)])
        self.assertTrue(poly.is_valid)
        self.assertAlmostEqual(poly.area, 0.5)
        self.assertEqual(poly.geom_type, 'Polygon')
        self.assertEqual(len(poly.exterior.coords), 4)

    def test_box(self):
        b = box(0, 0, 1, 1)
        self.assertEqual(b.bounds, (0.0, 0.0, 1.0, 1.0))
        self.assertAlmostEqual(b.area, 1.0)

    def test_collections(self):
        mp = MultiPoint([(0, 0), (1, 1)])
        self.assertEqual(len(mp.geoms), 2)
        self.assertEqual(mp.geom_type, 'MultiPoint')

        ml = MultiLineString([[(0, 0), (1, 1)], [(1, 0), (0, 1)]])
        self.assertEqual(len(ml.geoms), 2)
        self.assertAlmostEqual(ml.length, 2 * (2 ** 0.5))

        poly1 = Polygon([(0, 0), (1, 0), (0.5, 1), (0, 0)])
        poly2 = Polygon([(2, 0), (3, 0), (2.5, 1), (2, 0)])
        mp = MultiPolygon([poly1, poly2])
        self.assertEqual(len(mp.geoms), 2)
        self.assertTrue(mp.is_valid)

    def test_set_operations(self):
        a = Point(0, 0).buffer(1.0)
        b = Point(1, 0).buffer(1.0)

        inter = a.intersection(b)
        union = a.union(b)
        diff = a.difference(b)
        sym_diff = a.symmetric_difference(b)

        self.assertTrue(inter.area < a.area)
        self.assertTrue(union.area > a.area)
        self.assertTrue(diff.is_valid)
        self.assertTrue(sym_diff.is_valid)

    def test_geometry_collection(self):
        p = Point(0, 0)
        l = LineString([(1, 1), (2, 2)])
        gc = GeometryCollection([p, l])
        self.assertEqual(len(gc.geoms), 2)
        self.assertTrue(any(g.geom_type == 'Point' for g in gc.geoms))

    def test_predicates(self):
        a = Polygon([(0, 0), (0, 2), (2, 2), (2, 0), (0, 0)])
        b = Point(1, 1)
        c = Point(3, 3)

        self.assertTrue(b.within(a))
        self.assertFalse(c.within(a))
        self.assertTrue(a.contains(b))
        self.assertFalse(a.contains(c))
        self.assertTrue(a.intersects(b))

    def test_unary_union(self):
        polys = [Point(i, 0).buffer(0.6) for i in range(3)]
        merged = unary_union(polys)
        self.assertTrue(merged.is_valid)
        self.assertGreater(merged.area, 1.0)

if __name__ == '__main__':
    unittest.main()
