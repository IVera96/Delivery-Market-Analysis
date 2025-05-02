import duckdb
import matplotlib.pyplot as plt
import pandas as pd
import geopandas as gpd

from shapely.geometry import Point
from matplotlib_venn import venn3


conn = duckdb.connect('my_database.duckdb')


query_deliveroo = conn.execute("""
    SELECT 
        resto.name,
        loc.latitude,
        loc.longitude
    FROM deliveroo_restaurants AS resto
    JOIN deliveroo_locations_to_restaurants AS loc_to_resto
        ON resto.id = loc_to_resto.restaurant_id
    JOIN deliveroo_locations AS loc
        ON loc.id = loc_to_resto.location_id
    WHERE loc.name != '0'
    GROUP BY resto.name, loc.latitude, loc.longitude
""").fetch_df()

query_takeaway = conn.execute("""     
    SELECT
        resto.name,
        loc.latitude,
        loc.longitude
    FROM takeaway_restaurants AS resto
    JOIN takeaway_locations_to_restaurants AS loc_to_resto
        ON resto.primarySlug = loc_to_resto.restaurant_id
    JOIN takeaway_locations AS loc
        ON loc.ID = loc_to_resto.location_id
    WHERE loc.name != '0'
    GROUP BY resto.name, loc.latitude, loc.longitude
""").fetch_df()

query_ubereats = conn.execute("""     
    SELECT
        resto.title AS name,
        loc.latitude,
        loc.longitude
    FROM ubereats_restaurants AS resto
    JOIN ubereats_locations_to_restaurants AS loc_to_resto
        ON resto.id = loc_to_resto.restaurant_id
    JOIN ubereats_locations AS loc
        ON loc.id = loc_to_resto.location_id 
    WHERE loc.name != '0'
    GROUP BY resto.title, loc.latitude, loc.longitude
""").fetch_df()


deliveroo_geom = gpd.GeoDataFrame(query_deliveroo, geometry=gpd.points_from_xy(query_deliveroo.longitude, query_deliveroo.latitude), crs="EPSG:4326")
takeaway_geom = gpd.GeoDataFrame(query_takeaway, geometry=gpd.points_from_xy(query_takeaway.longitude, query_takeaway.latitude), crs="EPSG:4326").to_crs(epsg=3857)
ubereats_geom = gpd.GeoDataFrame(query_ubereats, geometry=gpd.points_from_xy(query_ubereats.longitude, query_ubereats.latitude), crs="EPSG:4326").to_crs(epsg=3857)


deliveroo_geom=deliveroo_geom.to_crs(epsg=3857)
takeaway_geom=takeaway_geom.to_crs(epsg=3857)
ubereats_geom=ubereats_geom.to_crs(epsg=3857)

buffer_size = 100


ubereats_buffer = ubereats_geom.copy()
ubereats_buffer["geometry"] = ubereats_buffer.geometry.buffer(buffer_size)

takeaway_buffer = takeaway_geom.copy()
takeaway_buffer["geometry"] = takeaway_buffer.geometry.buffer(buffer_size)


delivero_uber = gpd.sjoin(deliveroo_geom, ubereats_geom, how='inner', predicate='intersects')
delivero_uber_unique = delivero_uber.drop_duplicates(subset=["name_left"])

delivero_takeaway = gpd.sjoin(deliveroo_geom, takeaway_buffer, how='inner', predicate='intersects')
delivero_takeaway_unique = delivero_takeaway.drop_duplicates(subset=["name_left"])

uber_takeaway = gpd.sjoin(ubereats_geom, takeaway_buffer, how='inner', predicate='intersects')
uber_takeaway_unique = uber_takeaway.drop_duplicates(subset=["name_left"])


if 'index_right' in delivero_uber_unique.columns:
    delivero_uber_unique = delivero_uber_unique.drop(columns='index_right')

delivero_uber_takeaway = gpd.sjoin(delivero_uber_unique, takeaway_buffer, how='inner', predicate='intersects')
delivero_uber_takeaway_unique = delivero_uber_takeaway.drop_duplicates(subset=["name_left"])


# print(delivero_uber_takeaway_unique.head(), delivero_uber_takeaway_unique.columns)


uber_names = set(ubereats_geom['name'])
deliveroo_names = set(deliveroo_geom['name'])
takeaway_names = set(takeaway_geom['name'])



only_uber = uber_names - deliveroo_names - takeaway_names
only_deliveroo = deliveroo_names - uber_names - takeaway_names
only_takeaway = takeaway_names - uber_names - deliveroo_names

uber_and_deliveroo = (uber_names & deliveroo_names) - takeaway_names
deliveroo_and_takeaway = (deliveroo_names & takeaway_names) - uber_names
uber_and_takeaway = (uber_names & takeaway_names) - deliveroo_names

all_three = uber_names & deliveroo_names & takeaway_names


venn_data = {
    '100': len(only_uber),
    '010': len(only_deliveroo),
    '001': len(only_takeaway),
    '110': len(uber_and_deliveroo),
    '011': len(deliveroo_and_takeaway),
    '101': len(uber_and_takeaway),
    '111': len(all_three),
}




plt.figure(figsize=(8, 6))
venn3(subsets=venn_data, set_labels=('Uber Eats', 'Deliveroo', 'Takeaway'))
plt.title("Venn Diagram")
plt.show()

############################################################


fig, ax = plt.subplots(figsize=(12, 6))


deliveroo_geom.plot(ax=ax, color='blue', markersize=4, label='Deliveroo')
ubereats_geom.plot(ax=ax, color='green', markersize=4, label='UberEats')
takeaway_geom.plot(ax=ax, color='purple', markersize=4, label='Takeaway')


gpd.GeoDataFrame(delivero_uber_unique, geometry='geometry').plot(ax=ax, color='orange', markersize=10, label='Deliveroo ∩ UberEats')
gpd.GeoDataFrame(delivero_takeaway_unique, geometry='geometry').plot(ax=ax, color='brown', markersize=10, label='Deliveroo ∩ Takeaway')
gpd.GeoDataFrame(uber_takeaway_unique, geometry='geometry').plot(ax=ax, color='cyan', markersize=10, label='UberEats ∩ Takeaway')


gpd.GeoDataFrame(delivero_uber_takeaway_unique, geometry='geometry',crs="EPSG:4326").plot(ax=ax, color='red', markersize=20, label='Tutte le 3 piattaforme')


plt.title("Spatial Join UberEats, Deliveroo e Takeaway")
plt.legend()
plt.show()


