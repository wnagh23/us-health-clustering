# Data

All files are processed, state-level extracts (50 states; some files also contain DC or territories, which are dropped when merging). Total size is about 1 MB, so they are committed to the repo. The scripts in `scripts/` show how each file was obtained.

| File | Source | Content | Script |
|---|---|---|---|
| `brfss_npao_states.csv` | CDC BRFSS – [Nutrition, Physical Activity, and Obesity](https://data.cdc.gov/d/hn4x-zwk7) | Adult obesity, overweight, physical (in)activity and fruit/vegetable intake; "Total" stratification; 2011–2024 | `fetch_brfss.py` (no key) |
| `acs_states.csv` | U.S. Census Bureau – ACS 1-Year Data Profile | Income, poverty, education, health insurance, commuting, working from home; 2013–2023 without 2020 | `fetch_census.py` (`CENSUS_API_KEY`) |
| `cbp_businesses.csv` | U.S. Census Bureau – County Business Patterns | Number of fitness centers (NAICS 713940) and liquor stores (NAICS 445310); 2012–2023 | `fetch_census.py` |
| `noaa_weather_monthly.csv` | NOAA NCEI – Global Summary of the Month (CDO API) | Mean monthly temperature and precipitation, averaged over all GHCN stations in a state; 2011–2023 | `fetch_noaa.py` (`NOAA_TOKEN`) |
| `us_regions.csv` | U.S. Census Bureau regions and divisions | State → region / division | – |

## Known data issues (handled in `src/ushealth/data.py`)

- **ACS variable codes shift between years.** `DP02_0068PE` means "bachelor's degree or higher" only from 2019; in 2013–2018 the same measure is `DP02_0067PE` (stored in the `pct_wyksztalcenie_srednie` column). The loader uses the right code for each year. Other Data Profile columns with similar shifts were removed from the extract.
- **`pct_bez_ubezpieczenia` in the file is the share of people *with* health insurance** (`DP03_0096PE`). The loader converts it to the uninsured share (100 − x).
- `pct_ubóstwo` (`DP03_0119PE`) is the share of **families** below the poverty level. `pct_bezrobocie` (`DP03_0005PE`) is unemployed people as a share of the population aged 16+, not the unemployment rate.
- BRFSS asks about high physical activity only in odd years.
- ACS did not publish 1-Year estimates for 2020.

## Licensing

All sources are U.S. federal government works and are in the public domain. Attribution: CDC BRFSS, U.S. Census Bureau (ACS, CBP), NOAA National Centers for Environmental Information.

*This product uses the Census Bureau Data API but is not endorsed or certified by the Census Bureau.*
