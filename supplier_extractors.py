import pdfplumber
import re
from datetime import datetime, timedelta
from rapidfuzz import fuzz
import pytesseract
import pandas as pd

# ---------------------- Utility Functions ----------------------

def format_date(date_str, formats=["%d/%m/%Y", "%Y-%m-%d", "%d-%b-%Y", "%d-%m-%Y"]):
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%d-%m-%Y")
        except:
            continue
    return date_str


# ---------------------- Extractor Functions ----------------------

def extract_bidfood_soa(pdf_path, supplier_name, company_name):
    rows = []

    def parse_date(raw_date):
        for fmt in ("%d/%m/%y", "%d/%m/%Y"):
            try:
                return datetime.strptime(raw_date.strip(), fmt).strftime("%d/%m/%Y")
            except:
                continue
        return None

    credit_days = 7  # Based on "Credit Terms: 7 Days"

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text or "STATEMENT" not in text.upper():
                continue

            for line in text.splitlines():
                # Match line with optional reference
                match = re.match(
                    r"(\d{2}/\d{2}/\d{2})\s+Invoice\s+([A-Z0-9\-]+)(?:\s+([A-Z0-9]+))?\s+\d+\s+([\d,.]+)\s+[\d,.]+\s+[\d,.]+",
                    line
                )
                if match:
                    raw_date, invoice_no, reference, amount_str = match.groups()
                    invoice_date = parse_date(raw_date)
                    due_date = (
                        datetime.strptime(invoice_date, "%d/%m/%Y") + timedelta(days=credit_days)
                    ).strftime("%d/%m/%Y") if invoice_date else None
                    amount = float(amount_str.replace(",", ""))

                    rows.append({
                        "supplier_name": supplier_name,
                        "company_name": company_name,
                        "invoice_no": invoice_no,
                        "invoice_date": invoice_date,
                        "due_date": due_date,
                        "amount": amount,
                        "reference": reference or None
                    })

    return rows




def extract_fu_luxe_soa(pdf_path, supplier_name, company_name):

    def parse_date(raw):
        try:
            return datetime.strptime(raw.strip(), "%d %b %y").strftime("%d/%m/%Y")
        except:
            try:
                return datetime.strptime(raw.strip(), "%d %b %Y").strftime("%d/%m/%Y")
            except:
                return None

    rows = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            lines = page.extract_text().split("\n")

            for line in lines:
                match = re.match(
                    r"^(\d{2} \w{3} \d{2})\s+Invoice #\s+(INV-\d+)\s+.*?(\d{2} \w{3} \d{2})\s+([\d.,]+)\s+([\d.,]+)$",
                    line.strip()
                )
                if match:
                    invoice_date_raw, invoice_no, due_date_raw, amount, balance = match.groups()

                    rows.append({
                        "supplier_name": supplier_name,
                        "company_name": company_name,
                        "invoice_no": invoice_no,
                        "invoice_date": parse_date(invoice_date_raw),
                        "due_date": parse_date(due_date_raw),
                        "amount": balance.replace(",", ""),
                        "reference": None
                    })

    return rows



def extract_dawood_exports_soa(pdf_path, supplier_name, company_name):

    rows = []

    def parse_date(raw_date):
        try:
            return datetime.strptime(raw_date.strip(), "%d/%m/%Y").strftime("%d/%m/%Y")
        except:
            return None

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            for line in text.split("\n"):
                # Match invoice lines like: IN 10379765 202502190056 20/02/2025 20/02/2025 SGD 156.96
                match = re.match(
                    r"IN\s+(\d+)\s+(\d+)\s+(\d{2}/\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})\s+SGD\s+([\d.,]+)",
                    line
                )
                if match:
                    invoice_no, reference, post_date, due_date, amount = match.groups()
                    rows.append({
                        "supplier_name": supplier_name,
                        "company_name": company_name,
                        "invoice_no": invoice_no.strip(),
                        "invoice_date": parse_date(post_date),
                        "due_date": parse_date(due_date),
                        "amount": amount.replace(",", "").strip(),
                        "reference": reference.strip()
                    })

    return rows



