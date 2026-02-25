from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path

import streamlit as st

try:
    from streamlit_js_eval import streamlit_js_eval
except Exception:
    streamlit_js_eval = None

from utils import (
    build_order,
    format_euro,
    generate_order_pdf,
    get_contact_email,
    get_default_receiver,
    has_admin_password,
    is_valid_admin_password,
    load_products,
    make_safe_filename,
    send_email,
    validate_client_name,
)

PROJECT_ROOT = Path(__file__).resolve().parent
PRODUCTS_FILE = PROJECT_ROOT / "products.xlsx"
MOBILE_BREAKPOINT = 920
NARROW_BREAKPOINT = 560

st.set_page_config(
    page_title="Au Champ du Puits | Commande",
    page_icon="🌾",
    layout="wide",
)


if "editor_nonce" not in st.session_state:
    st.session_state.editor_nonce = 0
if "admin_unlocked" not in st.session_state:
    st.session_state.admin_unlocked = False
if "mobile_quantities" not in st.session_state:
    st.session_state.mobile_quantities = {}
if "pdf_cache_key" not in st.session_state:
    st.session_state.pdf_cache_key = ""
if "pdf_cache_bytes" not in st.session_state:
    st.session_state.pdf_cache_bytes = b""
if "layout_mode" not in st.session_state:
    st.session_state.layout_mode = "Auto"


def _detect_viewport_width() -> int | None:
    cached = st.session_state.get("viewport_width")
    if streamlit_js_eval is None:
        return cached

    try:
        raw_width = streamlit_js_eval(js_expressions="window.innerWidth", key="viewport_width_eval")
    except Exception:
        return cached

    width: int | None = None
    if isinstance(raw_width, (int, float)) and raw_width > 0:
        width = int(raw_width)
    elif isinstance(raw_width, str) and raw_width.isdigit():
        width = int(raw_width)

    if width is not None:
        st.session_state.viewport_width = width
        return width

    return cached


def _layout_mode_control() -> str:
    options = ["Auto", "Desktop", "Mobile"]
    default_mode = st.session_state.get("layout_mode", "Auto")
    if default_mode not in options:
        default_mode = "Auto"

    if hasattr(st, "segmented_control"):
        choice = st.segmented_control(
            "Affichage",
            options=options,
            default=default_mode,
            key="layout_mode",
        )
        return str(choice)

    idx = options.index(default_mode)
    choice = st.radio(
        "Affichage",
        options=options,
        index=idx,
        horizontal=True,
        key="layout_mode",
    )
    return str(choice)


def _is_mobile_layout(choice: str, viewport_width: int | None) -> bool:
    if choice == "Mobile":
        return True
    if choice == "Desktop":
        return False
    if viewport_width is None:
        return False
    return viewport_width <= MOBILE_BREAKPOINT


def _mobile_input_step(unit: str) -> tuple[float, str]:
    if (unit or "").strip() == "€":
        return 1.0, "%.0f"
    return 0.1, "%.1f"


def _reset_all_order_state() -> None:
    st.session_state.editor_nonce += 1
    st.session_state.admin_unlocked = False
    st.session_state.mobile_quantities = {}
    st.session_state.pdf_cache_key = ""
    st.session_state.pdf_cache_bytes = b""
    for key in list(st.session_state.keys()):
        if key.startswith("mobile_qty_"):
            del st.session_state[key]
    st.rerun()


