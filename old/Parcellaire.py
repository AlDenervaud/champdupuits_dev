import geopandas as gpd
import streamlit as st
import folium
from streamlit_folium import st_folium
import json


# Streamlit app configuration
st.title("Carte du parcellaire")

# Upload shapefile (multiple files including .shp, .shx, .dbf)
# shapefile = st.file_uploader("Upload a Shapefile (multiple files: .shp, .shx, .dbf, etc.)", type=["zip"])
shapefile = True

shapefile_path = r"https://github.com/AlDenervaud/champdupuits/raw/refs/heads/main/data/parcelles_v4.zip"

# Define a style function based on "exploite" attribute
def style_function(feature):
    exploite_value = feature['properties']['exploite']
    return {
        'fillColor': 'green' if exploite_value == 'oui' else 'red',  # Fill color
        'color': 'black',                                            # Stroke color (edge)
        'weight': 0.5,                                               # Stroke thickness
        'fillOpacity': 0.7 if exploite_value == 'oui' else 0.4,      # Fill opacity
        'opacity': 0.8 if exploite_value == 'oui' else 0.6,          # Stroke opacity
        'dashArray': '5, 5' if exploite_value == 'non' else '1',     # Optional: Dash pattern for edges
    }
        
if shapefile:
    try:
        # Extract and read the uploaded zip file
        #with open("uploaded_shapefile.zip", "wb") as f:
        #    f.write(shapefile.read())
        #gdf = gpd.read_file("zip://uploaded_shapefile.zip")
        gdf = gpd.read_file(shapefile_path)
        
        # Ensure correct CRS (change to your target CRS if known)
        target_crs = "EPSG:4326"  # WGS 84
        if gdf.crs != target_crs:
            gdf = gdf.to_crs(target_crs)
        
        # Convert the geopandas dataframe to GeoJSON format
        geojson_data = json.loads(gdf.to_json())
        
        # Initial map display
        m = folium.Map(location=[gdf.geometry.centroid.y.mean(), gdf.geometry.centroid.x.mean()], zoom_start=13)

        # Add GeoJson layer with the custom style function
        folium.GeoJson(
            geojson_data,
            name="Styled GeoJSON",
            style_function=style_function,
            tooltip=folium.GeoJsonTooltip(
                fields=["geo_parcel", "exploite"],                # Specify the column to display
                aliases=["Parcelle: ", "Exploitée: "],                 # Label before the value (optional)
                style="font-size: 24px;",
            )
        ).add_to(m)
        
        # Add JavaScript to capture the click event on polygons and send back the properties
        m.get_root().html.add_child(
            folium.Element("""
            <script>
                map.on('click', function(e) {
                    var layer = e.layer;
                    if (layer.feature && layer.feature.properties) {
                        var properties = layer.feature.properties;
                        var geo_parcel = properties.geo_parcel;
                        window.parent.postMessage({type: "click", geo_parcel: geo_parcel}, "*");
                    }
                });
            </script>
            """)
        )

        tile = folium.TileLayer(
                tiles = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                attr = 'Esri',
                name = 'Esri Satellite',
                overlay = False,
                control = True
               ).add_to(m)
                       
        map_display = st_folium(m, width=800, height=500)
        
        # Capture the clicked feature data from the map using the `last_clicked` field in `map_display`
        if map_display and 'last_object_clicked_tooltip' in map_display:
            clicked_data = map_display['last_object_clicked_tooltip']
            st.markdown("#### Sélection")
            try:
                clicked_data = clicked_data.replace(" ", "").split("\n")
                feature_name = [i for i in clicked_data if i != ""][1]
                st.success(feature_name)
            except Exception as e:
                st.warning("Aucune parcelle sélectionée")

    except Exception as e:
        st.error(f"Error: {str(e)}")
