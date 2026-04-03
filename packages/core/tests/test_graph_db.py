import unittest

class TestGraphDB(unittest.TestCase):
    def test_initialization(self):
        # Initialize GraphDB and test the instance
        self.assertIsNotNone(GraphDB())

if __name__ == '__main__':
    unittest.main()