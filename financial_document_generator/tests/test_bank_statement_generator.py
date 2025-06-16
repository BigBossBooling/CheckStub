import unittest
import os
import shutil
from financial_document_generator.app.bank_statement_generator import generate_bank_statement

class TestBankStatementGenerator(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up sample data and paths for all tests in this class."""
        cls.test_dir = os.path.dirname(__file__)
        cls.test_output_dir = os.path.join(cls.test_dir, 'test_outputs')
        cls.bank_statement_output_dir = os.path.join(cls.test_output_dir, 'generated_bank_statements')

        os.makedirs(cls.bank_statement_output_dir, exist_ok=True)

        cls.sample_statement_data = {
            'bank_name': 'Test Global Finance',
            'bank_address': '100 Test Plaza, Test City, TS 10000',
            'account_holder_name': 'Jane Tester Doe',
            'account_holder_address': '456 Test Ave, Testville, TS 12345',
            'account_number': 'XXXX-XXXX-XX5678',
            'statement_period_start': 'November 1, 2023',
            'statement_period_end': 'November 30, 2023',
            'statement_date': 'December 5, 2023',
            'opening_balance': '$500.00',
            'closing_balance': '$1,850.75',
            'total_deposits': '$2,000.00',
            'total_withdrawals': '$649.25',
            'transactions': [
                {'date': '11/01', 'description': 'Opening Balance', 'deposit_amount': '', 'withdrawal_amount': '', 'running_balance': '$500.00'},
                {'date': '11/05', 'description': 'Grocery Store Purchase', 'withdrawal_amount': '$75.50', 'deposit_amount': '', 'running_balance': '$424.50'},
                {'date': '11/15', 'description': 'Salary Deposit', 'deposit_amount': '$2,000.00', 'withdrawal_amount': '', 'running_balance': '$2,424.50'},
                {'date': '11/20', 'description': 'Rent Payment - Check #203', 'withdrawal_amount': '$550.00', 'deposit_amount': '', 'running_balance': '$1,874.50'},
                {'date': '11/28', 'description': 'Online Bill Pay - Internet Co.', 'withdrawal_amount': '$23.75', 'deposit_amount': '', 'running_balance': '$1,850.75'},
            ],
            'summary_messages': ["Remember to check your account online for real-time updates."],
            'customer_service_number': '1-888-TEST-BANK',
            'website': 'www.testglobalfinance.example.com'
        }
        cls.test_pdf_path = os.path.join(cls.bank_statement_output_dir, 'test_generated_bank_statement.pdf')

    @classmethod
    def tearDownClass(cls):
        """Clean up files and directories created by the test class."""
        if os.path.exists(cls.bank_statement_output_dir):
            shutil.rmtree(cls.bank_statement_output_dir)
        if os.path.exists(cls.test_output_dir) and not os.listdir(cls.test_output_dir) and \
           cls.test_output_dir == os.path.join(cls.test_dir, 'test_outputs'):
            os.rmdir(cls.test_output_dir)

    def test_generate_bank_statement_returns_bytes(self):
        """Test that generate_bank_statement returns PDF bytes when no output_path."""
        pdf_bytes = generate_bank_statement(self.sample_statement_data)
        self.assertIsNotNone(pdf_bytes, "Should return PDF bytes.")
        self.assertIsInstance(pdf_bytes, bytes, "Returned object should be bytes.")
        self.assertTrue(len(pdf_bytes) > 1000, "PDF bytes should not be trivially small.")
        self.assertTrue(pdf_bytes.startswith(b'%PDF-'), "Output does not look like a PDF file.")

    def test_generate_bank_statement_saves_to_file(self):
        """Test that generate_bank_statement saves a PDF file when output_path is provided."""
        if os.path.exists(self.test_pdf_path):
            os.remove(self.test_pdf_path)

        result = generate_bank_statement(self.sample_statement_data, output_path=self.test_pdf_path)
        self.assertTrue(result, "Should return True on successful save.")
        self.assertTrue(os.path.exists(self.test_pdf_path), "PDF file should be created.")
        self.assertTrue(os.path.getsize(self.test_pdf_path) > 1000, "Generated PDF file should not be trivially small.")
        with open(self.test_pdf_path, 'rb') as f:
            self.assertTrue(f.read(5).startswith(b'%PDF-'), "Saved file content does not appear to be a PDF.")

    def test_generate_bank_statement_minimal_data(self):
        """Test with minimal data, relying on template defaults."""
        minimal_data = {
            'account_holder_name': 'Minimal Tester',
            'account_number': 'XXXX-MINIMAL',
            'opening_balance': '$0.00',
            'closing_balance': '$0.00',
            'transactions': []
        }
        pdf_bytes = generate_bank_statement(minimal_data)
        self.assertIsNotNone(pdf_bytes, "Should generate PDF even with minimal data due to defaults.")
        self.assertTrue(pdf_bytes.startswith(b'%PDF-'), "Minimal data PDF should be valid.")

    def test_generate_bank_statement_no_transactions(self):
        """Test with an empty list for transactions."""
        data_no_transactions = self.sample_statement_data.copy()
        data_no_transactions['transactions'] = []
        data_no_transactions['opening_balance'] = '$100.00'
        data_no_transactions['closing_balance'] = '$100.00'
        data_no_transactions['total_deposits'] = '$0.00'
        data_no_transactions['total_withdrawals'] = '$0.00'

        pdf_bytes = generate_bank_statement(data_no_transactions)
        self.assertIsNotNone(pdf_bytes, "PDF should generate with no transactions.")
        self.assertTrue(pdf_bytes.startswith(b'%PDF-'), "PDF with no transactions should be valid.")

if __name__ == '__main__':
    unittest.main()
