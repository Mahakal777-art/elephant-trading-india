from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet


def _pdf_text(value):
    """Escape untrusted text before ReportLab's XML-like Paragraph parser."""
    return escape(str(value if value is not None else ""))


def make_agreement(path, party_name, party_role, product, deal_value, commission_pct, payment_terms, jurisdiction):
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(path), pagesize=A4)
    story = [Paragraph("ELEPHANT TRADING — INTRODUCTION &amp; COMMISSION AGREEMENT", styles["Title"]), Spacer(1, 14)]
    paras = [
        "Draft template only. Obtain Indian legal counsel review before signing.",
        f"Intermediary: Elephant Trading. Introduced party ({_pdf_text(party_role)}): {_pdf_text(party_name)}.",
        f"Product: {_pdf_text(product)}. Indicative transaction value: INR {float(deal_value):,.2f}.",
        f"Commission: {float(commission_pct):.2f}% of the agreed commission base, subject to written confirmation by all parties.",
        f"Payment terms: {_pdf_text(payment_terms)}.",
        "Direct transaction: Buyer and supplier contract, invoice, deliver and settle payment directly. Elephant Trading does not take title to, store, resell or warrant the goods.",
        "Non-circumvention: For 12 months from documented introduction, the introduced parties shall not intentionally bypass the intermediary for the specifically introduced transaction or repeat orders, where enforceable by applicable law.",
        f"Jurisdiction / courts: {_pdf_text(jurisdiction)}.",
        "Signatures: Buyer __________________ Supplier __________________ Elephant Trading __________________ Date __________",
        "This template is not legal advice and does not replace a lawyer-drafted agreement.",
    ]
    story.extend(Paragraph(text, styles["BodyText"]) for text in paras)
    doc.build(story)
