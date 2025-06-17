import os
from flask import Flask, render_template, url_for, request, send_file, flash, redirect
import io # For BytesIO if sending bytes directly
import uuid
from werkzeug.utils import secure_filename
import shutil # Added for cleanup
import time   # Added for cleanup
from .check_generator import generate_check # Assuming check_generator is in the same 'app' package
from .check_stub_generator import generate_check_stub
from .converters import convert_pdf_to_png, PDFInfoNotInstalledError
from .bank_statement_generator import generate_bank_statement
from .w2_form_generator import generate_w2_form
from .income_statement_generator import generate_income_statement
from .earning_statement_generator import generate_earning_statement

# It's good practice to make template and static folder paths relative to the app

def parse_and_validate_dynamic_items(form_data, item_type_prefix, field_definitions):
    """
    Parses and validates dynamic list items from form data.
    Example item_type_prefix: 'earning', 'deduction'
    field_definitions: list of tuples like [('desc', 'Description', True), ('current', 'Current Amount', True, 'number_positive_or_zero'), ...]
                       (field_suffix, display_name, is_required_if_desc_present, type_check [optional])
    """
    items = []
    errors = []
    idx = 1
    while True:
        # Check for a primary descriptor field to see if the row exists
        primary_desc_field_key = f'{item_type_prefix}{idx}_desc' # Assuming '_desc' is always the primary identifier

        if not form_data.get(primary_desc_field_key): # If no description for this index, assume no more items
            break

        item_data = {}
        has_primary_desc = bool(form_data.get(primary_desc_field_key, '').strip())
        # current_item_has_error = False # Not used in this version of logic

        for field_suffix, display_name, is_required, *type_info in field_definitions:
            field_key = f'{item_type_prefix}{idx}_{field_suffix}'
            value_str = form_data.get(field_key, '').strip()
            item_data[field_suffix] = value_str # Store original string value for repopulation or further use

            if is_required and has_primary_desc and not value_str:
                errors.append(f"{display_name} for {item_type_prefix.capitalize()} {idx} is required when description is present.")
                # current_item_has_error = True

            if value_str and type_info: # If value exists and type check is defined
                type_check = type_info[0]
                if type_check == 'number_positive_or_zero':
                    try:
                        val = float(value_str)
                        if val < 0:
                            errors.append(f"{display_name} for {item_type_prefix.capitalize()} {idx} must be zero or positive.")
                            # current_item_has_error = True
                    except ValueError:
                        errors.append(f"{display_name} for {item_type_prefix.capitalize()} {idx} must be a valid number.")
                        # current_item_has_error = True
                elif type_check == 'number': # Any number
                     try:
                        float(value_str)
                     except ValueError:
                        errors.append(f"{display_name} for {item_type_prefix.capitalize()} {idx} must be a valid number.")
                        # current_item_has_error = True

        if has_primary_desc: # Only add item if primary description was present
            items.append(item_data)

        idx += 1
        if idx > 50: # Safety break for runaway loops if form data is crafted maliciously
            errors.append(f"Exceeded maximum number of {item_type_prefix} items.")
            break
    return items, errors
# or use instance_path for more complex setups.
# For now, let's assume templates are in a 'web_templates' subdir of the app.
# And static files are in 'static' subdir of the app (which might conflict if not careful)
# Let's adjust template_folder to be more specific for web UI templates.

# Determine the absolute path to the 'app' directory
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_FOLDER = os.path.join(APP_ROOT, 'web_templates')
STATIC_FOLDER = os.path.join(APP_ROOT, '..', 'static') # Assuming static is one level up from 'app' and then into 'static'
                                                    # This matches the existing structure for PDF templates.
                                                    # For Flask specific static files, a sub-folder 'app/static' or 'app/web_static' might be better.
                                                    # Let's use the existing top-level 'static' for simplicity for now.

app = Flask(__name__, template_folder=TEMPLATE_FOLDER, static_folder=STATIC_FOLDER)
app.config['SECRET_KEY'] = os.urandom(24) # For session management, flash messages, etc.

# Configuration for file uploads
# Define UPLOAD_FOLDER relative to the app's root (APP_ROOT)
# e.g., financial_document_generator/app/uploads/
UPLOAD_FOLDER = os.path.join(APP_ROOT, 'uploads')
# Define PNG_OUTPUT_FOLDER relative to the static folder so images can be served
# e.g., financial_document_generator/static/generated_pngs/
PNG_OUTPUT_FOLDER_REL_STATIC = 'generated_pngs' # Relative to static folder
PNG_OUTPUT_FOLDER_ABS = os.path.join(app.static_folder, PNG_OUTPUT_FOLDER_REL_STATIC)

# TODO: Implement a robust cleanup strategy for subdirectories in PNG_OUTPUT_FOLDER_ABS.
# Potential strategies for cleaning up old generated PNG folders:
# 1. Periodic Cleanup Task: A separate script/cron job that runs periodically (e.g., daily)
#    and deletes folders older than a certain threshold (e.g., 24 hours).
#    This is the most robust approach for a production environment. Requires external scheduler.
# 2. Cleanup on New Request (Simpler, but can add overhead):
#    At the beginning of a new request to `convert_pdf_to_png_route` (or even a global request hook),
#    scan PNG_OUTPUT_FOLDER_ABS for subdirectories older than a threshold (e.g., > 1-2 hours old)
#    and delete them. Care must be taken to do this efficiently (e.g., not on every single request if high traffic)
#    to avoid slowing down user requests.
# 3. Manual Cleanup: For development or low-usage internal tools, manual deletion might be acceptable temporarily.
# 4. Per-session cleanup: If user sessions were implemented, temporary files could be tied to sessions
#    and cleaned up on session expiry, but this adds significant complexity not currently in scope.
# Current implementation does not automatically clean these PNG output folders.

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 # Example: 16MB upload limit

