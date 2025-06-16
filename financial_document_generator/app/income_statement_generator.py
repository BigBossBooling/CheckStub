import os
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

def generate_income_statement(data, output_path=None):
    '''
    Generates an Income Statement PDF from data.

    Args:
        data (dict): A dictionary containing Income Statement details,
                     matching the data model defined for income_statement.html.
                     This includes nested lists for revenue_items, cogs_items,
                     operating_expense_items, and other_income_expense_items.
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

        env = Environment(loader=FileSystemLoader(template_dir), autoescape=True)
        template = env.get_template('income_statement.html')

        # Render the HTML template with data
        html_string = template.render(data)

        html_obj = HTML(string=html_string, base_url=template_dir)

        if output_path:
            html_obj.write_pdf(output_path)
            print(f"Income Statement PDF generated and saved to {output_path}")
            return True
        else:
            pdf_bytes = html_obj.write_pdf()
            print("Income Statement PDF generated as bytes.")
            return pdf_bytes

    except Exception as e:
        print(f"Error generating Income Statement: {e}")
        return None

if __name__ == '__main__':
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    sample_income_statement_data = {
        'company_name': "Tech Innovations Ltd.",
        'statement_title': "Consolidated Statement of Operations",
        'period_covered': "For the Year Ended December 31, 2023",
        'currency_symbol': "$",
        'revenue_items': [
            {'description': 'Product Sales', 'amount': '250,000.00'},
            {'description': 'Service & Support Revenue', 'amount': '75,000.00'}
        ],
        'total_revenue': '325,000.00',
        'cogs_items': [
            # Example of detailed COGS, or could be a single 'Total COGS' line
            {'description': 'Cost of Product Sales', 'amount': '120,000.00'},
            {'description': 'Cost of Service & Support', 'amount': '25,000.00'}
        ],
        'total_cogs': '145,000.00',
        'gross_profit': '180,000.00', # 325000 - 145000
        'operating_expense_items': [
            {'description': 'Research and Development', 'amount': '35,000.00'},
            {'description': 'Sales and Marketing', 'amount': '30,000.00'},
            {'description': 'General and Administrative', 'amount': '25,000.00'},
            {'description': 'Depreciation and Amortization', 'amount': '10,000.00'}
        ],
        'total_operating_expenses': '100,000.00',
        'operating_income': '80,000.00', # 180000 - 100000
        'other_income_expense_items': [
            {'description': 'Interest Income', 'amount': '1,200.00'},
            {'description': 'Interest Expense', 'amount': '(800.00)'} # Represent as negative or let template handle
        ],
        'total_other_income_expenses': '400.00', # Net
        'income_before_tax': '80,400.00', # 80000 + 400
        'income_tax_expense': '16,080.00', # Assuming 20% tax rate for example
        'net_income': '64,320.00', # 80400 - 16080
        'notes_to_financial_statements': "1. All amounts are in USD unless otherwise stated.\n2. Revenue recognition policies are consistent with prior years."
    }

    output_file = os.path.join(project_root, 'generated_income_statement_test.pdf')
    print(f"Attempting to generate Income Statement PDF at: {output_file}")

    if generate_income_statement(sample_income_statement_data, output_path=output_file):
        print(f"Test Income Statement PDF saved to {output_file}")
    else:
        print(f"Failed to save test Income Statement PDF. Check for errors above (timeouts possible).")

    # Example of generating as bytes
    # print("Attempting to generate Income Statement as bytes...")
    # pdf_bytes = generate_income_statement(sample_income_statement_data)
    # if pdf_bytes:
    #     print(f"Generated Income Statement as {len(pdf_bytes)} bytes.")
    # else:
    #     print("Failed to generate Income Statement as bytes.")