def extract_tipo_novena_electric_invoice(pdf_path, supplier_name, company_name):
    invoice_no = None
    invoice_date = None
    due_date = None
    amount = None
    reference = None  # Not found, will stay None

    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())

    # Invoice No
    match = re.search(r"Invoice No[:\s]+(RR\d+)", text)
    if match:
        invoice_no = match.group(1)

    # Invoice Date
    match = re.search(r"Date of Invoice[:\s]+(\d{1,2})\s+([A-Za-z]{3,})\s+(\d{2})", text)
    if match:
        day, month_str, year_suffix = match.groups()
        try:
            invoice_date = datetime.strptime(f"{day} {month_str} 20{year_suffix}", "%d %b %Y").strftime("%d/%m/%Y")
        except ValueError:
            pass

    # Due Date
    match = re.search(r"due on (\d{1,2})\s+([A-Za-z]{3,})\s+(\d{2})", text)
    if match:
        day, month_str, year_suffix = match.groups()
        try:
            due_date = datetime.strptime(f"{day} {month_str} 20{year_suffix}", "%d %b %Y").strftime("%d/%m/%Y")
        except ValueError:
            pass

    # Amount
    match = re.search(r"Total\s+Current\s+charges\s+due.+?\$\s*([\d.,]+)", text)
    if match:
        amount = match.group(1).replace(",", "")

    return {
        "supplier_name": supplier_name,
        "company_name": company_name,
        "invoice_no": invoice_no,
        "invoice_date": invoice_date,
        "due_date": due_date,
        "amount": amount,
        "reference": reference
    }


def extract_foodxervices_inc_soa(pdf_path, supplier_name, company_name):
    rows = []

    def parse_date(d):
        try:
            return datetime.strptime(d.strip(), "%d/%m/%Y").strftime("%d/%m/%Y")
        except:
            return None

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            for line in text.splitlines():
                # Pattern 1: Format A
                match = re.search(
                    r"(\d{1,2}/\d{1,2}/\d{4})\s+"        # Invoice Date
                    r"(\d{1,2}/\d{1,2}/\d{4})\s+"        # Due Date
                    r"(FXINVX-\d+).*?"                   # Invoice Number
                    r"SGD\s+([\d,]+\.\d{2})",            # Amount
                    line
                )
                if not match:
                    # Pattern 2: Format B (New structure: date, invoice no, due date, SGD, debit, credit, balance)
                    match = re.search(
                        r"(\d{1,2}/\d{1,2}/\d{4})\s+(FXINVX-\d+)\s+(\d{1,2}/\d{1,2}/\d{4})\s+SGD\s+([\d,]+\.\d{2})",
                        line
                    )
                    if match:
                        invoice_date, invoice_no, due_date, amount = match.groups()
                    else:
                        continue
                else:
                    invoice_date, due_date, invoice_no, amount = match.groups()

                rows.append({
                    "supplier_name": supplier_name,
                    "company_name": company_name,
                    "invoice_no": invoice_no,
                    "invoice_date": parse_date(invoice_date),
                    "due_date": parse_date(due_date),
                    "amount": float(amount.replace(",", "")),
                    "reference": None
                })

    return rows



