import unittest
import os
import shutil
from financial_document_generator.app.w2_form_generator import generate_w2_form

class TestW2FormGenerator(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up sample data and paths for all tests in this class."""
        cls.test_dir = os.path.dirname(__file__)
        cls.test_output_dir = os.path.join(cls.test_dir, 'test_outputs')
        cls.w2_output_dir = os.path.join(cls.test_output_dir, 'generated_w2_forms')

        os.makedirs(cls.w2_output_dir, exist_ok=True)

        cls.sample_w2_data = {
            'form_year': "2023",
            'copy_designation': "Copy C, For EMPLOYEE'S RECORDS",
            'control_number': "W2CTRL-001",
            'employer_ein': "99-9999999",
            'employer_name_line1': "Sample Employer LLC",
            'employer_address_line1': "789 Business Park",
            'employer_city': "Workville",
            'employer_state_code': "CA",
            'employer_zip_code': "90210",
            'employee_ssn': "XXX-XX-1234",
            'employee_name_first': "Sarah",
            'employee_name_last': "Testsubject",
            'employee_address_line1': "1 Test Lane",
            'employee_city': "Homestead",
            'employee_state_code': "CA",
            'employee_zip_code': "90211",
            'wages_tips_other_comp': "72000.00",
            'federal_income_tax_withheld': "8200.00",
            'social_security_wages': "72000.00",
            'social_security_tax_withheld': "4464.00",
            'medicare_wages_and_tips': "72000.00",
            'medicare_tax_withheld': "1044.00",
            'dependent_care_benefits': "2000.00",
            'box12_items': [
                {'code': 'C', 'amount': '1000.00'},
                {'code': 'P', 'amount': '500.00'}
            ],
            'statutory_employee_checkbox': False,
            'retirement_plan_checkbox': True,
            'third_party_sick_pay_checkbox': False,
            'box14_items': [
                {'description': 'CA SDI', 'amount': '350.00'}
            ],
            'state_info_1': {
                'employer_state': "CA",
                'employer_state_id': "CA-12345678",
                'state_wages_tips': "72000.00",
                'state_income_tax': "3500.00"
            }
        }
        cls.test_pdf_path = os.path.join(cls.w2_output_dir, 'test_generated_w2_form.pdf')

    @classmethod
    def tearDownClass(cls):
        """Clean up files and directories created by the test class."""
        if os.path.exists(cls.w2_output_dir):
            shutil.rmtree(cls.w2_output_dir)
        if os.path.exists(cls.test_output_dir) and not os.listdir(cls.test_output_dir) and \
           cls.test_output_dir == os.path.join(cls.test_dir, 'test_outputs'):
            os.rmdir(cls.test_output_dir)

    def test_generate_w2_form_returns_bytes(self):
        """Test that generate_w2_form returns PDF bytes when no output_path."""
        pdf_bytes = generate_w2_form(self.sample_w2_data)
        self.assertIsNotNone(pdf_bytes, "Should return PDF bytes.")
        self.assertIsInstance(pdf_bytes, bytes, "Returned object should be bytes.")
        self.assertTrue(len(pdf_bytes) > 2000, "PDF bytes should not be excessively small for a W-2.")
        self.assertTrue(pdf_bytes.startswith(b'%PDF-'), "Output does not look like a PDF file.")

    def test_generate_w2_form_saves_to_file(self):
        """Test that generate_w2_form saves a PDF file when output_path is provided."""
        if os.path.exists(self.test_pdf_path):
            os.remove(self.test_pdf_path)

        result = generate_w2_form(self.sample_w2_data, output_path=self.test_pdf_path)
        self.assertTrue(result, "Should return True on successful save.")
        self.assertTrue(os.path.exists(self.test_pdf_path), "PDF file should be created.")
        self.assertTrue(os.path.getsize(self.test_pdf_path) > 2000, "Generated PDF file should not be excessively small.")
        with open(self.test_pdf_path, 'rb') as f:
            self.assertTrue(f.read(5).startswith(b'%PDF-'), "Saved file content does not appear to be a PDF.")

    def test_generate_w2_form_minimal_data_for_structure(self):
        """Test with truly minimal data, relying heavily on template defaults to check structure rendering."""
        minimal_data = {
            'form_year': "2023",
            'copy_designation': "Test Copy",
            'employer_ein': "00-0000000",
            'employer_name_line1': "Min Employer",
            'employer_city': "Min City", 'employer_state_code': "XX", 'employer_zip_code': "00000",
            'employee_ssn': "000-00-0000",
            'employee_name_first': "Min", 'employee_name_last': "Emp",
            'employee_city': "Min City", 'employee_state_code': "YY", 'employee_zip_code': "11111",
            'wages_tips_other_comp': "0.00",
            'federal_income_tax_withheld': "0.00",
            'social_security_wages': "0.00",
            'social_security_tax_withheld': "0.00",
            'medicare_wages_and_tips': "0.00",
            'medicare_tax_withheld': "0.00",
            'box12_items': [],
            'box14_items': [],
            'state_info_1': { 'employer_state': "XX", 'employer_state_id': "XXXXXXXX",
                              'state_wages_tips': "0.00", 'state_income_tax': "0.00"},
        }
        pdf_bytes = generate_w2_form(minimal_data)
        self.assertIsNotNone(pdf_bytes, "Should generate PDF even with minimal data due to defaults and structure.")
        self.assertTrue(pdf_bytes.startswith(b'%PDF-'), "Minimal data W-2 PDF should be valid.")

if __name__ == '__main__':
    unittest.main()
