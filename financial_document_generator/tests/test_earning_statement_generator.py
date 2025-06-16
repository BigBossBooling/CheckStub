import unittest
import os
import shutil
from financial_document_generator.app.earning_statement_generator import generate_earning_statement

class TestEarningStatementGenerator(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up sample data and paths for all tests in this class."""
        cls.test_dir = os.path.dirname(__file__)
        cls.test_output_dir = os.path.join(cls.test_dir, 'test_outputs')
        cls.earning_statement_output_dir = os.path.join(cls.test_output_dir, 'generated_earning_statements')

        os.makedirs(cls.earning_statement_output_dir, exist_ok=True)

        cls.sample_data = {
            'company_name': 'Direct Pay Corp.',
            'company_address': '100 Salary Lane, Payment City, ST 90000',
            'employee_name': 'WAYNE, BRUCE',
            'employee_id': 'EMP007',
            'pay_period_start': '12/01/2023',
            'pay_period_end': '12/15/2023',
            'pay_date': '12/20/2023',
            'check_number': 'DP-55678',
            'earnings': [
                {'description': 'Salary', 'hours': '', 'rate': '', 'current': '3000.00', 'ytd': '72000.00'},
                {'description': 'Performance Bonus', 'current': '500.00', 'ytd': '2000.00'}
            ],
            'total_earnings_current': '3500.00',
            'total_earnings_ytd': '74000.00',
            'deductions': [
                {'description': 'Federal Tax', 'current': '450.00', 'ytd': '10800.00'},
                {'description': 'Health Premium', 'current': '120.00', 'ytd': '1440.00'}
            ],
            'total_deductions_current': '570.00',
            'total_deductions_ytd': '12240.00',
            'net_pay_current': '2930.00',
            'ytd_net_pay': '61760.00',
            'employer_notes': 'This is your Earning Statement.'
        }
        cls.test_pdf_path = os.path.join(cls.earning_statement_output_dir, 'test_generated_earning_statement.pdf')

    @classmethod
    def tearDownClass(cls):
        """Clean up files and directories created by the test class."""
        if os.path.exists(cls.earning_statement_output_dir):
            shutil.rmtree(cls.earning_statement_output_dir)
        if os.path.exists(cls.test_output_dir) and not os.listdir(cls.test_output_dir) and \
           cls.test_output_dir == os.path.join(cls.test_dir, 'test_outputs'):
            os.rmdir(cls.test_output_dir)

    def test_generate_earning_statement_returns_bytes(self):
        """Test that generate_earning_statement returns PDF bytes."""
        pdf_bytes = generate_earning_statement(self.sample_data)
        self.assertIsNotNone(pdf_bytes, "Should return PDF bytes.")
        self.assertIsInstance(pdf_bytes, bytes, "Returned object should be bytes.")
        self.assertTrue(len(pdf_bytes) > 1000, "PDF bytes should not be excessively small.")
        self.assertTrue(pdf_bytes.startswith(b'%PDF-'), "Output does not look like a PDF file.")

    def test_generate_earning_statement_saves_to_file(self):
        """Test that generate_earning_statement saves a PDF file."""
        if os.path.exists(self.test_pdf_path):
            os.remove(self.test_pdf_path)

        result = generate_earning_statement(self.sample_data, output_path=self.test_pdf_path)
        self.assertTrue(result, "Should return True on successful save.")
        self.assertTrue(os.path.exists(self.test_pdf_path), "PDF file should be created.")
        self.assertTrue(os.path.getsize(self.test_pdf_path) > 1000, "Generated PDF file should not be excessively small.")
        with open(self.test_pdf_path, 'rb') as f:
            self.assertTrue(f.read(5).startswith(b'%PDF-'), "Saved file content does not appear to be a PDF.")

    def test_generate_earning_statement_minimal_data(self):
        """Test with minimal data, relying on template defaults."""
        minimal_data = {
            'company_name': "MinCo",
            'employee_name': "Min Emp",
            'pay_date': "01/01/2024",
            'total_earnings_current': '0.00',
            'total_deductions_current': '0.00',
            'net_pay_current': '0.00',
            'earnings': [],
            'deductions': []
        }
        pdf_bytes = generate_earning_statement(minimal_data)
        self.assertIsNotNone(pdf_bytes, "Should generate PDF even with minimal data.")
        self.assertTrue(pdf_bytes.startswith(b'%PDF-'), "Minimal data Earning Statement PDF should be valid.")

if __name__ == '__main__':
    unittest.main()