def extract_genie_pro_invoice(pdf_path, supplier_name, company_name):
    invoice_no = None
    invoice_date = None
    due_date = None
    amount = None
    reference = None  # No reference found in this format

    lines = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                lines.extend(text.splitlines())

    for i, line in enumerate(lines):
        lower = line.lower()

        # Invoice No
        if "invoice" in lower and not invoice_no:
            match = re.search(r"invoice\s+#?(\d+)", line, re.IGNORECASE)
            if match:
                invoice_no = match.group(1)

        # Invoice Date
        if "date" in lower and "invoice" not in lower and not invoice_date:
            match = re.search(r"(\d{1,2}/\d{1,2}/\d{4})", line)
            if match:
                invoice_date = match.group(1)

        # Due Date
        if "due date" in lower and not due_date:
            match = re.search(r"(\d{1,2}/\d{1,2}/\d{4})", line)
            if match:
                due_date = match.group(1)

        # Amount
        if "balance due" in lower and not amount:
            match = re.search(r"([\d,.]+\.\d{2})", line)
            if match:
                amount = match.group(1).replace(",", "")

    return {
        "supplier_name": supplier_name,
        "company_name": company_name,
        "invoice_no": invoice_no,
        "invoice_date": invoice_date,
        "due_date": due_date,
        "amount": amount,
        "reference": reference
    }




def extract_aardwolf_invoice(pdf_path, supplier_name, company_name):
    invoice_no = None
    invoice_date = None
    due_date = None
    amount = None
    reference = None

    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
        lines = text.splitlines()
 
    # ✅ Invoice No
    for line in lines:
        match = re.search(r"INVOICE\s+NO\s*[:\-]?\s*(\S+)", line, re.IGNORECASE)
        if match:
            invoice_no = match.group(1)
            break

    # ✅ Invoice Date (robust approach)
    for i, line in enumerate(lines):
        if "invoice date" in line.lower():
            # Try to find date in this line or next line
            for j in range(i, min(i + 2, len(lines))):
                date_match = re.search(r"\d{1,2}/\d{1,2}/\d{4}", lines[j])
                if date_match:
                    invoice_date = date_match.group()
                    break
            if invoice_date:
                break

    # ✅ Due Date (from credit term = 30 Days)
    if invoice_date:
        try:
            base_date = datetime.strptime(invoice_date, "%d/%m/%Y")
        except ValueError:
            base_date = datetime.strptime(invoice_date, "%d/%m/%Y")
        due_date = (base_date + pd.Timedelta(days=30)).strftime("%d/%m/%Y")

    # ✅ Amount (look for TOTAL AMOUNT or PAYMENT OF $...)
    for line in lines:
        match = re.search(r"TOTAL AMOUNT.*?\$?\s*([\d,.]+)", line)
        if not match:
            match = re.search(r"PAYMENT OF \$?\s*([\d,.]+)", line)
        if match:
            amount = match.group(1).replace(",", "")
            break

    # ✅ Reference: none for this invoice
    reference = None

    return {
        "supplier_name": supplier_name,
        "company_name": company_name,
        "invoice_no": invoice_no,
        "invoice_date": invoice_date,
        "due_date": due_date,
        "amount": amount,
        "reference": reference
    }



def extract_recipedia_soa(pdf_path, supplier_name, company_name):
    rows = []

    def parse_date(d):
        try:
            return datetime.strptime(d.strip(), "%d/%m/%Y").strftime("%d/%m/%Y")
        except:
            return None

    invoice_pattern = re.compile(
        r"(\d{2}/\d{2}/\d{4})\s+Invoice\s+(\S+)\s+.+?\s+(\d{2}/\d{2}/\d{4})\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})"
    )

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            for line in text.splitlines():
                match = invoice_pattern.match(line)
                if match:
                    invoice_date, invoice_no, due_date, amount, _ = match.groups()
                    rows.append({
                        "supplier_name": supplier_name,
                        "company_name": company_name,
                        "invoice_no": invoice_no,
                        "invoice_date": parse_date(invoice_date),
                        "due_date": parse_date(due_date),
                        "amount": amount.replace(",", ""),
                        "reference": None
                    })

    return rows