def _build_pdf_cache_key(order_df, client_name: str, note: str) -> str:
    payload = {
        "client_name": client_name,
        "note": note.strip(),
        "rows": order_df[
            ["name", "category", "price_label", "quantity_label", "line_total_label", "line_total"]
        ].to_dict("records"),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha1(encoded).hexdigest()


def _render_mobile_picker(products_df, viewport_width: int | None):
    st.markdown("### Sélection des produits")

    search = st.text_input(
        "Rechercher un produit",
        key="mobile_search",
        placeholder="Exemple: miel, raclette, fromage...",
    )

    categories = ["Toutes"] + sorted(
        category
        for category in products_df["category"].dropna().astype(str).str.strip().unique().tolist()
        if category
    )

    category = st.selectbox("Catégorie", categories, key="mobile_category")

    filtered = products_df.copy()
    if category != "Toutes":
        filtered = filtered[filtered["category"].astype(str) == category]

    search_text = search.strip().lower()
    if search_text:
        filtered = filtered[
            filtered["name"].astype(str).str.lower().str.contains(search_text, regex=False)
        ]

    valid_indices = {str(index) for index in products_df.index.tolist()}
    quantities = st.session_state.mobile_quantities
    for key in list(quantities.keys()):
        if key not in valid_indices:
            del quantities[key]

    if filtered.empty:
        st.info("Aucun produit ne correspond à vos filtres.")

    narrow = viewport_width is not None and viewport_width <= NARROW_BREAKPOINT

    for index, row in filtered.iterrows():
        idx_key = str(index)
        current_qty = float(quantities.get(idx_key, 0.0))
        step, fmt = _mobile_input_step(str(row["units"]))

        with st.container(border=True):
            if narrow:
                image_path = str(row["image_path"]).strip()
                if image_path:
                    st.image(image_path, use_container_width=True)
                st.markdown(f"**{row['name']}**")
                st.caption(f"{row['category']} | {row['price_label']}")
            else:
                image_col, content_col = st.columns([1, 2], gap="small")
                with image_col:
                    image_path = str(row["image_path"]).strip()
                    if image_path:
                        st.image(image_path, use_container_width=True)
                with content_col:
                    st.markdown(f"**{row['name']}**")
                    st.caption(f"{row['category']} | {row['price_label']}")

            qty = st.number_input(
                "Quantité",
                min_value=0.0,
                value=current_qty,
                step=step,
                format=fmt,
                key=f"mobile_qty_{idx_key}",
            )

            if qty > 0:
                quantities[idx_key] = float(qty)
            elif idx_key in quantities:
                del quantities[idx_key]

    selected_count = sum(1 for value in quantities.values() if float(value) > 0)
    st.caption(f"{selected_count} produit(s) sélectionné(s)")

    edited = products_df.copy()
    edited["select"] = False
    edited["quantity"] = 0.0

    for idx_key, qty in quantities.items():
        if idx_key in valid_indices and qty > 0:
            row_index = int(idx_key)
            edited.at[row_index, "select"] = True
            edited.at[row_index, "quantity"] = float(qty)

    return edited


st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,700&family=Source+Sans+3:wght@400;600;700&display=swap');

    :root {
        --cdp-cream: #fbf8f1;
        --cdp-green: #2f5d3b;
        --cdp-green-soft: #e8f0e8;
        --cdp-gold: #e5c47a;
        --cdp-ink: #1f2a22;
        --cdp-border: #d8d9cf;
    }

    .stApp {
        background:
            radial-gradient(1200px 500px at 10% -5%, #fff9e9 0%, transparent 60%),
            radial-gradient(1000px 500px at 90% -10%, #edf5ec 0%, transparent 60%),
            var(--cdp-cream);
    }

    .main .block-container {
        max-width: 1180px;
        padding-top: 2rem;
        padding-bottom: 2.8rem;
    }

    .cdp-hero {
        border: 1px solid var(--cdp-border);
        border-radius: 18px;
        padding: 1.2rem 1.4rem;
        background: linear-gradient(135deg, #fffdf7 0%, #f7f3e8 100%);
        box-shadow: 0 8px 24px rgba(31, 42, 34, 0.06);
        animation: cdp-fade 350ms ease-out;
    }

    .cdp-hero h1 {
        margin: 0;
        color: var(--cdp-green);
        font-family: "Fraunces", Georgia, serif;
        font-size: 2.1rem;
    }

    .cdp-sub {
        margin-top: 0.45rem;
        color: #3a483f;
        font-family: "Source Sans 3", Helvetica, sans-serif;
        font-size: 1.05rem;
    }

    .cdp-steps {
        margin-top: 0.8rem;
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 0.65rem;
    }

    .cdp-step {
        border: 1px solid #e2dfd3;
        border-radius: 12px;
        padding: 0.7rem 0.8rem;
        background: #fff;
        font-family: "Source Sans 3", Helvetica, sans-serif;
        font-size: 0.95rem;
        color: #2d362f;
    }

    .cdp-step strong {
        color: var(--cdp-green);
        font-weight: 700;
    }

    [data-testid="stMetricValue"] {
        color: var(--cdp-green);
        font-family: "Fraunces", Georgia, serif;
    }

    @media (max-width: 900px) {
        .main .block-container {
            padding-top: 1.2rem;
            padding-left: 1rem;
            padding-right: 1rem;
        }

        .cdp-hero h1 {
            font-size: 1.65rem;
        }

        .cdp-steps {
            grid-template-columns: 1fr;
        }
    }

    @keyframes cdp-fade {
        from {
            opacity: 0;
            transform: translateY(6px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <section class="cdp-hero">
      <h1>Bienvenue au Champ du Puits</h1>
      <p class="cdp-sub">Composez votre bon de commande en quelques clics. La liste est indicative et peut évoluer selon les stocks disponibles.</p>
      <div class="cdp-steps">
        <div class="cdp-step"><strong>1.</strong> Choisissez vos produits.</div>
        <div class="cdp-step"><strong>2.</strong> Saisissez les quantités.</div>
        <div class="cdp-step"><strong>3.</strong> Téléchargez le PDF.</div>
      </div>
    </section>
    """,
    unsafe_allow_html=True,
)

st.write("")

viewport_width = _detect_viewport_width()
layout_mode = _layout_mode_control()
is_mobile = _is_mobile_layout(layout_mode, viewport_width)

if layout_mode == "Auto":
    if viewport_width is None:
        st.caption("Mode automatique: largeur d'écran non détectée, affichage desktop appliqué.")
    else:
        st.caption(f"Mode automatique: {('mobile' if is_mobile else 'desktop')} ({viewport_width}px)")

try:
    products_df, warnings = load_products(PRODUCTS_FILE)
except FileNotFoundError:
    st.error("Le fichier products.xlsx est introuvable. Vérifiez sa présence à la racine du projet.")
    st.stop()
except ValueError as exc:
    st.error(f"Structure de données invalide: {exc}")
    st.stop()
except Exception:
    st.error("Impossible de charger la liste des produits pour le moment.")
    st.stop()

for warning in warnings:
    st.warning(warning)

if is_mobile:
    edited_df = _render_mobile_picker(products_df, viewport_width)
else:
    editor_key = f"order_editor_{st.session_state.editor_nonce}"
    edited_df = st.data_editor(
        products_df,
        key=editor_key,
        hide_index=True,
        use_container_width=True,
        row_height=88,
        disabled=["name", "price_label", "category", "image_path", "unit_price", "units"],
        column_order=["select", "image_path", "name", "price_label", "quantity", "category"],
        column_config={
            "select": st.column_config.CheckboxColumn(
                label="Commander",
                help="Cochez pour ajouter le produit au bon de commande.",
            ),
            "image_path": st.column_config.ImageColumn(
                label="Photo",
                width="small",
                help="Photo non contractuelle",
            ),
            "name": st.column_config.TextColumn(label="Produit", width="large"),
            "price_label": st.column_config.TextColumn(label="Prix unitaire"),
            "quantity": st.column_config.NumberColumn(
                label="Quantité",
                min_value=0.0,
                step=0.1,
                format="%.1f",
            ),
            "category": st.column_config.TextColumn(label="Catégorie"),
            "units": None,
            "unit_price": None,
        },
    )

order_df, total_amount = build_order(edited_df)

if order_df.empty:
    st.session_state.pdf_cache_key = ""
    st.session_state.pdf_cache_bytes = b""
    st.info("Sélectionnez au moins un produit avec une quantité supérieure à 0 pour générer un bon de commande.")
else:
    st.markdown("### Aperçu de la commande")

    if is_mobile:
        top_left, top_right = st.columns(2)
        top_left.metric("Produits", str(order_df.shape[0]))
        top_right.metric("Total", format_euro(total_amount))
        st.caption(f"Mise à jour: {datetime.now():%H:%M}")
    else:
        m1, m2, m3 = st.columns(3)
        m1.metric("Produits", str(order_df.shape[0]))
        m2.metric("Montant total", format_euro(total_amount))
        m3.metric("Mise à jour", datetime.now().strftime("%H:%M"))

    preview_df = order_df[["name", "price_label", "quantity_label", "line_total_label"]].rename(
        columns={
            "name": "Produit",
            "price_label": "Prix unitaire",
            "quantity_label": "Quantité",
            "line_total_label": "Total",
        }
    )

    st.dataframe(preview_df, hide_index=True, use_container_width=True)

    with st.container(border=True):
        st.markdown("#### Informations client")
        client_name_input = st.text_input(
            "Votre nom",
            value="",
            max_chars=80,
            placeholder="Exemple: Marie Dupont",
        )
        note = st.text_area(
            "Remarque (optionnel)",
            value="",
            max_chars=300,
            placeholder="Indications de retrait, contraintes horaires, etc.",
            height=90,
        )

        client_name = client_name_input.strip()
        is_name_valid, name_message = validate_client_name(client_name)

        if client_name and not is_name_valid:
            st.warning(name_message)

        pdf_bytes = None
        if is_name_valid:
            try:
                cache_key = _build_pdf_cache_key(order_df, client_name, note)
                if st.session_state.pdf_cache_key != cache_key:
                    st.session_state.pdf_cache_bytes = generate_order_pdf(order_df, client_name, note)
                    st.session_state.pdf_cache_key = cache_key
                pdf_bytes = st.session_state.pdf_cache_bytes
            except Exception:
                st.session_state.pdf_cache_key = ""
                st.session_state.pdf_cache_bytes = b""
                st.error("La génération du PDF a échoué. Réessayez après avoir vérifié les données.")

        safe_client_name = make_safe_filename(client_name or "client")
        pdf_filename = f"Commande_{safe_client_name}_{datetime.now():%Y%m%d}.pdf"

        if is_mobile:
            if st.button("Réinitialiser la commande", use_container_width=True):
                _reset_all_order_state()

            st.download_button(
                label="Télécharger le bon de commande",
                data=pdf_bytes if pdf_bytes is not None else b"",
                file_name=pdf_filename,
                mime="application/pdf",
                type="primary",
                disabled=pdf_bytes is None,
                use_container_width=True,
            )
        else:
            action_col_1, action_col_2 = st.columns([1, 2])
            if action_col_1.button("Réinitialiser la commande", use_container_width=True):
                _reset_all_order_state()

            action_col_2.download_button(
                label="Télécharger le bon de commande",
                data=pdf_bytes if pdf_bytes is not None else b"",
                file_name=pdf_filename,
                mime="application/pdf",
                type="primary",
                disabled=pdf_bytes is None,
                use_container_width=True,
            )

        if not client_name:
            st.caption("Renseignez votre nom pour activer le téléchargement.")

    with st.expander("Administration", expanded=False):
        if not has_admin_password():
            st.caption("Espace admin désactivé: définissez `admin.password` dans les secrets pour l'activer.")
        else:
            if not st.session_state.admin_unlocked:
                admin_password = st.text_input("Mot de passe admin", type="password")
                if st.button("Déverrouiller", use_container_width=False):
                    if is_valid_admin_password(admin_password):
                        st.session_state.admin_unlocked = True
                        st.success("Accès admin activé.")
                        st.rerun()
                    else:
                        st.error("Mot de passe invalide.")
            else:
                st.success("Mode administration actif.")

                default_receiver = get_default_receiver() or get_contact_email() or ""
                receiver = st.text_input("Destinataire", value=default_receiver)

                if st.button("Envoyer le PDF par e-mail", use_container_width=True, disabled=pdf_bytes is None):
                    if pdf_bytes is None:
                        st.error("Le PDF n'est pas prêt. Vérifiez le nom client et la commande.")
                    else:
                        subject = f"Commande de la part de {client_name}"
                        body = "Commande générée depuis l'application Streamlit."
                        success, message = send_email(
                            receiver=receiver,
                            subject=subject,
                            body=body,
                            attachment_bytes=pdf_bytes,
                            attachment_name=pdf_filename,
                        )
                        if success:
                            st.success(message)
                        else:
                            st.error(message)

st.markdown("---")
st.markdown("### Contact")
st.markdown("**GAEC Au Champ du Puits**")
st.markdown("211 chemin de la Fontaine")
st.markdown("01430 Peyriat")

contact_email = get_contact_email() or "lechampdupuits@gmail.com"
st.markdown(f"[✉️ {contact_email}](mailto:{contact_email})")
st.link_button("Instagram", "https://www.instagram.com/lechampdupuits/")
