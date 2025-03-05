import os
import streamlit as st
import pandas as pd
from datetime import datetime as dt
#Grid view
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode
from st_aggrid.shared import JsCode, ColumnsAutoSizeMode
# Report
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# PDF generation function
def generate_pdf(df):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    c.drawString(100, 750, "Commande - GAEC Champ du Puits")
    
    # Add dataframe content to PDF
    y_position = 720
    
    # Add headers 
    headers = " | ".join("{}".format(col) for col in df.columns)
    c.drawString(100, y_position, headers)
    y_position -= 50
    
    # Add rows
    for _, row in df.iterrows():
        line = " | ".join("{}".format(row[col]) for col in df.columns)
        c.drawString(100, y_position, line)
        y_position -= 20
        if y_position < 40:  # Simple page break logic
            c.showPage()
            y_position = 750
    c.save()
    
    buffer.seek(0)
    return buffer

# Title of the Streamlit app
st.title("Générer une commande pour les produits de la ferme")
st.markdown("""Sélectionnez les produits à ajouter à la commande dans la liste ci-dessous (vous pouvez utiliser les filtres pour faciliter la recherche)
et ENSUITE spécifiez la quantité. Tout ajout de produit à la sélection réinitialise les quantité.""")

# Basic settings
root_dir = os.path.dirname(os.path.dirname(__file__))
#root_root_dir = os.path.dirname(os.path.dirname(root_dir))
products_file_path = os.path.join(root_dir, "products.xlsx")


# Get list of products
df = pd.read_excel(products_file_path, sheet_name="apiculture")

### Display solution 2.0
# https://discuss.streamlit.io/t/streamlit-aggrid-version-creating-an-aggrid-with-columns-with-embedded-urls/39640
# https://discuss.streamlit.io/t/add-image-and-header-to-streamlit-dataframe-table/36065/3

gb = GridOptionsBuilder.from_dataframe(df) #, editable=True)
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
grid = AgGrid(df,
            gridOptions=gb.build(),
            updateMode=GridUpdateMode.VALUE_CHANGED,
            allow_unsafe_jscode=True,
            fit_columns_on_grid_load=True,
            columns_auto_size_mode=ColumnsAutoSizeMode.FIT_ALL_COLUMNS_TO_VIEW,
            height=600,
            custom_css={'.ag-row .ag-cell': {
                                             'display': 'flex',
                                             'justify-content': 'center',
                                             'align-items': 'center'
                                            },
                        '.ag-header-cell-label': {
                                                  'justify-content': 'center'
                                                 },
                        "#gridToolBar": {"padding-bottom": "0px !important"
                                        }
                        }
             )



# Display datframe of selected rows
if False:
    options_builder = GridOptionsBuilder.from_dataframe(df)
    grid_options = options_builder.build()

    grid_response = AgGrid(
        df,
        gridOptions=grid_options,
        data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
        update_mode='SELECTION_CHANGED',
        allow_unsafe_jscode=True,
    )

# Extract selected rows
selected_rows = grid['selected_rows']

# Display selected rows as a new dataframe
try:
    if selected_rows:
        pass
    else:
        st.write("Select rows to display them here.")
except:
    selected_df = pd.DataFrame(selected_rows)  # Properly create DataFrame from list of dicts
    selected_df["Quantité"] = [1 for i in range(selected_df.shape[0])]
    # Cleaning
    selected_df.drop("Image_Path", axis=1, inplace=True)
    st.markdown("### Sélection")
    command = st.data_editor(selected_df, use_container_width=False, hide_index=True)


# Button to generate and download PDF
if st.button("Validater la sélection et calculer le prix"):
    try:
        if command is not None:
            # Calculate totals
            command["total_temp"] = command["Prix"].apply(lambda x: float(x.split(" ")[0]))
            command["Total"] = command["total_temp"] * command["Quantité"]
            command = command._append({"Nom":"", "Prix":"", "Quantité":"", "Total":"{} €".format(command["Total"].sum())}, ignore_index=True)
            # Cleaning
            command.drop("total_temp", axis=1, inplace=True)
            # Display before download
            st.dataframe(command, use_container_width=False, hide_index=True)
            pdf_buffer = generate_pdf(pd.DataFrame(command))
            st.download_button(
                label="Télécharger le bon de commande",
                type="primary",
                data=pdf_buffer,
                file_name="Commande.pdf",
                mime="application/pdf"
            )
        else:
            st.error("La sélection est vide!")
    except ValueError as va:
        st.fail("Error: {}".format(va))
