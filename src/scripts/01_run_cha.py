#!/usr/bin/env python3
"""
CHA pipeline: District heating network analysis.

Generates:
- cha_kpis.json: EN 13941-1 compliance KPIs
- network.pickle: Converged pandapipes network
- interactive_map.html: Interactive visualization
"""
import sys
import argparse
import json
import pickle
import logging
from pathlib import Path
from typing import Tuple, Optional

sys.path.insert(0, str(Path(__file__).parents[1]))

import geopandas as gpd
import pandas as pd
import numpy as np
import pandapipes as pp
from shapely.geometry import Point

from branitz_heat_decision.config import (
    BUILDINGS_PATH, BUILDING_CLUSTER_MAP_PATH, DESIGN_TOPN_PATH,
    DATA_PROCESSED, DATA_RAW, HOURLY_PROFILES_PATH, resolve_cluster_path
)
from branitz_heat_decision.data.loader import (
    load_buildings_geojson, load_streets_geojson,
    filter_residential_buildings_with_heat_demand,
    load_processed_buildings
)
from branitz_heat_decision.cha.convergence_optimizer_spur import optimize_network_for_convergence
from branitz_heat_decision.cha.kpi_extractor import extract_kpis
from branitz_heat_decision.cha.qgis_export import create_interactive_map, export_pipe_velocity_csvs
from branitz_heat_decision.cha.config import CHAConfig, get_default_config
from branitz_heat_decision.cha.sizing import load_pipe_catalog
from branitz_heat_decision.cha.hydraulic_checks import HydraulicValidator
from branitz_heat_decision.cha.robustness_checks import RobustnessValidator
from branitz_heat_decision.config.validation_standards import ValidationConfig
from branitz_heat_decision.cha.network_builder_trunk_spur import build_trunk_spur_network
from branitz_heat_decision.cha.sizing_catalog import load_technical_catalog

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_cluster_data(
    cluster_id: str,
) -> Tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, Tuple[float, float], int, float, pd.DataFrame, Optional[str]]:
    """
    Load data for a specific cluster.
    
    Returns:
        Tuple of (buildings, streets, plant_coords, design_hour, design_load_kw, hourly_profiles, cluster_street_name)
        hourly_profiles: DataFrame with shape (8760, n_buildings) - hourly heat demand per building
    """
    # Validate cluster ID format (should be ST{number}_{STREET_NAME})
    import re
    if not re.match(r'^ST\d{3}_', cluster_id):
        logger.warning(f"Cluster ID {cluster_id} does not match expected format ST{{number}}_{{STREET_NAME}}")
    
    # Load street clusters to get cluster metadata and validate cluster exists
    street_clusters_path = DATA_PROCESSED / "street_clusters.parquet"
    if street_clusters_path.exists():
        street_clusters = pd.read_parquet(street_clusters_path)
        cluster_info = street_clusters[street_clusters['street_id'] == cluster_id]
        
        if len(cluster_info) == 0:
            logger.warning(f"Cluster {cluster_id} not found in street_clusters.parquet")
            # Continue anyway (might be test data)
            plant_coords_from_cluster = None
            cluster_street_name = None
        else:
            cluster_info = cluster_info.iloc[0]
            plant_coords_from_cluster = (cluster_info['plant_x'], cluster_info['plant_y'])
            cluster_street_name = cluster_info.get('cluster_name', None)
            logger.info(f"Found cluster metadata: {cluster_info.get('building_count', 'N/A')} buildings")
    else:
        logger.warning("street_clusters.parquet not found, using defaults")
        plant_coords_from_cluster = None
        cluster_street_name = None
    
    # Load cluster map
    if not BUILDING_CLUSTER_MAP_PATH.exists():
        raise FileNotFoundError(f"Cluster map not found: {BUILDING_CLUSTER_MAP_PATH}")
    
    cluster_map = pd.read_parquet(BUILDING_CLUSTER_MAP_PATH)
    cluster_buildings = cluster_map[cluster_map['cluster_id'] == cluster_id]['building_id'].tolist()
    
    if not cluster_buildings:
        raise ValueError(f"No buildings found for cluster {cluster_id}")
    
    logger.info(f"Found {len(cluster_buildings)} buildings in cluster {cluster_id}")
    
    # Load processed buildings (already filtered to residential with heat demand)
    # This uses the smart loader which checks if buildings are already filtered
    # and loads from processed file if available, eliminating redundant filtering
    logger.info("Loading processed buildings (residential with heat demand)...")
    buildings = load_processed_buildings(cluster_buildings=cluster_buildings)
    
    if len(buildings) == 0:
        raise ValueError(
            f"No residential buildings with heat demand found for cluster {cluster_id}. "
            f"Ensure data preparation has been run with --create-clusters flag."
        )
    
    logger.info(f"Loaded {len(buildings)} residential buildings with heat demand for cluster {cluster_id}")
    
    # Load streets.
    #
    # IMPORTANT: Keep ALL streets available here.
    # The trunk-spur builder needs nearby streets to place the plant on a *different* street
    # than the selected cluster street (and to connect it accordingly).
    streets_path = DATA_PROCESSED / "streets.geojson"
    if not streets_path.exists():
        # Try raw streets file
        streets_path = DATA_RAW / "strassen_mit_adressenV3_fixed.geojson"
        if not streets_path.exists():
            streets_path = DATA_RAW / "strassen_mit_adressenV3.geojson"
    
    if not streets_path.exists():
        # Create a minimal streets GeoDataFrame from building bounds
        logger.warning("No streets file found, creating minimal street network from building bounds")
        bounds = buildings.total_bounds
        from shapely.geometry import LineString
        street_geoms = [
            LineString([(bounds[0], bounds[1]), (bounds[2], bounds[1])]),  # Bottom
            LineString([(bounds[0], bounds[3]), (bounds[2], bounds[3])]),  # Top
            LineString([(bounds[0], bounds[1]), (bounds[0], bounds[3])]),  # Left
            LineString([(bounds[2], bounds[1]), (bounds[2], bounds[3])]),  # Right
        ]
        streets = gpd.GeoDataFrame(
            {'street_id': [f'street_{i}' for i in range(4)]},
            geometry=street_geoms,
            crs=buildings.crs
        )
    else:
        streets = load_streets_geojson(streets_path)
        
        if cluster_street_name:
            logger.info(
                f"Cluster street name is '{cluster_street_name}'. "
                "Keeping all streets loaded (plant siting needs nearby non-cluster streets)."
            )
        
        # Ensure CRS matches
        if streets.crs != buildings.crs:
            streets = streets.to_crs(buildings.crs)
    
    # Get plant coordinates (prefer from cluster metadata, otherwise use centroid)
    if plant_coords_from_cluster and plant_coords_from_cluster[0] != 0.0:
        plant_coords = plant_coords_from_cluster
        logger.info(f"Plant coordinates from cluster metadata: {plant_coords}")
    else:
        cluster_centroid = buildings.geometry.union_all().centroid
        plant_coords = (cluster_centroid.x, cluster_centroid.y)
        logger.info(f"Plant coordinates from building centroid: {plant_coords}")
    
    # Load design hour and load from design_topn
    design_hour = 0
    design_load_kw = 100.0  # Default
    
    if DESIGN_TOPN_PATH.exists():
        with open(DESIGN_TOPN_PATH, 'r') as f:
            design_topn = json.load(f)
        
        if cluster_id in design_topn.get('clusters', {}):
            cluster_info = design_topn['clusters'][cluster_id]
            design_hour = cluster_info.get('design_hour', 0)
            design_load_kw = cluster_info.get('design_load_kw', 100.0)
            logger.info(f"Design hour: {design_hour}, Design load: {design_load_kw:.1f} kW")
    
    # Load hourly heat demand profiles
    hourly_profiles = None
    if HOURLY_PROFILES_PATH.exists():
        hourly_profiles = pd.read_parquet(HOURLY_PROFILES_PATH)
        logger.info(f"Loaded hourly profiles: {hourly_profiles.shape} (8760 hours × {len(hourly_profiles.columns)} buildings)")
        
        # Filter to only buildings in this cluster
        cluster_building_ids = buildings['building_id'].tolist()
        available_buildings = [bid for bid in cluster_building_ids if bid in hourly_profiles.columns]
        
        if available_buildings:
            hourly_profiles = hourly_profiles[available_buildings]
            logger.info(f"Filtered hourly profiles to {len(available_buildings)} cluster buildings")
        else:
            logger.warning(f"No matching buildings found in hourly profiles for cluster {cluster_id}")
            hourly_profiles = None
    else:
        logger.warning(f"Hourly profiles file not found: {HOURLY_PROFILES_PATH}")
    
    return buildings, streets, plant_coords, design_hour, design_load_kw, hourly_profiles, cluster_street_name


