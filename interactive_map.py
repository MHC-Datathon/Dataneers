import os, glob, io, zipfile, webbrowser
import pandas as pd
import geopandas as gpd
from shapely import wkt
from shapely.geometry import LineString
from pathlib import Path
import folium

# If any packages or modules are missing, do pip install packagename
# (Ex: pip install geopandas) in any cell or in Bash/PowerShell

### Download all bus gtfs zipped files from https://www.mta.info/developers
### and add them to a folder in your working directory named "bus_gtfs"
FOLDER = Path("./bus_gtfs")  # or change to another working path
print("FOLDER exists?", FOLDER.exists())

### Verify the paths found in FOLDER
zip_paths = sorted(FOLDER.glob("gtfs_*.zip"))
print("Found:", [p.name for p in zip_paths])
assert zip_paths, f"No GTFS zips found in {FOLDER}/gtfs_*.zip"

# Set the pattern of the zipped filenames
ZIP_PATTERN = "gtfs_*.zip"
REQUIRED_FILES = ["shapes.txt", "stops.txt", "routes.txt", "trips.txt"]
buckets = {k: [] for k in REQUIRED_FILES}

zips = sorted(glob.glob(os.path.join(FOLDER, ZIP_PATTERN)))
assert zips, f"No GTFS zips found in {FOLDER}/{ZIP_PATTERN}"

for zp in zips:
    feed_name = os.path.splitext(os.path.basename(zp))[0]  # e.g., 'gtfs_m'
    with zipfile.ZipFile(zp) as z:
        names = set(z.namelist())
        for fn in REQUIRED_FILES:
            if fn in names:
                df = pd.read_csv(z.open(fn), dtype=str, low_memory=False)
                df["borough_feed"] = feed_name
                buckets[fn].append(df)
            else:
                print(f"[WARN] {fn} missing in {feed_name}")


# concat and normalize dtypes
shapes = pd.concat(buckets["shapes.txt"], ignore_index=True)
stops  = pd.concat(buckets["stops.txt"],  ignore_index=True)
routes = pd.concat(buckets["routes.txt"], ignore_index=True)
trips  = pd.concat(buckets["trips.txt"],  ignore_index=True)

# cast numeric columns
for col in ["shape_pt_lat", "shape_pt_lon"]:
    shapes[col] = shapes[col].astype(float)
shapes["shape_pt_sequence"] = shapes["shape_pt_sequence"].astype(int)

stops["stop_lat"] = stops["stop_lat"].astype(float)
stops["stop_lon"] = stops["stop_lon"].astype(float)

# make a collision-proof shape key (shape_id can repeat across feeds)
shapes["shape_uid"] = shapes["borough_feed"] + "_" + shapes["shape_id"]

# Mapping for shapes and route labels (short/long name)
# Merge trips to routes
shape2route = (
    trips[["route_id", "shape_id", "borough_feed"]].dropna()
    .drop_duplicates(["shape_id", "borough_feed"])
    .merge(
        routes[["route_id", "route_short_name", "route_long_name", "route_color", "borough_feed"]],
        on=["route_id", "borough_feed"], how="left"
    )
)
shape2route["shape_uid"] = shape2route["borough_feed"] + "_" + shape2route["shape_id"]

# build LineStrings per shapes (shape_uid)
shapes_sorted = shapes.sort_values(["shape_uid", "shape_pt_sequence"])
lines = (
    shapes_sorted
      .groupby("shape_uid")[["shape_pt_lon", "shape_pt_lat"]]
      .apply(lambda df: LineString(df.to_numpy()))
      .to_frame("geometry")
      .reset_index()
)


# Merge shapes with routes geodataframe
routes_gdf = gpd.GeoDataFrame(lines, geometry="geometry", crs="EPSG:4326")
routes_gdf = (
    routes_gdf
    .merge(
        shape2route[["shape_uid", "route_id", "route_short_name", "route_long_name", "route_color", "borough_feed"]],
        on="shape_uid", how="left"
    )
)

# filter for few specific routes if needed (specially If the map feels slow)
# routes_gdf = routes_gdf[routes_gdf["route_id"].isin(["Q43","Q1","Q17","Q83"])]

# Get stops GeoDataFrame (keep borough_feed to avoid ID ambiguity)
stops_gdf = gpd.GeoDataFrame(
    stops[["stop_id", "stop_name", "stop_lat", "stop_lon", "borough_feed"]],
    geometry=gpd.points_from_xy(stops["stop_lon"], stops["stop_lat"]),
    crs="EPSG:4326"
)

# create base folium map
m = folium.Map(
    location=[40.75, -73.97],
    zoom_start=12,
    tiles="cartodbdark_matter",
    prefer_canvas=True
)

# Create explicit panes so stops are ABOVE routes
folium.map.CustomPane("routes", z_index=400).add_to(m)
folium.map.CustomPane("stops",  z_index=650).add_to(m)


