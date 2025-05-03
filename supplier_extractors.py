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
        for fmt in ("%d %b %Y", "%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(date_str.strip(), fmt).strftime("%d/%m/%Y")
            except:
                continue
        return date_str

    invoice_no = find(r"Invoice Number[:\s]*([A-Z0-9\-]+)")
    invoice_date = to_ddmmyyyy(find(r"Invoice Date[:\s]*([\d]{1,2} \w{3} \d{4})"))
    reference = find(r"Reference[:\s]*([^\n]+)")
    due_date = to_ddmmyyyy(find(r"Due Date[:\s]*([\d]{1,2} \w{3} \d{4})"))
    amount = find(r"Amount Due SGD[:\s]*([\d,]+\.\d{2})") or find(r"Invoice Total SGD[:\s]*([\d,]+\.\d{2})")

    return {
        "supplier_name": supplier_name,
        "company_name": company_name,
        "invoice_no": invoice_no,
        "invoice_date": invoice_date,
        "due_date": due_date,
        "amount": amount.replace(",", "") if amount else None,
        "reference": reference
    }


def extract_air_liquide_invoice(pdf_path, supplier_name, company_name):
    import pdfplumber, re
    from datetime import datetime

    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())

    def find(pattern):
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1).strip() if match else None

    def to_ddmmyyyy(date_str):
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d %b %Y"):
            try:
                return datetime.strptime(date_str.strip(), fmt).strftime("%d/%m/%Y")
            except:
                continue
        return date_str

    # Match invoice no from 'DOC NO SV01961254'
    invoice_no = find(r"DOC NO\s+([A-Z0-9]+)")

    # Match 'Date 30/04/2025' pattern for invoice date
    invoice_date = to_ddmmyyyy(find(r"Date\s+(\d{2}/\d{2}/\d{4})"))

    # Match due date (optional)
    due_date = to_ddmmyyyy(find(r"Due Date\s+(\d{2}/\d{2}/\d{4})"))

    # Extract final numeric value after TOTAL (last amount in page)
    amounts = re.findall(r"\b(\d{2,4}\.\d{2})\b", text)
    amount = amounts[-1] if amounts else None

    return {
        "supplier_name": supplier_name,
        "company_name": company_name,
        "invoice_no": invoice_no,
        "invoice_date": invoice_date,
        "due_date": due_date,
        "amount": amount,
        "reference": None
    }


def extract_classic_fine_foods_soa(pdf_path, supplier_name, company_name):
    import pdfplumber
    import re
    from datetime import datetime

    def to_ddmmyyyy(date_str):
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(date_str.strip(), fmt).strftime("%d/%m/%Y")
            except:
                continue
        return date_str.strip()

    extracted_rows = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if not table:
                continue

            # Skip header row
            for row in table[1:]:
                if len(row) < 6:
                    continue

                due_date = to_ddmmyyyy(row[1])
                invoice_no = row[2].strip() if row[2] else None
                invoice_date = to_ddmmyyyy(row[3])
                reference = row[4].strip() if row[4] else None
                amount = row[5].replace(",", "").strip() if row[5] else None

                if invoice_no and invoice_date and amount:
                    extracted_rows.append({
                        "supplier_name": supplier_name,
                        "company_name": company_name,
                        "invoice_no": invoice_no,
                        "invoice_date": invoice_date,
                        "due_date": due_date,
                        "amount": amount,
                        "reference": reference
                    })
    print("Extracted rows:", extracted_rows)

    return extracted_rows


# ---------------------- Extractor Mapping ----------------------

SUPPLIER_EXTRACTORS = {
    "Sourdough Factory LLP": extract_sourdough_invoice,
    "Fu Luxe Pte. Ltd.": extract_fu_luxe_invoice,
    "Air Liquide Singapore Pte Ltd": extract_air_liquide_invoice,
    # Add more as needed
}

SUPPLIER_SOA_EXTRACTORS = {
    "Classic Fine Foods": extract_classic_fine_foods_soa,
    # Add here SOA Extractors
}

# ---------------------- Fuzzy Matching Function ----------------------

def get_best_supplier_match(text, extractor_map, threshold=85):
    best_score = 0
    best_supplier = None
    for supplier in extractor_map:
        score = fuzz.partial_ratio(supplier.lower(), text.lower())
        print(f"🔍 Score {score} for supplier: {supplier}")
        if score > best_score and score >= threshold:
            best_score = score
            best_supplier = supplier
    return best_supplier
