from typing import Dict, Any, Tuple, Optional
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from .base import DataAdapter, BuildingData, NetworkConstraints

class FraunhoferAdapter(DataAdapter):
    """
    Adapter for Fraunhofer IIS/EAS specific data formats
    Handles Shapefile/GeoJSON exports from their urban planning tools
    """
    
    # Mapping from Fraunhofer schema to standard schema
    COLUMN_MAPPINGS = {
        # Common German municipal data formats (ALKIS/ATKIS inspired)
        'gebaeudefu': 'usage_type',        # Gebäudefunktion
        'wohngeb': 'is_residential',       # Wohngebäude flag
        'grundflae': 'footprint_area',     # Grundfläche
        'geschosse': 'stories',            # Geschosszahl
        'baujahr': 'year_built',           # Baujahr
        'stra_sz_e': 'street_name',        # Straßenname
        'hausnummer': 'house_number',      # Hausnummer
        'nutzflae': 'floor_area',          # Nutzfläche
        'heizbedarf': 'heat_demand',       # Specific heat demand
        'kreis': 'district',               # Landkreis
        'gemeinde': 'municipality',        # Gemeinde
        'plz': 'postal_code',              # Postleitzahl
        
        # Alternative English/common naming
        'building_use': 'usage_type',
        'floor_area_m2': 'floor_area',
        'stories_above_ground': 'stories',
        'year_construction': 'year_built',
        'heat_demand_kwh_a': 'annual_heat_demand',
        'addr_street': 'street_name',
        'addr_number': 'house_number'
    }
    
    def validate_source(self, source: Dict[str, Any]) -> Tuple[bool, str]:
        """Validate Fraunhofer data package structure"""
        required_keys = ['file_path', 'connection_string']
        
        if not any(k in source for k in required_keys):
            return False, "Must provide file_path or database connection_string"
        
        if 'schema_type' in source:
            valid_schemas = ['alkis', 'fraunhofer_iis', 'municipal_gdb', 'custom']
            if source['schema_type'] not in valid_schemas:
                return False, f"Unknown schema_type. Use: {valid_schemas}"
        
        return True, "Valid Fraunhofer source configuration"
    
    def load_buildings(self, source: Dict[str, Any]) -> BuildingData:
        """
        Load from Fraunhofer data exports
        Supports: Shapefile, GeoJSON, GeoPackage, PostGIS
        """
        file_path = source.get('file_path')
        schema_type = source.get('schema_type', 'auto_detect')
        
        # Load based on file/connection
        if file_path and file_path.endswith('.shp'):
            gdf = gpd.read_file(file_path, encoding='utf-8')
        elif file_path and file_path.endswith('.geojson'):
            gdf = gpd.read_file(file_path)
        elif file_path and file_path.endswith('.gpkg'):
            layer = source.get('layer', 'buildings')
            gdf = gpd.read_file(file_path, layer=layer)
        elif 'connection_string' in source:
            # PostGIS direct connection
            gdf = self._load_from_postgis(source['connection_string'], source.get('query'))
        else:
            raise ValueError(f"Unsupported file format or source: {source}")
        
        # Apply schema mapping
        gdf = self._apply_schema_mapping(gdf, schema_type)
        
        # Fraunhofer-specific calculations
        gdf = self._calculate_fraunhofer_derived_fields(gdf, source)
        
        # Filter by district/municipality if specified
        if 'filter_district' in source:
            gdf = gdf[gdf['district'] == source['filter_district']]
        if 'filter_postal_code' in source:
            gdf = gdf[gdf['postal_code'] == source['filter_postal_code']]
        
        # Normalize to standard format
        gdf = self.normalize_buildings(gdf)
        
        metadata = {
            'source_type': 'fraunhofer',
            'schema_type': schema_type,
            'file_name': file_path.split('/')[-1] if file_path else 'postgis',
            'n_buildings': len(gdf),
            'crs_original': str(gdf.crs),
            'filters_applied': {
                'district': source.get('filter_district'),
                'postal_code': source.get('filter_postal_code')
            }
        }
        
        return BuildingData(
            gdf=gdf,
            crs=str(gdf.crs) if gdf.crs else "EPSG:4326",
            source_type="fraunhofer",
            metadata=metadata
        )
    
    def _apply_schema_mapping(self, gdf: gpd.GeoDataFrame, schema_type: str) -> gpd.GeoDataFrame:
        """Map Fraunhofer-specific columns to standard schema"""
        # Auto-detect if not specified
        if schema_type == 'auto_detect':
            schema_type = self._detect_schema(gdf)
        
        # Apply mappings
        rename_map = {}
        for orig, standard in self.COLUMN_MAPPINGS.items():
            if orig in gdf.columns:
                rename_map[orig] = standard
        
        if rename_map:
            gdf = gdf.rename(columns=rename_map)
        
        # Handle ALKIS specific codings
        if 'usage_type' in gdf.columns and schema_type == 'alkis':
            gdf['usage_type'] = gdf['usage_type'].astype(str).map(self._alkis_usage_map())
        
        return gdf
    
    def _detect_schema(self, gdf: gpd.GeoDataFrame) -> str:
        """Auto-detect schema type from column names"""
        cols = set(gdf.columns.str.lower())
        
        if 'gebaeudefu' in cols or 'alkis_id' in cols:
            return 'alkis'
        elif any('fh_' in c for c in cols) or 'iis_id' in cols:
            return 'fraunhofer_iis'
        elif 'nutzflae' in cols or 'grundflae' in cols:
            return 'municipal_gdb'
        else:
            return 'custom'
    
    def _alkis_usage_map(self) -> Dict[str, str]:
        """Convert ALKIS Gebäudefunktion codes to standard usage types"""
        return {
            '1000': 'residential',      # Wohnhaus
            '2000': 'industrial',       # Industriebau
            '3000': 'commercial',       # Geschäftshaus
            '4000': 'school',           # Schule
            '5000': 'hospital',         # Krankenhaus
            '6000': 'office',           # Bürohaus
            '10000': 'residential',     # Wohn- und Geschäftshaus
            '20000': 'mixed',           # Sonstige gemischte Nutzung
        }
    
    def _calculate_fraunhofer_derived_fields(self, gdf: gpd.GeoDataFrame, source: Dict) -> gpd.GeoDataFrame:
        """Calculate additional fields specific to Fraunhofer analysis"""
        # Calculate floor area if missing but stories and footprint exist
        if 'floor_area' not in gdf.columns:
            if 'footprint_area' in gdf.columns and 'stories' in gdf.columns:
                gdf['floor_area'] = gdf['footprint_area'] * gdf['stories'].fillna(1).astype(float)
            else:
                # Estimate from geometry and assumption of 1 story if unknown
                if gdf.crs and not gdf.crs.is_geographic:
                     gdf['floor_area'] = gdf.geometry.area * 3  # Fallback for projected CRS
                else:
                     # Very rough estimation if Geographic CRS
                     gdf_proj = gdf.to_crs(epsg=3857)
                     gdf['floor_area'] = gdf_proj.geometry.area * 3
        
        # Heat demand calculation using Fraunhofer IIS methodology (VDI 3807)
        if 'annual_heat_demand' not in gdf.columns:
            # Use TABULA building types if available
            if 'building_type_detailed' in gdf.columns:
                gdf['annual_heat_demand'] = gdf.apply(
                    lambda x: self._tabula_demand(x['building_type_detailed'], x['floor_area'], x.get('year_built', 1990)),
                    axis=1
                )
            else:
                # Default specific demand based on usage
                defaults = {
                    'residential': 120,
                    'commercial': 150,
                    'industrial': 200,
                    'school': 130,
                    'hospital': 180,
                    'office': 140
                }
                gdf['annual_heat_demand'] = gdf.apply(
                    lambda x: x['floor_area'] * defaults.get(str(x.get('usage_type', 'residential')), 120),
                    axis=1
                )
        
        # Add Fraunhofer-specific metadata columns
        gdf['data_source'] = 'fraunhofer_import'
        gdf['import_timestamp'] = pd.Timestamp.now()
        
        return gdf
    
    def _tabula_demand(self, building_type: str, floor_area: float, year_built: int) -> float:
        """Calculate heat demand using TABULA methodology (common in German research)"""
        if pd.isna(year_built):
             year_built = 1990
        try:
             year_built = int(year_built)
        except ValueError:
             year_built = 1990
             
        # Simplified TABULA categories
        era = 'new' if year_built > 2000 else ('modernized' if year_built > 1980 else 'old')
        
        demands = {
            'residential_old': 200,
            'residential_modernized': 120,
            'residential_new': 60,
            'non_residential_old': 250,
            'non_residential_modernized': 160,
            'non_residential_new': 80
        }
        
        key = f"{'residential' if 'wohn' in str(building_type).lower() else 'non_residential'}_{era}"
        return floor_area * demands.get(key, 150)
    
    def _load_from_postgis(self, conn_string: str, query: Optional[str]) -> gpd.GeoDataFrame:
        """Load from Fraunhofer PostGIS database"""
        import sqlalchemy
        engine = sqlalchemy.create_engine(conn_string)
        
        if not query:
            query = "SELECT * FROM buildings WHERE geometry IS NOT NULL"
        
        return gpd.read_postgis(query, engine, geom_col='geometry')
    
    def load_network_constraints(self, source: Dict[str, Any]) -> NetworkConstraints:
        """Load road network and existing infrastructure from Fraunhofer data"""
        # Look for accompanying files (e.g., roads.shp, existing_grid.shp)
        base_path = source.get('file_path', '').replace('.shp', '').replace('.gpkg', '').replace('.geojson', '')
        
        roads = None
        existing_grid = None
        
        if base_path:
            # Try to find road file
            road_candidates = [f"{base_path}_roads.shp", f"{base_path}_strassen.shp", "roads.shp"]
            for candidate in road_candidates:
                try:
                    roads = gpd.read_file(candidate)
                    break
                except Exception:
                    continue
            
            # Try to find existing heat grid
            grid_candidates = [f"{base_path}_grid.shp", f"{base_path}_netz.shp", "existing_grid.shp"]
            for candidate in grid_candidates:
                try:
                    existing_grid = gpd.read_file(candidate)
                    break
                except Exception:
                    continue
        
        return NetworkConstraints(
            roads=roads,
            existing_grid=existing_grid,
            water_bodies=None
        )

