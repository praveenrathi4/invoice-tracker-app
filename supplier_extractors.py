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


# ---------------------- Extractor Functions ----------------------

def extract_over_foods_invoice(pdf_path, supplier_name, company_name):
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())

    def extract_field(pattern, text, date=False):
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            if date:
                try:
                    return datetime.strptime(value, "%d %b %Y").strftime("%d/%m/%Y")
                except:
                    return None
            return value
        return None

    invoice_no = extract_field(r"Tax Invoice No:\s*(SINV\s*\d+-\d+)", text)
    invoice_date = extract_field(r"Invoice Date:\s*(\d{1,2} \w+ \d{4})", text, date=True)
    due_date = extract_field(r"Due Date:\s*(\d{1,2} \w+ \d{4})", text, date=True)
    amount = extract_field(r"Total\s*:\s*([\d.]+)", text)
    reference = extract_field(r"PO No:\s*(\d+)", text)

    return {
        "supplier_name": supplier_name,
        "company_name": company_name,
        "invoice_no": invoice_no,
        "invoice_date": invoice_date,
        "due_date": due_date,
        "amount": amount,
        "reference": reference
    }



def extract_gourmet_perfect_soa(pdf_path, supplier_name, company_name):
    import pdfplumber
    import re
    from datetime import datetime

    rows = []

    def parse_date(raw):
        try:
            return datetime.strptime(raw.strip(), "%d%b%Y").strftime("%d/%m/%Y")
        except:
            return None

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            lines = text.split("\n")

            for line in lines:
                match = re.match(
                    r"^(\d{1,2}[A-Za-z]{3}\d{4})\s+"     # invoice date
                    r"(\d{1,2}[A-Za-z]{3}\d{4})\s+"     # due date
                    r"(INV-\d+)\s+"                    # invoice number
                    r"([A-Z0-9\-]*)\s+"                # invoice reference (optional)
                    r"(?:[-\d.,]+\s+){5,6}"            # skip 5-6 aging columns
                    r"([\d.,]+)$",                    # final amount
                    line.strip()
                )
                if match:
                    invoice_date, due_date, invoice_no, reference, amount = match.groups()
                    try:
                        amount = float(amount.replace(",", ""))
                    except:
                        amount = None

                    rows.append({
                        "supplier_name": supplier_name,
                        "company_name": company_name,
                        "invoice_no": invoice_no,
                        "invoice_date": parse_date(invoice_date),
                        "due_date": parse_date(due_date),
                        "amount": amount,
                        "reference": reference or None
                    })

    return rows



def extract_double_chin_soa(pdf_path, supplier_name, company_name):
    rows = []

    def parse_date(raw):
        try:
            return datetime.strptime(raw.strip(), "%d/%m/%y").strftime("%d/%m/%Y")
        except:
            return None

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            lines = text.split('\n')
            for i, line in enumerate(lines):
                # Match the line with or without Ext Doc No
                match = re.match(
                    r'^(SI\d+)\s+(\d{2}/\d{2}/\d{2})\s+Order\s+(SI\d+)\s+(?:([A-Z0-9/\-]+)\s+)?([\d,]+\.\d{2})\s+([\d,]+\.\d{2})$',
                    line.strip()
                )

                if match:
                    invoice_no, post_date, desc_doc, ext_doc_no, rem_amt, balance = match.groups()
                    invoice_date = parse_date(post_date)

                    rows.append({
                        "supplier_name": supplier_name,
                        "company_name": company_name,
                        "invoice_no": invoice_no,
                        "invoice_date": invoice_date,
                        "due_date": invoice_date,
                        "amount": float(rem_amt.replace(",", "")),
                        "reference": ext_doc_no or None
                    })

                # Handle case when amount comes in next line (e.g. 392.40 in next line)
                elif re.match(r'^\d{2}/\d{2}/\d{2}', line.strip()) is None and re.match(r'^\d{1,3}(,\d{3})*\.\d{2}\s+\d{1,3}(,\d{3})*\.\d{2}$', line.strip()):
                    prev_line = lines[i - 1] if i > 0 else ""
                    match = re.match(
                        r'^(SI\d+)\s+(\d{2}/\d{2}/\d{2})\s+Order\s+(SI\d+)\s*(?:([A-Z0-9/\-]+))?$',
                        prev_line.strip()
                    )
                    if match:
                        invoice_no, post_date, desc_doc, ext_doc_no = match.groups()
                        invoice_date = parse_date(post_date)
                        amounts = re.findall(r"[\d,]+\.\d{2}", line)
                        if len(amounts) == 2:
                            rem_amt, balance = [float(a.replace(",", "")) for a in amounts]
                            rows.append({
                                "supplier_name": supplier_name,
                                "company_name": company_name,
                                "invoice_no": invoice_no,
                                "invoice_date": invoice_date,
                                "due_date": invoice_date,
                                "amount": rem_amt,
                                "reference": ext_doc_no or None
                            })

    return rows


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

    rows = []

    def parse_date(raw):
        for fmt in ("%d%b%Y", "%d %b %Y"):
            try:
                return datetime.strptime(raw.strip(), fmt).strftime("%d/%m/%Y")
            except:
                continue
        return None

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            invoice_blocks = re.findall(
                r"(\d{1,2}[A-Za-z]{3}\d{4})\s+Invoice\s+#\s+(INV-\d+)(.*?)?(\d{1,2}[A-Za-z]{3}\d{4})?\s+(\d+\.\d{2})",
                text
            )

            for match in invoice_blocks:
                invoice_date_raw, invoice_no, mid_text, due_date_raw, amount_str = match

                invoice_date = parse_date(invoice_date_raw)
                due_date = parse_date(due_date_raw) if due_date_raw else None
                try:
                    amount = float(amount_str.replace(",", ""))
                except:
                    amount = None

                reference = None
                if mid_text:
                    ref_match = re.search(r"(PO[#\s]?\d+|\d{6,})", mid_text)
                    if ref_match:
                        reference = ref_match.group(0).strip()

                rows.append({
                    "supplier_name": supplier_name,
                    "company_name": company_name,
                    "invoice_no": invoice_no,
                    "invoice_date": invoice_date,
                    "due_date": due_date,
                    "amount": amount,
                    "reference": reference
                })

    return rows

# ---------------------- Extractor Mapping ----------------------

SUPPLIER_EXTRACTORS = {
    ("Sourdough Factory LLP", False): extract_sourdough_invoice,
    ("Fu Luxe Pte. Ltd.", False): extract_fu_luxe_invoice,
    ("Air Liquide Singapore Pte Ltd", False): extract_air_liquide_invoice,
    ("Classic Fine Foods", True): extract_classic_fine_foods_soa,
    ("Mr Popiah Pte Ltd", True): extract_mr_popiah_soa,
    ("Double Chin Food Services Pte Ltd", True): extract_double_chin_soa,
    ("Gourmet Perfect Pte Ltd", True): extract_gourmet_perfect_soa,
    ("Over Foods Pte Ltd", False): extract_over_foods_invoice,

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