# Ensure upload and PNG output directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PNG_OUTPUT_FOLDER_ABS, exist_ok=True)

@app.route('/')
def home():
    return render_template('home.html', title='Home')

# Add a simple health check or debug route
@app.route('/ping')
def ping():
    return "Pong!"

@app.route('/generate/check', methods=['GET', 'POST'])
def generate_check_route():
    if request.method == 'POST':
        # Inside generate_check_route, within if request.method == 'POST':
        try:
            form_data_dict = request.form.to_dict() # Keep for passing to generate_check if valid
            form_data_for_repopulation = request.form # Use this for repopulating template
            errors = []

            # Rule 1: Required fields
            required_fields = {
                'bank_name': "Bank Name",
                'check_number': "Check Number",
                'date': "Date",
                'payee_name': "Payee Name",
                'amount_numeric': "Amount (Numeric)",
                'amount_words': "Amount (In Words)"
            }
            for field, display_name in required_fields.items():
                if not form_data_for_repopulation.get(field):
                    errors.append(f"{display_name} is required.")

            # Rule 2: amount_numeric must be a positive number
            amount_numeric_str = form_data_for_repopulation.get('amount_numeric')
            if amount_numeric_str: # Only proceed if it's not caught by 'required'
                try:
                    amount_val = float(amount_numeric_str)
                    if amount_val <= 0:
                        errors.append("Amount (Numeric) must be a positive value.")
                except ValueError:
                    errors.append("Amount (Numeric) must be a valid number (e.g., 123.45).")

            # Rule 3: check_number should be numeric (integer-like)
            check_number_str = form_data_for_repopulation.get('check_number')
            if check_number_str and not check_number_str.isdigit():
                errors.append("Check Number should consist of digits only.")

            # If there are any errors, flash them and re-render the form
            if errors:
                for error in errors:
                    flash(error, 'error')
                return render_template('generate_check_form.html', title='Generate Check', form_data=form_data_for_repopulation)

            # If validation passes, proceed to generate PDF
            # Use form_data_dict for the generate_check function as it expects a dict
            pdf_bytes = generate_check(form_data_dict)

            if pdf_bytes:
                return send_file(
                    io.BytesIO(pdf_bytes),
                    mimetype='application/pdf',
                    as_attachment=True,
                    download_name=f"check_{form_data_dict.get('check_number', 'generated')}.pdf"
                )
            else:
                # This else implies generate_check returned None (internal error or timeout)
                flash('Failed to generate check PDF. An internal error occurred or task timed out. Please check server logs.', 'error')
                # Re-render form with data, as it was valid input but generation failed
                return render_template('generate_check_form.html', title='Generate Check', form_data=form_data_for_repopulation)

        except Exception as e:
            app.logger.error(f"Error in generate_check_route: {e}", exc_info=True)
            flash(f'An unexpected server error occurred: {e}', 'error')
            # On general exception, redirect to avoid re-POST, but don't repopulate form (or pass form_data if desired)
            return redirect(url_for('generate_check_route'))

    return render_template('generate_check_form.html', title='Generate Check')

@app.route('/generate/check_stub', methods=['GET', 'POST'])
def generate_check_stub_route():
    if request.method == 'POST':
        try:
            form_data_for_repopulation = request.form
            form_data_dict = request.form.to_dict() # For passing to generator if valid
            errors = []
            parsed_data = form_data_dict.copy() # Start with all flat fields for the generator

            # Define field structures for dynamic items
            earning_field_defs = [
                ('desc', 'Description', True),
                ('hours', 'Hours', False, 'number_positive_or_zero'), # Optional, but numeric if present
                ('rate', 'Rate', False, 'number_positive_or_zero'),   # Optional, but numeric if present
                ('current', 'Current Amount', True, 'number_positive_or_zero'),
                ('ytd', 'YTD Amount', False, 'number_positive_or_zero') # Optional, but numeric if present
            ]
            deduction_field_defs = [
                ('desc', 'Description', True),
                ('current', 'Current Amount', True, 'number_positive_or_zero'),
                ('ytd', 'YTD Amount', False, 'number_positive_or_zero') # Optional, but numeric if present
            ]

            parsed_earnings, earning_errors = parse_and_validate_dynamic_items(form_data_for_repopulation, 'earning', earning_field_defs)
            errors.extend(earning_errors)
            parsed_data['earnings'] = parsed_earnings # This now contains dicts with string values

            parsed_deductions, deduction_errors = parse_and_validate_dynamic_items(form_data_for_repopulation, 'deduction', deduction_field_defs)
            errors.extend(deduction_errors)
            parsed_data['deductions'] = parsed_deductions

            # Static Required Fields
            required_static_fields = {
                'company_name': "Company Name", 'employee_name': "Employee Name",
                'pay_period_start': "Pay Period Start", 'pay_period_end': "Pay Period End", 'pay_date': "Pay Date",
                'total_earnings_current': "Total Current Earnings",
                'total_deductions_current': "Total Current Deductions",
                'net_pay_current': "Current Net Pay",
                'total_earnings_ytd': "YTD Total Earnings", # Made these required for example
                'total_deductions_ytd': "YTD Total Deductions",
                'ytd_net_pay': "YTD Net Pay"
            }
            for field, display_name in required_static_fields.items():
                if not form_data_for_repopulation.get(field):
                    errors.append(f"{display_name} is required.")

            # Numeric Checks for Totals (even if JS calculates, server should verify)
            numeric_total_fields = [
                'total_earnings_current', 'total_deductions_current', 'net_pay_current',
                'total_earnings_ytd', 'total_deductions_ytd', 'ytd_net_pay'
            ]
            for field_key in numeric_total_fields:
                value_str = form_data_for_repopulation.get(field_key, '').strip()
                if value_str: # Only validate if present (required check handles absence)
                    try:
                        # Net pay can be negative, others typically positive or zero
                        if field_key == 'net_pay_current' or field_key == 'ytd_net_pay':
                             float(value_str)
                        else:
                            val = float(value_str)
                            if val < 0:
                                 errors.append(f"{required_static_fields.get(field_key, field_key)} must be zero or positive.")
                    except ValueError:
                        errors.append(f"{required_static_fields.get(field_key, field_key)} must be a valid number.")
                # If field is required and empty, it's already caught by required_static_fields check

            if errors:
                for error in errors:
                    flash(error, 'error')
                return render_template('generate_check_stub_form.html', title='Generate Check Stub', form_data=form_data_for_repopulation)

            pdf_bytes = generate_check_stub(parsed_data)

            if pdf_bytes:
                return send_file(
                    io.BytesIO(pdf_bytes),
                    mimetype='application/pdf',
                    as_attachment=True,
                    download_name=f"check_stub_{parsed_data.get('check_number', 'generated')}.pdf"
                )
            else:
                flash('Failed to generate check stub PDF. An internal error occurred or task timed out. Please check server logs.', 'error')
                return render_template('generate_check_stub_form.html', title='Generate Check Stub', form_data=form_data_for_repopulation)

        except Exception as e:
            app.logger.error(f"Error generating check stub: {e}", exc_info=True)
            flash(f'An unexpected error occurred: {e}', 'error')
            return redirect(url_for('generate_check_stub_route'))

    return render_template('generate_check_stub_form.html', title='Generate Check Stub')

