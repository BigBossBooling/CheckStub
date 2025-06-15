import unittest
import os
import shutil
from financial_document_generator.app.converters import convert_pdf_to_png, PDFInfoNotInstalledError
from financial_document_generator.app.check_generator import generate_check # To create a sample PDF

class TestPdfToPngConverter(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        """Set up paths and create a sample PDF for all tests in this class."""
        cls.test_dir = os.path.dirname(__file__)
        cls.test_output_dir = os.path.join(cls.test_dir, 'test_outputs')
        cls.converter_output_dir = os.path.join(cls.test_output_dir, 'converted_pngs')

        # Create a sample PDF using our existing check generator
        cls.sample_check_data = {
            'bank_name': 'Test Bank for Converter',
            'bank_address': '123 Converter St, Image City, ST 00000',
            'check_number': 'CVT001',
            'date': '01/01/2024',
            'payee_name': 'PNG Recipient',
            'amount_numeric': '10.00',
            'amount_words': 'TEN AND 00/100',
            'memo': 'For PNG Conversion Test',
            'routing_number': '000000000',
            'account_number': '111111111'
        }

        # Ensure output directories exist
        if os.path.exists(cls.converter_output_dir):
            shutil.rmtree(cls.converter_output_dir) # Clean up from previous runs
        os.makedirs(cls.converter_output_dir, exist_ok=True)

        cls.sample_pdf_path = os.path.join(cls.test_output_dir, 'sample_for_conversion.pdf')

        try:
            success = generate_check(cls.sample_check_data, output_path=cls.sample_pdf_path)
            if not success or not os.path.exists(cls.sample_pdf_path):
                raise RuntimeError("Failed to generate sample PDF for converter tests.")
            cls.sample_pdf_bytes = None
            with open(cls.sample_pdf_path, 'rb') as f:
                cls.sample_pdf_bytes = f.read()

        except Exception as e:
            print(f"WARNING: Could not generate sample PDF for converter tests: {e}. Tests might be skipped or fail.")
            cls.sample_pdf_path = None
            cls.sample_pdf_bytes = None


    @classmethod
    def tearDownClass(cls):
        """Clean up files and directories created by the test class."""
        if hasattr(cls, 'sample_pdf_path') and cls.sample_pdf_path and os.path.exists(cls.sample_pdf_path) and cls.sample_pdf_path.startswith(cls.test_output_dir):
             os.remove(cls.sample_pdf_path)
        if hasattr(cls, 'converter_output_dir') and os.path.exists(cls.converter_output_dir):
            shutil.rmtree(cls.converter_output_dir)
        # Only remove test_output_dir if it was created by these tests and is empty
        if hasattr(cls, 'test_output_dir') and os.path.exists(cls.test_output_dir) and not os.listdir(cls.test_output_dir) and cls.test_output_dir == os.path.join(cls.test_dir, 'test_outputs'):
             os.rmdir(cls.test_output_dir)


    def test_convert_pdf_path_to_png(self):
        """Test converting a PDF from a file path to PNG images."""
        if not self.sample_pdf_path:
            self.skipTest("Sample PDF for conversion was not generated. Skipping test.")

        try:
            png_files = convert_pdf_to_png(self.sample_pdf_path, self.converter_output_dir, "path_conv_test")
            self.assertIsNotNone(png_files, "Should return a list of file paths.")
            self.assertTrue(len(png_files) > 0, "Should generate at least one PNG file for a single-page PDF.")
            for png_file in png_files:
                self.assertTrue(os.path.exists(png_file), f"PNG file {png_file} should exist.")
                self.assertTrue(png_file.endswith(".png"), "Generated file should have a .png extension.")
                self.assertTrue(os.path.getsize(png_file) > 1000, f"PNG file {png_file} should not be empty (size > 1KB).")
        except PDFInfoNotInstalledError:
            self.skipTest("Poppler is not installed or not in PATH. Skipping PDF to PNG conversion test.")
        except Exception as e:
            self.fail(f"PDF to PNG conversion (from path) failed unexpectedly: {e}")

    def test_convert_pdf_bytes_to_png(self):
        """Test converting PDF content as bytes to PNG images."""
        if not self.sample_pdf_bytes:
            self.skipTest("Sample PDF bytes for conversion were not available. Skipping test.")

        try:
            png_files = convert_pdf_to_png(self.sample_pdf_bytes, self.converter_output_dir, "bytes_conv_test")
            self.assertIsNotNone(png_files)
            self.assertTrue(len(png_files) > 0)
            for png_file in png_files:
                self.assertTrue(os.path.exists(png_file))
                self.assertTrue(png_file.endswith(".png"))
                self.assertTrue(os.path.getsize(png_file) > 1000)
        except PDFInfoNotInstalledError:
            self.skipTest("Poppler is not installed or not in PATH. Skipping PDF to PNG conversion test.")
        except Exception as e:
            self.fail(f"PDF to PNG conversion (from bytes) failed unexpectedly: {e}")

    def test_convert_pdf_invalid_path(self):
        """Test conversion with an invalid PDF file path."""
        with self.assertRaises(FileNotFoundError):
            convert_pdf_to_png("non_existent_document.pdf", self.converter_output_dir)

    def test_convert_pdf_invalid_bytes(self):
        """Test conversion with invalid PDF byte content."""
        from pdf2image.exceptions import PDFPageCountError, PDFSyntaxError
        with self.assertRaises((PDFPageCountError, PDFSyntaxError)):
            convert_pdf_to_png(b"This is not a PDF.", self.converter_output_dir)

    def test_convert_pdf_to_non_existent_output_folder(self):
        """Test that the output folder is created if it doesn't exist."""
        if not self.sample_pdf_path:
            self.skipTest("Sample PDF for conversion was not generated. Skipping test.")

        non_existent_folder = os.path.join(self.converter_output_dir, "new_folder_for_pngs")
        if os.path.exists(non_existent_folder):
            shutil.rmtree(non_existent_folder)

        try:
            png_files = convert_pdf_to_png(self.sample_pdf_path, non_existent_folder, "new_folder_test")
            self.assertTrue(os.path.exists(non_existent_folder), "Output folder should be created by the function.")
            self.assertTrue(len(png_files) > 0)
            self.assertTrue(os.path.exists(png_files[0]))
        except PDFInfoNotInstalledError:
            self.skipTest("Poppler is not installed. Skipping test.")
        except Exception as e:
            self.fail(f"Conversion to new folder failed: {e}")
        finally:
            if os.path.exists(non_existent_folder):
                shutil.rmtree(non_existent_folder)

if __name__ == '__main__':
    unittest.main()
