import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# --- Streamlit config must be first ---
st.set_page_config(layout="wide")

# --- Load Data ---
def load_eea_data():
    df = pd.read_excel(
        r"C:\Users\user\PycharmProjects\waste_to_wardrobe_index\data\raw\EEA_europe_waste_per_capita_2020.xlsx"
    )
    df.columns = df.columns.astype(str)
    df = df.rename(columns={df.columns[0]: "Country"})

    textile_col = "Total value"
    if textile_col not in df.columns:
        st.error(f"Column '{textile_col}' not found in EEA data.")
        return pd.DataFrame(columns=["Country", "Textile Waste (kg/person)"])

    df = df.rename(columns={textile_col: "Textile Waste (kg/person)"})
    exclude = ["EU27", "EU28", "Europe", "OECD", "EFTA", "EU", "European Union"]
    df = df[~df["Country"].isin(exclude)]
    df["Country"] = df["Country"].replace({"Türkiye": "Turkey"})
    return df[["Country", "Textile Waste (kg/person)"]].dropna()

df_eea = load_eea_data()
us_data = pd.DataFrame({"Country": ["United States"], "Textile Waste (kg/person)": [40.22]})
df = pd.concat([df_eea, us_data], ignore_index=True).sort_values("Country")


# --- Title and Styling ---
st.markdown("""
<style>
    html, body, [class*="css"] {
        font-family: 'Open Sans', sans-serif;
    }
</style>
""", unsafe_allow_html=True)

st.title("🧵 Waste-to-Wardrobe Index")
st.subheader("Estimate CO₂ savings from replacing textile waste with second-hand fashion")

# --- Scenario Slider ---
scenario_pct = st.slider("Select % of textile waste replaced via resale", 10, 50, 25, step=5)
reuse_fraction = scenario_pct / 100
CO2E_PER_ITEM = 1.25  # kg CO2e per item

# --- Population Settings ---
st.sidebar.header("👥 Population Settings (millions)")
default_pops = {
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
    default = default_pops.get(country, 10.0)
    populations[country] = st.sidebar.number_input(f"{country}", min_value=0.1, value=float(default), step=0.1)


# --- CO₂e Calculation ---
data = []
for _, row in df.iterrows():
    country = row["Country"]
    waste = row["Textile Waste (kg/person)"]
    pop = populations[country]
    reused = waste * reuse_fraction
    items = reused * pop * 1_000_000
    saved = items * CO2E_PER_ITEM / 1_000_000

    data.append({
        "Country": country,
        "Textile Waste (kg/person)": round(waste, 2),
        "Population (millions)": pop,
        f"Reused ({scenario_pct}%) (kg/person)": round(reused, 2),
        "CO₂ Avoided (kt)": round(saved, 2)
    })

result_df = pd.DataFrame(data).sort_values("CO₂ Avoided (kt)", ascending=False)

# --- ISO Mapping for Map ---
iso_df = pd.read_csv("https://raw.githubusercontent.com/datasets/country-codes/master/data/country-codes.csv")
iso_dict = dict(zip(iso_df["official_name_en"], iso_df["ISO3166-1-Alpha-3"]))
manual = {"United States": "USA", "Turkey": "TUR", "Czechia": "CZE"}
result_df["ISO_Code"] = result_df["Country"].map({**iso_dict, **manual})
result_df.dropna(subset=["ISO_Code"], inplace=True)

# --- Log Toggle ---
use_log = st.checkbox("Use log scale for CO₂ Avoided color scale", True)
if use_log:
    result_df["CO₂ Avoided (kt) Log"] = np.log1p(result_df["CO₂ Avoided (kt)"])
    color_col = "CO₂ Avoided (kt) Log"
    label = "Log kt CO₂e saved"
else:
    color_col = "CO₂ Avoided (kt)"
    label = "kt CO₂e saved"

# --- Plotly Bar Chart ---
st.subheader("📊 CO₂ Savings by Country (Excludes USA)")
bar_df = result_df[result_df["Country"] != "United States"]
fig_bar = go.Figure(go.Bar(
    y=bar_df["Country"],
    x=bar_df["CO₂ Avoided (kt)"],
    orientation='h',
    marker_color='mediumseagreen',
    hovertemplate='%{y}<br>CO₂ Avoided: %{x:.2f} kt'
))
fig_bar.update_layout(
    xaxis_title="CO₂e Avoided (kt/year)",
    yaxis=dict(autorange="reversed"),
    height=600,
    template="plotly_white",
    font=dict(family="Open Sans", size=14)
)
st.plotly_chart(fig_bar, use_container_width=True)

# --- Plotly Choropleth Map ---
st.subheader("🗼 CO₂e Savings Map")
fig_map = px.choropleth(
    result_df,
    locations="ISO_Code",
    color=color_col,
    hover_name="Country",
    color_continuous_scale="YlGn",
    labels={color_col: label},
    projection="natural earth"
)
fig_map.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
st.plotly_chart(fig_map, use_container_width=True)

# --- Table ---
st.subheader("📋 Detailed Table")
st.dataframe(result_df.set_index("Country"))

# --- Download ---
def convert_df(df):
    return df.to_csv(index=False).encode("utf-8")

st.download_button(
    label="📅 Download CSV",
    data=convert_df(result_df),
    file_name="waste_to_wardrobe_results.csv",
    mime="text/csv"
)
