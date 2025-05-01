import streamlit as st
import pdfplumber
import requests
import re
import pandas as pd
from datetime import datetime

# 🛠️ Supabase Config (replace with your own values)
import os

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")
TABLE_NAME = "invoices"

# 📤 Extract basic invoice fields (generic fallback, replace with supplier logic)
def extract_invoice_data_from_pdf(file):
    with pdfplumber.open(file) as pdf:
        text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())

    def find(pattern):
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1).strip() if match else None

    return {
        "supplier_name": find(r"(?:Supplier|From)[:\s]*([A-Za-z0-9 ,.&\-]+)"),
        "company_name": find(r"(?:Bill To|Company)[:\s]*([A-Za-z0-9 ,.&\-]+)"),
        "invoice_no": find(r"Invoice\s+(?:No|Number)[:\s]*([A-Z0-9\-\/]+)"),
        "invoice_date": find(r"Invoice\s+Date[:\s]*([\d]{1,2}\s\w+\s\d{4})"),
        "due_date": find(r"Due\s+Date[:\s]*([\d]{1,2}\s\w+\s\d{4})"),
        "amount": find(r"Amount\s+Due.*?([\d,]+\.\d{2})") or find(r"Invoice\s+Total.*?([\d,]+\.\d{2})"),
        "reference": find(r"Reference[:\s]*([^\n]+)"),
    }

# 🔗 Supabase Insert
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

# 🎯 UI Starts Here
st.set_page_config(page_title="Invoice Uploader", layout="centered")
st.title("📄 Invoice Uploader & Tracker")

uploaded_file = st.file_uploader("Upload Invoice PDF", type=["pdf"])

if uploaded_file:
    extracted = extract_invoice_data_from_pdf(uploaded_file)

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
        # Prepare for DB
        extracted["amount"] = float(extracted["amount"].replace(",", "")) if extracted["amount"] else None
        extracted["status"] = "Unpaid"
        status_code, response = insert_invoice_to_supabase(extracted)

        if status_code == 201:
            st.success("Invoice saved to Supabase ✅")
        else:
            st.error(f"Failed to insert: {response}")
