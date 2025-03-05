import os
import streamlit as st
import pandas as pd
import numpy as np
# Grid display
#Grid view
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode
from st_aggrid.shared import JsCode, ColumnsAutoSizeMode

from pages.utils.helper import UpdateOrder
       
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
quantity_conf = "Quantité (en kg ou nombre d\'unités)"
# Choose which column are editable
active_cols = ["select", "quantity"]
disabled_cols = [col for col in df.columns if col not in active_cols]

selected_rows = st.data_editor(
                                df,
                                column_config={
                                                "select":select_conf,
                                                "quantity":quantity_conf,
                                                "Image_Path":image_conf,
                                                },
                                hide_index = True,
                                disabled = disabled_cols,
                                row_height=75,
                            )

# # Display selected rows as a new dataframe
# if selected_rows.shape[0] < 1:
#     st.warning("Sélectionnez au moins un produit")
# else:
#     # Get selected rows and add them to the order df with UpdateOrder()
#     # The selection dataframe needs to be cleaned before
#     selected_rows.drop("Image_Path", axis=1, inplace=True)
#     selected_rows["Quantité"] = np.nan
    
#     UpdateOrder(order_update)


# # Display selected rows as a new dataframe
# try:
#     if selected_rows:
#         pass
#     else:
#         st.write("Les produits sélectionnés s'affichent ci-dessous:")
# except:
#     selected_df = pd.DataFrame(selected_rows)  # Properly create DataFrame from list of dicts
#     selected_df["Quantité"] = np.nan #df['your_column'].astype(float) #[1.0 for i in range(selected_df.shape[0])]
#     # Cleaning
#     selected_df.drop("Image_Path", axis=1, inplace=True)
#     st.markdown("#### Sélection")
#     st.markdown("Indiquez les quantités voulues dans le tableau ci-dessous.")
#     st.markdown("Pour retirer un produit du panier, indiquez 0 dans la colonne \"Quantité\".")
#     selected_df.rename(columns={'Quantité':'Quantité (en kg ou nombre d\'unités)'}, inplace=True)
#     order_update = st.data_editor(selected_df, use_container_width=False, hide_index=True, disabled=[col for col in selected_df if col != "Quantité (en kg ou nombre d\'unités)"])
#     order_update.rename(columns={'Quantité (en kg ou nombre d\'unités)': 'Quantité'}, inplace=True)




###############################################################################

st.markdown("### Contact")
st.markdown("GAEC Au Champ du Puits  \n211 chemin de la Fontaine  \n01430, Peyriat")

st.markdown('<a href="mailto:lechampdupuits@gmail.com">lechampdupuits@gmail.com</a>', unsafe_allow_html=True)
st.page_link("https://www.instagram.com/lechampdupuits/", label="-> Instagram <-")

