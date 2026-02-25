from __future__ import annotations

from datetime import datetime
from email.message import EmailMessage
import hmac
from pathlib import Path
import re
import smtplib
import ssl
from typing import Any, Sequence

from fpdf import FPDF
import numpy as np
import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent
FALLBACK_IMAGE = PROJECT_ROOT / "data" / "images" / "coming_soon.png"
FONT_PATH = PROJECT_ROOT / "data" / "fonts" / "Arial Unicode MS Regular.ttf"

REQUIRED_COLUMNS = {"name", "price", "units", "category", "image_path"}
ORDER_COLUMNS = [
    "name",
    "category",
    "units",
    "unit_price",
    "quantity",
    "line_total",
    "price_label",
    "quantity_label",
    "line_total_label",
]


def format_euro(value: float) -> str:
    return f"{value:.2f} €"


def make_safe_filename(raw_value: str) -> str:
    value = (raw_value or "").strip()
    value = re.sub(r"[^\w\-]+", "_", value, flags=re.UNICODE)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "client"


def validate_client_name(name: str) -> tuple[bool, str]:
    cleaned = (name or "").strip()
    if not cleaned:
        return False, "Veuillez saisir votre nom avant le téléchargement."
    if len(cleaned) < 2:
        return False, "Le nom doit contenir au moins 2 caractères."
    if len(cleaned) > 80:
        return False, "Le nom est trop long (maximum 80 caractères)."

    allowed = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ'\- ]+$")
    if not allowed.match(cleaned):
        return False, "Le nom contient des caractères non autorisés."

    return True, ""


def _get_secret(path: Sequence[str], default: Any = None) -> Any:
    current: Any = st.secrets
    try:
        for key in path:
            current = current[key]
    except Exception:
        return default
    return current


def get_contact_email() -> str | None:
    address = str(_get_secret(("email", "address"), default="")).strip()
    return address or None


def get_default_receiver() -> str | None:
    receiver = str(_get_secret(("email", "receiver"), default="")).strip()
    return receiver or None


def _get_email_credentials() -> tuple[str, str] | None:
    address = str(_get_secret(("email", "address"), default="")).strip()
    passkey = str(_get_secret(("email", "passkey"), default="")).strip()
    if not address or not passkey:
        return None

    return address, passkey


def has_admin_password() -> bool:
    expected = str(_get_secret(("admin", "password"), default="")).strip()
    return bool(expected)


def is_valid_admin_password(candidate: str) -> bool:
    expected = str(_get_secret(("admin", "password"), default="")).strip()
    if not expected:
        return False
    return hmac.compare_digest(str(candidate or ""), expected)


def _normalize_image_path(raw_path: Any) -> str:
    if pd.isna(raw_path):
        return FALLBACK_IMAGE.as_posix() if FALLBACK_IMAGE.exists() else ""

    value = str(raw_path).strip()
    if not value:
        return FALLBACK_IMAGE.as_posix() if FALLBACK_IMAGE.exists() else ""

    if value.startswith(("http://", "https://", "data:image/")):
        return value

    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = (PROJECT_ROOT / candidate).resolve()

    if candidate.exists() and candidate.is_file():
        return candidate.as_posix()

    return FALLBACK_IMAGE.as_posix() if FALLBACK_IMAGE.exists() else ""


def _parse_price_column(price_series: pd.Series) -> pd.Series:
    as_text = price_series.astype(str).str.replace(",", ".", regex=False)
    extracted = as_text.str.extract(r"([-+]?\d*\.?\d+)")[0]
    return pd.to_numeric(extracted, errors="coerce")


def _format_unit_price(unit_price: float, unit: str) -> str:
    safe_unit = (unit or "").strip()
    if safe_unit:
        return f"{unit_price:.2f} {safe_unit}"
    return f"{unit_price:.2f}"


def _format_quantity(quantity: float, unit: str) -> str:
    safe_unit = (unit or "").strip().lower()
    if safe_unit == "€":
        return str(int(quantity))

    if float(quantity).is_integer():
        return str(int(quantity))

    return f"{quantity:.1f}"


