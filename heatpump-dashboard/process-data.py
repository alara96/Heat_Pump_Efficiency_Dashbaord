import numpy as np 
import pandas as pd

# Load the data
us_cities_raw = pd.read_csv('data-raw/uscities.csv')

# Only includes cities with population greater than 10,000 or equal to 10,000
us_cities_raw = us_cities_raw[us_cities_raw['population'] >= 10000]

# Added the city_state column
us_cities_raw['city_state'] = us_cities_raw['city'] + ', ' + us_cities_raw['state_name']

print(us_cities_raw)

# Drop all the columns I don't need
us_cities_clean = us_cities_raw[['city_state','lat','lng']]
us_cities_clean = us_cities_clean.drop_duplicates(subset='city_state')

# Save the clean data and commented out to avoid overwriting
us_cities_clean.to_csv('data/cities.csv', index=False)
rows, cols = us_cities_clean.shape