@app.route('/generate/bank_statement', methods=['GET', 'POST'])
def generate_bank_statement_route():
    if request.method == 'POST':
        try:
            form_data_for_repopulation = request.form
            form_data_dict = request.form.to_dict()
            errors = []
            parsed_data = form_data_dict.copy() # Start with all flat fields

            # --- Custom Parsing for Transactions to match JS naming ---
            raw_transactions = []
            trx_idx = 1
            while True:
                desc_key = f'trx_desc_{trx_idx}'
                date_key = f'trx_date_{trx_idx}'

                if not form_data_for_repopulation.get(desc_key) and not form_data_for_repopulation.get(date_key):
                    break # Stop if key fields for this index are missing

                item_data = {
                    'description': form_data_for_repopulation.get(desc_key, ''),
                    'date': form_data_for_repopulation.get(date_key, ''),
                    'withdrawal_amount': form_data_for_repopulation.get(f'trx_withdrawal_{trx_idx}', ''),
                    'deposit_amount': form_data_for_repopulation.get(f'trx_deposit_{trx_idx}', ''),
                    'running_balance': form_data_for_repopulation.get(f'trx_balance_{trx_idx}', '')
                }

                # Validation for this specific transaction item
                if not item_data['description']:
                    errors.append(f"Description for Transaction {trx_idx} is required.")
                if not item_data['date']:
                    errors.append(f"Date for Transaction {trx_idx} is required.")
                if not item_data['running_balance']:
                    errors.append(f"Running Balance for Transaction {trx_idx} is required.")
                else:
                    try:
                        float(item_data['running_balance'])
                    except ValueError:
                        errors.append(f"Running Balance for Transaction {trx_idx} must be a valid number.")

                for amount_field_key, display_field_name in [
                    ('withdrawal_amount', 'Withdrawal Amount'),
                    ('deposit_amount', 'Deposit Amount')
                ]:
                    amount_val_str = item_data[amount_field_key]
                    if amount_val_str: # If provided
                        try:
                            val = float(amount_val_str)
                            if val < 0:
                                errors.append(f"{display_field_name} for Transaction {trx_idx} must be zero or positive.")
                        except ValueError:
                             errors.append(f"{display_field_name} for Transaction {trx_idx} must be a valid number.")

                raw_transactions.append(item_data)
                trx_idx += 1
                if trx_idx > 50: # Safety break
                    errors.append("Exceeded maximum number of transaction items.")
                    break
            parsed_data['transactions'] = raw_transactions
            # --- End Custom Transaction Parsing ---


            # Static Required Fields & Numeric Checks
            static_required_fields = {
                'bank_name': "Bank Name", 'account_holder_name': "Account Holder Name",
                'account_number': "Account Number", 'statement_date': "Statement Date",
                'statement_period_start': "Period Start Date", 'statement_period_end': "Period End Date",
                'opening_balance': "Opening Balance", 'closing_balance': "Closing Balance"
            }
            for field, display_name in static_required_fields.items():
                if not form_data_for_repopulation.get(field):
                    errors.append(f"{display_name} is required.")

            numeric_static_fields = { # Display Name, can_be_negative
                'opening_balance': ("Opening Balance", True), 'closing_balance': ("Closing Balance", True),
                'total_deposits': ("Total Deposits (Summary)", False), # Optional, but numeric if present
                'total_withdrawals': ("Total Withdrawals (Summary)", False) # Optional, but numeric if present
            }
            for field, (display_name, can_be_negative) in numeric_static_fields.items():
                value_str = form_data_for_repopulation.get(field, '').strip()
                if value_str: # If field is filled (optional fields might be blank)
                    try:
                        val = float(value_str)
                        if not can_be_negative and val < 0:
                            errors.append(f"{display_name} must be zero or positive.")
                    except ValueError:
                        errors.append(f"{display_name} must be a valid number.")
                elif field in ['opening_balance', 'closing_balance']: # These are required AND numeric
                     if not form_data_for_repopulation.get(field): # Already caught by static_required_fields if empty
                        pass
                     else: # Exists but couldn't be parsed by float() if it got here with error
                        errors.append(f"{display_name} must be a valid number.")

            # Parse Summary Messages (from textarea, one per line) - This was part of the old logic, ensure it's still here
            summary_messages_str = form_data_for_repopulation.get('summary_messages', '') # Use form_data_for_repopulation
            parsed_data['summary_messages'] = [msg.strip() for msg in summary_messages_str.splitlines() if msg.strip()]


            if errors:
                for error in errors:
                    flash(error, 'error')
                return render_template('generate_bank_statement_form.html', title='Generate Bank Statement', form_data=form_data_for_repopulation)

            # Proceed with PDF generation
            pdf_bytes = generate_bank_statement(parsed_data) # parsed_data contains original strings for amounts

            if pdf_bytes:
                return send_file(
                    io.BytesIO(pdf_bytes),
                    mimetype='application/pdf',
                    as_attachment=True,
                    download_name=f"bank_statement_{parsed_data.get('account_number', 'generated').replace(' ', '_')}.pdf"
                )
            else:
                flash('Failed to generate bank statement PDF. Rendering may have timed out or an error occurred. Check server logs.', 'error')
                return render_template('generate_bank_statement_form.html', title='Generate Bank Statement', form_data=form_data_for_repopulation)

        except Exception as e:
            app.logger.error(f"Error generating bank statement: {e}", exc_info=True)
            flash(f'An unexpected error occurred: {e}', 'error')
            return redirect(url_for('generate_bank_statement_route'))

    return render_template('generate_bank_statement_form.html', title='Generate Bank Statement')

