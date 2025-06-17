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
        try:
            form_data = request.form.to_dict()

            # Basic validation/conversion (more robust validation could be added)
            if not form_data.get('bank_name') or not form_data.get('payee_name') or \
               not form_data.get('amount_numeric') or not form_data.get('amount_words'):
                flash('Missing required check fields.', 'error')
                return redirect(url_for('generate_check_route'))

            # Call the existing generate_check function
            # Assuming it returns PDF bytes when output_path is None
            pdf_bytes = generate_check(form_data)

            if pdf_bytes:
                return send_file(
                    io.BytesIO(pdf_bytes),
                    mimetype='application/pdf',
                    as_attachment=True,
                    download_name=f"check_{form_data.get('check_number', 'generated')}.pdf"
                )
            else:
                flash('Failed to generate check PDF. Please check server logs.', 'error')
                return redirect(url_for('generate_check_route'))

        except Exception as e:
            app.logger.error(f"Error generating check: {e}", exc_info=True)
            flash(f'An unexpected error occurred: {e}', 'error')
            return redirect(url_for('generate_check_route'))

    return render_template('generate_check_form.html', title='Generate Check')

@app.route('/generate/check_stub', methods=['GET', 'POST'])
def generate_check_stub_route():
    if request.method == 'POST':
        try:
            form_data = request.form.to_dict()

            # --- Data Transformation for Dynamic Earnings & Deductions ---
            parsed_data = form_data.copy() # Start with all flat fields

            parsed_data['earnings'] = []
            earning_idx = 1
            while True:
                desc_key = f'earning{earning_idx}_desc'
                current_key = f'earning{earning_idx}_current'
                if desc_key in form_data and form_data[desc_key]: # Check if description exists and is not empty
                    parsed_data['earnings'].append({
                        'description': form_data[desc_key],
                        'hours': form_data.get(f'earning{earning_idx}_hours', ''),
                        'rate': form_data.get(f'earning{earning_idx}_rate', ''),
                        'current': form_data.get(current_key, ''), # Current amount should ideally exist if desc does
                        'ytd': form_data.get(f'earning{earning_idx}_ytd', '')
                    })
                    earning_idx += 1
                else:
                    # If a description is missing, assume no more earnings rows for this index.
                    # This handles cases where rows might be removed from the middle if JS doesn't re-index.
                    # A more robust way would be to count max index from keys if sparse indices are a concern.
                    # For now, sequential check is simpler if JS always adds sequentially.
                    break
                    # If we want to handle sparse indices (e.g. user removes row 1 but leaves row 2),
                    # we'd need to find all keys matching 'earningX_desc' and extract X.
                    # For now, this assumes JavaScript adds rows with contiguous indices starting from 1.

            parsed_data['deductions'] = []
            deduction_idx = 1
            while True:
                desc_key = f'deduction{deduction_idx}_desc'
                current_key = f'deduction{deduction_idx}_current'
                if desc_key in form_data and form_data[desc_key]:
                    parsed_data['deductions'].append({
                        'description': form_data[desc_key],
                        'current': form_data.get(current_key, ''),
                        'ytd': form_data.get(f'deduction{deduction_idx}_ytd', '')
                    })
                    deduction_idx += 1
                else:
                    break
            # --- End Data Transformation ---

            # Basic validation (can be enhanced)
            if not parsed_data.get('company_name') or not parsed_data.get('employee_name'):
                flash('Missing required check stub fields.', 'error')
                return redirect(url_for('generate_check_stub_route'))

            pdf_bytes = generate_check_stub(parsed_data)

            if pdf_bytes:
                return send_file(
                    io.BytesIO(pdf_bytes),
                    mimetype='application/pdf',
                    as_attachment=True,
                    download_name=f"check_stub_{parsed_data.get('check_number', 'generated')}.pdf"
                )
            else:
                flash('Failed to generate check stub PDF. Please check server logs.', 'error')
                return redirect(url_for('generate_check_stub_route'))

        except Exception as e:
            app.logger.error(f"Error generating check stub: {e}", exc_info=True)
            flash(f'An unexpected error occurred: {e}', 'error')
            return redirect(url_for('generate_check_stub_route'))

    return render_template('generate_check_stub_form.html', title='Generate Check Stub')

