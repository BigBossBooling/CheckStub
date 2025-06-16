import os
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

def generate_bank_statement(data, output_path=None):
    '''
    Generates a bank statement PDF from data.

    Args:
        data (dict): A dictionary containing bank statement details.
                     Expected keys match the data model defined for bank_statement.html,
                     including nested list for 'transactions'.
        output_path (str, optional): If provided, saves the PDF to this path.
                                     Otherwise, returns the PDF as bytes.

    Returns:
        bytes or bool: PDF content as bytes if output_path is None,
                       True if file is saved successfully, else None on error.
    '''
    try:
        # Determine base directory and template path
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # financial_document_generator/
        template_dir = os.path.join(base_dir, 'templates')

        # Set up Jinja2 environment
        env = Environment(loader=FileSystemLoader(template_dir), autoescape=True)
        template = env.get_template('bank_statement.html')

        # Render the HTML template with data
        html_string = template.render(data)

        # Create WeasyPrint HTML object
        # base_url is important for resolving relative paths in HTML (e.g., for images if not embedded as base64)
        # or for linked CSS if not fully embedded.
        html_obj = HTML(string=html_string, base_url=template_dir)

        if output_path:
            html_obj.write_pdf(output_path)
            print(f"Bank statement PDF generated and saved to {output_path}")
            return True # Indicate success
        else:
            pdf_bytes = html_obj.write_pdf()
            print("Bank statement PDF generated as bytes.")
            return pdf_bytes

    except Exception as e:
        print(f"Error generating bank statement: {e}")
        # In a real app, might want to log this with app.logger.error(..., exc_info=True) if Flask context is available
        return None

if __name__ == '__main__':
    # Example Usage (for testing purposes)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # financial_document_generator/

    sample_statement_data = {
        'bank_name': 'Global Finance Corp',
        'bank_address': '1 Financial Plaza, Metro City, ST 10001',
        # 'bank_logo_url': 'path/to/your/logo.png', # Optional: Provide a real path or URL if testing logo
        'account_holder_name': 'John D. Doe',
        'account_holder_address': '123 Main Street, Anytown, ST 12345',
        'account_number': 'XXXX-XXXX-XX1234',
        'statement_period_start': 'October 1, 2023',
        'statement_period_end': 'October 31, 2023',
        'statement_date': 'November 5, 2023',
        'opening_balance': '$1,234.56',
        'closing_balance': '$2,345.67',
        'total_deposits': '$1,500.00',
        'total_withdrawals': '$388.89', # This will be inconsistent with few transactions, but fine for render test
        'transactions': [
            {'date': '10/01', 'description': 'Opening Balance', 'deposit_amount': '', 'withdrawal_amount': '', 'running_balance': '$1,234.56'},
            {'date': '10/05', 'description': 'Online Purchase - Amazon.com', 'withdrawal_amount': '$50.25', 'deposit_amount': '', 'running_balance': '$1,184.31'},
            # Reduced number of transactions to speed up testing
            {'date': '10/15', 'description': 'Direct Deposit - Payroll', 'deposit_amount': '$750.00', 'withdrawal_amount': '', 'running_balance': '$1,934.31'},
        ],
        'summary_messages': ["Your new checking account features are now active!"], # Simplified messages
        'customer_service_number': '1-800-555-BANK',
        'website': 'www.globalfinancecorp.com'
    }

    # For bank_logo_url, if you want to test it with a local file:
    # Ensure the logo exists. The path in HTML needs to be resolvable by WeasyPrint.
    # If it's a local file, it's best to use an absolute path or a path relative to `base_url` in HTML object.
    # For simplicity, we can make it relative to the project root for this test.
    # dummy_logo_path = os.path.join(project_root, "static", "dummy_logo.png") # Example
    # if os.path.exists(dummy_logo_path):
    #    sample_statement_data['bank_logo_url'] = f"file://{os.path.abspath(dummy_logo_path)}"


    output_file = os.path.join(project_root, 'generated_bank_statement_test.pdf')
    if generate_bank_statement(sample_statement_data, output_path=output_file):
        print(f"Test bank statement saved to {output_file}")
    else:
        print(f"Failed to save test bank statement to {output_file}")

    # Example of generating as bytes
    # pdf_bytes = generate_bank_statement(sample_statement_data)
    # if pdf_bytes:
    #     print(f"Generated bank statement as {len(pdf_bytes)} bytes.")
    # else:
    #     print("Failed to generate bank statement as bytes.")