@app.route('/generate/w2', methods=['GET', 'POST'])
def generate_w2_route():
    if request.method == 'POST':
        try:
            form_data_for_repopulation = request.form # Use this for repopulating template
            errors = []

            # Data to be passed to the generator if validation succeeds
            validated_data = {}

            # --- 1. Static Required Fields & Basic Format Checks ---
            required_fields = {
                'form_year': "Form Year", 'employer_ein': "Employer EIN",
                'employer_name_line1': "Employer's Name (Line 1)",
                'employer_address_line1': "Employer Address (Line 1)", 'employer_city': "Employer City",
                'employer_state_code': "Employer State Code", 'employer_zip_code': "Employer ZIP Code",
                'employee_ssn': "Employee SSN", 'employee_name_first': "Employee First Name",
                'employee_name_last': "Employee Last Name",
                'employee_address_line1': "Employee Address (Line 1)", 'employee_city': "Employee City",
                'employee_state_code': "Employee State Code", 'employee_zip_code': "Employee ZIP Code",
                'wages_tips_other_comp': "Box 1 (Wages, tips, other comp.)",
                'federal_income_tax_withheld': "Box 2 (Federal income tax withheld)",
                'social_security_wages': "Box 3 (Social security wages)",
                'social_security_tax_withheld': "Box 4 (Social security tax withheld)",
                'medicare_wages_and_tips': "Box 5 (Medicare wages and tips)",
                'medicare_tax_withheld': "Box 6 (Medicare tax withheld)"
            }
            for field, display_name in required_fields.items():
                value = form_data_for_repopulation.get(field, '').strip()
                if not value:
                    errors.append(f"{display_name} is required.")
                validated_data[field] = value # Store it for now, further format checks below

            # Optional static fields (just copy them if present)
            optional_static_fields = [
                'copy_designation', 'control_number', 'employer_name_line2', 'employer_address_line2',
                'employer_zip_code_ext', 'employee_name_suffix', 'employee_address_line2',
                'employee_zip_code_ext', 'social_security_tips', 'allocated_tips',
                'verification_code', 'dependent_care_benefits', 'nonqualified_plans'
            ]
            for field in optional_static_fields:
                validated_data[field] = form_data_for_repopulation.get(field, '').strip()

            # --- 2. Format/Pattern Checks for specific static fields ---
            year_str = validated_data.get('form_year','')
            if year_str and (not year_str.isdigit() or len(year_str) != 4):
                errors.append("Form Year must be 4 digits.")

            # EIN: XX-XXXXXXX
            ein_str = validated_data.get('employer_ein','')
            if ein_str and not (len(ein_str) == 10 and ein_str[2] == '-' and ein_str.replace('-', '').isdigit()):
                errors.append("Employer EIN must be in XX-XXXXXXX format.")

            # SSN: XXX-XX-XXXX
            ssn_str = validated_data.get('employee_ssn','')
            if ssn_str and not (len(ssn_str) == 11 and ssn_str[3] == '-' and ssn_str[6] == '-' and ssn_str.replace('-', '').isdigit()):
                errors.append("Employee SSN must be in XXX-XX-XXXX format.")

            for field_key, display_name in [('employer_state_code', 'Employer State Code'), ('employee_state_code', 'Employee State Code')]:
                state_code = validated_data.get(field_key,'')
                if state_code and not (len(state_code) == 2 and state_code.isalpha() and state_code.isupper()):
                    errors.append(f"{display_name} must be 2 uppercase letters.")

            for field_key, display_name in [('employer_zip_code', 'Employer ZIP'), ('employee_zip_code', 'Employee ZIP')]:
                zip_code = validated_data.get(field_key,'')
                if zip_code and not (len(zip_code) == 5 and zip_code.isdigit()):
                    errors.append(f"{display_name} must be 5 digits.")

            for field_key, display_name in [('employer_zip_code_ext', 'Employer ZIP Ext.'), ('employee_zip_code_ext', 'Employee ZIP Ext.')]:
                zip_ext = validated_data.get(field_key,'')
                if zip_ext and not (len(zip_ext) == 4 and zip_ext.isdigit()): # Only validate if present
                    errors.append(f"{display_name} must be 4 digits if provided.")


            # --- 3. Numeric Field Checks (for wages, taxes etc.) ---
            # Includes fields from Box 1-8, 10, 11. More added for state/local later.
            monetary_fields_positive_or_zero = [
                'wages_tips_other_comp', 'federal_income_tax_withheld', 'social_security_wages',
                'social_security_tax_withheld', 'medicare_wages_and_tips', 'medicare_tax_withheld',
                'social_security_tips', 'allocated_tips', 'dependent_care_benefits', 'nonqualified_plans'
            ]
            for field in monetary_fields_positive_or_zero:
                value_str = validated_data.get(field, '') # Already in validated_data from required/optional
                if value_str: # If present (optional fields might be empty)
                    try:
                        val = float(value_str)
                        if val < 0:
                            errors.append(f"{required_fields.get(field, field)} must be zero or positive.")
                    except ValueError:
                        errors.append(f"{required_fields.get(field, field)} must be a valid number.")

            # --- 4. Box 12 Items ---
            validated_data['box12_items'] = []
            for i in range(1, 5): # Max 4 items (12a, 12b, 12c, 12d)
                code = form_data_for_repopulation.get(f'box12_{i}_code', '').strip()
                amount_str = form_data_for_repopulation.get(f'box12_{i}_amount', '').strip()
                if code or amount_str: # If either part of a Box 12 item is present, validate it
                    if not code:
                        errors.append(f"Code for Box 12 Item {i} is required if amount is present.")
                    # TODO: Add validation for code format if known (e.g. 1 or 2 chars, often uppercase)
                    if not amount_str:
                        errors.append(f"Amount for Box 12 Item {i} (Code: {code}) is required if code is present.")
                    else:
                        try:
                            val = float(amount_str)
                            # Amounts in Box 12 can be various things, typically positive.
                            if val < 0: errors.append(f"Amount for Box 12 Item {i} (Code: {code}) should generally be zero or positive.")
                        except ValueError:
                            errors.append(f"Amount for Box 12 Item {i} (Code: {code}) must be a valid number.")
                    if code and amount_str: # Only add if both parts were somewhat there
                         validated_data['box12_items'].append({'code': code, 'amount': amount_str})

            # --- 5. Box 13 Checkboxes ---
            validated_data['statutory_employee_checkbox'] = True if form_data_for_repopulation.get('statutory_employee_checkbox') == 'true' else False
            validated_data['retirement_plan_checkbox'] = True if form_data_for_repopulation.get('retirement_plan_checkbox') == 'true' else False
            validated_data['third_party_sick_pay_checkbox'] = True if form_data_for_repopulation.get('third_party_sick_pay_checkbox') == 'true' else False

            # --- 6. Box 14 Items ---
            validated_data['box14_items'] = []
            for i in range(1, 4): # Max 3 items from form
                desc = form_data_for_repopulation.get(f'box14_{i}_desc', '').strip()
                amount_str = form_data_for_repopulation.get(f'box14_{i}_amount', '').strip()
                if desc or amount_str:
                    if not desc:
                        errors.append(f"Description for Box 14 Item {i} is required if amount is present.")
                    if not amount_str:
                        errors.append(f"Amount for Box 14 Item {i} (Desc: {desc}) is required if description is present.")
                    else:
                        try:
                            float(amount_str) # Can be positive or negative
                        except ValueError:
                            errors.append(f"Amount for Box 14 Item {i} (Desc: {desc}) must be a valid number.")
                    if desc and amount_str:
                        validated_data['box14_items'].append({'description': desc, 'amount': amount_str})

            # --- 7. State & Local Info ---
            for i in range(1, 3): # state1, state2
                state_prefix = f'state{i}'
                state_code = form_data_for_repopulation.get(f'{state_prefix}_employer_state', '').strip()
                state_id = form_data_for_repopulation.get(f'{state_prefix}_employer_state_id', '').strip()
                state_wages_str = form_data_for_repopulation.get(f'{state_prefix}_state_wages_tips', '').strip()
                state_tax_str = form_data_for_repopulation.get(f'{state_prefix}_state_income_tax', '').strip()

                if state_code or state_id or state_wages_str or state_tax_str: # If any part of state info is present
                    if not state_code: errors.append(f"State Code for State Info {i} is required if other state fields are filled.")
                    elif not (len(state_code) == 2 and state_code.isalpha() and state_code.isupper()): errors.append(f"State Code for State Info {i} must be 2 uppercase letters.")
                    if not state_id: errors.append(f"Employer's State ID for State Info {i} is required.")
                    if not state_wages_str: errors.append(f"State Wages for State Info {i} are required.")
                    else:
                        try:
                            if float(state_wages_str) < 0: errors.append(f"State Wages for State Info {i} must be zero or positive.")
                        except ValueError: errors.append(f"State Wages for State Info {i} must be a valid number.")
                    if not state_tax_str: errors.append(f"State Income Tax for State Info {i} is required.")
                    else:
                        try:
                            if float(state_tax_str) < 0: errors.append(f"State Income Tax for State Info {i} must be zero or positive.")
                        except ValueError: errors.append(f"State Income Tax for State Info {i} must be a valid number.")

                    validated_data[f'state_info_{i}'] = {
                        'employer_state': state_code, 'employer_state_id': state_id,
                        'state_wages_tips': state_wages_str, 'state_income_tax': state_tax_str
                    }
                else: # Ensure key exists if template expects it, even if empty
                    validated_data[f'state_info_{i}'] = {}


            for i in range(1, 3): # local1, local2
                local_prefix = f'local{i}'
                locality_name = form_data_for_repopulation.get(f'{local_prefix}_locality_name', '').strip()
                local_wages_str = form_data_for_repopulation.get(f'{local_prefix}_local_wages_tips', '').strip()
                local_tax_str = form_data_for_repopulation.get(f'{local_prefix}_local_income_tax', '').strip()

                if locality_name or local_wages_str or local_tax_str:
                    if not locality_name: errors.append(f"Locality Name for Local Info {i} is required.")
                    if not local_wages_str: errors.append(f"Local Wages for Local Info {i} are required.")
                    else:
                        try:
                            if float(local_wages_str) < 0: errors.append(f"Local Wages for Local Info {i} must be zero or positive.")
                        except ValueError: errors.append(f"Local Wages for Local Info {i} must be a valid number.")
                    if not local_tax_str: errors.append(f"Local Income Tax for Local Info {i} is required.")
                    else:
                        try:
                            if float(local_tax_str) < 0: errors.append(f"Local Income Tax for Local Info {i} must be zero or positive.")
                        except ValueError: errors.append(f"Local Income Tax for Local Info {i} must be a valid number.")

                    validated_data[f'local_info_{i}'] = {
                        'local_wages_tips': local_wages_str, 'local_income_tax': local_tax_str,
                        'locality_name': locality_name
                    }
                else: # Ensure key exists
                    validated_data[f'local_info_{i}'] = {}


            if errors:
                for error in errors:
                    flash(error, 'error')
                return render_template('generate_w2_form.html', title='Generate W-2 Form', form_data=form_data_for_repopulation)

            # If validation passes, proceed to generate PDF
            pdf_bytes = generate_w2_form(validated_data)
            # ... (rest of PDF serving logic from existing route) ...
            # ... (ensure the success case and the "Failed to generate W-2 PDF" case still use form_data_for_repopulation for consistency if re-rendering)
            # Corrected: use validated_data for PDF name, and form_data_for_repopulation for re-rendering on PDF gen failure

            if pdf_bytes:
                return send_file(
                    io.BytesIO(pdf_bytes),
                    mimetype='application/pdf',
                    as_attachment=True,
                    download_name=f"W2_form_{validated_data.get('form_year', '')}_{validated_data.get('employee_name_last', 'generated')}.pdf"
                )
            else:
                flash('Failed to generate W-2 PDF. Rendering may have timed out or an error occurred. Check server logs.', 'error')
                return render_template('generate_w2_form.html', title='Generate W-2 Form', form_data=form_data_for_repopulation)

        except Exception as e:
            app.logger.error(f"Error generating W-2 form: {e}", exc_info=True)
            flash(f'An unexpected error occurred: {e}', 'error')
            return redirect(url_for('generate_w2_route'))

    return render_template('generate_w2_form.html', title='Generate W-2 Form')