def run_cha_pipeline(
    cluster_id: str,
    attach_mode: str = 'split_edge_per_building',
    output_dir: Optional[Path] = None,
    catalog_path: Optional[Path] = None,
    max_spur_length_m: float = 50.0,
    plant_wgs84_lat: Optional[float] = None,
    plant_wgs84_lon: Optional[float] = None,
    disable_auto_plant_siting: bool = False,
):
    """
    Run complete CHA pipeline for a cluster using the trunk-spur network builder.

    Args:
        cluster_id: Cluster identifier
        attach_mode: Building attachment mode ('split_edge_per_building')
        output_dir: Output directory (default: results/cha/{cluster_id})
        catalog_path: Optional path to technical pipe catalog Excel file
        max_spur_length_m: Maximum spur pipe length in metres (default 50)
        plant_wgs84_lat: Fixed plant latitude in WGS84 (optional)
        plant_wgs84_lon: Fixed plant longitude in WGS84 (optional)
        disable_auto_plant_siting: Disable automatic plant re-siting
    """
    logger.info(f"Starting CHA pipeline for cluster {cluster_id}")
    
    # Set output directory
    if output_dir is None:
        output_dir = resolve_cluster_path(cluster_id, "cha")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load cluster data
    buildings, streets, plant_coords, design_hour, design_load_kw, hourly_profiles, cluster_street_name = load_cluster_data(cluster_id)

    # Override plant location if WGS84 coordinates are provided (EPSG:4326 lat/lon)
    # Automatically disable auto-plant-siting when fixed coordinates are provided
    if plant_wgs84_lat is not None and plant_wgs84_lon is not None:
        pt = gpd.GeoDataFrame(
            {"_": [1]},
            geometry=[Point(float(plant_wgs84_lon), float(plant_wgs84_lat))],  # (lon, lat)
            crs="EPSG:4326",
        )
        target_crs = buildings.crs if buildings.crs else "EPSG:25833"
        pt_proj = pt.to_crs(target_crs)
        plant_coords = (float(pt_proj.geometry.iloc[0].x), float(pt_proj.geometry.iloc[0].y))
        logger.info(
            f"Using fixed plant (WGS84): lat={plant_wgs84_lat}, lon={plant_wgs84_lon} "
            f"-> projected {target_crs}: {plant_coords}"
        )
        # Automatically disable auto-plant-siting when fixed coordinates are provided
        if not disable_auto_plant_siting:
            disable_auto_plant_siting = True
            logger.info("Auto-plant-siting automatically disabled (using fixed WGS84 coordinates)")
    
    # Get CHA config
    config = get_default_config()

    logger.info("Building trunk-spur network (strict street-following trunks + exclusive spurs)...")

    # Load technical pipe catalog
    if catalog_path is None:
        candidates = [
            DATA_RAW / "Technikkatalog_Wärmeplanung_Version_1.1_August24_CC-BY.xlsx",
            DATA_RAW / "Technikkatalog_Wärmeplanung_Version_1.1_August24_CC-BY (1).xlsx",
            Path("data/raw/Technikkatalog_Wärmeplanung_Version_1.1_August24_CC-BY.xlsx"),
            Path("data/raw/Technikkatalog_Wärmeplanung_Version_1.1_August24_CC-BY (1).xlsx"),
        ]
        catalog_path = next((p for p in candidates if p.exists()), candidates[0])

    if not catalog_path.exists():
        logger.warning(f"Technical catalog not found at {catalog_path}, using default pipe catalog")
        pipe_catalog = load_pipe_catalog()
    else:
        pipe_catalog = load_technical_catalog(catalog_path)

    # Prepare per-building design loads from hourly profiles at the design hour
    design_loads_kw = {}
    if hourly_profiles is not None and not hourly_profiles.empty:
        for _, building in buildings.iterrows():
            bid = building['building_id']
            if bid in hourly_profiles.columns:
                design_loads_kw[bid] = float(hourly_profiles.loc[design_hour, bid])
                logger.debug(f"Building {bid}: {design_loads_kw[bid]:.2f} kW (hourly profile, hour {design_hour})")
            else:
                logger.warning(f"Building {bid} not in hourly profiles, using distributed cluster load")
                total_area = buildings['floor_area_m2'].sum() if 'floor_area_m2' in buildings.columns else 0
                area_share = (building['floor_area_m2'] / total_area
                              if total_area > 0 else 1.0 / len(buildings))
                design_loads_kw[bid] = float(design_load_kw * area_share)
    else:
        logger.warning("Hourly profiles not available, distributing cluster design load per building")
        for _, building in buildings.iterrows():
            bid = building['building_id']
            total_area = buildings['floor_area_m2'].sum() if 'floor_area_m2' in buildings.columns else 0
            area_share = (building['floor_area_m2'] / total_area
                          if total_area > 0 else 1.0 / len(buildings))
            design_loads_kw[bid] = float(design_load_kw * area_share)

    total_cluster_load = sum(design_loads_kw.values())
    logger.info(
        f"Building heat demands (design hour {design_hour}): "
        f"total={total_cluster_load:.1f} kW across {len(design_loads_kw)} buildings"
    )

    net, topology_info = build_trunk_spur_network(
        cluster_id=cluster_id,
        buildings=buildings,
        streets=streets,
        plant_coords=plant_coords,
        selected_street_name=cluster_street_name,
        design_loads_kw=design_loads_kw,
        pipe_catalog=pipe_catalog,
        config=config,
        max_spur_length_m=max_spur_length_m,
        attach_mode=attach_mode,
        disable_auto_plant_siting=disable_auto_plant_siting,
    )

    # Trunk-spur builder already runs pipeflow internally
    initial_converged = topology_info.get('converged', False)
    final_converged = initial_converged
    logger.info(f"Trunk-spur network built: converged={initial_converged}")
    
    # Update heat consumer loads with per-building design loads (trunk-spur uses heat_consumer elements)
    total_load_kw = sum(design_loads_kw.values())
    if hasattr(net, 'heat_consumer') and net.heat_consumer is not None and not net.heat_consumer.empty:
        for _, building in buildings.iterrows():
            bid = building['building_id']
            qext_w = float(design_loads_kw.get(bid, 0.0)) * 1000.0
            hc_mask = net.heat_consumer['name'] == f"hc_{bid}"
            if hc_mask.any():
                net.heat_consumer.loc[hc_mask, 'qext_w'] = qext_w
                if 'controlled_mdot_kg_per_s' in net.heat_consumer.columns:
                    cp_j_per_kgk = 4180.0
                    deltat_k = max(1.0, float(config.delta_t_k))
                    net.heat_consumer.loc[hc_mask, 'controlled_mdot_kg_per_s'] = max(
                        1e-5, qext_w / (cp_j_per_kgk * deltat_k)
                    )
        logger.info(
            f"Set design loads: total={total_load_kw:.1f} kW across "
            f"{len(design_loads_kw)} buildings (heat_consumer)"
        )
        # Re-run pipeflow in thermal mode so temperatures reflect updated loads
        try:
            pp.pipeflow(net, mode='sequential', verbose=False, max_iter_hyd=80, max_iter_therm=80)
        except Exception as e:
            logger.warning(f"Thermal pipeflow (sequential) failed after updating heat_consumer loads: {e}")
    
    # Extract topology information for logging
    topology_stats = {}
    if 'trunk_edges' in topology_info:
        topology_stats['trunk_edges'] = len(topology_info['trunk_edges'])
    if 'service_connections' in topology_info:
        topology_stats['service_connections'] = len(topology_info['service_connections'])
    if 'buildings_snapped' in topology_info:
        topology_stats['buildings_connected'] = len(topology_info['buildings_snapped'])
    if 'trunk_nodes' in topology_info:
        topology_stats['trunk_nodes'] = len(topology_info['trunk_nodes'])
    if 'spurs' in topology_info or 'spur_assignments' in topology_info:
        spurs = topology_info.get('spur_assignments', topology_info.get('spurs', {}))
        if isinstance(spurs, dict):
            topology_stats['spurs'] = len(spurs)
        else:
            topology_stats['spurs'] = len(spurs) if hasattr(spurs, '__len__') else 0
    
    # Extract KPIs (only if network converged)
    if final_converged:
        logger.info("Extracting KPIs...")
        kpis = extract_kpis(net, cluster_id, design_hour, config, detailed=True)
        kpis['convergence'] = {
            'initial_converged': initial_converged,
            'final_converged': final_converged,
            'optimized': False  # trunk-spur builder handles optimization internally
        }
        # Add topology info to KPIs
        kpis['topology'] = topology_stats
    else:
        logger.warning("Network did not converge. KPIs may be unreliable.")
        # Still extract KPIs but mark as non-converged
        try:
            kpis = extract_kpis(net, cluster_id, design_hour, config, detailed=True)
            kpis['convergence'] = {
                'initial_converged': initial_converged,
                'final_converged': False,
                'optimized': False,
                'warning': 'KPIs extracted from non-converged network'
            }
            # Add topology info to KPIs
            kpis['topology'] = topology_stats
        except Exception as e:
            logger.error(f"Could not extract KPIs: {e}")
            kpis = {
                'cluster_id': cluster_id,
                'convergence': {
                    'initial_converged': initial_converged,
                    'final_converged': False,
                    'optimized': False,
                    'error': str(e)
                },
                'feasible': False,
                'error': 'Network did not converge',
                'topology': topology_stats
            }
    
    # ── Hydraulic validation (EN 13941-1) ─────────────────────────────────────
    hyd_path = None
    if final_converged:
        try:
            val_cfg = ValidationConfig()
            hydraulic_result = HydraulicValidator(val_cfg).validate(net)
            kpis["hydraulic_validation"] = {
                "passed": hydraulic_result.passed,
                "issues": hydraulic_result.issues,
                "warnings": hydraulic_result.warnings,
                "metrics": hydraulic_result.metrics,
            }
            hyd_path = output_dir / "hydraulic_validation.json"
            with open(hyd_path, "w") as f:
                json.dump(kpis["hydraulic_validation"], f, indent=2, default=str)
            logger.info(
                f"Hydraulic validation (EN 13941-1): "
                f"{'PASSED' if hydraulic_result.passed else 'FAILED'} "
                f"→ {hyd_path}"
            )
        except Exception as e:
            logger.warning(f"Hydraulic validation skipped: {e}")

    # ── Robustness validation (Monte Carlo) ────────────────────────────────────
    rob_path = None
    if final_converged:
        try:
            val_cfg = ValidationConfig()
            n_sc = val_cfg.robustness.n_scenarios
            logger.info(f"Running robustness validation ({n_sc} Monte Carlo scenarios)...")
            robustness_result = RobustnessValidator(val_cfg).validate(net)
            kpis["robustness_validation"] = {
                "passed": robustness_result.passed,
                "issues": robustness_result.issues,
                "warnings": robustness_result.warnings,
                "metrics": robustness_result.metrics,
                "scenario_results": robustness_result.scenario_results,
            }
            rob_path = output_dir / "robustness_validation.json"
            with open(rob_path, "w") as f:
                json.dump(kpis["robustness_validation"], f, indent=2, default=str)
            success_rate = robustness_result.metrics.get("robustness_success_rate", 0.0)
            logger.info(
                f"Robustness validation ({n_sc} scenarios): "
                f"{'PASSED' if robustness_result.passed else 'FAILED'} "
                f"(success rate: {success_rate:.1%}) → {rob_path}"
            )
        except Exception as e:
            logger.warning(f"Robustness validation skipped: {e}")

    # Save KPIs to JSON (after validators so their results are included)
    kpis_path = output_dir / "cha_kpis.json"
    with open(kpis_path, 'w') as f:
        json.dump(kpis, f, indent=2, default=str)
    logger.info(f"Saved KPIs to {kpis_path}")

    # Save network as pickle
    network_path = output_dir / "network.pickle"
    with open(network_path, 'wb') as f:
        pickle.dump(net, f)
    logger.info(f"Saved network to {network_path}")
    
    # Generate interactive maps (with error handling so one failure doesn't stop others)
    map_path = None
    temp_map_path = None
    pressure_map_path = None
    
    # Generate velocity map
    logger.info("Generating interactive map (velocity)...")
    map_path = output_dir / "interactive_map.html"
    try:
        create_interactive_map(
            net=net,
            buildings=buildings,
            cluster_id=cluster_id,
            output_path=map_path,
            config=config,
            color_by="velocity",
            title_suffix="(Velocity)"
        )
        logger.info(f"Saved interactive map to {map_path}")
    except Exception as e:
        logger.error(f"Failed to generate velocity map: {e}", exc_info=True)
        map_path = None

    # Generate temperature map (cascading colors by temperature)
    logger.info("Generating temperature interactive map...")
    temp_map_path = output_dir / "interactive_map_temperature.html"
    try:
        create_interactive_map(
            net=net,
            buildings=buildings,
            cluster_id=cluster_id,
            output_path=temp_map_path,
            config=config,
            color_by="temperature",
            title_suffix="(Temperature)"
        )
        logger.info(f"Saved temperature interactive map to {temp_map_path}")
    except Exception as e:
        logger.error(f"Failed to generate temperature map: {e}", exc_info=True)
        temp_map_path = None

    # Generate pressure map (cascading colors by mean pipe pressure)
    logger.info("Generating pressure interactive map...")
    pressure_map_path = output_dir / "interactive_map_pressure.html"
    try:
        create_interactive_map(
            net=net,
            buildings=buildings,
            cluster_id=cluster_id,
            output_path=pressure_map_path,
            config=config,
            color_by="pressure",
            title_suffix="(Pressure)"
        )
        logger.info(f"Saved pressure interactive map to {pressure_map_path}")
    except Exception as e:
        logger.error(f"Failed to generate pressure map: {e}", exc_info=True)
        pressure_map_path = None

    # Export updated pipe CSVs (velocities + temperatures + map scaling/colors)
    try:
        export_pipe_velocity_csvs(
            net=net,
            output_dir=output_dir,
            cluster_id=cluster_id,
            scale_to_data_range=True,
        )
    except Exception as e:
        logger.warning(f"Failed to export pipe velocity CSVs: {e}")
    
    # Print summary statistics
    logger.info(f"{'='*60}")
    logger.info(f"CHA Pipeline Complete: {cluster_id}")
    logger.info(f"{'='*60}")
    logger.info(f"Buildings: {len(buildings)}")
    if topology_stats:
        for key, value in topology_stats.items():
            logger.info(f"{key.replace('_', ' ').title()}: {value}")
    logger.info(f"Converged: {'✓' if final_converged else '✗'}")
    if final_converged and 'feasible' in kpis:
        logger.info(f"Feasible: {'✓' if kpis.get('feasible') else '✗'}")
    if final_converged and 'aggregate' in kpis and 'v_share_within_limits' in kpis.get('aggregate', {}):
        v_share = kpis['aggregate'].get('v_share_within_limits', 0.0)
        logger.info(f"Velocity compliance: {v_share:.1%}")
    logger.info(f"Results saved to {output_dir}")
    logger.info(f"{'='*60}")
    
    return {
        'kpis': kpis_path,
        'network': network_path,
        'interactive_map': map_path,
        'interactive_map_temperature': temp_map_path,
        'interactive_map_pressure': pressure_map_path,
        'hydraulic_validation': hyd_path,
        'robustness_validation': rob_path,
    }


