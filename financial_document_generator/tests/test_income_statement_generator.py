import unittest
import os
import shutil
from financial_document_generator.app.income_statement_generator import generate_income_statement

class TestIncomeStatementGenerator(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up sample data and paths for all tests in this class."""
        cls.test_dir = os.path.dirname(__file__)
        cls.test_output_dir = os.path.join(cls.test_dir, 'test_outputs')
        cls.income_statement_output_dir = os.path.join(cls.test_output_dir, 'generated_income_statements')

        os.makedirs(cls.income_statement_output_dir, exist_ok=True)

        cls.sample_data = {
            'company_name': "TestCo Inc.",
            'statement_title': "Income Statement",
            'period_covered': "For the Year Ended December 31, 2023",
            'currency_symbol': "$",
            'revenue_items': [{'description': 'Total Sales', 'amount': '500,000.00'}],
            'total_revenue': '500,000.00',
            'cogs_items': [{'description': 'Cost of Goods Sold', 'amount': '200,000.00'}],
            'total_cogs': '200,000.00',
            'gross_profit': '300,000.00',
            'operating_expense_items': [
                {'description': 'Salaries', 'amount': '80,000.00'},
                {'description': 'Rent', 'amount': '24,000.00'},
                {'description': 'Utilities', 'amount': '6,000.00'}
            ],
            'total_operating_expenses': '110,000.00',
            'operating_income': '190,000.00',
            'other_income_expense_items': [{'description': 'Interest Income', 'amount': '1,000.00'}],
            'total_other_income_expenses': '1,000.00',
            'income_before_tax': '191,000.00',
            'income_tax_expense': '38,200.00',
            'net_income': '152,800.00',
            'notes_to_financial_statements': "This is a sample income statement for testing."
        }
        cls.test_pdf_path = os.path.join(cls.income_statement_output_dir, 'test_generated_income_statement.pdf')

    @classmethod
    def tearDownClass(cls):
        """Clean up files and directories created by the test class."""
        if os.path.exists(cls.income_statement_output_dir):
            shutil.rmtree(cls.income_statement_output_dir)
        if os.path.exists(cls.test_output_dir) and not os.listdir(cls.test_output_dir) and \
           cls.test_output_dir == os.path.join(cls.test_dir, 'test_outputs'):
            os.rmdir(cls.test_output_dir)

    def test_generate_income_statement_returns_bytes(self):
        """Test that generate_income_statement returns PDF bytes."""
        pdf_bytes = generate_income_statement(self.sample_data)
        self.assertIsNotNone(pdf_bytes, "Should return PDF bytes.")
        self.assertIsInstance(pdf_bytes, bytes, "Returned object should be bytes.")
        self.assertTrue(len(pdf_bytes) > 1000, "PDF bytes should not be excessively small.")
        self.assertTrue(pdf_bytes.startswith(b'%PDF-'), "Output does not look like a PDF file.")

    def test_generate_income_statement_saves_to_file(self):
        """Test that generate_income_statement saves a PDF file."""
        if os.path.exists(self.test_pdf_path):
            os.remove(self.test_pdf_path)

        result = generate_income_statement(self.sample_data, output_path=self.test_pdf_path)
        self.assertTrue(result, "Should return True on successful save.")
        self.assertTrue(os.path.exists(self.test_pdf_path), "PDF file should be created.")
        self.assertTrue(os.path.getsize(self.test_pdf_path) > 1000, "Generated PDF file should not be excessively small.")
        with open(self.test_pdf_path, 'rb') as f:
            self.assertTrue(f.read(5).startswith(b'%PDF-'), "Saved file content does not appear to be a PDF.")

    def test_generate_income_statement_minimal_data(self):
        """Test with minimal data, relying on template defaults and structure."""
        minimal_data = {
            'company_name': "Minimal Corp",
            'period_covered': "FY 2023",
            'currency_symbol': "$",
            'total_revenue': '0.00',
            'gross_profit': '0.00',
            'operating_income': '0.00',
            'income_before_tax': '0.00',
            'net_income': '0.00',
            'revenue_items': [],
            'operating_expense_items': []
        }
        pdf_bytes = generate_income_statement(minimal_data)
        self.assertIsNotNone(pdf_bytes, "Should generate PDF even with minimal data.")
        self.assertTrue(pdf_bytes.startswith(b'%PDF-'), "Minimal data Income Statement PDF should be valid.")

if __name__ == '__main__':
    unittest.main()
