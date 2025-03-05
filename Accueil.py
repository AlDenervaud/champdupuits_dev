import os
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime as dt
# Grid display
#Grid view
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode
from st_aggrid.shared import JsCode, ColumnsAutoSizeMode

from pages.utils.helper import UpdateOrderFinal, ResetOrder
from pages.utils.helper import GeneratePDF, SendEmail

# Retrieve secrets
secrets_email = st.secrets["email"]
email_address = secrets_email["address"]
email_passkey = secrets_email["passkey"]
email_receiver = secrets_email["receiver"]



# Inject custom CSS to enable full screen width
st.markdown(
    """
    <style>
        /* Center content horizontally and align to the top */
        .main .block-container {
            max-width: 2500px;  /* Adjust width as needed */
            margin: 50 auto;    /* Center horizontally */
            padding-top: 50px; /* Adjust top padding for spacing */
            text-align: center; /* Center text */
        }
    </style>
    """,
    unsafe_allow_html=True
)
       
# Title of the Streamlit app
st.title(":rainbow[Bienvenue au Champs du Puits]")

st.markdown("""Sur ce site vous pourrez trouver la liste des produits de la ferme Au Champ du Puits
 et créer un bon de commande à télécharger. Envoyez le bon de commande à l'adresse email ci-dessous, 
 nous tâcherons de vous répondre au plus vite!
 
 La liste est indicative uniquement et ne reflète pas l'état des stocks,
 il se peut que certains produits soient indisponibles.""")
 
###############################################################################

# Basic settings
root_dir = os.path.dirname(__file__)
products_file_path = os.path.join(root_dir, "products.xlsx")

# Get list of products
df = pd.read_excel(products_file_path, sheet_name="products")
df["Prix"] = df["Prix"].apply(lambda x: x if "/kg" in str(x).lower() else "{} €".format(x))
#df["Image_Path"] = df["Image_Path"].astype(str)
df.insert(0, "quantity", 0)
df.insert(0, "select", False)



import pandas as pd
import streamlit as st

# Column configs
image_conf = st.column_config.ImageColumn(label="Photo", width="small", help="Photo non contractuelle")
select_conf = st.column_config.CheckboxColumn(label="Ajouter au panier")
quantity_conf = "Quantité (en kg ou unités)"
# Choose which column are editable
active_cols = ["select", "quantity"]
disabled_cols = [col for col in df.columns if col not in active_cols]

selected_rows = st.data_editor(
                                df,
                                column_config={
                                                "select":select_conf,
                                                "quantity":quantity_conf,
                                                "Catégorie":None,
                                                "Image_Path":image_conf,
                                                },
                                hide_index = True,
                                disabled = disabled_cols,
                                row_height=75,
                            )


# Reset order button
if st.button("Réinitialiser la commande"):
    ResetOrder()

order = selected_rows[selected_rows["select"]]

if order.shape[0]>0:
    
    st.dataframe(order.drop("Image_Path", axis=1))

    # Retrieve client's name
    client_name = st.text_input("Votre nom (appuyez sur entrée pour valider)", value="", placeholder="Veuillez entrer votre nom")
    note = st.text_input("Ajouter une remarque (appuyez sur entrée pour valider)", value="", placeholder="...")
    st.session_state["client_name"] = client_name
    
    # Update prices
    final_order = UpdateOrderFinal(order)
    st.dataframe(final_order)
    # Generate PDF
    pdf_buffer = GeneratePDF(pd.DataFrame(final_order), client_name, note)
    
    # Download button - PDF need to be generated before
    if st.download_button(label="Télécharger le bon de commande",
                    type="primary",
                    data=pdf_buffer,
                    file_name="Commande_{}_{}.pdf".format(client_name.replace(" ", "_"), dt.now().strftime("%d%m%Y")),
                    mime="application/pdf"
                    ):
        pass
    
    if True:#client_name == "admin":
        if st.button("Send Email"):
            #receiver = #"lechampdupuits@gmail.com"
            receiver = email_receiver
            subject = "Commande de la part de {}".format(client_name)
            body = "Test"
            if receiver and subject and body and pdf_buffer:
                SendEmail(receiver, subject, body)
            else:
                st.warning("Please fill in all fields.")
    





###############################################################################

st.markdown("### Contact")
st.markdown("GAEC Au Champ du Puits  \n211 chemin de la Fontaine  \n01430, Peyriat")

st.markdown('<a href="mailto:lechampdupuits@gmail.com">lechampdupuits@gmail.com</a>', unsafe_allow_html=True)
st.page_link("https://www.instagram.com/lechampdupuits/", label="-> Instagram <-")