def main():
    parser = argparse.ArgumentParser(
        description='Run CHA pipeline for district heating network analysis',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/01_run_cha.py --cluster-id ST001_HEINRICH_ZILLE_STRASSE
  python scripts/01_run_cha.py --cluster-id ST001 --catalog path/to/catalog.xlsx
  python scripts/01_run_cha.py --cluster-id ST001 --max-spur-length 30
  python scripts/01_run_cha.py --cluster-id ST001 --enable-auto-plant-siting
        """
    )
    
    parser.add_argument(
        '--cluster-id',
        type=str,
        required=True,
        help='Cluster identifier (e.g., ST001_HEINRICH_ZILLE_STRASSE)'
    )
    
    parser.add_argument(
        '--attach-mode',
        type=str,
        default='split_edge_per_building',
        choices=['split_edge_per_building', 'nearest_node'],
        help='Building attachment mode'
    )
    

    parser.add_argument(
        '--catalog',
        type=str,
        default=None,
        help='Path to technical catalog Excel file (for trunk-spur builder)'
    )
    
    parser.add_argument(
        '--max-spur-length',
        type=float,
        default=50.0,
        help='Maximum spur length in meters (default: 50.0)'
    )

    parser.add_argument(
        '--plant-wgs84-lat',
        type=float,
        default=51.7601419,
        help='Fixed plant latitude in WGS84 (EPSG:4326). Default: 51.758 (HKW Cottbus)'
    )
    parser.add_argument(
        '--plant-wgs84-lon',
        type=float,
        default=14.3700521,
        help='Fixed plant longitude in WGS84 (EPSG:4326). Default: 14.364 (HKW Cottbus)'
    )
    parser.add_argument(
        '--enable-auto-plant-siting',
        action='store_true',
        help='Override: use automatic plant siting instead of fixed CHP coordinates.'
    )
    parser.add_argument(
        '--disable-auto-plant-siting',
        action='store_true',
        help='Disable automatic re-siting of plant (auto-set when using fixed coordinates).'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default=None,
        help='Output directory (default: results/cha/{cluster_id})'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        output_dir = Path(args.output_dir) if args.output_dir else None
        catalog_path = Path(args.catalog) if args.catalog else None
        
        # Fixed CHP plant location (default). Override with --enable-auto-plant-siting.
        plant_lat = None if args.enable_auto_plant_siting else args.plant_wgs84_lat
        plant_lon = None if args.enable_auto_plant_siting else args.plant_wgs84_lon
        
        results = run_cha_pipeline(
            cluster_id=args.cluster_id,
            attach_mode=args.attach_mode,
            output_dir=output_dir,
            catalog_path=catalog_path,
            max_spur_length_m=args.max_spur_length,
            plant_wgs84_lat=plant_lat,
            plant_wgs84_lon=plant_lon,
            disable_auto_plant_siting=args.disable_auto_plant_siting,
        )
        
        print("\n" + "="*60)
        print("CHA Pipeline Complete")
        print("="*60)
        print(f"Cluster ID: {args.cluster_id}")
        
        # Print convergence status and topology if available
        import json
        if results['kpis'].exists():
            with open(results['kpis'], 'r') as f:
                kpis = json.load(f)
                
                if 'convergence' in kpis:
                    conv = kpis['convergence']
                    print(f"\nConvergence Status:")
                    print(f"  Initial: {'✓ Converged' if conv.get('initial_converged') else '✗ Failed'}")
                    print(f"  Final: {'✓ Converged' if conv.get('final_converged') else '✗ Failed'}")
                    if conv.get('optimized'):
                        print(f"  Optimization: Applied")
                    if 'warning' in conv:
                        print(f"  Warning: {conv['warning']}")
                
                if 'topology' in kpis:
                    topo = kpis['topology']
                    print(f"\nTopology Statistics:")
                    for key, value in topo.items():
                        print(f"  {key.replace('_', ' ').title()}: {value}")
                
                if 'feasible' in kpis:
                    print(f"\nFeasibility: {'✓ Feasible' if kpis.get('feasible') else '✗ Not Feasible'}")
                    if 'aggregate' in kpis and 'v_share_within_limits' in kpis.get('aggregate', {}):
                        v_share = kpis['aggregate'].get('v_share_within_limits', 0.0)
                        print(f"Velocity Compliance: {v_share:.1%}")
        
        print(f"\nOutputs:")
        print(f"  KPIs: {results['kpis']}")
        print(f"  Network: {results['network']}")
        print(f"  Interactive Map: {results['interactive_map']}")
        print("="*60)
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
