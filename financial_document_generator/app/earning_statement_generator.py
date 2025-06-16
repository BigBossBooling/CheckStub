import os
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

# This generator assumes the data structure is identical to that of a check stub.
# The primary difference is the template used and potentially minor content variations
# handled within that template or by specific data passed.

def generate_earning_statement(data, output_path=None):
    '''
    Generates an Earning Statement PDF from data.
    Uses 'earning_statement.html' template.
    Expects data structure similar to generate_check_stub.

    Args:
        data (dict): A dictionary containing earning statement details.
                     Expected keys include: company_name, company_address,
                                          employee_name, employee_id,
                                          pay_period_start, pay_period_end, pay_date,
                                          earnings (list of dicts),
                                          total_earnings_current, total_earnings_ytd,
                                          deductions (list of dicts),
                                          total_deductions_current, total_deductions_ytd,
                                          net_pay_current, ytd_net_pay, employer_notes.
                                          Optional: check_number (may be less relevant).
        output_path (str, optional): If provided, saves the PDF to this path.
                                     Otherwise, returns the PDF as bytes.

    Returns:
        bytes or bool: PDF content as bytes if output_path is None,
                       True if file is saved successfully, else None on error.
    '''
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # financial_document_generator/
        template_dir = os.path.join(base_dir, 'templates')

        env = Environment(loader=FileSystemLoader(template_dir), autoescape=True)
        template = env.get_template('earning_statement.html') # Use the new template

        html_string = template.render(data)
        html_obj = HTML(string=html_string, base_url=template_dir)

        if output_path:
            html_obj.write_pdf(output_path)
            print(f"Earning Statement PDF generated and saved to {output_path}")
            return True
        else:
            pdf_bytes = html_obj.write_pdf()
            print("Earning Statement PDF generated as bytes.")
            return pdf_bytes

    except Exception as e:
        print(f"Error generating Earning Statement: {e}")
        return None

if __name__ == '__main__':
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Sample data (can be identical or similar to check_stub_generator's sample)
    sample_earning_data = {
        'company_name': 'Direct Pay Corp.',
        'company_address': '100 Salary Lane, Payment City, ST 90000',
        'employee_name': 'WAYNE, BRUCE',
        'employee_id': 'EMP007',
        'pay_period_start': '12/01/2023',
        'pay_period_end': '12/15/2023',
        'pay_date': '12/20/2023',
        'check_number': 'DP-55678', # Could be a direct deposit advice number
        'earnings': [
            {'description': 'Salary', 'hours': '', 'rate': '', 'current': '3000.00', 'ytd': '72000.00'},
            {'description': 'Performance Bonus', 'hours': '', 'rate': '', 'current': '500.00', 'ytd': '2000.00'}
        ],
        'total_earnings_current': '3500.00',
        'total_earnings_ytd': '74000.00',
        'deductions': [
            {'description': 'Federal Tax', 'current': '450.00', 'ytd': '10800.00'},
            {'description': 'State Tax', 'current': '150.00', 'ytd': '3600.00'},
            {'description': 'Health Premium', 'current': '120.00', 'ytd': '1440.00'},
            {'description': 'Retirement Fund', 'current': '300.00', 'ytd': '3600.00'}
        ],
        'total_deductions_current': '1020.00',
        'total_deductions_ytd': '19440.00',
        'net_pay_current': '2480.00',
        'ytd_net_pay': '54560.00',
        'employer_notes': 'This is a statement of your earnings. Direct deposit has been made to your nominated account.'
    }

    output_file = os.path.join(project_root, 'generated_earning_statement_test.pdf')
    print(f"Attempting to generate Earning Statement PDF at: {output_file}")

    if generate_earning_statement(sample_earning_data, output_path=output_file):
        print(f"Test Earning Statement PDF saved to {output_file}")
    else:
        print(f"Failed to save test Earning Statement PDF. Check for errors (timeouts possible).")