def extract_equipmax_soa(pdf_path, supplier_name, company_name):
    rows = []

    def parse_date(raw):
        try:
            return datetime.strptime(raw.strip(), "%d/%m/%Y").strftime("%d/%m/%Y")
        except:
            return None

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue

            for line in text.split("\n"):
                # Match pattern: DATE INVOICE_NO ... AMOUNT AMOUNT
                match = re.match(
                    r"^(\d{2}/\d{2}/\d{4})\s+(INV\d{4}/\d{3})\s+.*?([\d,]+\.\d{2})\s+([\d,]+\.\d{2})$",
                    line
                )
                if match:
                    date_str, invoice_no, debit, balance = match.groups()
                    invoice_date = parse_date(date_str)
                    due_date = invoice_date  # COD terms

                    rows.append({
                        "supplier_name": supplier_name,
                        "company_name": company_name,
                        "invoice_no": invoice_no,
                        "invoice_date": invoice_date,
                        "due_date": due_date,
                        "amount": float(debit.replace(",", "")),
                        "reference": None
                    })

    return rows



def extract_dutch_colony_invoice(pdf_path, supplier_name, company_name):
    rows = []

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            # 🧾 Skip first page if it's a statement
            if i == 0:
                first_text = page.extract_text()
                if first_text and "statement of account" in first_text.lower():
                    continue

            image = page.to_image(resolution=300).original
            text = pytesseract.image_to_string(image)

            # 🔍 Extract fields
            invoice_no = re.search(r'Tax\s+Invoice\s+(\S+)', text)
            invoice_date = re.search(r'Date\s+(\d{1,2}/\d{1,2}/\d{4})', text)
            due_date = re.search(r'Due\s+Date\s*=?\s*(\d{1,2}/\d{1,2}/\d{4})', text)
            reference = re.search(r'P\.?O\.?\s+No\.\s+([A-Z0-9\-]+)', text)
            amount_matches = re.findall(r'\b\d{1,3}(?:,\d{3})*(?:\.\d{2})\b', text)

            base_amount = None
            total_amount = None

            if amount_matches:
                try:
                    base_amount = float(amount_matches[-1].replace(",", ""))
                    total_amount = round(base_amount, 2)
                except:
                    pass

            row = {
                "supplier_name": supplier_name,
                "company_name": company_name,
                "invoice_no": invoice_no.group(1) if invoice_no else None,
                "invoice_date": invoice_date.group(1) if invoice_date else None,
                "due_date": due_date.group(1) if due_date else None,
                "reference": reference.group(1) if reference else None,
                "amount": str(total_amount) if total_amount else None
            }

            if row["invoice_no"] or row["invoice_date"]:
                rows.append(row)

    return rows




def extract_nopests_soa(pdf_path, supplier_name, company_name):
    import pdfplumber
    import re
    from datetime import datetime

    rows = []

    def parse_date(date_str):
        try:
            return datetime.strptime(date_str.strip(), "%d%b%Y").strftime("%d/%m/%Y")
        except:
            return None

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            lines = text.split('\n')

            for line in lines:
                if re.search(r"\bInvoice\s+#\s+I\d+", line):
                    parts = line.split()
                    try:
                        invoice_date = parse_date(parts[0])
                        invoice_no_index = parts.index("Invoice") + 2
                        invoice_no = parts[invoice_no_index]
                        due_date = parse_date(parts[invoice_no_index + 1])
                        amount = float(parts[invoice_no_index + 2].replace(",", ""))
                    except:
                        continue

                    rows.append({
                        "supplier_name": supplier_name,
                        "company_name": company_name,
                        "invoice_no": invoice_no,
                        "invoice_date": invoice_date,
                        "due_date": due_date,
                        "amount": amount,
                        "reference": None
                    })

    return rows




