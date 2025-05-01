
import streamlit as st
import pdfplumber
import requests
import re
import pandas as pd
from datetime import datetime
import os
from supplier_extractors import SUPPLIER_EXTRACTORS, get_best_supplier_match

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
def extract_invoice_data_from_pdf(file, supplier_name, company_name):
    with pdfplumber.open(file) as pdf:
        text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())

    matched_supplier = get_best_supplier_match(text, SUPPLIER_EXTRACTORS)
    if matched_supplier:
        st.info(f"📌 Matched Supplier Extractor: {matched_supplier}")
        return SUPPLIER_EXTRACTORS[matched_supplier](file, supplier_name, company_name)

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
st.set_page_config(page_title="Invoice Uploader", layout="centered")
st.title("📄 Invoice Uploader & Tracker")

# Dropdowns for Supplier and Company
supplier_options = get_dropdown_values("name", "supplier_names")
company_options = get_dropdown_values("name", "company_names")

supplier_name = st.selectbox("Select Supplier Name", supplier_options)
company_name = st.selectbox("Select Company Name", company_options)

uploaded_files = st.file_uploader("Upload One or More Invoice PDFs", type=["pdf"], accept_multiple_files=True)

if uploaded_files:
    extracted_rows = []
    for file in uploaded_files:
        extracted = extract_invoice_data_from_pdf(file, supplier_name, company_name)

        # Format dates
        for key in ["invoice_date", "due_date"]:
            try:
                if extracted[key]:
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

    # Filter valid rows
    valid_rows = [row for row in extracted_rows if row["invoice_no"] and row["invoice_date"] and row["amount"] is not None]
    invalid_rows = [row for row in extracted_rows if row not in valid_rows]

    st.subheader("🧾 Valid Extracted Invoice Data")
    if valid_rows:
        df_valid = pd.DataFrame(valid_rows)
        st.dataframe(df_valid)
    else:
        st.info("No valid invoice data to show.")

    if invalid_rows:
        st.subheader("⚠️ Skipped Invalid Invoices")
        df_invalid = pd.DataFrame(invalid_rows)
        st.dataframe(df_invalid)

    if valid_rows and st.button("✅ Save Valid Invoices to Supabase"):
        status_code, response = insert_batch_to_supabase(valid_rows)
        if status_code == 201:
            st.success(f"{len(valid_rows)} invoices saved to Supabase ✅")
        else:
            st.error(f"Failed to insert: {response}")
