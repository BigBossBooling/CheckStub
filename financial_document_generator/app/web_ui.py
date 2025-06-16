import os
from flask import Flask, render_template, url_for, request, send_file, flash, redirect
import io # For BytesIO if sending bytes directly
import uuid
from werkzeug.utils import secure_filename
from .check_generator import generate_check # Assuming check_generator is in the same 'app' package
from .check_stub_generator import generate_check_stub
from .converters import convert_pdf_to_png, PDFInfoNotInstalledError
from .bank_statement_generator import generate_bank_statement

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

@app.route('/convert/pdf-to-png', methods=['GET', 'POST'])
def convert_pdf_to_png_route():
    if request.method == 'POST':
        if 'pdf_file' not in request.files:
            flash('No file part in the request.', 'error')
            return redirect(request.url)

        file = request.files['pdf_file']
        if file.filename == '':
            flash('No selected file.', 'error')
            return redirect(request.url)

        if file and file.filename.lower().endswith('.pdf'):
            filename = secure_filename(file.filename)
            # Save uploaded PDF to a temporary location
            uploaded_pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            try:
                file.save(uploaded_pdf_path)

                # Create a unique sub-directory for this conversion's PNGs
                # This directory will be inside static/generated_pngs/
                unique_conversion_id = str(uuid.uuid4())
                specific_png_output_dir_abs = os.path.join(PNG_OUTPUT_FOLDER_ABS, unique_conversion_id)
                os.makedirs(specific_png_output_dir_abs, exist_ok=True)

                # Call the converter
                png_file_paths = convert_pdf_to_png(uploaded_pdf_path, specific_png_output_dir_abs)

                # Create URLs for the generated PNGs
                png_urls = []
                for png_path in png_file_paths:
                    # Get filename relative to the 'specific_png_output_dir_abs'
                    png_filename = os.path.basename(png_path)
                    # Construct URL relative to static folder
                    # e.g., static/generated_pngs/<unique_id>/page_1.png
                    url = url_for('static', filename=os.path.join(PNG_OUTPUT_FOLDER_REL_STATIC, unique_conversion_id, png_filename))
                    png_urls.append(url)

                # Clean up the uploaded PDF file after conversion
                # os.remove(uploaded_pdf_path) # TODO: Add robust cleanup later

                if png_urls:
                    flash(f'PDF converted to {len(png_urls)} PNG image(s).', 'success')
                    return render_template('display_pngs_results.html', title='Conversion Results', png_urls=png_urls)
                else:
                    flash('Conversion succeeded but no PNG files were generated.', 'warning')
                    return redirect(url_for('convert_pdf_to_png_route'))

            except PDFInfoNotInstalledError:
                app.logger.error("Poppler is not installed or not in PATH.")
                flash('Conversion failed: Poppler (PDF rendering library) is not installed on the server.', 'error')
                return redirect(url_for('convert_pdf_to_png_route'))
            except Exception as e:
                app.logger.error(f"Error during PDF to PNG conversion: {e}", exc_info=True)
                flash(f'An error occurred during conversion: {e}', 'error')
                # Clean up uploaded PDF if it exists and an error occurred during conversion part
                if os.path.exists(uploaded_pdf_path):
                    pass # os.remove(uploaded_pdf_path) # TODO: Add robust cleanup
                return redirect(url_for('convert_pdf_to_png_route'))
            finally:
                # More robust cleanup should be implemented (e.g. scheduled task for old files)
                # For now, uploaded PDF is not deleted to allow inspection on error.
                # if os.path.exists(uploaded_pdf_path):
                #    os.remove(uploaded_pdf_path)
                pass

        else:
            flash('Invalid file type. Please upload a PDF.', 'error')
            return redirect(request.url)

    return render_template('convert_pdf_form.html', title='Convert PDF to PNG')

@app.route('/generate/bank_statement', methods=['GET', 'POST'])
def generate_bank_statement_route():
    if request.method == 'POST':
        try:
            form_data = request.form.to_dict()
            parsed_data = form_data.copy()

            # Parse Transactions (up to 3 from the form)
            parsed_data['transactions'] = []
            for i in range(1, 4): # Corresponds to trx1, trx2, trx3 in form
                trx_date = form_data.get(f'trx{i}_date')
                trx_desc = form_data.get(f'trx{i}_desc')
                # Only add transaction if at least date and description are present
                if trx_date and trx_desc:
                    parsed_data['transactions'].append({
                        'date': trx_date,
                        'description': trx_desc,
                        'withdrawal_amount': form_data.get(f'trx{i}_withdrawal', ''),
                        'deposit_amount': form_data.get(f'trx{i}_deposit', ''),
                        'running_balance': form_data.get(f'trx{i}_balance', '')
                    })

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
