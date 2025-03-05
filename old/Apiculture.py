import os
import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
from st_aggrid.shared import JsCode, ColumnsAutoSizeMode

# Title of the Streamlit app
st.title("Liste des produits Apicoles :bee:")

# Basic settings
root_dir = os.path.dirname(os.path.dirname(__file__))
#root_root_dir = os.path.dirname(os.path.dirname(root_dir))
products_file_path = os.path.join(root_dir, "products.xlsx")


# Get list of products
df = pd.read_excel(products_file_path, sheet_name="apiculture")

### Display solution 2.0
# https://discuss.streamlit.io/t/streamlit-aggrid-version-creating-an-aggrid-with-columns-with-embedded-urls/39640
# https://discuss.streamlit.io/t/add-image-and-header-to-streamlit-dataframe-table/36065/3

gb = GridOptionsBuilder.from_dataframe(df, editable=True)
gb.configure_grid_options(rowHeight=100)
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

grid = AgGrid(df,
            gridOptions=gb.build(),
            updateMode=GridUpdateMode.VALUE_CHANGED,
            allow_unsafe_jscode=True,
            fit_columns_on_grid_load=True,
            columns_auto_size_mode=ColumnsAutoSizeMode.FIT_ALL_COLUMNS_TO_VIEW,
            height=800,
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
