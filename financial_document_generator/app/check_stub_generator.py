import os
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

def generate_check_stub(data, output_path=None):
    '''
    Generates a check stub PDF from data.

    Args:
        data (dict): A dictionary containing check stub details.
                     Expected keys include: company_name, company_address,
                                          employee_name, employee_id,
                                          pay_period_start, pay_period_end, pay_date, check_number,
                                          earnings (list of dicts: description, hours, rate, current, ytd),
                                          total_earnings_current, total_earnings_ytd,
                                          deductions (list of dicts: description, current, ytd),
                                          total_deductions_current, total_deductions_ytd,
                                          net_pay_current, ytd_net_pay, employer_notes.
        output_path (str, optional): If provided, saves the PDF to this path.
                                     Otherwise, returns the PDF as bytes.

    Returns:
        bytes or bool: PDF content as bytes if output_path is None,
                       True if file is saved successfully, else None on error.
    '''
    try:
        # Determine base directory and template/static paths
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        template_dir = os.path.join(base_dir, 'templates')

        # Set up Jinja2 environment
        env = Environment(loader=FileSystemLoader(template_dir), autoescape=True)
        template = env.get_template('check_stub.html')

        # Render the HTML template with data
        html_string = template.render(data)

        # Create WeasyPrint HTML object
        # base_url is important for resolving relative paths in HTML (e.g., for CSS if not embedded)
        html_obj = HTML(string=html_string, base_url=template_dir)

        if output_path:
            html_obj.write_pdf(output_path)
            print(f"Check stub PDF generated and saved to {output_path}")
            return True # Indicate success
        else:
            pdf_bytes = html_obj.write_pdf()
            print("Check stub PDF generated as bytes.")
            return pdf_bytes

    except Exception as e:
        print(f"Error generating check stub: {e}")
        return None

if __name__ == '__main__':
    # Example Usage (for testing purposes)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    sample_stub_data = {
        'company_name': 'Tech Solutions Inc.',
        'company_address': '789 Innovation Drive, Silicon Valley, CA 94000',
        'employee_name': 'DOE, JOHN A.',
        'employee_id': 'EMP78901',
        'pay_period_start': '11/01/2023',
        'pay_period_end': '11/15/2023',
        'pay_date': '11/20/2023',
        'check_number': '1001', # Should match the check
        'earnings': [
            {'description': 'Regular Pay', 'hours': '80', 'rate': '50.00', 'current': '4000.00', 'ytd': '88000.00'},
            {'description': 'Overtime Pay', 'hours': '10', 'rate': '75.00', 'current': '750.00', 'ytd': '3000.00'},
            {'description': 'Bonus', 'current': '500.00', 'ytd': '2000.00'}
        ],
        'total_earnings_current': '5250.00',
        'total_earnings_ytd': '93000.00',
        'deductions': [
            {'description': 'Federal Income Tax', 'current': '600.00', 'ytd': '13200.00'},
            {'description': 'State Income Tax', 'current': '250.00', 'ytd': '5500.00'},
            {'description': 'Social Security', 'current': '325.50', 'ytd': '7161.00'},
            {'description': 'Medicare', 'current': '76.13', 'ytd': '1674.86'},
            {'description': 'Health Insurance', 'current': '150.00', 'ytd': '3300.00'},
            {'description': '401k Contribution', 'current': '200.00', 'ytd': '4400.00'}
        ],
        'total_deductions_current': '1601.63',
        'total_deductions_ytd': '35235.86',
        'net_pay_current': '3648.37',
        'ytd_net_pay': '57764.14',
        'employer_notes': 'Happy Holidays! Year-end bonus included.'
    }

    # Generate and save to file
    output_file = os.path.join(project_root, 'generated_check_stub_test.pdf')
    if generate_check_stub(sample_stub_data, output_path=output_file):
        print(f"Test check stub saved to {output_file}")
    else:
        print(f"Failed to save test check stub to {output_file}")

    # Example of generating as bytes (optional to test here)
    # pdf_bytes = generate_check_stub(sample_stub_data)
    # if pdf_bytes:
    #     print(f"Generated check stub as {len(pdf_bytes)} bytes.")
    # else:
    #     print("Failed to generate check stub as bytes.")
