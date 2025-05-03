import streamlit as st
import pdfplumber
import requests
import re
import pandas as pd
from datetime import datetime
import os
from io import BytesIO
from supplier_extractors import SUPPLIER_EXTRACTORS, SUPPLIER_SOA_EXTRACTORS, get_best_supplier_match

# Supabase Config
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")
TABLE_NAME = "invoices"

def supabase_headers():
    return {
        "apikey": SUPABASE_API_KEY,
        "Authorization": f"Bearer {SUPABASE_API_KEY}",
        "Content-Type": "application/json"
    }

# Fetch dropdown values from Supabase
def get_dropdown_values(column, table):
    url = f"{SUPABASE_URL}/rest/v1/{table}?select={column}"
    response = requests.get(url, headers=supabase_headers())
    if response.status_code == 200:
        return sorted(set(row[column] for row in response.json() if row[column]))
    return []

# Insert batch to Supabase with error logging
def insert_batch_to_supabase(data_list):
    url = f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}"
    headers = supabase_headers()
    headers["Prefer"] = "return=representation"
    try:
        response = requests.post(url, json=data_list, headers=headers)
        if response.status_code != 201:
            st.error(f"❌ Supabase Error {response.status_code}:")
            st.json(response.json())
            st.warning("📦 Payload sent to Supabase:")
            st.json(data_list)
        return response.status_code, response.json()
    except Exception as e:
        st.error(f"🔴 Request failed: {str(e)}")
        return 500, {"error": str(e)}

# Extract invoice using matched extractor
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

# Fetch invoices by status
def get_invoices_by_status(status):
    url = f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}?status=eq.{status}&select=*"
    response = requests.get(url, headers=supabase_headers())
    return response.json() if response.status_code == 200 else []

# Update invoice status
def update_invoice_status(invoice_ids, new_status):
    url = f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}"
    headers = supabase_headers()
    for inv_id in invoice_ids:
        patch_url = f"{url}?invoice_no=eq.{inv_id}"
        requests.patch(patch_url, headers=headers, json={"status": new_status})
    return True

# ---------------- UI ----------------
st.set_page_config(page_title="Invoice Tracker", layout="wide")
st.sidebar.title("🧭 Navigation")
tab = st.sidebar.radio("Go to", ["📤 Upload Invoices", "📋 Outstanding Invoices", "✅ Mark as Paid", "📁 Paid History"])

# Upload Tab
if tab == "📤 Upload Invoices":
    st.title("📤 Upload Invoices or SOA")

    is_invoice = st.checkbox("Processing Invoices", value=True)

    supplier_options = [""] + get_dropdown_values("name", "supplier_names")
    company_options = [""] + get_dropdown_values("name", "company_names")

    supplier_name = st.selectbox("Select Supplier Name", supplier_options, index=0)
    company_name = st.selectbox("Select Company Name", company_options, index=0)

    uploaded_files = st.file_uploader("Upload PDF files", type=["pdf"], accept_multiple_files=True)

    if uploaded_files:
        if not supplier_name or not company_name:
            st.warning("Please select both Supplier Name and Company Name before processing.")
        else:
            extracted_rows = []
            for file in uploaded_files:
                extracted_data = extract_invoice_data_from_pdf(file, supplier_name, company_name, is_invoice)
                extracted_list = extracted_data if isinstance(extracted_data, list) else [extracted_data]

                for row in extracted_list:
                    for date_field in ["invoice_date", "due_date"]:
                        try:
                            if row.get(date_field):
                                row[date_field] = datetime.strptime(row[date_field], "%d/%m/%Y").strftime("%d/%m/%Y")
                        except:
                            pass
                    try:
                        row["amount"] = float(str(row.get("amount", "0")).replace(",", ""))
                    except:
                        row["amount"] = None
                    row["status"] = "Unpaid"
                    extracted_rows.append(row)

            required_fields = ["invoice_no", "invoice_date", "amount"]
            valid_rows = [r for r in extracted_rows if all(r.get(f) not in [None, ""] for f in required_fields)]

            st.subheader("🧾 Valid Extracted Invoices")
            if valid_rows:
                st.dataframe(pd.DataFrame(valid_rows))
                if st.button("✅ Save to Supabase"):
                    status_code, response = insert_batch_to_supabase(valid_rows)
                    if status_code == 201:
                        st.success("✅ Data saved to Supabase.")
                    else:
                        st.error("❌ Failed to insert records.")
            else:
                st.info("No valid invoice data to display.")

# Filter and export
def filter_and_export(df):
    col1, col2 = st.columns(2)
    supplier_filter = col1.text_input("🔍 Filter by Supplier")
    company_filter = col2.text_input("🏢 Filter by Company")

    date_col = "invoice_date" if "invoice_date" in df.columns else "due_date"
    date_range = st.date_input("📅 Filter by Invoice Date Range", [])

    if supplier_filter:
        df = df[df["supplier_name"].str.contains(supplier_filter, case=False, na=False)]
    if company_filter:
        df = df[df["company_name"].str.contains(company_filter, case=False, na=False)]
    if len(date_range) == 2:
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df[(df[date_col] >= pd.to_datetime(date_range[0])) & (df[date_col] <= pd.to_datetime(date_range[1]))]

    st.dataframe(df)

    if not df.empty:
        excel = BytesIO()
        df.to_excel(excel, index=False)
        st.download_button("⬇️ Download as Excel", excel.getvalue(), file_name="invoices.xlsx")

    return df

# Outstanding Tab
if tab == "📋 Outstanding Invoices":
    st.title("📋 Outstanding Invoices")
    data = get_invoices_by_status("Unpaid")
    if data:
        df = pd.DataFrame(data)
        df["amount"] = df["amount"].astype(float)
        filter_and_export(df)
    else:
        st.info("🎉 No outstanding invoices.")

# Mark as Paid
elif tab == "✅ Mark as Paid":
    st.title("✅ Mark Invoices as Paid")
    data = get_invoices_by_status("Unpaid")
    if not data:
        st.info("✅ No unpaid invoices found.")
    else:
        df = pd.DataFrame(data)
        df["select"] = False
        edited = st.data_editor(df, use_container_width=True, num_rows="dynamic")
        selected = edited[edited["select"] == True]

        if not selected.empty and st.button("Mark Selected as Paid"):
            invoice_ids = selected["invoice_no"].tolist()
            update_invoice_status(invoice_ids, "Paid")
            st.success(f"✅ {len(invoice_ids)} invoices marked as Paid. Please refresh the page.")

# Paid History Tab
elif tab == "📁 Paid History":
    st.title("📁 Paid Invoice History")
    data = get_invoices_by_status("Paid")
    if not data:
        st.info("No paid invoices found.")
    else:
        df = pd.DataFrame(data)
        df["select"] = False
        filter_and_export(df)

        edited = st.data_editor(df, use_container_width=True, num_rows="dynamic")
        selected = edited[edited["select"] == True]

        if not selected.empty and st.button("↩️ Mark Selected as Unpaid"):
            invoice_ids = selected["invoice_no"].tolist()
            update_invoice_status(invoice_ids, "Unpaid")
            st.success(f"🔁 {len(invoice_ids)} invoices marked as Unpaid. Please refresh the page.")
