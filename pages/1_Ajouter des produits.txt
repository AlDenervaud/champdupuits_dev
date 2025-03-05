import os
import streamlit as st
import pandas as pd
import numpy as np
#Grid view
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
from st_aggrid.shared import JsCode, ColumnsAutoSizeMode


# Title of the Streamlit app
st.title("Liste des produits")

# Basic settings
root_dir = os.path.dirname(os.path.dirname(__file__))
products_file_path = os.path.join(root_dir, "products.xlsx")

# Get list of products
df = pd.read_excel(products_file_path, sheet_name="products")
df["Prix"] = df["Prix"].apply(lambda x: x if "/kg" in str(x).lower() else "{} €".format(x))

### Display solution 2.0
# https://discuss.streamlit.io/t/streamlit-aggrid-version-creating-an-aggrid-with-columns-with-embedded-urls/39640
# https://discuss.streamlit.io/t/add-image-and-header-to-streamlit-dataframe-table/36065/3

filtered_df = df.copy()

st.dataframe(filtered_df)

gb = GridOptionsBuilder.from_dataframe(filtered_df) #, editable=True)
gb.configure_grid_options(rowHeight=100)
gb.configure_selection(selection_mode='multiple', use_checkbox=True)

#gb.configure_pagination(paginationAutoPageSize=False)  # Disable pagination

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

gb.configure_column(
    "Image_Path",
    headerName="Photo",
    width=100,
    cellRenderer=thumbnail_renderer
)

# Display the dataframe with AgGrid
try:
    grid = AgGrid(filtered_df,
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
except Exception as e:
    st.write(e)

# Extract selected rows
selected_rows = grid['selected_rows']

# Display selected rows as a new dataframe
try:
    if selected_rows:
        pass
    else:
        st.write("Les produits sélectionnés s'affichent ci-dessous:")
except:
    selected_df = pd.DataFrame(selected_rows)  # Properly create DataFrame from list of dicts
    selected_df["Quantité"] = np.nan #df['your_column'].astype(float) #[1.0 for i in range(selected_df.shape[0])]
    # Cleaning
    selected_df.drop("Image_Path", axis=1, inplace=True)
    st.markdown("#### Sélection")
    st.markdown("Indiquez les quantités voulues dans le tableau ci-dessous.")
    st.markdown("Pour retirer un produit du panier, indiquez 0 dans la colonne \"Quantité\".")
    selected_df.rename(columns={'Quantité':'Quantité (en kg ou nombre d\'unités)'}, inplace=True)
    order_update = st.data_editor(selected_df, use_container_width=False, hide_index=True, disabled=[col for col in selected_df if col != "Quantité (en kg ou nombre d\'unités)"])
    order_update.rename(columns={'Quantité (en kg ou nombre d\'unités)': 'Quantité'}, inplace=True)

# Button to generate and download PDF
if st.button("Ajouter la sélection à la commande"):
    try:
        if order_update is not None:
            if order_update['Quantité'].isnull().any():
                st.error("Veuillez indiquer une quantité pour chaque élément")
            else:
                # Save to session state
                UpdateOrder(order_update)
                order_df = st.session_state["order_df"]
                # Display current order
                st.markdown("### Commande")
                st.dataframe(order_df, use_container_width=False, hide_index=True)

        else:
            st.error("La sélection est vide!")
    except ValueError as va:
        st.error("Error: {}".format(va))
