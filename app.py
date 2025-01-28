from flask import Flask, request, jsonify, render_template, send_file, url_for
import pandas as pd
import io
import json
import os
import tempfile
app = Flask(__name__)

# Function to process the Excel file and convert it to JSON
def process_excel(file):
    employee_details = pd.read_excel(file, sheet_name='Employee Details ').head(36)
    garnishment_order_details = pd.read_excel(file, sheet_name='Garnishment Order details').head(36)
    payroll_batch_details = pd.read_excel(file, sheet_name='Payroll Batch Details', header=[0, 1]).head(36)

    concatenated_df = pd.concat([employee_details, garnishment_order_details, payroll_batch_details], axis=1)

    concatenated_df.columns = concatenated_df.columns.map(lambda x: '_'.join(str(i) for i in x) if isinstance(x, tuple) else x)
    concatenated_df.rename(columns={
        "Deductions 401K": 'Deductions 401(K)',
        "Deductions_MedicalInsurance": 'medical_insurance',
        "Deductions_SDI": 'SDI',
        "Deductions_UnionDues": 'union_dues',
        "Deductions_Voluntary": 'voluntary',
        "GrossPay_Unnamed: 6_level_1": 'gross_pay',
        "NetPay_Unnamed: 17_level_1": 'net_pay',
        "PayPeriod_Unnamed: 3_level_1": 'Pay cycle',
        "PayPeriod": "pay_period",
        "PayDate_Unnamed: 5_level_1": 'Pay Date',
        "PayrollDate_Unnamed: 4_level_1": 'Payroll Date',
        "State Unnamed: 2_level_1": 'state',
        'Taxes_FederalIncomeTax': 'federal_income_tax',
        'Taxes_StateTax': 'state_tax',
        'Taxes_LocalTax': 'local_tax',
        'Taxes_SocialSecurityTax': 'social_security_tax',
        'Taxes_MedicareTax': 'medicare_tax',
    }, inplace=True)

    concatenated_df.rename(columns={
        'EEID': 'ee_id',
        "CID": 'cid',
        'IsBlind': 'is_blind',
        'Age': 'age',
        'FilingStatus': 'filing_status',
        'SupportSecondFamily': 'support_second_family',
        'SpouseAge ': 'spouse_age',
        'IsSpouseBlind': 'is_spouse_blind',
        'Amount': 'amount',
        'ArrearsGreaterThan12Weeks?': 'arrears_greater_than_12_weeks',
        "CaseID": 'case_id',
        'TotalExemptions': 'no_of_exception_for_self',
        'WorkState': 'Work State',
        'HomeState': 'Home State',
        'NumberofStudentLoan': 'no_of_student_default_loan',
        'No.OFExemptionIncludingSelf': 'no_of_exception_for_self',
        "Type": "garnishment_type",
        "ArrearAmount": "arrear",
        "State": "state"
    }, inplace=True)

    concatenated_df = concatenated_df.loc[:, ~concatenated_df.columns.duplicated(keep='first')]

    concatenated_df['filing_status'] = concatenated_df['filing_status'].str.lower().str.replace(' ', '_')
    concatenated_df['batch_id'] = "B001A"
    concatenated_df['arrears_greater_than_12_weeks'] = concatenated_df['arrears_greater_than_12_weeks'].replace({True: "Yes", False: "No"})
    concatenated_df['support_second_family'] = concatenated_df['support_second_family'].replace({True: "Yes", False: "No"})
    concatenated_df['garnishment_type'] = concatenated_df['garnishment_type'].replace({'Student Loan': "student default loan"})
    concatenated_df['filing_status'] = concatenated_df['filing_status'].apply(lambda x: 'married_filing_separate' if x == 'married_filing_separate_return' else x)

    output_json = {}
    for (batch_id, cid), group in concatenated_df.groupby(["batch_id", "cid"]):
        employees = []
        for _, row in group.iterrows():
            employee = {
                "ee_id": row["ee_id"],
                "gross_pay": row["gross_pay"],
                "state": row["state"],
                "no_of_exemption_for_self": row["no_of_exception_for_self"],
                "pay_period": row["pay_period"],
                "filing_status": row["filing_status"],
                "net_pay": row["net_pay"],
                "payroll_taxes": [
                    {"federal_income_tax": row["federal_income_tax"]},
                    {"social_security_tax": row["social_security_tax"]},
                    {"medicare_tax": row["medicare_tax"]},
                    {"state_tax": row["state_tax"]},
                    {"local_tax": row["local_tax"]}
                ],
                "payroll_deductions": {
                    "medical_insurance": row["medical_insurance"]
                },
                "age": row["age"],
                "is_blind": row["is_blind"],
                "is_spouse_blind": row["is_spouse_blind"],
                "spouse_age": row["spouse_age"],
                "support_second_family": row["support_second_family"],
                "no_of_student_default_loan": row["no_of_student_default_loan"],
                "arrears_greater_than_12_weeks": row["arrears_greater_than_12_weeks"],
                "garnishment_data": [
                    {
                        "type": row["garnishment_type"],
                        "data": [
                            {
                                "case_id": row["case_id"],
                                "amount": row.get("Amount1", None),
                                "arrear": row.get("ArrearAmount1", None)
                            },
                            {
                                "case_id": row["case_id"],
                                "amount": row.get("Amount2", None),
                                "arrear": row.get("ArrearAmount2", None)
                            }
                        ]
                    }
                ]
            }
            employees.append(employee)

        if "cid" not in output_json:
            output_json["cid"] = {}
        output_json["cid"][cid] = {"employees": employees}

    output_json["batch_id"] = batch_id
    return output_json

@app.route('/')
def home():
    return render_template('index.html')

# @app.route('/convert', methods=['POST'])
# def convert():
#     if 'file' not in request.files:
#         return "No file uploaded", 400

#     file = request.files['file']

#     if file.filename == '':
#         return "No selected file", 400

#     # Process the Excel file in memory
#     output_json = process_excel(file)

#     # Convert JSON to a downloadable file
#     json_file = io.BytesIO()
#     # Use json.dumps to serialize output_json to a string, then encode it as bytes before writing to json_file
#     json_file.write(json.dumps(output_json, indent=2).encode('utf-8'))
#     json_file.seek(0)

#     return send_file(json_file, as_attachment=True, download_name="output.json", mimetype='application/json')



@app.route('/convert', methods=['POST'])
def convert():
    if 'file' not in request.files:
        return "No file uploaded", 400

    file = request.files['file']

    if file.filename == '':
        return "No selected file", 400

    # Process the Excel file in memory
    output_json = process_excel(file)

    # Create a temporary file to store the JSON output
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
    with open(temp_file.name, 'w', encoding='utf-8') as f:
        json.dump(output_json, f, indent=2)

    # Generate the download URL (Flask will automatically serve static files)
    download_url = url_for('download_json', filename=os.path.basename(temp_file.name), _external=True)
    
    # Return the download URL as part of the response
    return jsonify({'json_content': output_json, 'download_url': download_url})

@app.route('/download/<filename>')
def download_json(filename):
    # The file path will be relative to the temporary directory
    file_path = os.path.join(tempfile.gettempdir(), filename)
    return send_file(file_path, as_attachment=True, download_name=filename, mimetype='application/json')



if __name__ == '__main__':
    app.run(debug=True)
