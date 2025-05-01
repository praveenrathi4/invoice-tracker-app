
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
    import pdfplumber, re
    from datetime import datetime

    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())

    def find(pattern):
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1).strip() if match else None

    def to_ddmmyyyy(date_str):
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").strftime("%d/%m/%Y")
        except:
            try:
                return datetime.strptime(date_str, "%d/%m/%Y").strftime("%d/%m/%Y")
            except:
                return date_str

    invoice_no = find(r"Invoice No[:\s]*([0-9]+)")
    invoice_date = to_ddmmyyyy(find(r"Invoice Date[:\s]*([\d/-]+)"))
    po_ref = find(r"Po Ref[:\s]*([A-Z0-9]+)")
    delivery_date = to_ddmmyyyy(find(r"Delivery Date[:\s]*([\d/-]+)"))
    amount = find(r"Balance Due[:\s]*\$?([\d,]+\.\d{2})")

    return {
        "supplier_name": supplier_name,
        "company_name": company_name,
        "invoice_no": invoice_no,
        "invoice_date": invoice_date,
        "due_date": delivery_date,
        "amount": amount.replace(",", "") if amount else None,
        "reference": po_ref
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