@app.route('/generate/bank_statement', methods=['GET', 'POST'])
def generate_bank_statement_route():
    if request.method == 'POST':
        try:
            form_data = request.form.to_dict()
            parsed_data = form_data.copy()

            # Parse Dynamic Transactions
            parsed_data['transactions'] = []
            trx_idx = 1
            while True:
                # Use the new field name convention from the updated HTML/JS (e.g., trx_date_1, trx_desc_1)
                date_key = f'trx_date_{trx_idx}'
                desc_key = f'trx_desc_{trx_idx}'

                trx_date = form_data.get(date_key)
                trx_desc = form_data.get(desc_key)

                # A transaction is considered present if its date and description are provided
                if trx_date and trx_desc:
                    parsed_data['transactions'].append({
                        'date': trx_date,
                        'description': trx_desc,
                        'withdrawal_amount': form_data.get(f'trx_withdrawal_{trx_idx}', ''),
                        'deposit_amount': form_data.get(f'trx_deposit_{trx_idx}', ''),
                        'running_balance': form_data.get(f'trx_balance_{trx_idx}', '')
                    })
                    trx_idx += 1
                else:
                    # Stop if a primary field (like date or description) for the current index is missing
                    break

            # Parse Summary Messages (from textarea, one per line)
            summary_messages_str = form_data.get('summary_messages', '')
            parsed_data['summary_messages'] = [msg.strip() for msg in summary_messages_str.splitlines() if msg.strip()]

            # Basic validation
            if not parsed_data.get('account_holder_name') or not parsed_data.get('account_number'):
                flash('Missing required bank statement fields (e.g., Account Holder, Account Number).', 'error')
                return redirect(url_for('generate_bank_statement_route'))

            # Call the generator
            # This might be slow due to WeasyPrint rendering complex tables
            pdf_bytes = generate_bank_statement(parsed_data)

            if pdf_bytes:
                return send_file(
                    io.BytesIO(pdf_bytes),
                    mimetype='application/pdf',
                    as_attachment=True,
                    download_name=f"bank_statement_{parsed_data.get('account_number', 'generated')}.pdf"
                )
            else:
                flash('Failed to generate bank statement PDF. Rendering may have timed out or an error occurred. Check server logs.', 'error')
                return redirect(url_for('generate_bank_statement_route'))

        except Exception as e:
            app.logger.error(f"Error generating bank statement: {e}", exc_info=True)
            flash(f'An unexpected error occurred: {e}', 'error')
            return redirect(url_for('generate_bank_statement_route'))

    return render_template('generate_bank_statement_form.html', title='Generate Bank Statement')