# draw each shape (LineString) as a polyline
def line_to_latlon_coords(geom):
    # geom is a shapely LineString or MultiLineString
    if geom.geom_type == "LineString":
        return [(lat, lon) for lon, lat in geom.coords]
    elif geom.geom_type == "MultiLineString":
        coords = []
        for part in geom.geoms:
            coords.extend([(lat, lon) for lon, lat in part.coords])
        return coords
    else:
        return []

# color by route
palette = [
    "#4169e1", #Royal Blue (Normal bus routes)
    "#dc143c", #Crismon (ACE/ABLE Routes)
    "#FFFFFF", #White (Bus Stops)
    "rgba(245, 230, 180)" #Congestion zone highlight
    "rgba(244, 184, 138)" #congetion zone outline
]
color_map = {}

# Tooltip fields if present
tooltip_fields = [f for f in ["route_id","route_long_name"] if f in routes_gdf.columns]

ace_able_df = pd.read_csv("ace_able_routes/ace_able_routes.csv", dtype=str, low_memory=False)
ace_able_routes = set(ace_able_df["Route"].unique())

#mark every ace/able lines
routes_gdf["is_ACE/ABLE"] = routes_gdf["route_id"].isin(ace_able_routes)
routes_gdf["is_ACE/ABLE"] = routes_gdf["is_ACE/ABLE"].map({True: "Yes", False: "No"})

def style(routes):
    route = routes["properties"].get("route_id", "")
    if route in ace_able_routes:
        return { # return the ACE/ABLE routes
            "color": palette[1],
            "weight": 3,
            "opacity": 0.8
        }
    else:
        return { # return the normal bus route color
            "color": palette[0],
            "weight": 1,
            "opacity": 0.7
        }

# highlights
def highlight(route): #highlights a route when hovered
    return {
        "color": "yellow",
        "weight": 4,
        "opacity": 0.8
    }

routes_layer = folium.GeoJson(
    routes_gdf,
    name="Bus Routes",
    style_function=style,
    highlight_function=highlight,
    tooltip=folium.GeoJsonTooltip(
        fields=["route_id", "route_long_name"],
        aliases=["Route ID", "Route Name"],
        sticky=True
    ),
    popup=folium.GeoJsonPopup(
        fields=["route_id", "route_long_name", "is_ACE/ABLE"],
        aliases=["Route ID:", "Route Name:","ACE/ABLE:"],
        localize=True,
        labels=True,
        max_width=300
    )

)

routes_layer.add_to(m)


# Add stops as dots
stops_raw = folium.FeatureGroup(name="Stops", show=False)
for _, s in stops_gdf.iterrows():
    folium.CircleMarker(
        location=[s["stop_lat"], s["stop_lon"]],
        radius=0.05,
        color="white",
        fill=True,
        fill_opacity=0.8,
        opacity=0.8,
        tooltip=f"{s.get('stop_name','')} (ID: {s.get('stop_id','')})"
    ).add_to(stops_raw)

stops_raw.add_to(m)


# Add congestion zone as a colored layer
congestion_df = pd.read_csv("nyc_congestion_zone/nyc_congestion_zone.csv")

congestion_df["geometry"] = congestion_df["polygon"].apply(wkt.loads) #converting the wkt into geometries
congestion = gpd.GeoDataFrame(congestion_df, geometry="geometry", crs="EPSG:4326")
print(congestion.crs)
folium.GeoJson(
    congestion,
    name="Congestion Zone",
    style_function=lambda feature: {
        "color": "rgba(244, 184, 138)",
        "weight": 1,
        "fillColor": "rgba(245, 230, 180)",
        "fillOpacity": 0.25,
    },
    tooltip="NYC Congestion Zone",
).add_to(m)


#creating a legend table explaining the colors
legend_html = '''
<div style="position: fixed; 
     bottom: 50px; left: 50px; width: 200px; height: 125px; 
     border:2px solid grey; z-index:9999; font-size:14px;
     background-color:#708090; opacity: 0.85;">
     &nbsp; <b>Legend</b> <br>
     &nbsp; Bus Stops &nbsp; <i class="fa fa-circle" style="color:#FFFFFF"></i><br>
     &nbsp; Normal Bus Route &nbsp; <i class="fa fa-circle" style="color:#4169e1"></i><br>
     &nbsp; ACE/ABLE Bus Routes &nbsp; <i class="fa fa-circle" style="color:#dc143c"></i><br>
     &nbsp; Congestion Zone &nbsp; <i class="fa fa-circle" style="color:rgba(244, 184, 138)"></i><br>
</div>
'''
m.get_root().html.add_child(folium.Element(legend_html))


folium.LayerControl(collapsed=False).add_to(m)

# Open map on the web
out = Path("mta_bus_map.html").resolve()
m.save(str(out))
print(f"Wrote {out}")
webbrowser.open(out.as_uri(), new=2)
