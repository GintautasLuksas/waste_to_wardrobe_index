import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import plotly.express as px
import numpy as np
import os, pathlib, tempfile
asds
tmp_home = pathlib.Path(tempfile.gettempdir())
os.environ["HOME"] = str(tmp_home)
os.environ["STREAMLIT_HOME"] = str(tmp_home)
os.environ["STREAMLIT_DISABLE_USAGE_STATS"] = "true"


# --- Streamlit Config ---
st.set_page_config(layout="wide")

# --- Load EEA Data ---
@st.cache_data
def load_eea_data():
    df = pd.read_excel(
        r"C:\Users\user\PycharmProjects\waste_to_wardrobe_index\data\raw\EEA_europe_waste_per_capita_2020.xlsx"
    )
    df.columns = df.columns.astype(str)
    df = df.rename(columns={df.columns[0]: "Country"})
    df = df.rename(columns={"Total value": "Textile Waste (kg/person)"})
    df = df[~df["Country"].isin(["EU27", "EU28", "Europe", "OECD", "EFTA", "EU", "European Union"])]
    df["Country"] = df["Country"].replace({"Türkiye": "Turkey"})
    df = df[["Country", "Textile Waste (kg/person)"]].dropna()
    return df

eea_df = load_eea_data()

# --- Add United States ---
us_data = pd.DataFrame({
    "Country": ["United States"],
    "Textile Waste (kg/person)": [40.22]
})
df_full = pd.concat([eea_df, us_data], ignore_index=True).sort_values("Country")

# --- Title ---
st.title("🧵 Waste-to-Wardrobe Index")
st.subheader("Estimate CO₂ savings from replacing textile waste with second-hand fashion")

# --- Country Selector ---
all_countries = df_full["Country"].unique().tolist()
selected_countries = st.multiselect(
    "🌍 Select countries to include in the analysis:",
    options=all_countries,
    default=[c for c in all_countries if c != "United States"]
)

df = df_full[df_full["Country"].isin(selected_countries)]

# --- Reuse Scenario ---
scenario_pct = st.slider("♻️ % of textile waste replaced via resale", 10, 50, 25, step=5)
reuse_fraction = scenario_pct / 100
CO2E_PER_ITEM = 1.25  # kg CO2e per item resold

# --- Sidebar: Population Inputs ---
st.sidebar.header("👥 Population Settings (millions)")
default_populations = {
    "Austria": 9, "Belgium": 11.5, "Bulgaria": 7, "Croatia": 4, "Cyprus": 1.2,
    "Czechia": 10.7, "Denmark": 5.8, "Estonia": 1.3, "Finland": 5.5, "France": 67,
    "Germany": 83, "Greece": 10.7, "Hungary": 9.7, "Iceland": 0.36, "Ireland": 5,
    "Italy": 60, "Latvia": 1.9, "Lithuania": 2.8, "Luxembourg": 0.6, "Malta": 0.5,
    "Netherlands": 17, "Norway": 5.4, "Poland": 38, "Portugal": 10.2, "Romania": 19,
    "Slovakia": 5.5, "Slovenia": 2.1, "Spain": 47, "Sweden": 10, "Turkey": 85,
    "United Kingdom": 67, "United States": 327
}
populations = {}
for country in df["Country"]:
    default = float(default_populations.get(country, 10.0))
    pop = st.sidebar.number_input(f"{country}", min_value=0.1, value=default, step=0.1)
    populations[country] = pop

# --- Calculate CO₂ Savings ---
data = []
for _, row in df.iterrows():
    country = row["Country"]
    waste_kg = row["Textile Waste (kg/person)"]
    pop_mil = populations[country]
    reused_kg_per_person = waste_kg * reuse_fraction
    total_items = reused_kg_per_person * pop_mil * 1_000_000
    co2e_saved_kg = total_items * CO2E_PER_ITEM
    co2e_saved_kt = co2e_saved_kg / 1_000_000

    data.append({
        "Country": country,
        "Textile Waste (kg/person)": round(waste_kg, 2),
        "Population (millions)": pop_mil,
        f"Reused ({scenario_pct}%) (kg/person)": round(reused_kg_per_person, 2),
        "CO₂ Avoided (kt)": round(co2e_saved_kt, 2)
    })

result_df = pd.DataFrame(data).sort_values(by="CO₂ Avoided (kt)", ascending=False)

# --- ISO Codes for Map ---
iso_map = pd.read_csv(
    "https://raw.githubusercontent.com/datasets/country-codes/master/data/country-codes.csv"
)[["official_name_en", "ISO3166-1-Alpha-3"]]
country_to_iso = dict(zip(iso_map["official_name_en"], iso_map["ISO3166-1-Alpha-3"]))
manual_iso = {"United States": "USA", "Turkey": "TUR", "Czechia": "CZE"}
country_to_iso.update(manual_iso)
result_df["ISO_Code"] = result_df["Country"].map(country_to_iso)
result_df = result_df.dropna(subset=["ISO_Code"])

# --- Optional Log Scale ---
use_log_scale = st.toggle("Use log scale on map", value=True)
if use_log_scale:
    result_df["CO₂ Avoided (kt) Log"] = np.log1p(result_df["CO₂ Avoided (kt)"])
    color_col = "CO₂ Avoided (kt) Log"
    color_label = "Log kt CO₂e saved"
else:
    color_col = "CO₂ Avoided (kt)"
    color_label = "kt CO₂e saved"

# --- TABS: Chart | Map | Table ---
tab1, tab2, tab3 = st.tabs(["📊 Bar Chart", "🗺️ Map", "📋 Data Table"])

with tab1:
    fig_bar, ax = plt.subplots(figsize=(10, 6))
    ax.barh(result_df["Country"], result_df["CO₂ Avoided (kt)"], color='seagreen')
    ax.set_xlabel("CO₂e Avoided (kt/year)")
    ax.set_title(f"CO₂e Savings if {scenario_pct}% of Textile Waste is Replaced by Resale")
    ax.invert_yaxis()
    st.pyplot(fig_bar)

with tab2:
    fig_map = px.choropleth(
        result_df,
        locations="ISO_Code",
        color=color_col,
        hover_name="Country",
        color_continuous_scale="YlGn",
        labels={color_col: color_label},
        template="plotly_white",
        projection="natural earth"
    )
    fig_map.update_layout(
        geo=dict(showframe=False, showcoastlines=True),
        margin={"r": 0, "t": 0, "l": 0, "b": 0}
    )
    st.plotly_chart(fig_map, use_container_width=True)

with tab3:
    st.dataframe(result_df.set_index("Country"))

# --- Export CSV ---
def convert_df(df):
    return df.to_csv(index=False).encode('utf-8')

st.download_button(
    label="📥 Download Results as CSV",
    data=convert_df(result_df),
    file_name="waste_to_wardrobe_results.csv",
    mime="text/csv"
)
