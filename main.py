"""Waste-to-Wardrobe Index module.

Provides functions to estimate potential avoided textile waste and
associated CO₂ emissions if Vinted‑style peer‑to‑peer resale covers a
given share of total clothing purchases for each country.

The workflow:

1. Download per‑capita textile waste data for EU member states (EEA
   Circularity Lab) and for the United States (EPA SIT).
2. Retrieve most recent total population figures from the World
   Bank API.
3. Combine datasets to calculate annual textile waste mass for each
   country.
4. Apply user‑defined resale coverage scenarios to estimate the share
   of waste diverted.
5. Convert diverted waste mass to number of items and CO₂ avoided
   using Vinted’s 2023 impact factors.
6. Write results to CSV and generate a choropleth map plus bar chart
   ranking top countries.

Assumptions embedded here are placeholders; update them with the
official values from the source reports as soon as possible.
"""

import pathlib
from typing import List, Dict

import requests
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt

EEA_WASTE_CSV_URL = 'data/raw/Waste generation.csv'
EPA_WASTE_PER_CAPITA_KG_US = 47.0  # Placeholder
WORLD_BANK_POP_API = (
    "https://api.worldbank.org/v2/country/{code}/indicator/SP.POP.TOTL" "?format=json&per_page=1"
)
AVG_ITEM_WEIGHT_KG = 0.6  # Placeholder; refine with Vinted data
CO2_SAVED_PER_ITEM_KG = 1.25
COVERAGE_SCENARIOS = [0.10, 0.25]
OUTPUT_DIR = pathlib.Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)


def load_eea_waste() -> pd.DataFrame:
    """Return EU per‑capita textile waste in kilograms."""
    df = pd.read_csv(EEA_WASTE_CSV_URL)
    return df[["country_code", "country_name", "waste_kg_per_capita"]]


def load_epa_waste() -> pd.DataFrame:
    """Return US per‑capita textile waste in kilograms."""
    return pd.DataFrame(
        {
            "country_code": ["USA"],
            "country_name": ["United States"],
            "waste_kg_per_capita": [EPA_WASTE_PER_CAPITA_KG_US],
        }
    )


def fetch_population(country_code: str, year: int = 2023) -> int:
    """Retrieve population from World Bank for the specified year."""
    resp = requests.get(WORLD_BANK_POP_API.format(code=country_code))
    data = resp.json()
    for row in data[1]:
        if row["date"] == str(year):
            return int(row["value"])
    raise ValueError(f"Population for {country_code} {year} not found")


def add_population(df: pd.DataFrame, year: int = 2023) -> pd.DataFrame:
    """Append population column to dataframe."""
    pops: Dict[str, int] = {}
    for code in df["country_code"]:
        pops[code] = fetch_population(code, year)
    df["population"] = df["country_code"].map(pops)
    return df


def calculate_potential(df: pd.DataFrame) -> pd.DataFrame:
    """Compute avoided waste and CO₂ for each coverage scenario."""
    df["annual_waste_kg"] = df["waste_kg_per_capita"] * df["population"]
    results: List[pd.DataFrame] = []
    for cov in COVERAGE_SCENARIOS:
        temp = df.copy()
        temp["coverage"] = cov
        temp["avoided_waste_kg"] = temp["annual_waste_kg"] * cov
        temp["avoided_items"] = temp["avoided_waste_kg"] / AVG_ITEM_WEIGHT_KG
        temp["avoided_co2_kg"] = temp["avoided_items"] * CO2_SAVED_PER_ITEM_KG
        results.append(temp)
    return pd.concat(results, ignore_index=True)


def save_results(df: pd.DataFrame) -> None:
    """Write computation results to CSV."""
    df.to_csv(OUTPUT_DIR / "waste_to_wardrobe_results.csv", index=False)


def plot_choropleth(df: pd.DataFrame, coverage: float) -> None:
    """Generate choropleth map of avoided CO₂ emissions."""
    world = gpd.read_file(gpd.datasets.get_path("naturalearth_lowres"))
    data = (
        df[df["coverage"] == coverage]
        .rename(columns={"country_code": "iso_a3"})
        .copy()
    )
    merged = world.merge(data, on="iso_a3", how="left")
    ax = merged.plot(
        column="avoided_co2_kg",
        scheme="quantiles",
        legend=True,
        figsize=(12, 6),
    )
    ax.set_title(
        f"Potential CO₂ Avoided via Resale Coverage {coverage:.0%}"
    )
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / f"map_co2_{int(coverage*100)}.png", dpi=300)


def plot_bar_top(df: pd.DataFrame, coverage: float, top_n: int = 15) -> None:
    """Plot bar chart of top countries by avoided CO₂."""
    data = (
        df[df["coverage"] == coverage]
        .sort_values("avoided_co2_kg", ascending=False)
        .head(top_n)
    )
    plt.figure(figsize=(10, 6))
    plt.bar(
        data["country_name"],
        data["avoided_co2_kg"] / 1e6,
    )
    plt.xticks(rotation=45, ha="right")
    plt.ylabel("Avoided CO₂ (Mt)")
    plt.title(
        f"Top {top_n} Countries: CO₂ Avoided at {coverage:.0%} Coverage"
    )
    plt.tight_layout()
    plt.savefig(OUTPUT_DIR / f"bar_co2_{int(coverage*100)}.png", dpi=300)


def main() -> None:
    """Run full pipeline."""
    eea = load_eea_waste()
    epa = load_epa_waste()
    waste = pd.concat([eea, epa], ignore_index=True)
    waste = add_population(waste)
    potential = calculate_potential(waste)
    save_results(potential)
    for cov in COVERAGE_SCENARIOS:
        plot_choropleth(potential, cov)
        plot_bar_top(potential, cov)


if __name__ == "__main__":
    main()
