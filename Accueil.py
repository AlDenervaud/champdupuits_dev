import os
import streamlit as st
import pandas as pd
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

# Create a grid
gb = GridOptionsBuilder.from_dataframe(df) #, editable=True)
gb.configure_grid_options(rowHeight=100)
gb.configure_selection(selection_mode='multiple', use_checkbox=True)
#gb.configure_pagination(paginationAutoPageSize=False)  # Disable pagination

# Option to add image into the grid display
thumbnail_renderer = JsCode("""
        class ThumbnailRenderer {
            init(params) {
            this.eGui = document.createElement('img');
            this.eGui.setAttribute('src', params.value);
            this.eGui.setAttribute('width', 'auto');
            this.eGui.setAttribute('height', '100');
            }
            getGui() {
            return this.eGui;
            }
        }
    """)

st.success("thumbnail renderer")

# Configure image column to use the renderer
gb.configure_column(
        "Image_Path",
        headerName="Photo",
        width=100,
        cellRenderer=thumbnail_renderer
    )
st.success("column config")
# Display the dataframe with AgGrid
grid = AgGrid(df,
            gridOptions=gb.build(),
            updateMode=GridUpdateMode.VALUE_CHANGED,
            allow_unsafe_jscode=True,
            fit_columns_on_grid_load=True,
            columns_auto_size_mode=ColumnsAutoSizeMode.FIT_ALL_COLUMNS_TO_VIEW,
            height=400,
            custom_css={'.ag-row .ag-cell': {
                                             'display': 'flex',
                                             'justify-content': 'left',
                                             'align-items': 'center'
                                            },
                        '.ag-header-cell-label': {
                                                  'justify-content': 'center'
                                                 },
                        "#gridToolBar": {"padding-bottom": "0px !important"
                                        }
                        }
             )



###############################################################################

st.markdown("### Contact")
st.markdown("GAEC Au Champ du Puits  \n211 chemin de la Fontaine  \n01430, Peyriat")

st.markdown('<a href="mailto:lechampdupuits@gmail.com">lechampdupuits@gmail.com</a>', unsafe_allow_html=True)
st.page_link("https://www.instagram.com/lechampdupuits/", label="-> Instagram <-")

