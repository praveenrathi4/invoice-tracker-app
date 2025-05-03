
import streamlit as st
import pdfplumber
import requests
import re
import pandas as pd
from datetime import datetime
import os
from supplier_extractors import SUPPLIER_EXTRACTORS, SUPPLIER_SOA_EXTRACTORS, get_best_supplier_match

# Supabase Config
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")
TABLE_NAME = "invoices"

# Fetch dropdown values from Supabase
def get_dropdown_values(column, table):
    url = f"{SUPABASE_URL}/rest/v1/{table}?select={column}"
    headers = {
        "apikey": SUPABASE_API_KEY,
        "Authorization": f"Bearer {SUPABASE_API_KEY}"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return sorted(set(row[column] for row in response.json() if row[column]))
    return []

# Extract invoice using supplier-specific logic
def extract_invoice_data_from_pdf(file, supplier_name, company_name, is_invoice=True):
    with pdfplumber.open(file) as pdf:
        text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())

    extractor_map = SUPPLIER_EXTRACTORS if is_invoice else SUPPLIER_SOA_EXTRACTORS
    matched_supplier = get_best_supplier_match(text, extractor_map)

    if matched_supplier:
        st.info(f"📌 Matched Supplier Extractor: {matched_supplier} ({'Invoice' if is_invoice else 'SOA'})")
        return extractor_map[matched_supplier](file, supplier_name, company_name)

    st.warning("⚠️ No matching extractor found.")
    return {
        "supplier_name": supplier_name,
        "company_name": company_name,
        "invoice_no": None,
        "invoice_date": None,
        "due_date": None,
        "amount": None,
        "reference": None
    }

# Insert records into Supabase
def insert_batch_to_supabase(data_list):
    url = f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}"
    headers = {
        "apikey": SUPABASE_API_KEY,
        "Authorization": f"Bearer {SUPABASE_API_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    response = requests.post(url, json=data_list, headers=headers)
    return response.status_code, response.json()

# Streamlit UI
st.set_page_config(page_title="Invoice/SOA Uploader", layout="centered")
st.title("📄 Invoice/SOA Uploader & Tracker")

# Toggle checkbox for Invoice vs SOA
is_invoice = st.checkbox("Processing Invoices", value=True)

# Dropdowns for Supplier and Company with blank default
supplier_options = [""] + get_dropdown_values("name", "supplier_names")
company_options = [""] + get_dropdown_values("name", "company_names")

supplier_name = st.selectbox("Select Supplier Name", supplier_options, index=0)
company_name = st.selectbox("Select Company Name", company_options, index=0)

uploaded_files = st.file_uploader("Upload One or More PDF Files", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    if not supplier_name or not company_name:
        st.warning("Please select both Supplier Name and Company Name before processing.")
    else:
        extracted_rows = []
        for file in uploaded_files:
            extracted_data = extract_invoice_data_from_pdf(file, supplier_name, company_name, is_invoice)
            extracted_list = extracted_data if isinstance(extracted_data, list) else [extracted_data]

            for extracted in extracted_list:
                # Format dates
                for key in ["invoice_date", "due_date"]:
                    try:
                        if extracted.get(key):
                            extracted[key] = datetime.strptime(extracted[key], "%d %b %Y").strftime("%d/%m/%Y")
                    except:
                        pass

                # Parse amount safely
                raw_amount = extracted.get("amount")
                if isinstance(raw_amount, str):
                    try:
                        raw_amount = raw_amount.replace(",", "")
                        extracted["amount"] = float(raw_amount)
                    except:
                        st.warning(f"Invalid amount in file: {file.name}")
                        extracted["amount"] = None
                elif isinstance(raw_amount, (int, float)):
                    extracted["amount"] = float(raw_amount)
                else:
                    extracted["amount"] = None

                extracted["status"] = "Unpaid"
                extracted_rows.append(extracted)

        # Validation
        required_fields = ["invoice_no", "invoice_date", "amount"]
        valid_rows = [
            row for row in extracted_rows
            if all(k in row and row[k] not in [None, ""] for k in required_fields)
        ]
        invalid_rows = [row for row in extracted_rows if row not in valid_rows]

        st.subheader("🧾 Valid Extracted Data")
        if valid_rows:
            df_valid = pd.DataFrame(valid_rows)
            st.dataframe(df_valid)
        else:
            st.info("No valid data to show.")

        if invalid_rows:
            st.subheader("⚠️ Skipped Invalid Entries")
            df_invalid = pd.DataFrame(invalid_rows)
            st.dataframe(df_invalid)

        if valid_rows and st.button("✅ Save Valid Records to Supabase"):
            status_code, response = insert_batch_to_supabase(valid_rows)
            if status_code == 201:
                st.success(f"{len(valid_rows)} record(s) saved to Supabase ✅")
            else:
                st.error(f"Failed to insert: {response}")
