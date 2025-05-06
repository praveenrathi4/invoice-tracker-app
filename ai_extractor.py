def ai_extract_invoice_fields(pdf_text, supplier_name, company_name):
    prompt = INVOICE_FIELDS_PROMPT + pdf_text.strip()[:4000]  # Keep token length safe

    try:
        response = None
        for model in ["gpt-4-turbo", "gpt-3.5-turbo"]:
            try:
                response = openai.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": "You are a document extraction assistant."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                    max_tokens=300
                )
                st.info(f"✅ Extraction succeeded with {model}")
                break
            except Exception as inner_e:
                st.warning(f"❌ {model} failed: {inner_e}")
                continue

        if not response:
            raise Exception("No available model succeeded.")

        reply = response.choices[0].message.content.strip()
        st.text_area("🤖 Raw AI Response", reply, height=150)

        # Remove code block markers if any
        cleaned = re.sub(r"^```(?:json)?|```$", "", reply.strip(), flags=re.IGNORECASE | re.MULTILINE).strip()

        # Attempt to extract a JSON object using regex
        match = re.search(r"{[^{}]+}", cleaned, re.DOTALL)
        if not match:
            st.warning("⚠️ No valid JSON object found in the AI response.")
            raise ValueError("No valid JSON structure detected.")

        json_str = match.group(0)
        st.code(json_str, language="json")

        result = json.loads(json_str)

        return {
            "supplier_name": supplier_name,
            "company_name": company_name,
            "invoice_no": result.get("invoice_no"),
            "invoice_date": result.get("invoice_date"),
            "due_date": result.get("due_date"),
            "amount": result.get("amount"),
            "reference": result.get("reference")
        }

    except Exception as e:
        st.error(f"⚠️ AI Extraction failed: {str(e)}")
        return {
            "supplier_name": supplier_name,
            "company_name": company_name,
            "invoice_no": None,
            "invoice_date": None,
            "due_date": None,
            "amount": None,
            "reference": None
        }
