import os
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

def generate_w2_form(data, output_path=None):
    '''
    Generates a W-2 form PDF from data.

    Args:
        data (dict): A dictionary containing W-2 form details, matching the
                     data model defined for w2_form.html. This includes
                     nested lists for box12_items, box14_items, and
                     dictionaries for state_info_1, state_info_2, etc.
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
        env = Environment(loader=FileSystemLoader(template_dir), autoescape=True) # autoescape is good for HTML context
        template = env.get_template('w2_form.html')

        # Render the HTML template with data
        # Ensure all expected keys are present in data, or have defaults in template
        html_string = template.render(data)

        # Create WeasyPrint HTML object
        # base_url is important if your HTML template links to external resources like images or CSS
        # that are not findable via their relative paths from the HTML string alone.
        # For w2_form.html, all CSS is embedded, and images are not used by default.
        html_obj = HTML(string=html_string, base_url=template_dir)

        if output_path:
            html_obj.write_pdf(output_path)
            print(f"W-2 Form PDF generated and saved to {output_path}")
            return True # Indicate success
        else:
            pdf_bytes = html_obj.write_pdf()
            print("W-2 Form PDF generated as bytes.")
            return pdf_bytes

    except Exception as e:
        print(f"Error generating W-2 Form: {e}")
        # Consider more specific error logging or handling if this were part of a larger app
        return None

if __name__ == '__main__':
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Comprehensive sample data for W-2
    sample_w2_data = {
        'form_year': "2023",
        'copy_designation': "Copy B, To Be Filed With Employee's FEDERAL Tax Return",
        'control_number': "ABC-123-XYZ-789",
        'employer_ein': "12-3456789",
        'employer_name_line1': "Anytown Employer Inc.",
        'employer_address_line1': "100 Business Loop",
        'employer_city': "Anytown",
        'employer_state_code': "NY",
        'employer_zip_code': "12345",
        'employee_ssn': "XXX-XX-6789", # Masked for privacy
        'employee_name_first': "John M.",
        'employee_name_last': "Doe",
        'employee_address_line1': "55 Main Street",
        'employee_address_line2': "Apt 2B",
        'employee_city': "Metropolis",
        'employee_state_code': "NY",
        'employee_zip_code': "10001",
        'wages_tips_other_comp': "65000.00",
        'federal_income_tax_withheld': "7500.00",
        'social_security_wages': "65000.00",
        'social_security_tax_withheld': "4030.00", # 6.2% of 65000
        'medicare_wages_and_tips': "65000.00",
        'medicare_tax_withheld': "942.50",    # 1.45% of 65000
        'social_security_tips': "",
        'allocated_tips': "",
        'verification_code': "XY12AB34CD56EF78",
        'dependent_care_benefits': "1500.00",
        'nonqualified_plans': "",
        'box12_items': [
            {'code': 'D', 'amount': '1200.00'}, # 401k
            {'code': 'DD', 'amount': '5500.00'},# Cost of employer-sponsored health coverage
            {'code': 'W', 'amount': '300.00'}  # Employer contributions to HSA
        ],
        'statutory_employee_checkbox': False,
        'retirement_plan_checkbox': True,
        'third_party_sick_pay_checkbox': False,
        'box14_items': [
            {'description': 'NY SDI', 'amount': '150.75'},
            {'description': 'Union Dues', 'amount': '250.00'}
        ],
        'state_info_1': {
            'employer_state': "NY",
            'employer_state_id': "NY-9876543",
            'state_wages_tips': "65000.00",
            'state_income_tax': "2800.00"
        },
        # 'state_info_2': {}, # Optional second state
        'local_info_1': {
            'local_wages_tips': "65000.00",
            'local_income_tax': "650.00",
            'locality_name': "NYC"
        },
        # 'local_info_2': {} # Optional second locality
    }

    output_file = os.path.join(project_root, 'generated_w2_form_test.pdf')
    print(f"Attempting to generate W-2 PDF at: {output_file}")
    if generate_w2_form(sample_w2_data, output_path=output_file):
        print(f"Test W-2 Form PDF saved to {output_file}")
    else:
        print(f"Failed to save test W-2 Form PDF. This might be due to rendering timeout for complex W-2 template.")

    # Example of generating as bytes (might also timeout)
    # print("Attempting to generate W-2 as bytes...")
    # pdf_bytes = generate_w2_form(sample_w2_data)
    # if pdf_bytes:
    #     print(f"Generated W-2 Form as {len(pdf_bytes)} bytes.")
    #     # Optionally save the bytes to a file for verification
    #     # with open(os.path.join(project_root, 'generated_w2_form_bytes_test.pdf'), 'wb') as f_bytes:
    #     #     f_bytes.write(pdf_bytes)
    #     # print("Saved W-2 from bytes to generated_w2_form_bytes_test.pdf")
    # else:
    #     print("Failed to generate W-2 Form as bytes. This might be due to rendering timeout.")
