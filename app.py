import streamlit as st
st.set_page_config(page_title="Invoice Tracker", layout="wide")
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader

# Load credentials from YAML
with open("auth_config.yaml") as file:
    config = yaml.load(file, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    config["credentials"],
    config["cookie"]["name"],
    config["cookie"]["key"],
    config["cookie"]["expiry_days"],
)

name, authentication_status, username = authenticator.login(
    fields={'Form name': 'Login'}, location="main"
)


if authentication_status is False:
    st.error("❌ Incorrect username or password.")
elif authentication_status is None:
    st.warning("🔐 Please enter your credentials.")
elif authentication_status:
    authenticator.logout("Logout", "sidebar")
    st.sidebar.success(f"Welcome {name}!")
    # 🔓 Place your entire app here (all tab logic, etc.)
    import streamlit as st
    import pdfplumber
    import requests
    import re
    import pandas as pd
    from datetime import datetime, date
    import os
    from io import BytesIO
    from supplier_extractors import SUPPLIER_EXTRACTORS, get_best_supplier_match
    
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")
    TABLE_NAME = "invoices"
    
    def supabase_headers():
        return {
            "apikey": SUPABASE_API_KEY,
            "Authorization": f"Bearer {SUPABASE_API_KEY}",
            "Content-Type": "application/json"
        }
    
    def get_dropdown_values(column, table):
        url = f"{SUPABASE_URL}/rest/v1/{table}?select={column}"
        response = requests.get(url, headers=supabase_headers())
        if response.status_code == 200:
            return sorted(set(row[column] for row in response.json() if row[column]))
        return []
    
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
    
    def extract_invoice_data_from_pdf(file, supplier_name, company_name, is_invoice=True):
        with pdfplumber.open(file) as pdf:
            text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())
    
        # Use the unified dictionary with (name, is_soa) keys
        is_soa = not is_invoice
        matched_supplier = get_best_supplier_match(text, [key[0] for key in SUPPLIER_EXTRACTORS.keys()])
    
        if matched_supplier:
            key = (matched_supplier, is_soa)
            extractor = SUPPLIER_EXTRACTORS.get(key)
            if extractor:
                st.info(f"📌 Matched Supplier Extractor: {matched_supplier} ({'SOA' if is_soa else 'Invoice'})")
                return extractor(file, supplier_name, company_name)
    
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

    
    def get_invoices_by_status(status):
        url = f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}?status=eq.{status}&select=*"
        response = requests.get(url, headers=supabase_headers())
        return response.json() if response.status_code == 200 else []
    
    def update_invoice_paid_fields(invoice_ids, paid_date, paid_via, remark, status="Paid"):
        url = f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}"
        headers = supabase_headers()
        for inv_id in invoice_ids:
            patch_url = f"{url}?invoice_no=eq.{inv_id}"
            payload = {
                "status": status,
                "paid_date": paid_date,
                "paid_via": paid_via,
                "remarks": remark
            }
            requests.patch(patch_url, headers=headers, json=payload)
        return True
    
    st.sidebar.title("🧭 Navigation")
    tab = st.sidebar.radio("Go to", ["📤 Upload Invoices", "📋 Outstanding Invoices", "✅ Mark as Paid", "📁 Paid History"])
    
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
                                    row[date_field] = datetime.strptime(row[date_field], "%d/%m/%Y").strftime("%Y-%m-%d")
                            except:
                                pass
                        try:
                            row["amount"] = float(str(row.get("amount", "0")).replace(",", ""))
                        except:
                            row["amount"] = None
                        row["status"] = "Unpaid"
                        extracted_rows.append(row)
    
                if extracted_rows:
                    st.subheader("🔍 Raw Extracted Rows (Before Validation)")
                    st.dataframe(pd.DataFrame(extracted_rows))
                else:
                    st.info("🕵️ No rows were extracted from the uploaded PDFs.")
                    
                required_fields = ["invoice_no", "invoice_date", "amount"]
                valid_rows = [r for r in extracted_rows if all(r.get(f) not in [None, ""] for f in required_fields)]
    
                if valid_rows:
                    # ✅ Step 1: Fetch existing invoice_no + invoice_date from Supabase
                    response = requests.get(
                        f"{SUPABASE_URL}/rest/v1/invoices?select=invoice_no,invoice_date",
                        headers=supabase_headers()
                    )
                    existing_keys = set()
                    if response.status_code == 200:
                        existing_data = response.json()
                        existing_keys = {
                            (item["invoice_no"], item["invoice_date"])
                            for item in existing_data if item.get("invoice_no") and item.get("invoice_date")
                        }
                    
                    # ✅ Step 2: Normalize and detect duplicates
                    df_all = pd.DataFrame(valid_rows)
                    df_all["invoice_date"] = pd.to_datetime(df_all["invoice_date"], errors="coerce").dt.strftime("%Y-%m-%d")
                    
                    df_all["is_duplicate"] = df_all.apply(
                        lambda r: (r["invoice_no"], r["invoice_date"]) in existing_keys, axis=1
                    )
                    
                    unique_df = df_all[~df_all["is_duplicate"]].drop(columns=["is_duplicate"])
                    duplicates_df = df_all[df_all["is_duplicate"]].drop(columns=["is_duplicate"])
                    
                    # ✅ Step 3: Show and Save
                    st.subheader("🧾 Valid Extracted Invoices (New Only)")
                    st.dataframe(unique_df)
                    
                    if not unique_df.empty and st.button("✅ Save to Supabase"):
                        status_code, response = insert_batch_to_supabase(unique_df.to_dict(orient="records"))
                        if status_code == 201:
                            st.success("✅ Data saved to Supabase.")
                            if not duplicates_df.empty:
                                dup_invoices = ", ".join(duplicates_df['invoice_no'].astype(str).unique())
                                st.warning(f"⚠️ Skipped {len(duplicates_df)} duplicate invoice(s): {dup_invoices}")
                        else:
                            st.error("❌ Failed to insert records.")
                    elif unique_df.empty:
                        st.info("📌 All uploaded invoices already exist. No new records to save.")
                else:
                    st.info("No valid invoice data to display.")
    
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
            df.to_excel(excel, index=False, engine='openpyxl')
            st.download_button("⬇️ Download as Excel", excel.getvalue(), file_name="invoices.xlsx")
    
        return df
    
    if tab == "📋 Outstanding Invoices":
        st.title("📋 Outstanding Invoices")
        data = get_invoices_by_status("Unpaid")
        if data:
            df = pd.DataFrame(data)
            df = df.drop(columns=["id", "status", "created_at", "paid_date", "paid_via", "remarks"], errors="ignore")
            df["amount"] = df["amount"].astype(float)
            filter_and_export(df)
        else:
            st.info("🎉 No outstanding invoices.")
    
    elif tab == "✅ Mark as Paid":
        st.title("✅ Mark Invoices as Paid")
    
        data = get_invoices_by_status("Unpaid")
        if not data:
            st.info("✅ No unpaid invoices found.")
        else:
            df = pd.DataFrame(data)
    
            # Step 1: Initialize filter state
            if "mark_supplier_filter" not in st.session_state:
                st.session_state["mark_supplier_filter"] = ""
            if "mark_company_filter" not in st.session_state:
                st.session_state["mark_company_filter"] = ""
            if "mark_date_range" not in st.session_state:
                st.session_state["mark_date_range"] = []
    
            # Step 2: Clear All Filters
            if st.button("🧹 Clear All Filters"):
                st.session_state.update({
                    "mark_supplier_filter": "",
                    "mark_company_filter": "",
                    "mark_date_range": []
                })
                st.rerun()
    
            # Step 3: Filter Controls
            with st.expander("🔍 Filter Options", expanded=True):
                col1, col2 = st.columns(2)
                supplier_filter = col1.text_input("🔍 Filter by Supplier", st.session_state.get("mark_supplier_filter", ""), key="mark_supplier_filter")
                company_filter = col2.text_input("🏢 Filter by Company", st.session_state.get("mark_company_filter", ""), key="mark_company_filter")
                date_range = st.date_input("📅 Filter by Invoice Date Range", st.session_state.get("mark_date_range", []), key="mark_date_range")
    
            # Step 4: Apply Filters
            if supplier_filter:
                df = df[df["supplier_name"].str.contains(supplier_filter, case=False, na=False)]
            if company_filter:
                df = df[df["company_name"].str.contains(company_filter, case=False, na=False)]
            
            # Filter by date range
            df["invoice_date"] = pd.to_datetime(df["invoice_date"], errors="coerce")
            
            if len(date_range) == 2:
                df = df[
                    (df["invoice_date"] >= pd.to_datetime(date_range[0])) &
                    (df["invoice_date"] <= pd.to_datetime(date_range[1]))
                ]
            
            # Format invoice_date as dd-mm-yyyy string
            df["invoice_date"] = df["invoice_date"].apply(
                lambda x: x.strftime("%d-%m-%Y") if pd.notnull(x) else ""
            )
    
            
            # Step 5: Select All + Table Setup
            select_all = st.checkbox("🟢 Select All Filtered Rows", value=False, key="select_all_mark_paid")
            df["select"] = select_all
            df = df.drop(columns=["id", "status", "created_at", "paid_date", "paid_via", "remarks"], errors="ignore")
            cols = ["select"] + [col for col in df.columns if col != "select"]
            df = df[cols]
    
            # Step 6: Show Table
            editable_cols = ["select"]
            edited = st.data_editor(
                df,
                use_container_width=True,
                num_rows="dynamic",
                key="mark_paid_editor",
                hide_index=True,
                column_order=cols,
                disabled=[col for col in df.columns if col not in editable_cols]
            )
    
            # Step 7: Extract selected rows
            selected = edited[edited["select"] == True]
    
            # Step 8: Payment Form
            if not selected.empty:
                paid_date = st.date_input("🗓️ Enter Paid Date", value=date.today())
                paid_sources = [""] + get_dropdown_values("name", "paid_sources")
                paid_via = st.selectbox("💳 Select Payment Source", paid_sources, index=0)
                remark = st.text_area("📝 Remarks (Optional)")
    
                if not paid_via:
                    st.warning("⚠️ Please select a valid payment source.")
                if not paid_date:
                    st.warning("⚠️ Please select a valid paid date.")
    
                if paid_via and paid_date and st.button("✅ Confirm Mark as Paid"):
                    invoice_ids = selected["invoice_no"].tolist()
                    update_invoice_paid_fields(invoice_ids, paid_date.isoformat(), paid_via, remark)
                    st.success(f"✅ {len(invoice_ids)} invoice(s) marked as Paid.")
    
    
    
    elif tab == "📁 Paid History":
        st.title("📁 Paid Invoice History")
    
        data = get_invoices_by_status("Paid")
        if not data:
            st.info("No paid invoices found.")
        else:
            df = pd.DataFrame(data)
    
            # Step 1: Initialize filter state
            if "supplier_filter" not in st.session_state:
                st.session_state["supplier_filter"] = ""
            if "company_filter" not in st.session_state:
                st.session_state["company_filter"] = ""
            if "paid_via_filter" not in st.session_state:
                st.session_state["paid_via_filter"] = ""
            if "paid_history_date_range" not in st.session_state:
                st.session_state["paid_history_date_range"] = []
    
            # Step 2: Filters
            if st.button("🧹 Clear All Filters"):
                st.session_state.update({
                    "supplier_filter": "",
                    "company_filter": "",
                    "paid_via_filter": "",
                    "paid_history_date_range": []
                })
                st.rerun()
    
            
            with st.expander("🔍 Filter Options", expanded=True):
                col1, col2 = st.columns(2)
                supplier_filter = col1.text_input("🔍 Filter by Supplier", st.session_state.get("supplier_filter", ""), key="supplier_filter")
                company_filter = col2.text_input("🏢 Filter by Company", st.session_state.get("company_filter", ""), key="company_filter")
            
                paid_via_filter = st.selectbox(
                    "💳 Filter by Payment Source",
                    options=[""] + get_dropdown_values("name", "paid_sources"),
                    index=0,
                    key="paid_via_filter"
                )
            
                date_range = st.date_input(
                    "📅 Filter by Invoice Date Range",
                    st.session_state.get("paid_history_date_range", []),
                    key="paid_history_date_range"
                )
            
    
            # Step 4: Apply filters
            if supplier_filter:
                df = df[df["supplier_name"].str.contains(supplier_filter, case=False, na=False)]
            if company_filter:
                df = df[df["company_name"].str.contains(company_filter, case=False, na=False)]
            if paid_via_filter:
                df = df[df["paid_via"].str.contains(paid_via_filter, case=False, na=False)]
            # ✅ Step 1: Filter if date range is selected
            # Filter by date range
            df["invoice_date"] = pd.to_datetime(df["invoice_date"], errors="coerce")
            
            if len(date_range) == 2:
                df = df[
                    (df["invoice_date"] >= pd.to_datetime(date_range[0])) &
                    (df["invoice_date"] <= pd.to_datetime(date_range[1]))
                ]
            
            # Format invoice_date as dd-mm-yyyy string
            df["invoice_date"] = df["invoice_date"].apply(
                lambda x: x.strftime("%d-%m-%Y") if pd.notnull(x) else ""
            )
    
    
            # Step 5: Select All
            select_all = st.checkbox("🟢 Select All Filtered Rows", value=False, key="select_all_paid_history")
            df["select"] = select_all
    
            # Step 6: Drop irrelevant columns
            df = df.drop(columns=["id", "status", "created_at"], errors="ignore")
    
            # Step 7: Reorder columns
            cols = ["select"] + [col for col in df.columns if col != "select"]
            df = df[cols]
    
            # Step 8: Show data editor
            editable_cols = ["select"]
            edited = st.data_editor(
                df,
                use_container_width=True,
                num_rows="dynamic",
                key="paid_history_editor",
                hide_index=True,
                column_order=cols,
                disabled=[col for col in df.columns if col not in editable_cols]
            )
    
            # Step 9: Get selected rows
            selected = edited[edited["select"] == True]
    
            # Step 10: Export all filtered rows
            export_df = edited.drop(columns=["select"], errors="ignore")
            excel = BytesIO()
            export_df.to_excel(excel, index=False)
            st.download_button(
                label="📤 Download Filtered Invoices (Excel)",
                data=excel.getvalue(),
                file_name="paid_invoices.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    
            # Step 11: Mark as Unpaid
            if not selected.empty and st.button("↩️ Mark Selected as Unpaid"):
                invoice_ids = selected["invoice_no"].tolist()
                update_invoice_paid_fields(invoice_ids, None, None, None, status="Unpaid")
                st.success(f"🔁 {len(invoice_ids)} invoices marked as Unpaid. Please refresh the page.")