@app.route('/generate/income_statement', methods=['GET', 'POST'])
def generate_income_statement_route():
    if request.method == 'POST':
        try:
            form_data = request.form.to_dict()
            parsed_data = form_data.copy() # Copy flat fields first

            # Helper function for parsing list items
            def parse_list_items(prefix, count_limit=10): # Limit to avoid abuse if someone crafts many fields
                items = []
                idx = 1
                while idx <= count_limit:
                    desc_key = f'{prefix}_{idx}_desc'
                    amount_key = f'{prefix}_{idx}_amount'

                    desc = form_data.get(desc_key)
                    amount = form_data.get(amount_key)

                    if desc and amount is not None: # Amount can be "0.00"
                        items.append({'description': desc, 'amount': amount})
                        idx += 1
                    else:
                        # If primary field (desc) is missing for current index, stop.
                        break
                return items

            parsed_data['revenue_items'] = parse_list_items('revenue')
            parsed_data['cogs_items'] = parse_list_items('cogs')
            parsed_data['operating_expense_items'] = parse_list_items('opex')
            parsed_data['other_income_expense_items'] = parse_list_items('otherincex')

            # Basic validation
            if not parsed_data.get('company_name') or not parsed_data.get('period_covered') or \
               not parsed_data.get('total_revenue') or not parsed_data.get('net_income'):
                flash('Missing required fields for Income Statement (e.g., Company Name, Period, Total Revenue, Net Income).', 'error')
                return redirect(url_for('generate_income_statement_route'))

            pdf_bytes = generate_income_statement(parsed_data)

            if pdf_bytes:
                return send_file(
                    io.BytesIO(pdf_bytes),
                    mimetype='application/pdf',
                    as_attachment=True,
                    download_name=f"Income_Statement_{parsed_data.get('company_name', 'generated').replace(' ', '_')}.pdf"
                )
            else:
                flash('Failed to generate Income Statement PDF. Rendering may have timed out or an error occurred.', 'error')
                return redirect(url_for('generate_income_statement_route'))

        except Exception as e:
            app.logger.error(f"Error generating Income Statement: {e}", exc_info=True)
            flash(f'An unexpected error occurred: {e}', 'error')
            return redirect(url_for('generate_income_statement_route'))

    return render_template('generate_income_statement_form.html', title='Generate Income Statement')

