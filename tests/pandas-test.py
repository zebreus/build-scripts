import unittest
import pandas as pd
import numpy as np

class TestPandasBasics(unittest.TestCase):

    def setUp(self):
        self.df = pd.DataFrame({
            'A': [1, 2, 3],
            'B': [4, 5, 6],
            'C': ['x', 'y', 'z']
        })
        self.series = pd.Series([10, 20, 30], name='numbers')

    def test_dataframe_creation(self):
        self.assertEqual(self.df.shape, (3, 3))
        self.assertListEqual(list(self.df.columns), ['A', 'B', 'C'])

    def test_series_creation(self):
        self.assertEqual(len(self.series), 3)
        self.assertEqual(self.series.name, 'numbers')

    def test_column_selection(self):
        self.assertTrue((self.df['A'] == pd.Series([1, 2, 3])).all())

    def test_row_selection(self):
        row = self.df.iloc[1]
        self.assertEqual(row['A'], 2)
        self.assertEqual(row['C'], 'y')

    def test_filtering(self):
        filtered = self.df[self.df['A'] > 1]
        self.assertEqual(len(filtered), 2)

    def test_assignment(self):
        self.df['D'] = self.df['A'] + self.df['B']
        self.assertIn('D', self.df.columns)
        self.assertTrue((self.df['D'] == pd.Series([5, 7, 9])).all())

    def test_aggregation(self):
        self.assertEqual(self.df['A'].mean(), 2.0)
        self.assertEqual(self.df['B'].sum(), 15)

    def test_groupby(self):
        df = pd.DataFrame({
            'group': ['A', 'A', 'B'],
            'value': [10, 20, 30]
        })
        grouped = df.groupby('group')['value'].mean()
        self.assertEqual(grouped['A'], 15)
        self.assertEqual(grouped['B'], 30)

    def test_missing_data(self):
        df = self.df.copy()
        df.loc[1, 'A'] = np.nan
        self.assertTrue(pd.isna(df['A'][1]))
        df_filled = df.fillna(0)
        self.assertEqual(df_filled['A'][1], 0)

if __name__ == '__main__':
    unittest.main()