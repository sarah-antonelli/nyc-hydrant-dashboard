# app.py
# ---------------------------------------------------------------------------
# Streamlit dashboard for NYC hydrant density analysis.
#
# Displays an interactive map and data table of fire hydrant density
# by neighborhood, with sidebar filters for borough and density range.
#
# Data:     data.parquet (GeoParquet from Lesson 2.5)
#           262 NYC neighborhoods with hydrant_count, area_km2,
#           and hydrants_per_km2 columns.
#
# Usage:    streamlit run app.py
# ---------------------------------------------------------------------------

import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

# --- Page config ----------------------------------------------------------
st.set_page_config(
    page_title="NYC Hydrant Density",
    page_icon="🚒",
    layout="wide",
)

# --- Load data (cached so it only reads once) -----------------------------
@st.cache_data
def load_data():
    gdf = gpd.read_parquet("data.parquet")
    # Only keep residential neighborhoods (ntatype '0') that have hydrants
    gdf = gdf[gdf["ntatype"] == "0"].copy()
    # Round for cleaner display
    gdf["area_km2"] = gdf["area_km2"].round(2)
    gdf["hydrants_per_km2"] = gdf["hydrants_per_km2"].round(1)
    return gdf

data = load_data()


# --- Sidebar filters ------------------------------------------------------
st.sidebar.header("Filters")

# Borough filter
boroughs = sorted(data["boroname"].unique())
selected_boroughs = st.sidebar.multiselect(
    "Borough",
    options=boroughs,
    default=boroughs,
)

# Density range slider
density_min = float(data["hydrants_per_km2"].min())
density_max = float(data["hydrants_per_km2"].max())
density_range = st.sidebar.slider(
    "Hydrant density (per km²)",
    min_value=density_min,
    max_value=density_max,
    value=(density_min, density_max),
    step=0.1,
)

# Apply filters
filtered = data[
    (data["boroname"].isin(selected_boroughs))
    & (data["hydrants_per_km2"] >= density_range[0])
    & (data["hydrants_per_km2"] <= density_range[1])
].copy()

# --- Title and description ------------------------------------------------
st.title("NYC Fire Hydrant Density")
st.markdown(
    "Explore fire hydrant density across NYC neighborhoods. "
    "Use the sidebar to filter by borough and density range."
)

# --- Metrics row ----------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)
col1.metric("Neighborhoods", f"{len(filtered):,}")
col2.metric("Total Hydrants", f"{int(filtered['hydrant_count'].sum()):,}")
col3.metric(
    "Mean Density",
    f"{filtered['hydrants_per_km2'].mean():.1f} / km²" if len(filtered) > 0 else "—",
)
col4.metric(
    "Max Density",
    f"{filtered['hydrants_per_km2'].max():.1f} / km²" if len(filtered) > 0 else "—",
)

# --- Map ------------------------------------------------------------------
st.subheader("Map")

if len(filtered) == 0:
    st.warning("No neighborhoods match the current filters. Adjust the sidebar.")
else:
    # Build a color map matching the YlOrRd scheme used in Lessons 2.5 and 3.3
    ramp_colors = [
        "#ffffcc",
        "#fed976",
        "#fd8d3c",
        "#e31a1c",
        "#800026",
    ]

    colormap = mcolors.LinearSegmentedColormap.from_list(
        "hydrant",
        ramp_colors,
    )

    norm = mcolors.Normalize(
        vmin=data["hydrants_per_km2"].min(),
        vmax=data["hydrants_per_km2"].max(),
    )

    def get_color(density):
        rgba = colormap(norm(density))
        return mcolors.to_hex(rgba)

    # Create the Folium map centered on the filtered data
    bounds = filtered.total_bounds  # [minx, miny, maxx, maxy]
    center_lat = (bounds[1] + bounds[3]) / 2
    center_lon = (bounds[0] + bounds[2]) / 2

    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=11,
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
        attr="Esri"
    )

    # Add each neighborhood as a colored polygon with a tooltip
    for _, row in filtered.iterrows():
        color = get_color(row["hydrants_per_km2"])

        # Convert geometry to GeoJSON for Folium
        geo_json = gpd.GeoSeries([row["geometry"]]).__geo_interface__

        folium.GeoJson(
            geo_json,
            style_function=lambda feature, c=color: {
                "fillColor": c,
                "color": "#333",
                "weight": 0.5,
                "fillOpacity": 0.7,
            },
            tooltip=folium.Tooltip(
                f"<b>{row['ntaname']}</b><br>"
                f"{row['boroname']}<br>"
                f"Hydrants: {row['hydrant_count']}<br>"
                f"Density: {row['hydrants_per_km2']} / km²"
            ),
        ).add_to(m)

    # Fit the map to the filtered extent
    m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])

    # Add map legend
    legend_min = data["hydrants_per_km2"].min()
    legend_max = data["hydrants_per_km2"].max()

    gradient = ", ".join(ramp_colors)

    legend_html = f"""
    <div style="
    position: fixed;
    bottom: 40px;
    left: 40px;
    width: 200px;
    background-color: white;
    border: 2px solid grey;
    border-radius: 5px;
    padding: 10px;
    font-size: 14px;
    color: black;
    z-index: 9999;
    ">
    <b>Hydrant Density per km²</b><br>

    <div style="display:flex; justify-content:space-between;">
    <span>{legend_min:.1f}</span>
    <span>{legend_max:.1f}</span>
    </div>

    <div style="
    margin-top: 5px;
    height: 20px;
    background: linear-gradient(
        to right,
        {gradient}
    );  
    background: linear-gradient(
        to right,
        #ffffcc,
        #fed976,
        #fd8d3c,
        #e31a1c,
        #800026
    );
    "></div>

    <div style="
    display:flex;
    justify-content:space-between;
    margin-top:4px;
    ">
    <span>Low</span>
    <span>High</span>
    </div>

    </div>
    """

    m.get_root().html.add_child(
        folium.Element(legend_html)
    )

    st_folium(m, use_container_width=True, height=500)

