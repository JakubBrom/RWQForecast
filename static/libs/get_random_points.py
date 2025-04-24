import os
from re import error
from warnings import warn

import numpy as np
import pandas as pd
import geopandas as gpd
from pyproj import CRS

from shapely.geometry import Polygon, Point, MultiPolygon
from scipy.spatial import Delaunay, Voronoi, KDTree
from sqlalchemy import create_engine, text
from multiprocessing import Pool
try:
    from .AIHABs_wrappers import measure_execution_time
except ImportError:
    from AIHABs_wrappers import measure_execution_time

def points_clip(points, polygon):
    """
    Clip points to the polygon
    :param points: GeoDataFrame with points
    :param polygon: GeoDataFrame with polygons
    :return: Clipped points (GeoDataFrame)
    """
    return points[points.intersects(polygon)]


def point_mesh(polygon, distance_lat=0.01, distance_lon=0.01, crs='epsg:4326'):
    """
    Create a grid of points based on the bounding box of the input polygon.

    :param polygon: A GeoDataFrame representing a polygon.
    :param distance_lat: The distance between grid points in latitude. Default 0.01° for EPSG:4326.
    :param distance_lon: The distance between grid points in longitude. Default 0.01° for EPSG:4326.
    :return: A GeoDataFrame containing the grid points.
    """

    # Get the bounding box of the polygon
    minx, miny, maxx, maxy = polygon.total_bounds

    # Calculate the number of grid points based on the distance and bounding box size
    num_points_lat = int((maxy - miny)/distance_lat)
    num_points_lon = int((maxx - minx)/distance_lon)

    # Create the grid points
    latitudes = np.linspace(miny, maxy, num_points_lat)
    longitudes = np.linspace(minx, maxx, num_points_lon)
    grid_points = [Point(lon, lat) for lat in latitudes for lon in longitudes]

    # Convert the grid points into a GeoDataFrame
    gdf_grid = gpd.GeoDataFrame(geometry=grid_points, crs=crs)

    return gdf_grid


def delaunay_centroids(vertices, crs='epsg:4326'):
    """
    Perform Delaunay triangulation on the given vertices and return a GeoDataFrame
    containing the centroids of the Voronoi regions.

    :param vertices: The vertices for the Delaunay triangulation. Points geometry.
    :return: A GeoDataFrame containing the centroids of the Delaunay triangles.
    """

    # Calculate Delaunay triangulation
    tri = Delaunay(vertices)

    # Get triangles
    triangles = np.array([Polygon(vertices[simplex]) for simplex in tri.simplices])
    gdf_triangles = gpd.GeoDataFrame(geometry=triangles)

    # Centroids of the triangles
    centroids = gdf_triangles['geometry'].centroid
    gdf_centroids = gpd.GeoDataFrame(geometry=centroids, crs=crs)

    return gdf_centroids


def voronoi_centroids(vertices, crs='epsg:4326'):
    """
    Perform Voronoi triangulation on the given vertices and return a GeoDataFrame
    containing the centroids of the Voronoi regions.

    :param vertices: The vertices for the Voronoi triangulation. Points geometry.
    :return: A GeoDataFrame containing the centroids of the Voronoi triangles.
    """
    # Calculate Voronoi triangulation
    vor = Voronoi(vertices)

    # Get valid regions
    valid_regions = [region for region in vor.regions if -1 not in region and len(region) > 0]

    # Get Voronoi polygons
    vor_polygons = [Polygon(vor.vertices[region]) for region in valid_regions]
    gdf_polygons = gpd.GeoDataFrame(geometry=vor_polygons)

    # Centroids of the polygons
    centroids = gdf_polygons['geometry'].centroid
    gdf_centroids = gpd.GeoDataFrame(geometry=centroids, crs=crs)

    return gdf_centroids

def get_vertices(geom):
    """
    Extracts the coordinates of the vertices from a Polygon or MultiPolygon.
    
    :param geom: A shapely Polygon or MultiPolygon object.
    :return: A numpy array of all vertex coordinates (x, y).
    """
    coords = []

    if isinstance(geom, Polygon):
        # Exterior
        coords.append(np.array(geom.exterior.coords))
        # Interiors (holes)
        for interior in geom.interiors:
            coords.append(np.array(interior.coords))

    elif isinstance(geom, MultiPolygon):
        for poly in geom.geoms:
            coords.append(np.array(poly.exterior.coords))
            for interior in poly.interiors:
                coords.append(np.array(interior.coords))

    else:
        raise TypeError("Geometry must be a Polygon or MultiPolygon.")

    # Sloučíme všechny body dohromady do jedné matice
    all_coords = np.vstack(coords)
    return all_coords