def extract_nopests_invoice(pdf_path, supplier_name, company_name):
    
    with pdfplumber.open(pdf_path) as pdf:
        lines = []
        text = ""
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                lines += t.split("\n")
                text += t + "\n"

    invoice_no = None
    invoice_date = None
    due_date = None
    amount = None

    # Extract invoice number from full text (more reliable)
    match = re.search(r"InvoiceNumber\s+([A-Z]\d+)", text)
    if match:
        invoice_no = match.group(1)

    # Extract invoice date from line following "InvoiceDate"
    for i, line in enumerate(lines):
        if "InvoiceDate" in line:
            if i + 1 < len(lines):
                raw = lines[i + 1].strip()
                try:
                    invoice_date = datetime.strptime(raw, "%d%b%Y").strftime("%d/%m/%Y")
                except:
                    pass
            break

    # Extract due date from line containing "DueDate"
    for line in lines:
        if "DueDate" in line:
            match = re.search(r"(\d{1,2}[A-Za-z]{3}\d{4})", line)
            if match:
                try:
                    due_date = datetime.strptime(match.group(1), "%d%b%Y").strftime("%d/%m/%Y")
                except:
                    pass
            break

    # Extract amount from "TOTALSGD"
    for line in lines:
        if "TOTALSGD" in line:
            match = re.search(r"TOTALSGD\s+([\d.]+)", line)
            if match:
                amount = match.group(1)
            break

    return {
        "supplier_name": supplier_name,
        "company_name": company_name,
        "invoice_no": invoice_no,
        "invoice_date": invoice_date,
        "due_date": due_date,
        "amount": amount,
        "reference": None
    }



import pdfplumber
import re

def extract_gan_teck_invoice(pdf_path, supplier_name, company_name):
    with pdfplumber.open(pdf_path) as pdf:
        text = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])

    invoice_no = None
    invoice_date = None
    due_date = None
    amount = None
    reference = None

    # Extract Invoice No
    match = re.search(r"INVOICE ID\s+(SXI\.SG\d+)", text)
    if match:
        invoice_no = match.group(1)

    # Extract Invoice Date
    match = re.search(r"DATE\s+(\d{1,2}/\d{1,2}/\d{4})", text)
    if match:
        invoice_date = match.group(1)

    # Extract PO ID (Reference)
    match = re.search(r"PO ID\s+(#[\d]+)", text)
    if match:
        reference = match.group(1)

    # ✅ Extract only the final TOTAL amount by grabbing all matches and using the last
    matches = re.findall(r"TOTAL\s+S\$([\d.,]+)", text)
    if matches:
        amount = matches[-1].replace(",", "")  # Last occurrence = correct total

    # Handle Due Date based on Terms
    if "TERMS CASH" in text.upper() and invoice_date:
        due_date = invoice_date  # Set due date same as invoice date

    return {
        "supplier_name": supplier_name,
        "company_name": company_name,
        "invoice_no": invoice_no,
        "invoice_date": invoice_date,
        "due_date": due_date,
        "amount": amount,
        "reference": reference
    }



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
    ("Sourdough Factory", False): extract_sourdough_invoice,
    ("Fuluxe", False): extract_fu_luxe_invoice,
    ("Air Liquide Singapore", False): extract_air_liquide_invoice,
    ("Classic Fine Foods", True): extract_classic_fine_foods_soa,
    ("Mr Popiah", True): extract_mr_popiah_soa,
    ("Double Chin Food", True): extract_double_chin_soa,
    ("Gourmet Perfect", True): extract_gourmet_perfect_soa,
    ("Over Foods", False): extract_over_foods_invoice,
    ("Gan Teck Kar Investments", False): extract_gan_teck_invoice,
    ("1800 NO PESTS", False): extract_nopests_invoice,
    ("1800 NO PESTS", True): extract_nopests_soa,
    ("Dutch Colony", False): extract_dutch_colony_invoice,
    ("Equipmax", True): extract_equipmax_soa,
    ("Recipedia Group", True): extract_recipedia_soa,
    ("Ardwolf Pestkare", False): extract_aardwolf_invoice,
    ("Genie Pro", False): extract_genie_pro_invoice,
    ("Food Xervices", True): extract_foodxervices_inc_soa,
    ("Electric Tipo Novena - RR60063", False): extract_tipo_novena_electric_invoice,
    ("Dawood Exports", True): extract_dawood_exports_soa,
    ("Fuluxe", True): extract_fu_luxe_soa,
    ("Bidfood", True): extract_bidfood_soa,


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