@st.cache_data(show_spinner=False)
def load_products(products_path: str | Path) -> tuple[pd.DataFrame, list[str]]:
    path = Path(products_path)
    if not path.exists():
        raise FileNotFoundError(path)

    df = pd.read_excel(path, sheet_name="products")
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Colonnes manquantes: {', '.join(sorted(missing))}")

    warnings: list[str] = []
    data = df.copy()

    data["name"] = data["name"].fillna("").astype(str).str.strip()
    data["category"] = data["category"].fillna("Autres").astype(str).str.strip()
    data["units"] = data["units"].fillna("").astype(str).str.strip()
    data["image_path"] = data["image_path"].apply(_normalize_image_path)

    data["unit_price"] = _parse_price_column(data["price"])
    invalid_price_mask = data["unit_price"].isna()
    if invalid_price_mask.any():
        count = int(invalid_price_mask.sum())
        warnings.append(
            f"{count} produit(s) ont un prix invalide et ont été fixés à 0,00 € pour éviter les erreurs."
        )
        data.loc[invalid_price_mask, "unit_price"] = 0.0

    data["unit_price"] = data["unit_price"].astype(float).round(2)
    data["price_label"] = data.apply(
        lambda row: _format_unit_price(float(row["unit_price"]), str(row["units"])),
        axis=1,
    )

    data["select"] = False
    data["quantity"] = 0.0

    display_columns = [
        "select",
        "image_path",
        "name",
        "price_label",
        "quantity",
        "category",
        "unit_price",
        "units",
    ]

    return data[display_columns], warnings


def _empty_order() -> pd.DataFrame:
    return pd.DataFrame(columns=ORDER_COLUMNS)


