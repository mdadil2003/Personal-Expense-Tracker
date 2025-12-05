import unittest
from datetime import datetime
from trail import ExpenseTracker

class TestExpenseTracker(unittest.TestCase):

    def setUp(self):
        self.tracker = ExpenseTracker(db_name=":memory:")

    def tearDown(self):
        
        self.tracker.close()

    def test_add_transaction(self):
        """Test if transactions are inserted correctly"""
        trans_id = self.tracker.add_transaction(
            date="2025-01-10",
            category="Food",
            amount=150.0,
            description="Lunch"
        )
        self.assertIsNotNone(trans_id)

        rows = self.tracker.get_all_transactions()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][2], "Food")
        self.assertEqual(rows[0][3], 150.0)

    def test_get_transactions_by_month(self):
        """Test month filtering"""
        # Insert sample transactions
        self.tracker.add_transaction("2025-02-05", "Food", 100, "")
        self.tracker.add_transaction("2025-02-14", "Transport", 200, "")
        self.tracker.add_transaction("2025-03-01", "Food", 300, "")

        feb_trans = self.tracker.get_transactions_by_month(2025, 2)
        self.assertEqual(len(feb_trans), 2)

        mar_trans = self.tracker.get_transactions_by_month(2025, 3)
        self.assertEqual(len(mar_trans), 1)

    def test_category_summary(self):
        """Test category-wise summary"""
        self.tracker.add_transaction("2025-01-01", "Food", 50, "")
        self.tracker.add_transaction("2025-01-01", "Food", 50, "")
        self.tracker.add_transaction("2025-01-01", "Transport", 100, "")

        summary = self.tracker.get_category_summary(2025, 1)

        summary_dict = {row[0]: row[1] for row in summary}

        self.assertEqual(summary_dict["Food"], 100)
        self.assertEqual(summary_dict["Transport"], 100)

    def test_delete_transaction(self):
        """Test deleting a transaction"""
        trans_id = self.tracker.add_transaction("2025-01-01", "Bills", 500, "")

        success = self.tracker.delete_transaction(trans_id)
        self.assertTrue(success)

        rows = self.tracker.get_all_transactions()
        self.assertEqual(len(rows), 0)


if __name__ == "__main__":
    unittest.main()
