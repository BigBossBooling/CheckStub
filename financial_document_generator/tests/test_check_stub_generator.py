import unittest
import os
from financial_document_generator.app.check_stub_generator import generate_check_stub

class TestCheckStubGenerator(unittest.TestCase):

    def setUp(self):
        """Set up sample data and test output paths."""
        self.sample_stub_data = {
            'company_name': 'Test Corp Inc.',
            'company_address': '101 Test Parkway, Testville, TS 10101',
            'employee_name': 'SMITH, JANE M.',
            'employee_id': 'TEST001',
            'pay_period_start': '12/01/2023',
            'pay_period_end': '12/15/2023',
            'pay_date': '12/20/2023',
            'check_number': 'TEST9001',
            'earnings': [
                {'description': 'Regular Hours', 'hours': '80', 'rate': '25.00', 'current': '2000.00', 'ytd': '48000.00'},
                {'description': 'Holiday Pay', 'hours': '8', 'rate': '25.00', 'current': '200.00', 'ytd': '400.00'}
            ],
            'total_earnings_current': '2200.00',
            'total_earnings_ytd': '48400.00',
            'deductions': [
                {'description': 'Federal Tax', 'current': '180.00', 'ytd': '4320.00'},
                {'description': 'State Tax', 'current': '70.00', 'ytd': '1680.00'},
                {'description': 'Medical Insurance', 'current': '120.00', 'ytd': '2880.00'}
            ],
            'total_deductions_current': '370.00',
            'total_deductions_ytd': '8880.00',
            'net_pay_current': '1830.00',
            'ytd_net_pay': '39520.00',
            'employer_notes': 'Thank you for your hard work!'
        }
        self.test_output_dir = os.path.join(os.path.dirname(__file__), 'test_outputs')
        if not os.path.exists(self.test_output_dir):
            os.makedirs(self.test_output_dir)

        self.test_pdf_path = os.path.join(self.test_output_dir, 'test_generated_check_stub.pdf')

    def tearDown(self):
        """Clean up generated files after tests."""
        if os.path.exists(self.test_pdf_path):
            os.remove(self.test_pdf_path)
        if os.path.exists(self.test_output_dir) and not os.listdir(self.test_output_dir):
            os.rmdir(self.test_output_dir)

    def test_generate_check_stub_returns_bytes(self):
        """Test that generate_check_stub returns PDF bytes."""
        pdf_bytes = generate_check_stub(self.sample_stub_data)
        self.assertIsNotNone(pdf_bytes, "generate_check_stub should return PDF bytes.")
        self.assertIsInstance(pdf_bytes, bytes, "Returned object should be bytes.")
        self.assertTrue(len(pdf_bytes) > 100, "PDF bytes should not be empty.")
        self.assertTrue(pdf_bytes.startswith(b'%PDF-'), "Output does not appear to be a PDF.")

    def test_generate_check_stub_saves_to_file(self):
        """Test that generate_check_stub saves a PDF file."""
        if os.path.exists(self.test_pdf_path):
            os.remove(self.test_pdf_path)

        result = generate_check_stub(self.sample_stub_data, output_path=self.test_pdf_path)
        self.assertTrue(result, "generate_check_stub should return True on successful save.")
        self.assertTrue(os.path.exists(self.test_pdf_path), "PDF file should be created.")
        self.assertTrue(os.path.getsize(self.test_pdf_path) > 100, "Generated PDF file should not be empty.")
        with open(self.test_pdf_path, 'rb') as f:
            self.assertTrue(f.read(5).startswith(b'%PDF-'), "Saved file content does not appear to be a PDF.")

    def test_generate_check_stub_minimal_data(self):
        """Test with minimal data, relying on template defaults."""
        minimal_data = {
            'employee_name': 'MINIMAL, EMP',
            'pay_date': '12/21/2023',
            # Most fields will use defaults from the template
        }
        pdf_bytes = generate_check_stub(minimal_data)
        self.assertIsNotNone(pdf_bytes)
        self.assertTrue(pdf_bytes.startswith(b'%PDF-'), "PDF with minimal data should still be valid.")

    def test_generate_check_stub_empty_lists(self):
        """Test with empty lists for earnings and deductions."""
        data_empty_lists = self.sample_stub_data.copy()
        data_empty_lists['earnings'] = []
        data_empty_lists['deductions'] = []
        data_empty_lists['total_earnings_current'] = '0.00'
        data_empty_lists['total_deductions_current'] = '0.00'
        data_empty_lists['net_pay_current'] = '0.00'
        # YTD values would typically be non-zero, but for this test, let's assume consistency
        data_empty_lists['total_earnings_ytd'] = '40000.00' # example
        data_empty_lists['total_deductions_ytd'] = '8000.00' # example
        data_empty_lists['ytd_net_pay'] = '32000.00' # example


        pdf_bytes = generate_check_stub(data_empty_lists)
        self.assertIsNotNone(pdf_bytes)
        self.assertTrue(pdf_bytes.startswith(b'%PDF-'), "PDF with empty earnings/deductions lists should be valid.")

if __name__ == '__main__':
    unittest.main()
