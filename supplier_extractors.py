
import pdfplumber
import re
from datetime import datetime
from rapidfuzz import fuzz

# ---------------------- Utility Functions ----------------------

def format_date(date_str, formats=["%d/%m/%Y", "%Y-%m-%d", "%d-%b-%Y", "%d-%m-%Y"]):
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%d-%m-%Y")
        except:
            continue
    return date_str

# ---------------------- Sample Extractor: Sourdough ----------------------

def extract_sourdough_invoice(pdf_path, supplier_name, company_name):
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())

    invoice_no = re.search(r"Invoice\s+No[:\.]?\s*([A-Z0-9\-]+)", text)
    invoice_date = re.search(r"Invoice\s+Date[:\.]?\s*([\d]{4}-[\d]{2}-[\d]{2})", text)
    po_ref = re.search(r"PO\s+Ref[:\.]?\s*([A-Z0-9\-\/]+)", text)
    delivery_date = re.search(r"Delivery\s+Date[:\.]?\s*([\d]{2}/[\d]{2}/[\d]{4})", text)
    balance_due = re.search(r"Balance\s+Due[:\.]?\s*\$?([\d,]+\.\d{2})", text)

    return {
        "Supplier Name": supplier_name,
        "Company Name": company_name,
        "Invoice No": invoice_no.group(1).strip() if invoice_no else None,
        "Invoice Date": invoice_date.group(1).strip() if invoice_date else None,
        "Due Date": format_date(delivery_date.group(1)) if delivery_date else None,
        "Amount": balance_due.group(1).replace(",", "") if balance_due else None,
        "Reference": po_ref.group(1).strip() if po_ref else None
    }


def extract_fu_luxe_invoice(pdf_path, supplier_name, company_name):
    import pdfplumber, re
    from datetime import datetime

    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())

    def find(pattern):
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1).strip() if match else None

    def to_ddmmyyyy(date_str):
        try:
            return datetime.strptime(date_str, "%d %b %Y").strftime("%d/%m/%Y")
        except:
            return date_str

    invoice_no = find(r"Invoice Number[:\.]?\s*(INV-\d+)")
    invoice_date = to_ddmmyyyy(find(r"Invoice Date[:\.]?\s*([\d]{1,2} \w{3} \d{4})"))
    reference = find(r"Reference[:\.]?\s*(.*)")
    due_date = to_ddmmyyyy(find(r"Due Date[:\.]?\s*([\d]{1,2} \w{3} \d{4})"))
    amount = find(r"Amount Due SGD\s*([\d,]+\.\d{2})")
    if not amount:
        amount = find(r"Invoice Total SGD\s*([\d,]+\.\d{2})")

    return {
        "Supplier Name": supplier_name,
        "Company Name": company_name,
        "Invoice No": invoice_no,
        "Invoice Date": invoice_date,
        "Due Date": due_date,
        "Amount": amount.replace(",", "") if amount else None,
        "Reference": reference
    }



# ---------------------- Extractor Mapping ----------------------

SUPPLIER_EXTRACTORS = {
    "Sourdough Factory LLP": extract_sourdough_invoice,
    "Fu Luxe Pte. Ltd.": extract_fu_luxe_invoice,
    # Add more as needed
}

# ---------------------- Fuzzy Matching Function ----------------------

def get_best_supplier_match(text, extractor_map, threshold=85):
    for supplier in extractor_map:
        score = fuzz.partial_ratio(supplier.lower(), text.lower())
        if score >= threshold:
            print(f"🔍 Matched '{supplier}' with score {score}")
            return supplier
    print("⚠️ No supplier matched.")
    return None