def build_order(edited_df: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    if edited_df.empty or "select" not in edited_df.columns:
        return _empty_order(), 0.0

    order = edited_df.loc[edited_df["select"] == True].copy()  # noqa: E712
    if order.empty:
        return _empty_order(), 0.0

    order["quantity"] = pd.to_numeric(order["quantity"], errors="coerce").fillna(0.0)
    order["quantity"] = order["quantity"].clip(lower=0.0)

    euro_units = order["units"].astype(str).str.strip().str.lower().eq("€")
    order.loc[euro_units, "quantity"] = np.floor(order.loc[euro_units, "quantity"])
    order.loc[~euro_units, "quantity"] = order.loc[~euro_units, "quantity"].round(1)

    order = order[order["name"].astype(str).str.strip() != ""]
    order = order[order["quantity"] > 0]
    if order.empty:
        return _empty_order(), 0.0

    order["line_total"] = (order["unit_price"].astype(float) * order["quantity"].astype(float)).round(2)
    order["price_label"] = order.apply(
        lambda row: _format_unit_price(float(row["unit_price"]), str(row["units"])),
        axis=1,
    )
    order["quantity_label"] = order.apply(
        lambda row: _format_quantity(float(row["quantity"]), str(row["units"])),
        axis=1,
    )
    order["line_total_label"] = order["line_total"].apply(lambda value: format_euro(float(value)))

    order = order.sort_values(by=["category", "name"], kind="stable")
    result = order[ORDER_COLUMNS].reset_index(drop=True)

    total = float(result["line_total"].sum())
    return result, total


def _safe_pdf_text(value: Any, unicode_ready: bool) -> str:
    text = str(value if value is not None else "")
    if unicode_ready:
        return text
    return text.encode("latin-1", errors="ignore").decode("latin-1")


def generate_order_pdf(order_df: pd.DataFrame, client_name: str, note: str = "") -> bytes:
    if order_df.empty:
        raise ValueError("Order is empty")

    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()
    pdf.set_margins(12, 12, 12)

    unicode_ready = FONT_PATH.exists()
    font_family = "Helvetica"
    if unicode_ready:
        pdf.add_font("FarmUnicode", "", FONT_PATH.as_posix(), uni=True)
        font_family = "FarmUnicode"

    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    pdf.set_font(font_family, size=18)
    pdf.cell(0, 10, _safe_pdf_text("Bon de commande", unicode_ready), ln=True, align="C")
    pdf.set_font(font_family, size=12)
    pdf.cell(0, 7, _safe_pdf_text("GAEC Au Champ du Puits", unicode_ready), ln=True, align="C")
    pdf.ln(6)
    pdf.cell(0, 7, _safe_pdf_text(f"Client: {client_name}", unicode_ready), ln=True)
    pdf.cell(0, 7, _safe_pdf_text(f"Date: {now}", unicode_ready), ln=True)
    pdf.ln(5)

    w_product, w_price, w_qty, w_total = 84, 32, 28, 34
    row_h = 8

    pdf.set_fill_color(226, 232, 221)
    pdf.set_font(font_family, size=11)
    pdf.cell(w_product, row_h, _safe_pdf_text("Produit", unicode_ready), border=1, align="C", fill=True)
    pdf.cell(w_price, row_h, _safe_pdf_text("Prix unitaire", unicode_ready), border=1, align="C", fill=True)
    pdf.cell(w_qty, row_h, _safe_pdf_text("Quantité", unicode_ready), border=1, align="C", fill=True)
    pdf.cell(w_total, row_h, _safe_pdf_text("Total", unicode_ready), border=1, align="C", fill=True)
    pdf.ln(row_h)

    for category in order_df["category"].dropna().astype(str).unique():
        pdf.set_fill_color(247, 245, 238)
        pdf.cell(
            w_product + w_price + w_qty + w_total,
            row_h,
            _safe_pdf_text(category, unicode_ready),
            border=1,
            align="L",
            fill=True,
            ln=True,
        )

        subset = order_df[order_df["category"].astype(str) == category]
        for _, row in subset.iterrows():
            pdf.set_fill_color(255, 255, 255)
            pdf.cell(w_product, row_h, _safe_pdf_text(row["name"], unicode_ready), border=1)
            pdf.cell(w_price, row_h, _safe_pdf_text(row["price_label"], unicode_ready), border=1, align="C")
            pdf.cell(w_qty, row_h, _safe_pdf_text(row["quantity_label"], unicode_ready), border=1, align="C")
            pdf.cell(w_total, row_h, _safe_pdf_text(row["line_total_label"], unicode_ready), border=1, align="C")
            pdf.ln(row_h)

    grand_total = float(order_df["line_total"].sum())
    pdf.set_font(font_family, size=12)
    pdf.cell(w_product + w_price + w_qty, row_h, _safe_pdf_text("Total commande", unicode_ready), border=1)
    pdf.cell(w_total, row_h, _safe_pdf_text(format_euro(grand_total), unicode_ready), border=1, align="C", ln=True)

    clean_note = (note or "").strip()
    if clean_note:
        pdf.ln(4)
        pdf.set_font(font_family, size=11)
        pdf.cell(0, 6, _safe_pdf_text("Remarque:", unicode_ready), ln=True)
        pdf.multi_cell(0, 6, _safe_pdf_text(clean_note, unicode_ready))

    output = pdf.output(dest="S")
    if isinstance(output, bytes):
        return output
    return output.encode("latin-1")


def send_email(
    receiver: str,
    subject: str,
    body: str,
    attachment_bytes: bytes | None = None,
    attachment_name: str = "commande.pdf",
) -> tuple[bool, str]:
    credentials = _get_email_credentials()
    if credentials is None:
        return False, "Configuration e-mail absente: vérifiez `email.address` et `email.passkey` dans les secrets."

    sender_address, sender_passkey = credentials
    receiver_clean = (receiver or "").strip()
    if not receiver_clean:
        return False, "Adresse destinataire manquante."

    msg = EmailMessage()
    msg["Subject"] = (subject or "Commande Champ du Puits").strip()
    msg["From"] = sender_address
    msg["To"] = receiver_clean
    msg.set_content((body or "Commande générée depuis l'application.").strip())

    if attachment_bytes:
        msg.add_attachment(
            attachment_bytes,
            maintype="application",
            subtype="pdf",
            filename=attachment_name,
        )

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context, timeout=20) as server:
            server.login(sender_address, sender_passkey)
            server.send_message(msg)
    except smtplib.SMTPAuthenticationError:
        return False, "Échec d'authentification SMTP. Vérifiez l'adresse et la passkey de l'expéditeur."
    except (smtplib.SMTPException, OSError):
        return False, "Échec d'envoi de l'e-mail. Vérifiez la connectivité réseau et la configuration SMTP."

    return True, f"E-mail envoyé à {receiver_clean}."