@app.route('/convert/pdf-to-png', methods=['GET', 'POST']) # Ensure this is the correct route name from previous step
def convert_pdf_to_png_route():
    # --- Cleanup old generated PNG directories ---
    try:
        now = time.time()
        # PNG_OUTPUT_FOLDER_ABS is like 'financial_document_generator/static/generated_pngs/'
        # It should be defined globally in the script, e.g.,
        # PNG_OUTPUT_FOLDER_ABS = os.path.join(app.static_folder, PNG_OUTPUT_FOLDER_REL_STATIC)

        cleanup_threshold_seconds = 3600 # 1 hour (3600 seconds)

        if os.path.exists(PNG_OUTPUT_FOLDER_ABS): # Ensure base folder exists
            for dirname in os.listdir(PNG_OUTPUT_FOLDER_ABS):
                dirpath = os.path.join(PNG_OUTPUT_FOLDER_ABS, dirname)
                if os.path.isdir(dirpath): # Ensure it's a directory (UUID subfolders)
                    try:
                        dir_mod_time = os.path.getmtime(dirpath)
                        if (now - dir_mod_time) > cleanup_threshold_seconds:
                            shutil.rmtree(dirpath)
                            app.logger.info(f"Successfully cleaned up old PNG directory: {dirpath}")
                    except Exception as e_inner_cleanup:
                        # Log error for specific directory, but continue trying to clean others
                        app.logger.warning(f"Error during cleanup of individual directory {dirpath}: {e_inner_cleanup}")
    except Exception as e_outer_cleanup:
        # Log error if the cleanup process itself fails at a higher level (e.g., listing directories)
        # Set exc_info=False or limit its verbosity for cleanup tasks to avoid flooding logs.
        app.logger.error(f"Error during PNG cleanup scan: {e_outer_cleanup}", exc_info=False)
    # --- End cleanup ---
        # TESTING NOTE FOR PNG CLEANUP:
        # To manually test this cleanup logic:
        # 1. Ensure `PNG_OUTPUT_FOLDER_ABS` (e.g., `static/generated_pngs/`) exists.
        # 2. Manually create a few subdirectories inside it with UUID-like names
        #    (e.g., `static/generated_pngs/some-uuid-1234/`). Add some dummy files inside them.
        # 3. Modify the `last modification time` of one or more of these test subdirectories
        #    to be older than the `cleanup_threshold_seconds` (e.g., >1 hour ago).
        #    On Linux/macOS, this can be done with the `touch` command. For example, to set
        #    a directory's modification time to 2 hours ago:
        #    `touch -mt $(date -d '2 hours ago' +'%Y%m%d%H%M.%S') static/generated_pngs/some-uuid-1234`
        #    (Adjust path and command for your OS if different).
        # 4. Access the `/convert/pdf-to-png` route in the web application (either by loading
        #    the form or submitting a new conversion).
        # 5. Check the server logs for messages about directory cleanup.
        # 6. Verify that the old test subdirectories have been deleted from the file system,
        #    while newer ones (if any) remain.
        # Automated testing for this time-based cleanup in a short-lived test environment
        # is complex and typically requires mocking `time.time()` and `os.path.getmtime()`,
        # or a dedicated integration test setup that can manipulate file system timestamps.

    # Existing logic starts here
    if request.method == 'POST':
        if 'pdf_file' not in request.files: # This line and below is existing code
            flash('No file part in the request.', 'error')
            return redirect(request.url)

        file = request.files['pdf_file']
        if file.filename == '':
            flash('No selected file.', 'error')
            return redirect(request.url)

        if file and file.filename.lower().endswith('.pdf'):
            filename = secure_filename(file.filename)
            uploaded_pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            saved_uploaded_pdf_path = None # To keep track if file was actually saved

            try:
                file.save(uploaded_pdf_path)
                saved_uploaded_pdf_path = uploaded_pdf_path # Mark as saved

                # Create a unique sub-directory for this conversion's PNGs
                # This directory will be inside static/generated_pngs/
                unique_conversion_id = str(uuid.uuid4())
                specific_png_output_dir_abs = os.path.join(PNG_OUTPUT_FOLDER_ABS, unique_conversion_id)
                os.makedirs(specific_png_output_dir_abs, exist_ok=True)
                # TODO: This `specific_png_output_dir_abs` and its contents (the generated PNGs for this specific request)
                #       are not automatically cleaned up by the current logic after the user has viewed/downloaded them.
                #       Refer to cleanup strategies documented near the definition of PNG_OUTPUT_FOLDER_ABS.
                #       A very simple approach for these specific request folders might be to delete them after a short
                #       time if they are only meant for immediate viewing, but that requires more state management
                #       or a separate cleanup mechanism.

                # Call the converter
                png_file_paths = convert_pdf_to_png(saved_uploaded_pdf_path, specific_png_output_dir_abs)

                png_urls = []
                if png_file_paths: # Check if list is not None and not empty
                    for png_path in png_file_paths:
                        # Get filename relative to the 'specific_png_output_dir_abs'
                        png_filename = os.path.basename(png_path)
                        # Construct URL relative to static folder
                        # e.g., static/generated_pngs/<unique_id>/page_1.png
                        url = url_for('static', filename=os.path.join(PNG_OUTPUT_FOLDER_REL_STATIC, unique_conversion_id, png_filename))
                        png_urls.append(url)


                if png_urls:
                    flash(f'PDF converted to {len(png_urls)} PNG image(s).', 'success')
                    return render_template('display_pngs_results.html', title='Conversion Results', png_urls=png_urls)
                else:
                    # This case means convert_pdf_to_png ran but produced no images (e.g. blank PDF)
                    flash('Conversion ran but no PNG files were generated from the PDF.', 'warning')
                    # Still want to redirect to form, not results page
                    return redirect(url_for('convert_pdf_to_png_route'))


            except PDFInfoNotInstalledError:
                app.logger.error("Poppler is not installed or not in PATH.")
                flash('Conversion failed: Poppler (PDF rendering library) is not installed on the server.', 'error')
                return redirect(url_for('convert_pdf_to_png_route'))
            except Exception as e:
                app.logger.error(f"Error during PDF to PNG conversion: {e}", exc_info=True)
                flash(f'An error occurred during conversion: {e}', 'error')
                return redirect(url_for('convert_pdf_to_png_route'))
            finally:
                if saved_uploaded_pdf_path and os.path.exists(saved_uploaded_pdf_path):
                    try:
                        os.remove(saved_uploaded_pdf_path)
                        app.logger.info(f"Successfully deleted uploaded PDF: {saved_uploaded_pdf_path}")
                    except Exception as e_remove:
                        app.logger.error(f"Failed to delete uploaded PDF {saved_uploaded_pdf_path}: {e_remove}")
                # Note: Cleanup of generated PNGs in specific_png_output_dir_abs is NOT handled here.
                # That's a separate, more complex task (step 2.1 in the plan - document strategy).

        else:
            flash('Invalid file type. Please upload a PDF.', 'error')
            return redirect(request.url)

    return render_template('convert_pdf_form.html', title='Convert PDF to PNG')

