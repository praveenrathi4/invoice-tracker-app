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
    import pandas as pd
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
            text = page.extract_text()
            lines = text.split("\n") if text else []

            for line in lines:
                if any(char.isdigit() for char in line) and '/' in line:
                    parts = line.split()
                    if len(parts) >= 6:
                        try:
                            invoice_date = to_ddmmyyyy(parts[0])   # Was "credit"
                            invoice_no = parts[1]                  # Was "due_date"
                            reference = parts[2]                   # Was "doc_no"
                            # description = " ".join(parts[3:-3])  # optional
                            due_date = to_ddmmyyyy(parts[-3])      # Was "date"
                            amount = parts[-2].replace(",", "")    # Was "balance"
                            # doc_ref = parts[-1]                  # extra field

                            extracted_rows.append({
                                "supplier_name": supplier_name,
                                "company_name": company_name,
                                "invoice_no": invoice_no,
                                "invoice_date": invoice_date,
                                "due_date": due_date,
                                "amount": amount,
                                "reference": reference
                            })
                        except:
                            continue

    # Optionally remove last row (summary)
    if extracted_rows:
        extracted_rows.pop()

    return extracted_rows


def extract_mr_popiah_soa(pdf_path, supplier_name, company_name):
    import pdfplumber
    import pandas as pd
    import re
    from datetime import datetime

    rows = []

    def parse_date(raw):
        for fmt in ("%d%b%Y", "%d %b %Y"):
            try:
                return datetime.strptime(raw.strip().replace("\n", " "), fmt).strftime("%d/%m/%Y")
            except:
                continue
        return None

    with pdfplumber.open(pdf_path) as pdf:
        all_lines = []
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                all_lines.extend(text.split("\n"))

        i = 0
        while i < len(all_lines):
            line = all_lines[i]
            if "INV-" in line:
                next_line = all_lines[i + 1] if (i + 1 < len(all_lines)) else ""
                use_next_line = bool(re.search(r"\d{1,2} \w+ ?\d{4}", next_line))
                combined_line = f"{line} {next_line}" if use_next_line else line
                tokens = combined_line.split()

                try:
                    # Extract invoice no
                    invoice_no = next(t for t in tokens if t.startswith("INV-"))

                    # Extract invoice date: first token that looks like ddMMMyyyy or dd MMM yyyy
                    invoice_date = None
                    for t in tokens:
                        if re.match(r"\d{1,2}[A-Za-z]{3}\d{4}", t) or re.match(r"\d{1,2} [A-Za-z]{3} \d{4}", t):
                            invoice_date = parse_date(t)
                            break

                    # Extract due date: scan right side from invoice_no
                    due_date = None
                    try:
                        idx = tokens.index(invoice_no)
                        for j in range(idx + 1, len(tokens)):
                            if re.match(r"\d{1,2}[A-Za-z]{3}\d{4}", tokens[j]) or re.match(r"\d{1,2} [A-Za-z]{3} \d{4}", tokens[j]):
                                due_date = parse_date(tokens[j])
                                break
                    except:
                        pass

                    # Extract amount: last token that looks like a decimal
                    amount = None
                    for t in reversed(tokens):
                        if re.match(r"^\d+\.\d{2}$", t):
                            amount = float(t.replace(",", "").replace("$", ""))
                            break

                    if invoice_no and invoice_date and amount is not None:
                        rows.append({
                            "supplier_name": supplier_name,
                            "company_name": company_name,
                            "invoice_no": invoice_no,
                            "invoice_date": invoice_date,
                            "due_date": due_date,  # leave as None if not parsed
                            "amount": amount,
                            "reference": None
                        })

                except:
                    pass

            i += 1

    return rows


# ---------------------- Extractor Mapping ----------------------

SUPPLIER_EXTRACTORS = {
    ("Sourdough Factory LLP", False): extract_sourdough_invoice,
    ("Fu Luxe Pte. Ltd.", False): extract_fu_luxe_invoice,
    ("Air Liquide Singapore Pte Ltd", False): extract_air_liquide_invoice,
    ("Classic Fine Foods", True): extract_classic_fine_foods_soa,
    ("Mr Popiah Pte Ltd", True): extract_mr_popiah_soa,
    # Add more (supplier_name, is_soa): extractor_function
}


# ---------------------- Fuzzy Matching Function ----------------------

def get_best_supplier_match(text, extractor_map, threshold=70):
    best_score = 0
    best_supplier = None
    for supplier in extractor_map:
        score = fuzz.partial_ratio(supplier.lower(), text.lower())
        print(f"🔍 Score {score} for supplier: {supplier}")
        if score > best_score and score >= threshold:
            best_score = score
            best_supplier = supplier
    return best_supplier
