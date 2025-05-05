# dashboard.py
import streamlit as st
import pandas as pd
from datetime import datetime
import requests
import os

# Fetch all invoices
def fetch_all_invoices():
    url = f"{SUPABASE_URL}/rest/v1/invoices?select=*&limit=10000"
 
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_API_KEY = os.getenv("SUPABASE_API_KEY")
    
    headers = {
        "apikey": SUPABASE_API_KEY,
        "Authorization": f"Bearer {SUPABASE_API_KEY}",
    }

    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        return res.json()
    return []

# Dashboard Tab
def render_dashboard():
    st.title("📊 Invoice Tracker Dashboard")

    invoices = fetch_all_invoices()
    if not invoices:
        st.warning("No invoice data found.")
        return

    df = pd.DataFrame(invoices)

    # Clean and convert
    df["invoice_date"] = pd.to_datetime(df["invoice_date"], errors="coerce")
    df["due_date"] = pd.to_datetime(df["due_date"], errors="coerce")

    # KPI Metrics
    total = len(df)
    paid = df[df["status"] == "Paid"]
    unpaid = df[df["status"] == "Unpaid"]

    col1, col2, col3 = st.columns(3)
    col1.metric("📦 Total Invoices", total)
    col2.metric("✅ Paid", len(paid), f"${paid['amount'].sum():,.2f}")
    col3.metric("⏳ Outstanding", len(unpaid), f"${unpaid['amount'].sum():,.2f}")

    # Monthly Trend
    df["month"] = df["invoice_date"].dt.to_period("M").astype(str)
    trend = df.groupby(["month", "status"])["amount"].sum().unstack(fill_value=0).reset_index()
    st.subheader("📈 Monthly Invoice Trend")
    st.line_chart(trend.set_index("month"))

    # Supplier Outstanding
    out_by_supplier = unpaid.groupby("supplier_name")["amount"].sum().sort_values()
    st.subheader("🏢 Outstanding Amount by Supplier")
    st.bar_chart(out_by_supplier)

    # Aging Report
    today = pd.Timestamp.today()
    unpaid["age"] = (today - unpaid["due_date"]).dt.days
    unpaid["bucket"] = pd.cut(unpaid["age"], bins=[-9999, 0, 30, 60, 90, 99999],
                                labels=["Not Due", "0–30", "31–60", "61–90", "90+"])
    aging = unpaid.groupby("bucket")["amount"].sum().reindex(["Not Due", "0–30", "31–60", "61–90", "90+"]).fillna(0)
    st.subheader("📊 Aging Summary (Outstanding)")
    st.bar_chart(aging)