@app.route('/generate/earning_statement', methods=['GET', 'POST'])
def generate_earning_statement_route():
    if request.method == 'POST':
        try:
            form_data_for_repopulation = request.form
            form_data_dict = request.form.to_dict()
            errors = []
            parsed_data = form_data_dict.copy()

            earning_field_defs = [
                ('desc', 'Description', True),
                ('hours', 'Hours', False, 'number_positive_or_zero'),
                ('rate', 'Rate', False, 'number_positive_or_zero'),
                ('current', 'Current Amount', True, 'number_positive_or_zero'),
                ('ytd', 'YTD Amount', False, 'number_positive_or_zero')
            ]
            deduction_field_defs = [
                ('desc', 'Description', True),
                ('current', 'Current Amount', True, 'number_positive_or_zero'),
                ('ytd', 'YTD Amount', False, 'number_positive_or_zero')
            ]

            parsed_earnings, earning_errors = parse_and_validate_dynamic_items(form_data_for_repopulation, 'earning', earning_field_defs)
            errors.extend(earning_errors)
            parsed_data['earnings'] = parsed_earnings

            parsed_deductions, deduction_errors = parse_and_validate_dynamic_items(form_data_for_repopulation, 'deduction', deduction_field_defs)
            errors.extend(deduction_errors)
            parsed_data['deductions'] = parsed_deductions

            required_static_fields = {
                'company_name': "Company Name", 'employee_name': "Employee Name",
                'pay_period_start': "Pay Period Start", 'pay_period_end': "Pay Period End", 'pay_date': "Pay Date",
                'total_earnings_current': "Total Current Earnings",
                'total_deductions_current': "Total Current Deductions",
                'net_pay_current': "Current Net Pay",
                'total_earnings_ytd': "YTD Total Earnings",
                'total_deductions_ytd': "YTD Total Deductions",
                'ytd_net_pay': "YTD Net Pay"
            }
            for field, display_name in required_static_fields.items():
                if not form_data_for_repopulation.get(field):
                    errors.append(f"{display_name} is required.")

            numeric_total_fields = [
                'total_earnings_current', 'total_deductions_current', 'net_pay_current',
                'total_earnings_ytd', 'total_deductions_ytd', 'ytd_net_pay'
            ]
            for field_key in numeric_total_fields:
                value_str = form_data_for_repopulation.get(field_key, '').strip()
                if value_str:
                    try:
                        if field_key == 'net_pay_current' or field_key == 'ytd_net_pay':
                             float(value_str)
                        else:
                            val = float(value_str)
                            if val < 0:
                                 errors.append(f"{required_static_fields.get(field_key, field_key)} must be zero or positive.")
                    except ValueError:
                        errors.append(f"{required_static_fields.get(field_key, field_key)} must be a valid number.")

            if errors:
                for error in errors:
                    flash(error, 'error')
                return render_template('generate_earning_statement_form.html', title='Generate Earning Statement', form_data=form_data_for_repopulation)

            pdf_bytes = generate_earning_statement(parsed_data)

            if pdf_bytes:
                return send_file(
                    io.BytesIO(pdf_bytes),
                    mimetype='application/pdf',
                    as_attachment=True,
                    download_name=f"Earning_Statement_{parsed_data.get('employee_id', 'generated')}.pdf"
                )
            else:
                flash('Failed to generate Earning Statement PDF. An internal error occurred or task timed out. Please check server logs.', 'error')
                return render_template('generate_earning_statement_form.html', title='Generate Earning Statement', form_data=form_data_for_repopulation)

        except Exception as e:
            app.logger.error(f"Error generating Earning Statement: {e}", exc_info=True)
            flash(f'An unexpected error occurred: {e}', 'error')
            return redirect(url_for('generate_earning_statement_route'))

    return render_template('generate_earning_statement_form.html', title='Generate Earning Statement')

if __name__ == '__main__':
    # Make sure to run this from the project root (financial_document_generator)
    # or adjust paths accordingly if run from financial_document_generator/app/
    # Example: python -m app.web_ui (from financial_document_generator directory)
    # Or: python web_ui.py (if run from financial_document_generator/app/ directory)
    print(f"Attempting to run Flask app...")
    print(f"Serving templates from: {app.template_folder}")
    print(f"Serving static files from: {app.static_folder}")
    print(f"Flask app name: {app.name}")
    # Important: Update route listing for debugging
    with app.app_context(): # Need app context for url_for and to iterate rules
         print(f"Routes: {[str(rule) for rule in app.url_map.iter_rules()]}")
    app.run(debug=True, host='0.0.0.0', port=5000)
