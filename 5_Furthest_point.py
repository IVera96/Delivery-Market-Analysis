

### Find the furthest point in Flanders from a bottle of Coke, using geospatial data.
import duckdb
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import numpy as np
from shapely.wkt import loads
from shapely.geometry import Point
import geopandas as gpd
import leafmap.maplibregl as leafmap
import folium

import webbrowser

conn=duckdb.connect('my_database.duckdb')

coke_df_deliveroo = conn.execute("""
    SELECT
        resto.name,
        loc.latitude AS latitude,
        loc.longitude AS longitude
                                 
    FROM deliveroo_restaurants AS resto
    JOIN deliveroo_locations_to_restaurants AS loc_to_resto
        ON resto.id = loc_to_resto.restaurant_id
    JOIN deliveroo_locations AS loc
        ON loc.id = loc_to_resto.location_id
    JOIN deliveroo_menu_items AS menu
    ON resto.id = menu.restaurant_id
    WHERE LOWER(menu.name) LIKE '%coca%' OR LOWER(menu.name) LIKE '%coke%'
    GROUP BY resto.name, loc.latitude, loc.longitude
    
""").fetch_df()

coke_df_takeaway=conn.execute(
    """ 
SELECT
    resto.name,
    loc.latitude  AS latitude,
    loc.longitude  AS longitude,
   
FROM takeaway_restaurants AS resto
JOIN takeaway_locations_to_restaurants AS loc_to_resto
    ON resto.primarySlug = loc_to_resto.restaurant_id
JOIN takeaway_locations AS loc
    ON loc.ID = loc_to_resto.location_id
JOIN takeaway_menuItems AS menu
    ON resto.primarySlug = menu.primarySlug
WHERE LOWER(menu.name) LIKE '%coca%' OR LOWER(menu.name) LIKE '%coke%'

GROUP BY resto.name, loc.latitude, loc.longitude 

"""
).fetch_df()

coke_df_ubereats=conn.execute("""   
    SELECT
    resto.title,
    loc.latitude  AS latitude,
    loc.longitude  AS longitude,
  
FROM ubereats_restaurants as resto
JOIN ubereats_locations_to_restaurants as loc_to_resto
    ON resto.id=loc_to_resto.restaurant_id
JOIN ubereats_locations as loc
    ON loc.id=loc_to_resto.location_id 
JOIN ubereats_menu_items AS menu
    ON resto.id = menu.restaurant_id
GROUP BY resto.title, loc.latitude, loc.longitude 

""").fetch_df()

# 
coke_df=pd.concat([coke_df_deliveroo,coke_df_takeaway,coke_df_ubereats])

# Charger la région 
regions = gpd.read_file("https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_BEL_1.json")
flanders=regions[regions['NAME_1']=="Vlaanderen"]

#Obtenir la bounding box de la reg
minx, miny, maxx, maxy = flanders.total_bounds

grid_spacing = 0.01  # ~1km in lat/lon (approx.) l'espacement 
x_coords = np.arange(minx, maxx, grid_spacing)
y_coords = np.arange(miny, maxy, grid_spacing)

points_grid_fl=[Point(x,y) for x in x_coords for y in y_coords] #creer les points de le grille


flanders_union = flanders.unary_union #fusionner la geometrie de la Fl. by def:Returns a geometry containing the union of all geometries in the GeoSeries.

grid_points_within = [point for point in points_grid_fl if flanders_union.contains(point)] #garder que les point de la flandre

grid_gdf=gpd.GeoDataFrame(geometry=grid_points_within, crs=flanders.crs) 

# print(grid_gdf.head())
#       geometry
# 0  POINT (2.5654 51.0629)
# 1  POINT (2.5654 51.0729)
# 2  POINT (2.5654 51.0829)
# 3  POINT (2.5654 51.0929)
# 4  POINT (2.5754 51.0329)


coke_gpd=gpd.GeoDataFrame(coke_df,geometry=gpd.points_from_xy(coke_df.longitude, coke_df.latitude), crs="EPSG:4326"
)

coke_gpd = coke_gpd.to_crs(flanders.crs) #reprojecte coke_gpd dans le meme system que FL.

coke_in_flanders = gpd.sjoin(coke_gpd, flanders, predicate="within") #filtre 
# print(coke_in_flanders.head())                                     

def haversine_np(lat1, lon1, lat2, lon2):
    R = 6371.0  
    dlat = np.radians(lat2 - lat1) 
    dlon = np.radians(lon2 - lon1)  
    a = (
        np.sin(dlat / 2) ** 2 
        + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2) ** 2
    )
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))  
    distance = R * c  
    return distance

def calculate_min_distances(grid_df, restos_df):
    distances = []
    for i, row in grid_df.iterrows():
        lat1 = row["latitude"]
        lon1 = row["longitude"]
        
        lat2 = restos_df["latitude"].values
        lon2 = restos_df["longitude"].values
        
        dist = haversine_np(lat1, lon1, lat2, lon2)
        distances.append(np.min(dist))  
    return distances


grid_gdf["longitude"] = grid_gdf.geometry.x
grid_gdf["latitude"] = grid_gdf.geometry.y

coke_in_flanders["longitude"] = coke_in_flanders.geometry.x
coke_in_flanders["latitude"] = coke_in_flanders.geometry.y

grid_gdf["min_distance_to_coke"] = calculate_min_distances(grid_gdf, coke_in_flanders)


furthest_point = grid_gdf.loc[grid_gdf["min_distance_to_coke"].idxmax()]

# print(furthest_point)
# geometry                POINT (3.3853999999999824 51.33289999999987)
# longitude                                                     3.3854
# latitude                                                     51.3329
# min_distance_to_coke                                        5.633149



# Afficher Flandre et les Coca
ax = flanders.plot(edgecolor='black', facecolor='none')
grid_gdf.plot(ax=ax, column='min_distance_to_coke', cmap='OrRd', markersize=1, legend=True)
coke_in_flanders.plot(ax=ax, color='blue', markersize=5, label="Coca-Cola")

# Afficher le point le plus éloigné
gpd.GeoSeries(furthest_point.geometry).plot(ax=ax, color='red', markersize=50, label="Point le plus éloigné")

plt.legend()
plt.title("Distances aux Coca en Flandre")
plt.show()