def coords_to_geodf(coords_array, crs='epsg:4326'):
    """Transform Numpy array with coordinates to GeodataFrame"""
    
    points = [Point(xy) for xy in coords_array]

    # Převedeme na GeoDataFrame
    gdf = gpd.GeoDataFrame(geometry=points, crs=crs)
    
    return gdf

def safe_gpd_concat(gdf_list):
    """Safe concatenation of GeoDataFrames with the same CRS."""
    
    # Check if all GeoDataFrames have the same CRS
    crs_list = [gdf.crs for gdf in gdf_list]
    
    if len(set(crs_list)) != 1:
        raise ValueError(f"CRS mismatch: {crs_list}")
    crs = 'epsg:4326' if crs_list[0] is None else crs_list[0]
    
    # List of geometries
    geom_list = [i.geometry for i in gdf_list]
    
    # Concatenate GeoDataFrames
    geometries = pd.concat(geom_list, ignore_index=True)
    return gpd.GeoDataFrame(geometry=geometries, crs=crs)

def sample_with_min_distance_kdtree(gdf, npoints, min_dist, max_iter=10000):
    """Select points with distance constrains"""
    
    # Převod na metrický CRS, pokud ještě není
    if not gdf.crs.is_projected:
        raise ValueError("GeoDataFrame musí být v metrickém souřadnicovém systému (projektovaném CRS).")

    coords = np.array([[geom.x, geom.y] for geom in gdf.geometry])
    indices = np.random.permutation(len(coords))
    
    selected_indices = []
    selected_coords = []

    attempts = 0
    for idx in indices:
        candidate = coords[idx]
        if selected_coords:
            tree = KDTree(selected_coords)
            if tree.query_ball_point(candidate, r=min_dist):
                # Je příliš blízko k již vybraným bodům
                attempts += 1
                if attempts > max_iter:
                    print("Reached max iterations. Sampled fewer points than requested.")
                    break
                continue
        selected_indices.append(idx)
        selected_coords.append(candidate)
        if len(selected_indices) == npoints:
            break

    return gdf.iloc[selected_indices]    