@app.route('/generate/w2', methods=['GET', 'POST'])
def generate_w2_route():
    if request.method == 'POST':
        try:
            form_data = request.form
            parsed_data = {}

            # Simple fields
            simple_fields = [
                'form_year', 'copy_designation', 'control_number', 'employer_ein',
                'employer_name_line1', 'employer_name_line2', 'employer_address_line1', 'employer_address_line2',
                'employer_city', 'employer_state_code', 'employer_zip_code', 'employer_zip_code_ext',
                'employee_ssn', 'employee_name_first', 'employee_name_last', 'employee_name_suffix',
                'employee_address_line1', 'employee_address_line2', 'employee_city', 'employee_state_code',
                'employee_zip_code', 'employee_zip_code_ext',
                'wages_tips_other_comp', 'federal_income_tax_withheld', 'social_security_wages',
                'social_security_tax_withheld', 'medicare_wages_and_tips', 'medicare_tax_withheld',
                'social_security_tips', 'allocated_tips', 'verification_code',
                'dependent_care_benefits', 'nonqualified_plans'
            ]
            for field in simple_fields:
                parsed_data[field] = form_data.get(field, '')

            # Checkboxes for Box 13
            parsed_data['statutory_employee_checkbox'] = True if form_data.get('statutory_employee_checkbox') == 'true' else False
            parsed_data['retirement_plan_checkbox'] = True if form_data.get('retirement_plan_checkbox') == 'true' else False
            parsed_data['third_party_sick_pay_checkbox'] = True if form_data.get('third_party_sick_pay_checkbox') == 'true' else False

            # Box 12 items (list of dicts) - up to 4
            parsed_data['box12_items'] = []
            for i in range(1, 5):
                code = form_data.get(f'box12_{i}_code')
                amount = form_data.get(f'box12_{i}_amount')
                if code and amount: # Only add if both code and amount are present
                    parsed_data['box12_items'].append({'code': code, 'amount': amount})

            # Box 14 items (list of dicts) - up to 3
            parsed_data['box14_items'] = []
            for i in range(1, 4):
                desc = form_data.get(f'box14_{i}_desc')
                amount = form_data.get(f'box14_{i}_amount')
                if desc and amount: # Only add if both description and amount are present
                    parsed_data['box14_items'].append({'description': desc, 'amount': amount})

            # State Info (dictionaries)
            for i in range(1, 3): # state1, state2
                state_key_prefix = f'state{i}'
                if form_data.get(f'{state_key_prefix}_employer_state'): # Check if primary field for state exists
                    parsed_data[f'state_info_{i}'] = {
                        'employer_state': form_data.get(f'{state_key_prefix}_employer_state', ''),
                        'employer_state_id': form_data.get(f'{state_key_prefix}_employer_state_id', ''),
                        'state_wages_tips': form_data.get(f'{state_key_prefix}_state_wages_tips', ''),
                        'state_income_tax': form_data.get(f'{state_key_prefix}_state_income_tax', '')
                    }
                else: # Ensure the key exists even if empty, as template might expect it
                     parsed_data[f'state_info_{i}'] = {}


            # Local Info (dictionaries)
            for i in range(1, 3): # local1, local2
                local_key_prefix = f'local{i}'
                if form_data.get(f'{local_key_prefix}_locality_name'): # Check if primary field for local exists
                     parsed_data[f'local_info_{i}'] = {
                        'local_wages_tips': form_data.get(f'{local_key_prefix}_local_wages_tips', ''),
                        'local_income_tax': form_data.get(f'{local_key_prefix}_local_income_tax', ''),
                        'locality_name': form_data.get(f'{local_key_prefix}_locality_name', '')
                    }
                else: # Ensure the key exists even if empty
                     parsed_data[f'local_info_{i}'] = {}


            # Basic validation (can be more thorough)
            if not parsed_data.get('employer_ein') or not parsed_data.get('employee_ssn'):
                flash('Missing required W-2 fields (e.g., Employer EIN, Employee SSN).', 'error')
                return redirect(url_for('generate_w2_route'))

            pdf_bytes = generate_w2_form(parsed_data)

            if pdf_bytes:
                return send_file(
                    io.BytesIO(pdf_bytes),
                    mimetype='application/pdf',
                    as_attachment=True,
                    download_name=f"W2_form_{parsed_data.get('form_year', '')}_{parsed_data.get('employee_name_last', 'generated')}.pdf"
                )
            else:
                flash('Failed to generate W-2 PDF. Rendering may have timed out or an error occurred. Check server logs.', 'error')
                return redirect(url_for('generate_w2_route'))

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
            form_data = request.form.to_dict()
            # Data Transformation for Dynamic Earnings & Deductions (same as check_stub_route)
            parsed_data = form_data.copy()

            parsed_data['earnings'] = []
            earning_idx = 1
            while True:
                desc_key = f'earning{earning_idx}_desc'
                if desc_key in form_data and form_data[desc_key]:
                    parsed_data['earnings'].append({
                        'description': form_data[desc_key],
                        'hours': form_data.get(f'earning{earning_idx}_hours', ''),
                        'rate': form_data.get(f'earning{earning_idx}_rate', ''),
                        'current': form_data.get(f'earning{earning_idx}_current', ''),
                        'ytd': form_data.get(f'earning{earning_idx}_ytd', '')
                    })
                    earning_idx += 1
                else:
                    break

            parsed_data['deductions'] = []
            deduction_idx = 1
            while True:
                desc_key = f'deduction{deduction_idx}_desc'
                if desc_key in form_data and form_data[desc_key]:
                    parsed_data['deductions'].append({
                        'description': form_data[desc_key],
                        'current': form_data.get(f'deduction{deduction_idx}_current', ''),
                        'ytd': form_data.get(f'deduction{deduction_idx}_ytd', '')
                    })
                    deduction_idx += 1
                else:
                    break

            if not parsed_data.get('company_name') or not parsed_data.get('employee_name'):
                flash('Missing required Earning Statement fields.', 'error')
                return redirect(url_for('generate_earning_statement_route'))

            pdf_bytes = generate_earning_statement(parsed_data)

            if pdf_bytes:
                return send_file(
                    io.BytesIO(pdf_bytes),
                    mimetype='application/pdf',
                    as_attachment=True,
                    download_name=f"Earning_Statement_{parsed_data.get('employee_id', 'generated')}.pdf"
                )
            else:
                flash('Failed to generate Earning Statement PDF. Check server logs.', 'error')
                return redirect(url_for('generate_earning_statement_route'))

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
