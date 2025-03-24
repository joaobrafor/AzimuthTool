# AzimuthTool

A powerful QGIS plugin for generating vector line layers from azimuths or quadrant bearings and distances, starting from a user-defined point.

## Features
- Create lines based on azimuth (e.g., `90-30-15.50`) or bearing (e.g., `45-15-30-NE`).
- Supports decimal distances (e.g., `100.25`).
- Select the initial point on the map (optional snapping).
- Import/export data from text files.
- Import vertices from line or polygon layers.
- Output layers as temporary layers, Shapefiles, or GeoPackages.

## Requirements
- QGIS 3.0 or later

## Installation
1. Download or clone this repository.
2. Copy the `AzimuthTool` folder to the QGIS plugins directory (e.g., `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins` on Linux).
3. Restart QGIS and enable the plugin under **Plugins > Manage and Install Plugins**.

## Quick Usage
1. Open the plugin from the **Toolbar** or **Plugins** menu.
2. Set (or select) the initial coordinate.
3. Fill in the table with angles (azimuth/bearing) and distances.
4. Click **Process** to generate the output layer.

## Support and Issues
- [Project Homepage](https://github.com/joaobrafor/AzimuthTool)
- [Issue Tracker](https://github.com/joaobrafor/AzimuthTool/issues)

## Author
- **João Ubaldo** - [joao@brafor.com.br](mailto:joao@brafor.com.br)