def generate_points_in_polygon(in_gdf_polygon, lake_buffer=-20, n_points_km=100, n_max_points=10000, **kwargs):
    """
    Generate points within a polygon with respect of its complexity, and clip them with a buffer zone.

    :param in_gdf_polygon: The input polygon as a GeoDataFrame.
    :param lake_buffer: The buffer distance inside the selected water reservoir. Defaults to -20.
    :param n_points_km: The number of points per square kilometer in the area of the reservoir. Defaults to 100.
    :param n_max_points: The maximum number of points to be generated. Defaults to 5000.

    :returns: - The generated points clipped with the buffer layer (GeoDataFrame).
              - The randomly selected points within the buffer layer (GeoDataFrame).
              - The buffer layer in the original coordinate reference system (GeoDataFrame).
    """

    # Create a buffer zone inside the selected water reservoir
    # Get original CRS of the input layer
    try:
        epsg_orig = in_gdf_polygon.crs()
    except:
        epsg_orig = 'epsg:4326'

     # Convert selected layer to UTM CRS
    epsg_utm = in_gdf_polygon.estimate_utm_crs()
    
    gdf_polygon_utm = in_gdf_polygon.to_crs(epsg_utm)

    # Remove buffer zone of the selected water reservoir
    gdf_buffer_utm = gdf_polygon_utm.buffer(lake_buffer)
    gdf_buffer_utm = gpd.GeoDataFrame(gdf_buffer_utm, geometry=gdf_buffer_utm.geometry, crs=epsg_utm)

    # Get geometry from the buffer for the points definition 
    buffer_geom = gdf_buffer_utm['geometry'][0].simplify(0, preserve_topology=True)  
    
    # Get the vertices of the polygon
    vertices = get_vertices(buffer_geom)
    
    # Get random points
    gdf_vertices = coords_to_geodf(vertices, crs=epsg_utm)
    gdf_Delaunay_centroids = delaunay_centroids(vertices, crs=epsg_utm)
    gdf_Voronoi_centroids = voronoi_centroids(vertices, crs=epsg_utm)
    gdf_mesh = point_mesh(gdf_buffer_utm, distance_lat=100, distance_lon=100, crs=epsg_utm)     

    # Concatenate all centroids
    gdf_centroids = safe_gpd_concat([gdf_Delaunay_centroids, gdf_Voronoi_centroids, gdf_mesh, gdf_vertices])
    
    # # Clip centroids with the buffer layer
    gdf_centroids_clipped = gpd.clip(gdf_centroids, gdf_buffer_utm)
    
    # Calculate area of the reservoir
    area = gdf_polygon_utm.area.values[0] / 10000

    # Get number of points for the area
    n_points = int(area * n_points_km / 100) + 1

    n_centroids_clipped = len(gdf_centroids_clipped)

    if n_points <= n_points_km:
        n_points = min(n_points_km, n_centroids_clipped)
    else:
        n_points = min(n_points, n_centroids_clipped, n_max_points)    

    # # Sample points
    gdf_centroids_selected = sample_with_min_distance_kdtree(gdf_centroids_clipped, npoints=n_points, min_dist=20)
    gdf_centroids_selected = gpd.GeoDataFrame(gdf_centroids_selected, geometry='geometry', crs=epsg_utm)
    
    # Transform to WGS84
    # gdf_centroids_clipped = gdf_centroids_clipped.to_crs(epsg_orig)
    gdf_centroids_selected = gdf_centroids_selected.to_crs(epsg_orig)
    # gdf_buffer_wgs = gdf_buffer_utm.to_crs(epsg_orig)
    # gdf_centroids = gdf_centroids.to_crs(epsg_orig)
    
    # print(f'Number of points for the reservoir: {len(gdf_centroids_selected)}')
    
    return gdf_centroids_selected

@measure_execution_time
def get_sampling_points(osm_id, db_name, user, db_table_reservoirs, db_table_points, **kwargs):
    """

    :param osm_id: OSM object id
    :param db_name: Database name
    :param user: Database user
    :param db_table_reservoirs: Database table with water reservoirs polygons
    :param db_table_points: Database table with points for reservoir polygons
    :param kwargs: Additional parameters
    :return: The randomly selected points within the buffer layer of reservoirs (GeoDataFrame). Points for reservoirs are stored in the db_table_points database table.
    """

    # Connect to PostGIS
    engine = create_engine('postgresql://{user}@/{db_name}'.format(user=user, db_name=db_name))

    # Check if points table exists and create new one if not
    query = text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = '{tab_name}')".format(tab_name=db_table_points))

    with engine.connect() as connection:
        result = connection.execute(query)
        exists = result.scalar()

    if exists:
        # Check if are the data available in the table
        query = text("SELECT EXISTS (SELECT 1 FROM {db_table} WHERE osm_id = '{osm_id}')".format(db_table=db_table_points, osm_id=str(osm_id)))
        with engine.connect() as connection:
            result = connection.execute(query)
            data_exists = result.scalar()

        if data_exists:
            query = text("SELECT * FROM {db_table} WHERE osm_id = '{osm_id}'".format(db_table=db_table_points, osm_id=str(osm_id)))
            points_selected = gpd.read_postgis(query, engine, geom_col='geometry')

            return points_selected

    # Get polygon of the reservoir from the DB
    sql_query = "SELECT * FROM {db_table} WHERE osm_id = '{osm_id}'".format(osm_id=str(osm_id), db_table=db_table_reservoirs)
    gdf = gpd.read_postgis(sql_query, engine, geom_col='geometry')
    polygon = gpd.GeoDataFrame(gdf, geometry='geometry', crs='epsg:4326')
    
    print(polygon)

    # Produce random points in the reservoir polygon
    points_selected = generate_points_in_polygon(polygon, **kwargs)
    points_selected['osm_id'] = str(osm_id)  # Add osm_id
    points_selected['PID'] = [i for i in range(len(points_selected))]

    # Insert points into the DB table
    points_selected.to_postgis(db_table_points, con=engine, if_exists='append', index=False)
    engine.dispose()
    
    print(f'Number of points for the reservoir: {len(points_selected)}')

    return points_selected
