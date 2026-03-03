# Fraunhofer Integration Guide

## Overview

This guide details the integration of the Branitz multi-agent heat planning system with Fraunhofer's existing enterprise infrastructure.

## Key Features

- **Custom Data Connectors**: Supports ALKIS, Fraunhofer IIS specific formats, PostGIS direct connection.
- **Enterprise Access Control**: Implemented JWT and API key authentication using tenant ID isolation.
- **Branding Engine**: Full white-label support via `config/branding.yaml` that dynamically overrides the front-end interface built on Leaflet Map layers.

## Deployment Checklist

- Apply `.env.fraunhofer` settings for Fraunhofer configurations.
- Use `adapters/fraunhofer_adapter.py` for mapping Fraunhofer internal data models to standard geometries.
- Access the secure simulation endpoints via `/api/v1/secure/simulate` passing in an authorized JWT or API-Key.
- Monitor access with the Prometheus scrape configuration included.
