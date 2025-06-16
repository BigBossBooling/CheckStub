import unittest
import os
# Adjust import path to correctly locate the module
# from ..app.check_generator import generate_check
# Assuming 'financial_document_generator' is the top-level package and tests are run from there
from financial_document_generator.app.check_generator import generate_check

class TestCheckGenerator(unittest.TestCase):

    def setUp(self):
        """Set up sample data for tests."""
        self.sample_check_data = {
            'bank_name': 'Test Bank United',
            'bank_address': '789 Test Ave, Testville, ST 99999',
            'check_number': '9001',
            'date': 'December 25, 2023',
            'payee_name': 'Test Recipient LLC',
            'amount_numeric': '987.65',
            'amount_words': 'NINE HUNDRED EIGHTY-SEVEN AND 65/100',
            'memo': 'Test Memo - Payment for services',
            'routing_number': '000111222',
            'account_number': '1122334455',
            'payment_category': 'Office Supplies'
        }
        # Define a directory for test outputs within the tests folder
        self.test_output_dir = os.path.join(os.path.dirname(__file__), 'test_outputs')
        if not os.path.exists(self.test_output_dir):
            os.makedirs(self.test_output_dir)

        self.test_pdf_path = os.path.join(self.test_output_dir, 'test_generated_check.pdf')

    def tearDown(self):
        """Clean up generated files after tests."""
        if os.path.exists(self.test_pdf_path):
            os.remove(self.test_pdf_path)
        # Remove the test_outputs directory if it's empty
        if os.path.exists(self.test_output_dir) and not os.listdir(self.test_output_dir):
            os.rmdir(self.test_output_dir)

    def test_generate_check_returns_bytes(self):
        """Test that generate_check returns PDF bytes when no output_path is given."""
        pdf_bytes = generate_check(self.sample_check_data)
        self.assertIsNotNone(pdf_bytes, "generate_check should return PDF bytes.")
        self.assertIsInstance(pdf_bytes, bytes, "Returned object should be of type bytes.")
        self.assertTrue(len(pdf_bytes) > 100, "PDF bytes should not be empty.") # Basic check for some content
        # Check for PDF header (common PDF magic number)
        self.assertTrue(pdf_bytes.startswith(b'%PDF-'), "Output does not look like a PDF file.")


    def test_generate_check_saves_to_file(self):
        """Test that generate_check saves a PDF file when output_path is provided."""
        # Ensure file does not exist before test
        if os.path.exists(self.test_pdf_path):
            os.remove(self.test_pdf_path)

        result = generate_check(self.sample_check_data, output_path=self.test_pdf_path)
        self.assertTrue(result, "generate_check should return True on successful save.")
        self.assertTrue(os.path.exists(self.test_pdf_path), "PDF file should be created at the specified path.")
        self.assertTrue(os.path.getsize(self.test_pdf_path) > 100, "Generated PDF file should not be empty.")

        # Optionally, check the PDF header of the file
        with open(self.test_pdf_path, 'rb') as f:
            file_content = f.read(5) # Read first 5 bytes
        self.assertEqual(file_content, b'%PDF-', "Saved file does not appear to be a valid PDF.")


    def test_generate_check_missing_data(self):
        """Test how generate_check handles incomplete data (optional, depends on implementation)."""
        incomplete_data = self.sample_check_data.copy()
        del incomplete_data['payee_name']

        # Assuming the template has defaults or the function handles missing keys gracefully
        # If it's supposed to raise an error, the test should check for that
        # For now, let's assume it runs due to defaults in template or graceful handling
        pdf_bytes = generate_check(incomplete_data)
        self.assertIsNotNone(pdf_bytes, "generate_check should still run with some missing data if defaults are present.")
        self.assertTrue(pdf_bytes.startswith(b'%PDF-'), "Output with missing data does not look like a PDF file.")

    def test_generate_check_invalid_data_type(self):
        """Test generate_check with invalid data types (e.g., amount as string instead of number if formatting depends on it)."""
        invalid_data = self.sample_check_data.copy()
        invalid_data['amount_numeric'] = "NOT_A_NUMBER" # Example of invalid data

        # Depending on how robust the HTML/Jinja template is, this might still produce a PDF
        # or it might cause an error during rendering if specific filters are used (e.g. |float)
        # For this example, we'll assume it will render, possibly with "NOT_A_NUMBER" in the PDF.
        pdf_bytes = generate_check(invalid_data)
        self.assertIsNotNone(pdf_bytes, "generate_check should handle some invalid data types by rendering them as strings.")
        self.assertTrue(pdf_bytes.startswith(b'%PDF-'), "Output with invalid data does not look like a PDF file.")

    def test_generate_check_with_and_without_payment_category(self):
        """Test check generation with and without the optional payment category."""
        # Test with payment category (already in self.sample_check_data via setUp)
        pdf_bytes_with_category = generate_check(self.sample_check_data)
        self.assertIsNotNone(pdf_bytes_with_category)
        self.assertTrue(pdf_bytes_with_category.startswith(b'%PDF-'))

        # Test without payment category
        data_without_category = self.sample_check_data.copy()
        # Ensure 'payment_category' is present before attempting to delete, to avoid KeyError if setUp changes
        if 'payment_category' in data_without_category:
            del data_without_category['payment_category']
        pdf_bytes_without_category = generate_check(data_without_category)
        self.assertIsNotNone(pdf_bytes_without_category)
        self.assertTrue(pdf_bytes_without_category.startswith(b'%PDF-'))

        # Test with empty payment category
        data_empty_category = self.sample_check_data.copy()
        data_empty_category['payment_category'] = ''
        pdf_bytes_empty_category = generate_check(data_empty_category)
        self.assertIsNotNone(pdf_bytes_empty_category)
        self.assertTrue(pdf_bytes_empty_category.startswith(b'%PDF-'))

if __name__ == '__main__':
    unittest.main()