# --- Top 15 Neighborhoods Chart -------------------------------------------
st.subheader("Top 15 Neighborhoods by Hydrant Density")

if len(filtered) > 0:

    top15 = (
        filtered.sort_values(
            "hydrants_per_km2",
            ascending=False
        )
        .head(15)
    )

    borough_colors = {
        "Manhattan": "#1f77b4",
        "Brooklyn": "#ff7f0e",
        "Queens": "#2ca02c",
        "Bronx": "#d62728",
        "Staten Island": "#9467bd",
    }

    colors = [
        borough_colors.get(boro, "gray")
        for boro in top15["boroname"]
    ]

    fig, ax = plt.subplots(figsize=(14, 8))

    ax.barh(
        top15["ntaname"],
        top15["hydrants_per_km2"],
        color=colors
    )

    ax.set_xlabel("Hydrants per km²")
    ax.set_ylabel("Neighborhood")
    ax.set_title("Top 15 Neighborhoods by Hydrant Density")

    ax.invert_yaxis()

    from matplotlib.patches import Patch

    present_boroughs = top15["boroname"].unique()

    legend_elements = [
        Patch(facecolor=color, label=boro)
        for boro, color in borough_colors.items()
        if boro in present_boroughs
    ]

    ax.legend(
        handles=legend_elements,
        title="Borough",
        bbox_to_anchor=(1.02, 1),
        loc="upper left"
    )

    plt.subplots_adjust(right=0.80)
    st.pyplot(fig)

# --- Download Filtered Data ----------------------------------------------
csv = (
    filtered[
        [
            "ntaname",
            "boroname",
            "hydrant_count",
            "area_km2",
            "hydrants_per_km2",
        ]
    ]
    .to_csv(index=False)
)

st.download_button(
    label="Download filtered data (CSV)",
    data=csv,
    file_name="nyc_hydrant_density_filtered.csv",
    mime="text/csv",
)

# --- Data table -----------------------------------------------------------
st.subheader("Data Table")

display_cols = ["ntaname", "boroname", "hydrant_count", "area_km2", "hydrants_per_km2"]
st.dataframe(
    filtered[display_cols]
    .sort_values("hydrants_per_km2", ascending=False)
    .reset_index(drop=True),
    use_container_width=True,
    column_config={
        "ntaname": "Neighborhood",
        "boroname": "Borough",
        "hydrant_count": st.column_config.NumberColumn("Hydrants", format="%d"),
        "area_km2": st.column_config.NumberColumn("Area (km²)", format="%.2f"),
        "hydrants_per_km2": st.column_config.NumberColumn("Density (/km²)", format="%.1f"),
    },
)

# --- Sidebar info ---------------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.markdown(
    "**Data Source:** NYC Open Data — "
    "[NTA Neighborhoods](https://data.cityofnewyork.us/City-Government/2020-Neighborhood-Tabulation-Areas-NTAs-/9nt8-h7nd) "
    "and [Hydrants](https://data.cityofnewyork.us/Environment/Hydrants/5bgh-vtsn)"
)

st.sidebar.markdown("**About This Project:** Created as part of the Modern GIS Accelerator to demonstrate an end-to-end geospatial"
"   workflow, from data aquisition and spatial analysis through interactive web mapping and cloud deployment.")

st.sidebar.markdown(
    """
    **Built With**
    
    • Python and Pandas for data processing  
    • GeoPandas for spatial analysis  
    • Folium and Leaflet for web mapping  
    • Matplotlib for visualization  
    • Streamlit for dashboard development and deployment  
    • Apache Parquet for data storage
    """
)