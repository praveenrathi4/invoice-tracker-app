
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

# Insert record into Supabase
def insert_invoice_to_supabase(data):
    url = f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}"
    headers = {
        "apikey": SUPABASE_API_KEY,
        "Authorization": f"Bearer {SUPABASE_API_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    response = requests.post(url, json=[data], headers=headers)
    return response.status_code, response.json()

# Streamlit UI
st.set_page_config(page_title="Invoice Uploader", layout="centered")
st.title("📄 Invoice Uploader & Tracker")

# Dropdowns for Supplier and Company
supplier_options = get_dropdown_values("name", "supplier_names")
company_options = get_dropdown_values("name", "company_names")

supplier_name = st.selectbox("Select Supplier Name", supplier_options)
company_name = st.selectbox("Select Company Name", company_options)

uploaded_file = st.file_uploader("Upload Invoice PDF", type=["pdf"])

if uploaded_file:
    extracted = extract_invoice_data_from_pdf(uploaded_file, supplier_name, company_name)

    # Format dates
    for key in ["invoice_date", "due_date"]:
        try:
            if extracted[key]:
                extracted[key] = datetime.strptime(extracted[key], "%d %b %Y").strftime("%d/%m/%Y")
        except:
            pass

    st.subheader("🧾 Extracted Invoice Data")
    st.json(extracted)

    if st.button("✅ Save to Supabase"):
        try:
            extracted["amount"] = float(extracted["amount"].replace(",", "")) if extracted["amount"] else None
        except:
            st.error("Amount format is invalid.")
            extracted["amount"] = None

        extracted["status"] = "Unpaid"
        status_code, response = insert_invoice_to_supabase(extracted)

        if status_code == 201:
            st.success("Invoice saved to Supabase ✅")
        else:
            st.error(f"Failed to insert: {response}")
