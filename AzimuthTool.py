from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QFileDialog, QMessageBox, QAction, QToolBar,
    QHeaderView, QDesktopWidget, QInputDialog
)
from qgis.PyQt.QtCore import Qt, QVariant, QCoreApplication, QTranslator, QSettings, QLocale
from qgis.PyQt.QtGui import QIcon
from qgis.core import (
    QgsFeature, QgsGeometry, QgsPointXY, QgsField, QgsFields, QgsWkbTypes,
    QgsVectorFileWriter, QgsProject, QgsVectorLayer, QgsCoordinateTransform,
    QgsSnappingConfig, QgsTolerance, QgsApplication
)
from qgis.gui import QgsMapToolEmitPoint, QgsRubberBand
from qgis.utils import iface
import math
import os
import tempfile

class SnappingPointMapTool(QgsMapToolEmitPoint):
    def __init__(self, canvas):
        super().__init__(canvas)
        self.canvas = canvas
        self.rubberBand = QgsRubberBand(self.canvas, QgsWkbTypes.PointGeometry)
        self.rubberBand.setColor(Qt.red)
        self.rubberBand.setWidth(2)
        self.rubberBand.setIcon(QgsRubberBand.ICON_CIRCLE)
        self.rubberBand.setIconSize(10)
        self.snappingUtils = iface.mapCanvas().snappingUtils()

    def canvasMoveEvent(self, event):
        point = self.toMapCoordinates(event.pos())
        match = self.snappingUtils.snapToMap(point)
        if match.isValid():
            snap_point = match.point()
            self.rubberBand.setToGeometry(QgsGeometry.fromPointXY(snap_point), None)
            self.rubberBand.show()
        else:
            self.rubberBand.hide()

    def canvasPressEvent(self, event):
        point = self.toMapCoordinates(event.pos())
        match = self.snappingUtils.snapToMap(point)
        if match.isValid():
            snap_point = match.point()
        else:
            snap_point = point
        self.rubberBand.hide()
        self.canvasClicked.emit(snap_point, Qt.LeftButton)

    def deactivate(self):
        self.rubberBand.hide()
        super().deactivate()

class AzimuthToolDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(self.tr('Azimuth Tool'))
        self.setGeometry(300, 300, 600, 400)
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.layout = QVBoxLayout()
        self.setup_ui()
        self.mapTool = None
        self.center_window()

    def tr(self, message):
        return QCoreApplication.translate('AzimuthToolDialog', message)

    def center_window(self):
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    def setup_ui(self):
        self.setup_output_shapefile_field()
        self.setup_initial_point_field()
        self.setup_distance_azimuth_table()
        self.setup_import_export_buttons()
        self.setup_process_button()
        self.setLayout(self.layout)

    def setup_output_shapefile_field(self):
        self.output_shapefile_label = QLabel(self.tr('Output Layer:'))
        self.output_shapefile_edit = QLineEdit()
        self.output_shapefile_button = QPushButton(self.tr('Browse'))
        self.output_shapefile_button.clicked.connect(self.browse_output_shapefile)
        h_layout = QHBoxLayout()
        h_layout.addWidget(self.output_shapefile_label)
        h_layout.addWidget(self.output_shapefile_edit)
        h_layout.addWidget(self.output_shapefile_button)
        self.layout.addLayout(h_layout)
        self.set_temporary_output_path()

    def setup_initial_point_field(self):
        self.initial_point_label = QLabel(self.tr('Initial Coordinate:'))
        self.initial_point_edit = QLineEdit()
        self.set_canvas_center_as_initial_point()
        self.initial_point_button = QPushButton(self.tr('Select on Canvas'))
        self.initial_point_button.clicked.connect(self.select_initial_point)
        h_layout = QHBoxLayout()
        h_layout.addWidget(self.initial_point_label)
        h_layout.addWidget(self.initial_point_edit)
        h_layout.addWidget(self.initial_point_button)
        self.layout.addLayout(h_layout)

    def setup_distance_azimuth_table(self):
        self.distance_azimuth_label = QLabel(self.tr('List of Vertices, Azimuths/Bearings, Distances, and Adjacency:'))
        info_icon_path = os.path.join(os.path.dirname(__file__), 'icon_info.png')
        self.info_button = QPushButton()
        self.info_button.setIcon(QIcon(info_icon_path))
        self.info_button.clicked.connect(self.show_info)

        label_layout = QHBoxLayout()
        label_layout.addWidget(self.distance_azimuth_label)
        label_layout.addWidget(self.info_button)
        label_layout.addStretch()
        self.layout.addLayout(label_layout)

        self.table = QTableWidget(10, 4)
        self.table.setHorizontalHeaderLabels([
            self.tr('Vertex'),
            self.tr('Angle'),
            self.tr('Distance (m)'),
            self.tr('Adjacency')
        ])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

        self.add_row_button = QPushButton('+')
        self.add_row_button.clicked.connect(self.add_row)
        self.remove_row_button = QPushButton('-')
        self.remove_row_button.clicked.connect(self.remove_selected_rows)

        h_layout = QHBoxLayout()
        h_layout.addWidget(self.remove_row_button)
        h_layout.addWidget(self.add_row_button)

        self.layout.addWidget(self.table)
        self.layout.addLayout(h_layout)

    def setup_import_export_buttons(self):
        self.import_button = QPushButton(self.tr('Import from .txt'))
        self.import_button.clicked.connect(self.import_from_txt)
        self.export_button = QPushButton(self.tr('Export to .txt'))
        self.export_button.clicked.connect(self.export_to_txt)
        self.import_polygon_button = QPushButton(self.tr('Import from Line/Polygon'))
        self.import_polygon_button.clicked.connect(self.import_from_line_or_polygon)
        h_layout = QHBoxLayout()
        h_layout.addWidget(self.import_button)
        h_layout.addWidget(self.export_button)
        h_layout.addWidget(self.import_polygon_button)
        self.layout.addLayout(h_layout)

    def setup_process_button(self):
        self.process_button = QPushButton(self.tr('Process'))
        self.process_button.clicked.connect(self.process_data)
        self.layout.addWidget(self.process_button)

    def set_temporary_output_path(self):
        self.output_shapefile_edit.setText(self.tr('Temporary Layer'))

    def set_canvas_center_as_initial_point(self):
        canvas = iface.mapCanvas()
        extent = canvas.extent()
        center = extent.center()
        self.initial_point_edit.setText(f"{center.x()},{center.y()}")

    def browse_output_shapefile(self):
        filename, _ = QFileDialog.getSaveFileName(
            self,
            self.tr('Select output file'),
            '',
            self.tr('GeoPackages (*.gpkg);;Shapefiles (*.shp)')
        )
        if filename:
            self.output_shapefile_edit.setText(filename)

    def select_initial_point(self):
        selected_layers = iface.layerTreeView().selectedLayers()
        if len(selected_layers) == 1 and isinstance(selected_layers[0], QgsVectorLayer):
            self.show_message(self.tr("Snapping is enabled for the selected vector layer."))
        else:
            self.show_message(
                self.tr("You can enable snapping if you select exactly one vector layer before clicking 'Select on Canvas'.")
            )
        self.mapTool = SnappingPointMapTool(iface.mapCanvas())
        self.mapTool.canvasClicked.connect(self.set_initial_point)
        iface.mapCanvas().setMapTool(self.mapTool)
        self.configure_snapping()

    def configure_snapping(self):
        selected_layers = iface.layerTreeView().selectedLayers()
        if not selected_layers or len(selected_layers) != 1:
            self.show_message(self.tr("Select only one vector layer for snapping."))
            return
        layer = selected_layers[0]
        if not isinstance(layer, QgsVectorLayer):
            self.show_message(self.tr("Select a vector layer for snapping."))
            return
        project = QgsProject.instance()
        snapping_config = QgsSnappingConfig()
        snapping_config.setEnabled(True)
        snapping_config.setMode(QgsSnappingConfig.AdvancedConfiguration)
        individual_settings = QgsSnappingConfig.IndividualLayerSettings(
            True,
            QgsSnappingConfig.VertexFlag | QgsSnappingConfig.SegmentFlag,
            10,
            QgsTolerance.Pixels
        )
        snapping_config.setIndividualLayerSettings(layer, individual_settings)
        project.setSnappingConfig(snapping_config)
        iface.mapCanvas().snappingUtils().setConfig(snapping_config)

    def set_initial_point(self, point):
        self.initial_point_edit.setText(f"{point.x()},{point.y()}")
        iface.mapCanvas().unsetMapTool(self.mapTool)
        self.mapTool.canvasClicked.disconnect(self.set_initial_point)
        self.mapTool = None

    def add_row(self):
        row_count = self.table.rowCount()
        self.table.insertRow(row_count)

    def remove_selected_rows(self):
        indices = self.table.selectionModel().selectedRows()
        for index in sorted(indices, reverse=True):
            self.table.removeRow(index.row())

    def import_from_txt(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, self.tr('Import from TXT'), '', self.tr('Text Files (*.txt)')
        )
        if filename:
            self.table.setRowCount(0)
            with open(filename, 'r', encoding='utf-8') as file:
                lines = file.readlines()
                if lines:
                    first_line_parts = lines[0].strip().split(';')
                    if first_line_parts[0] == "Initial Point":
                        self.initial_point_edit.setText(first_line_parts[1])
                        lines = lines[1:]
                for line in lines:
                    parts = line.strip().split(';')
                    parts += [''] * (4 - len(parts))
                    vertex, azimuth, distance, adjacency = parts
                    row_position = self.table.rowCount()
                    self.table.insertRow(row_position)
                    self.table.setItem(row_position, 0, QTableWidgetItem(vertex))
                    self.table.setItem(row_position, 1, QTableWidgetItem(azimuth))
                    self.table.setItem(row_position, 2, QTableWidgetItem(distance))
                    self.table.setItem(row_position, 3, QTableWidgetItem(adjacency))

    def export_from_txt_normalization(self, raw_azimuth):
        if any(letter in raw_azimuth.upper() for letter in ['N', 'S', 'E', 'W']):
            return self.export_format_rumo(raw_azimuth)
        else:
            return self.export_format_azimuth(raw_azimuth)

    def export_format_azimuth(self, azimuth_text):
        sep = ',' if ',' in azimuth_text else '.'
        try:
            value = float(azimuth_text.replace(',', '.'))
            if sep == '.':
                decimals = len(azimuth_text.split('.')[1]) if '.' in azimuth_text else 0
            else:
                decimals = len(azimuth_text.split(',')[1]) if ',' in azimuth_text else 0
            if decimals == 0:
                decimals = 2
            degrees = int(value)
            minutes_full = (value - degrees) * 60
            minutes = int(minutes_full)
            seconds = (minutes_full - minutes) * 60
            seconds_str = f"{seconds:0.{decimals}f}"
            if '.' in seconds_str or ',' in seconds_str:
                if '.' in seconds_str:
                    int_part, frac_part = seconds_str.split('.')
                else:
                    int_part, frac_part = seconds_str.split(',')
                seconds_str = f"{int(int_part):02d}{sep}{frac_part}"
            else:
                seconds_str = f"{int(seconds):02d}"
            return f"{degrees:02d}-{minutes:02d}-{seconds_str}"
        except ValueError:
            parts = azimuth_text.split('-')
            if len(parts) == 2:
                try:
                    degrees = int(parts[0])
                    minutes = int(parts[1])
                except:
                    return azimuth_text
                seconds = 0.0
                decimals = 2
                seconds_str = f"{seconds:0.{decimals}f}"
                if '.' in seconds_str or ',' in seconds_str:
                    if '.' in seconds_str:
                        int_part, frac_part = seconds_str.split('.')
                    else:
                        int_part, frac_part = seconds_str.split(',')
                    seconds_str = f"{int(int_part):02d}{sep}{frac_part}"
                else:
                    seconds_str = f"{int(seconds):02d}"
                return f"{degrees:02d}-{minutes:02d}-{seconds_str}"
            elif len(parts) == 3:
                try:
                    degrees = int(parts[0])
                    minutes = int(parts[1])
                    seconds = float(parts[2].replace(',', '.'))
                except:
                    return azimuth_text
                if sep == '.':
                    decimals = len(parts[2].split('.')[1]) if '.' in parts[2] else 2
                else:
                    decimals = len(parts[2].split(',')[1]) if ',' in parts[2] else 2
                seconds_str = f"{seconds:0.{decimals}f}"
                if '.' in seconds_str or ',' in seconds_str:
                    if '.' in seconds_str:
                        int_part, frac_part = seconds_str.split('.')
                    else:
                        int_part, frac_part = seconds_str.split(',')
                    seconds_str = f"{int(int_part):02d}{sep}{frac_part}"
                else:
                    seconds_str = f"{int(seconds):02d}"
                return f"{degrees:02d}-{minutes:02d}-{seconds_str}"
            else:
                return azimuth_text

    def export_format_rumo(self, rumo_text):
        allowed_directions = {"NE", "NW", "SE", "SW"}
        sep = ',' if ',' in rumo_text else '.'
        parts = rumo_text.split('-')
        parts = [p.strip() for p in parts if p.strip()]
        n = len(parts)
        if n == 2:
            try:
                deg = int(parts[0])
            except:
                raise ValueError(self.tr("Invalid degrees."))
            direction = parts[1].upper()
            if direction not in allowed_directions:
                raise ValueError(self.tr("Invalid direction."))
            minutes = 0
            seconds = 0.0
            raw_seconds = "0"
        elif n == 3:
            try:
                deg = int(parts[0])
                minutes = int(parts[1])
            except:
                raise ValueError(self.tr("Invalid degrees or minutes."))
            direction = parts[2].upper()
            if direction not in allowed_directions:
                raise ValueError(self.tr("Invalid direction."))
            seconds = 0.0
            raw_seconds = "0"
        elif n == 4:
            try:
                deg = int(parts[0])
                minutes = int(parts[1])
            except:
                raise ValueError(self.tr("Invalid degrees or minutes."))
            raw_seconds = parts[2]
            try:
                seconds = float(raw_seconds.replace(',', '.'))
            except:
                raise ValueError(self.tr("Invalid seconds."))
            direction = parts[3].upper()
            if direction not in allowed_directions:
                raise ValueError(self.tr("Invalid direction."))
        else:
            raise ValueError(self.tr("Invalid number of parts for bearing."))
        if sep == ',':
            decimals = len(raw_seconds.split(',')[1]) if ',' in raw_seconds else 0
        else:
            decimals = len(raw_seconds.split('.')[1]) if '.' in raw_seconds else 0
        if decimals == 0:
            decimals = 2
        seconds_str = f"{seconds:0.{decimals}f}"
        if '.' in seconds_str or ',' in seconds_str:
            if '.' in seconds_str:
                int_part, frac_part = seconds_str.split('.')
            else:
                int_part, frac_part = seconds_str.split(',')
            seconds_str = f"{int(int_part):02d}{sep}{frac_part}"
        else:
            seconds_str = f"{int(seconds):02d}"
        return f"{deg:02d}-{minutes:02d}-{seconds_str}-{direction}"

    def export_format_distance(self, distance_text):
        try:
            value = float(distance_text.replace(',', '.'))
        except ValueError:
            return distance_text
        sep = ',' if ',' in distance_text else '.'
        s = distance_text.replace(',', '.')
        if '.' in s:
            decimals = len(s.split('.')[1])
            if decimals < 3:
                decimals = 3
            formatted = f"{value:0.{decimals}f}"
        else:
            formatted = f"{value:0.3f}"
        if sep == ',':
            formatted = formatted.replace('.', ',')
        return formatted

    def export_to_txt(self):
        filename, _ = QFileDialog.getSaveFileName(
            self, self.tr('Export to TXT'), '', self.tr('Text Files (*.txt)')
        )
        if filename:
            with open(filename, 'w', encoding='utf-8') as file:
                initial_point = self.initial_point_edit.text()
                file.write(f"{self.tr('Initial Point')};{initial_point}\n")
                for row in range(self.table.rowCount()):
                    vertex_item = self.table.item(row, 0)
                    azimuth_item = self.table.item(row, 1)
                    distance_item = self.table.item(row, 2)
                    adjacency_item = self.table.item(row, 3)
                    vertex = vertex_item.text() if vertex_item else ''
                    raw_azimuth = azimuth_item.text() if azimuth_item else ''
                    distance_raw = distance_item.text() if distance_item else ''
                    adjacency = adjacency_item.text() if adjacency_item else ''
                    if raw_azimuth or distance_raw or adjacency or vertex:
                        azimuth_export = self.export_from_txt_normalization(raw_azimuth) if raw_azimuth else ''
                        distance_export = self.export_format_distance(distance_raw) if distance_raw else ''
                        file.write(f"{vertex};{azimuth_export};{distance_export};{adjacency}\n")

    def import_from_line_or_polygon(self):
        mode, ok = QInputDialog.getItem(
            self,
            self.tr('Import from Line/Polygon'),
            self.tr('Select import format:'),
            [self.tr('Azimuth'), self.tr('Bearing')],
            0,
            False
        )
        if not ok:
            return
        selected_layers = iface.layerTreeView().selectedLayers()
        if not selected_layers:
            self.show_message(self.tr('No layer selected.'))
            return
        layer = selected_layers[0]
        selected_features = layer.selectedFeatures()
        if not selected_features:
            self.show_message(self.tr('No feature selected.'))
            return
        self.table.setRowCount(0)
        project_crs = QgsProject.instance().crs()
        layer_crs = layer.crs()
        transform = QgsCoordinateTransform(layer_crs, project_crs, QgsProject.instance())
        first_vertex_set = False
        for feature in selected_features:
            geometry = feature.geometry()
            if geometry.type() in (QgsWkbTypes.PolygonGeometry, QgsWkbTypes.CurvePolygon):
                if geometry.isMultipart():
                    polygons = (geometry.asMultiPolygon()
                                if geometry.type() == QgsWkbTypes.PolygonGeometry
                                else geometry.asMultiSurface())
                else:
                    polygons = ([geometry.asPolygon()]
                                if geometry.type() == QgsWkbTypes.PolygonGeometry
                                else [geometry.asCurvePolygon()])
                for polygon in polygons:
                    exterior_ring = polygon[0]
                    if not first_vertex_set and exterior_ring:
                        first_vertex = transform.transform(exterior_ring[0])
                        self.initial_point_edit.setText(f"{first_vertex.x()},{first_vertex.y()}")
                        first_vertex_set = True
                    for i in range(len(exterior_ring) - 1):
                        vertex1 = transform.transform(exterior_ring[i])
                        vertex2 = transform.transform(exterior_ring[i + 1])
                        dx = vertex2.x() - vertex1.x()
                        dy = vertex2.y() - vertex1.y()
                        angle = math.atan2(dx, dy)
                        azimuth_decimal = math.degrees(angle) if angle >= 0 else math.degrees(angle) + 360
                        if mode == self.tr('Azimuth'):
                            azimuth_formatted = self.convert_decimal_to_dms(azimuth_decimal)
                        else:
                            azimuth_formatted = self.convert_decimal_to_rumo(azimuth_decimal)
                        distance = self.calculate_distance(vertex1, vertex2)
                        row_position = self.table.rowCount()
                        self.table.insertRow(row_position)
                        self.table.setItem(row_position, 0, QTableWidgetItem(''))
                        self.table.setItem(row_position, 1, QTableWidgetItem(azimuth_formatted))
                        self.table.setItem(row_position, 2, QTableWidgetItem(f"{distance:.10f}"))
                        self.table.setItem(row_position, 3, QTableWidgetItem(''))
            elif geometry.type() in (QgsWkbTypes.LineGeometry, QgsWkbTypes.CurveLine):
                if geometry.isMultipart():
                    lines = (geometry.asMultiPolyline()
                             if geometry.type() == QgsWkbTypes.LineGeometry
                             else geometry.asMultiCurve())
                else:
                    lines = ([geometry.asPolyline()]
                             if geometry.type() == QgsWkbTypes.LineGeometry
                             else [geometry.asCurve()])
                for line in lines:
                    if not first_vertex_set and line:
                        first_vertex = transform.transform(line[0])
                        self.initial_point_edit.setText(f"{first_vertex.x()},{first_vertex.y()}")
                        first_vertex_set = True
                    for i in range(len(line) - 1):
                        vertex1 = transform.transform(line[i])
                        vertex2 = transform.transform(line[i + 1])
                        dx = vertex2.x() - vertex1.x()
                        dy = vertex2.y() - vertex1.y()
                        angle = math.atan2(dx, dy)
                        azimuth_decimal = math.degrees(angle) if angle >= 0 else math.degrees(angle) + 360
                        if mode == self.tr('Azimuth'):
                            azimuth_formatted = self.convert_decimal_to_dms(azimuth_decimal)
                        else:
                            azimuth_formatted = self.convert_decimal_to_rumo(azimuth_decimal)
                        distance = self.calculate_distance(vertex1, vertex2)
                        row_position = self.table.rowCount()
                        self.table.insertRow(row_position)
                        self.table.setItem(row_position, 0, QTableWidgetItem(''))
                        self.table.setItem(row_position, 1, QTableWidgetItem(azimuth_formatted))
                        self.table.setItem(row_position, 2, QTableWidgetItem(f"{distance:.10f}"))
                        self.table.setItem(row_position, 3, QTableWidgetItem(''))

    def calculate_azimuth(self, point1, point2):
        dx = point2.x() - point1.x()
        dy = point2.y() - point1.y()
        angle = math.atan2(dx, dy)
        azimuth = math.degrees(angle) if angle >= 0 else math.degrees(angle) + 360
        return self.convert_decimal_to_dms(azimuth)

    def calculate_distance(self, point1, point2):
        return math.sqrt((point2.x() - point1.x())**2 + (point2.y() - point1.y())**2)

    def convert_decimal_to_dms(self, decimal_degrees):
        degrees = int(decimal_degrees)
        minutes_full = (decimal_degrees - degrees) * 60
        minutes = int(minutes_full)
        seconds = round((minutes_full - minutes) * 60, 3)
        if seconds == 60.000:
            seconds = 0.000
            minutes += 1
        if minutes == 60:
            minutes = 0
            degrees += 1
        return f"{degrees:02d}-{minutes:02d}-{seconds:06.3f}"

    def convert_dms_to_decimal(self, dms):
        dms = dms.replace(',', '.')
        parts = dms.split('-')
        d = float(parts[0])
        m = float(parts[1]) if len(parts) > 1 else 0.0
        s = float(parts[2]) if len(parts) > 2 else 0.0
        return d + (m / 60.0) + (s / 3600.0)

    def convert_rumo_to_decimal(self, rumo):
        rumo = rumo.replace(',', '.').upper()
        parts = rumo.split('-')
        if len(parts) == 2:
            d = float(parts[0])
            m = 0.0
            s = 0.0
            direction = parts[1]
        elif len(parts) == 3:
            d = float(parts[0])
            m = float(parts[1])
            s = 0.0
            direction = parts[2]
        elif len(parts) == 4:
            d = float(parts[0])
            m = float(parts[1])
            s = float(parts[2])
            direction = parts[3]
        else:
            raise ValueError(self.tr("Invalid bearing format."))
        decimal_degrees = d + (m / 60.0) + (s / 3600.0)
        if 'S' in direction:
            decimal_degrees = 180 - decimal_degrees
        if 'W' in direction:
            decimal_degrees = 360 - decimal_degrees
        return decimal_degrees

    def convert_decimal_to_rumo(self, decimal_degrees):
        if decimal_degrees < 90:
            direction = 'NE'
        elif decimal_degrees < 180:
            direction = 'SE'
            decimal_degrees = 180 - decimal_degrees
        elif decimal_degrees < 270:
            direction = 'SW'
            decimal_degrees = decimal_degrees - 180
        else:
            direction = 'NW'
            decimal_degrees = 360 - decimal_degrees
        degrees = int(decimal_degrees)
        minutes_full = (decimal_degrees - degrees) * 60
        minutes = int(minutes_full)
        seconds = round((minutes_full - minutes) * 60, 3)
        if seconds == 60.000:
            seconds = 0.000
            minutes += 1
        if minutes == 60:
            minutes = 0
            degrees += 1
        return f"{degrees:02d}-{minutes:02d}-{seconds:06.3f}-{direction}"

    def format_dms(self, dms, sep='.'):
        parts = dms.split('-')
        degrees = int(parts[0])
        minutes = int(parts[1])
        seconds = round(float(parts[2].replace(',', '.')), 3)
        if seconds == int(seconds):
            seconds = int(seconds)
            return f"{degrees}°{minutes:02d}'{seconds:02d}\"".replace('.', sep)
        else:
            return f"{degrees}°{minutes:02d}'{seconds:06.3f}\"".replace('.', sep)

    def show_info(self):
        info_text = (
            self.tr("In this plugin, the Angle field accepts values in the following format: ") +
            self.tr("AZIMUTH: such as 80-00-00 or similar (without decimals unless specified). Examples: ") +
            self.tr("80 -> 80-00-00 | 80-00 -> 80-00-00 | 80-00-00.00 -> 80-00-00.00. ") +
            self.tr("BEARING: such as 80-00-00-NE (with directions NE, NW, SE, SW). Examples: ") +
            self.tr("80-NE -> 80-00-00-NE | 80-00-NE -> 80-00-00-NE | 80-00-00.00-NE -> 80-00-00.00-NE | ") +
            self.tr("80-45-NE -> 80-45-00-NE | 80-45-38.00-NE -> 80-45-38.00-NE. ") +
            self.tr("Directions: can be uppercase or lowercase; extra text is not accepted. ") +
            self.tr("Decimals: both Angle and Distance accept commas or dots as separators. ") +
            self.tr("Note: Vertex and Adjacency fields are optional and can be left blank.")
        )
        QMessageBox.information(self, self.tr('Information'), info_text)

    def parse_angle(self, angle_str):
        original_angle = angle_str
        if ',' in angle_str:
            sep = ','
        elif '.' in angle_str:
            sep = '.'
        else:
            sep = None
        parts = angle_str.split('-')
        if len(parts) >= 2 and parts[-1].upper() in ['NE', 'NW', 'SE', 'SW']:
            direction = parts[-1].upper()
            numeric_parts = parts[:-1]
            if len(numeric_parts) == 1:
                degrees = numeric_parts[0]
                minutes = '00'
                seconds = '00'
                if sep:
                    seconds += sep + '000'
            elif len(numeric_parts) == 2:
                degrees = numeric_parts[0]
                minutes = numeric_parts[1]
                seconds = '00'
                if sep:
                    seconds += sep + '000'
            elif len(numeric_parts) == 3:
                degrees = numeric_parts[0]
                minutes = numeric_parts[1]
                seconds = numeric_parts[2]
            else:
                raise ValueError("Invalid rumo format")
            try:
                int(degrees)
                int(minutes)
                if seconds:
                    if sep:
                        float(seconds.replace(sep, '.'))
                    else:
                        float(seconds)
            except ValueError:
                raise ValueError("Invalid numeric values in angle")
            return 'rumo', degrees, minutes, seconds, direction, sep
        else:
            if len(parts) == 1:
                degrees = parts[0]
                minutes = '00'
                seconds = '00'
                if sep:
                    seconds += sep + '000'
            elif len(parts) == 2:
                degrees = parts[0]
                minutes = parts[1]
                seconds = '00'
                if sep:
                    seconds += sep + '000'
            elif len(parts) == 3:
                degrees = parts[0]
                minutes = parts[1]
                seconds = parts[2]
            else:
                raise ValueError("Invalid azimute format")
            try:
                int(degrees)
                int(minutes)
                if seconds:
                    if sep:
                        float(seconds.replace(sep, '.'))
                    else:
                        float(seconds)
            except ValueError:
                raise ValueError("Invalid numeric values in angle")
            return 'azimute', degrees, minutes, seconds, sep

    def show_message(self, message):
        QMessageBox.information(self, self.tr('Information'), message)

    def process_data(self):
        output_shapefile_path = self.output_shapefile_edit.text()
        initial_point_text = self.initial_point_edit.text()
        if not initial_point_text:
            self.show_message(self.tr('Initial coordinate is required.'))
            self.show_info()
            return
        try:
            x, y = map(float, initial_point_text.split(','))
            initial_point = QgsPointXY(x, y)
        except ValueError:
            self.show_message(self.tr('Invalid format for initial coordinate.'))
            self.show_info()
            return
        distances_azimuths = []
        for row in range(self.table.rowCount()):
            vertex_item = self.table.item(row, 0)
            azimuth_item = self.table.item(row, 1)
            distance_item = self.table.item(row, 2)
            adjacency_item = self.table.item(row, 3)
            if not azimuth_item or not distance_item:
                continue
            try:
                azimuth_dms = azimuth_item.text().replace(',', '.')
                if any(x in azimuth_dms.upper() for x in ['N', 'S', 'E', 'W']):
                    azimuth = self.convert_rumo_to_decimal(azimuth_dms)
                else:
                    azimuth = self.convert_dms_to_decimal(azimuth_dms)
                distance = float(distance_item.text().replace(',', '.'))
                vertex = vertex_item.text() if vertex_item else ''
                adjacency = adjacency_item.text() if adjacency_item else ''
                distances_azimuths.append((vertex, azimuth, round(distance, 10), adjacency, azimuth_item.text()))
            except ValueError:
                err_template = self.tr("Invalid data in row %1.")
                err_text = err_template.replace("%1", str(row + 1))
                self.show_message(err_text)
                self.show_info()
                return
        if not distances_azimuths:
            self.show_message(self.tr('No valid azimuth and distance provided.'))
            self.show_info()
            return
        points = self.calculate_points(initial_point, distances_azimuths)
        self.create_shapefile(output_shapefile_path, points, distances_azimuths)

    def calculate_points(self, initial_point, distance_azimuths):
        points = [initial_point]
        for vertex, azimuth, distance, adjacency, azimuth_dms in distance_azimuths:
            last_point = points[-1]
            azimuth_rad = math.radians(azimuth)
            dx = distance * math.sin(azimuth_rad)
            dy = distance * math.cos(azimuth_rad)
            new_point = QgsPointXY(last_point.x() + dx, last_point.y() + dy)
            points.append(new_point)
        return points

    def create_shapefile(self, shapefile_path, points, distances_azimuths):
        fields = QgsFields()
        fields.append(QgsField(self.tr('ID'), QVariant.Double, 'numeric', 10, 0))
        fields.append(QgsField(self.tr('Vertex'), QVariant.String))
        fields.append(QgsField(self.tr('Angle'), QVariant.String))
        fields.append(QgsField(self.tr('Distance'), QVariant.Double, 'numeric', 20, 3))
        fields.append(QgsField(self.tr('Adjacency'), QVariant.String))

        crs = QgsProject.instance().crs()
        if shapefile_path and shapefile_path != self.tr('Temporary Layer'):
            if shapefile_path.lower().endswith('.shp'):
                driver_name = 'ESRI Shapefile'
            elif shapefile_path.lower().endswith('.gpkg'):
                driver_name = 'GPKG'
            else:
                driver_name = 'ESRI Shapefile'
            writer = QgsVectorFileWriter(
                shapefile_path, 'UTF-8', fields,
                QgsWkbTypes.LineString, crs, driver_name
            )
            if writer.hasError() != QgsVectorFileWriter.NoError:
                self.show_message(self.tr(f'Error creating file: {writer.errorMessage()}'))
                self.show_info()
                return
            del writer
            layer = QgsVectorLayer(shapefile_path, os.path.basename(shapefile_path), 'ogr')
        else:
            layer = QgsVectorLayer(
                f'LineString?crs={crs.authid()}',
                self.tr('Output Lines'),
                'memory'
            )
            pr = layer.dataProvider()
            pr.addAttributes(fields)
            layer.updateFields()

        for i in range(len(points) - 1):
            feature = QgsFeature()
            feature.setGeometry(QgsGeometry.fromPolylineXY([points[i], points[i + 1]]))
            vertex, azimuth, distance, adjacency, azimuth_dms = distances_azimuths[i]
            try:
                angle_type, deg, min, sec, *extra = self.parse_angle(azimuth_dms)
                if angle_type == 'rumo':
                    direction = extra[0]
                    sep = extra[1]
                    if sep and sep in sec:
                        sec_parts = sec.split(sep)
                        sec_int = sec_parts[0].zfill(2)
                        sec_dec = sec_parts[1] if len(sec_parts) > 1 else '000'
                        sec_formatted = f"{sec_int}{sep}{sec_dec}"
                    else:
                        sec_formatted = sec.zfill(2)
                    angle_formatted = f"{deg.zfill(2)}°{min.zfill(2)}'{sec_formatted}\"{direction}"
                else:
                    sep = extra[0]
                    if sep and sep in sec:
                        sec_parts = sec.split(sep)
                        sec_int = sec_parts[0].zfill(2)
                        sec_dec = sec_parts[1] if len(sec_parts) > 1 else '000'
                        sec_formatted = f"{sec_int}{sep}{sec_dec}"
                    else:
                        sec_formatted = sec.zfill(2)
                    angle_formatted = f"{deg.zfill(2)}°{min.zfill(2)}'{sec_formatted}\""
            except ValueError as e:
                self.show_message(self.tr(f"Invalid angle format in row {i+1}: {e}"))
                self.show_info()
                return
            attributes = [i + 1, vertex, angle_formatted, round(distance, 3), adjacency]
            feature.setAttributes(attributes)
            pr.addFeature(feature)

        layer.updateExtents()
        QgsProject.instance().addMapLayer(layer)
        if shapefile_path and shapefile_path != self.tr('Temporary Layer'):
            self.show_message(self.tr(f'File created at {shapefile_path}'))
        else:
            self.show_message(self.tr('Temporary layer created.'))

class AzimuthToolPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self.toolbar = None
        self.plugin_dir = os.path.dirname(__file__)
        self.translator = QTranslator()
        settings = QSettings()
        locale = settings.value("locale/userLocale", QLocale.system().name()).split('_')[0]
        locale_path = os.path.join(self.plugin_dir, 'i18n', f'azimuth_tool_{locale}.qm')
        if os.path.exists(locale_path):
            self.translator.load(f'azimuth_tool_{locale}.qm', os.path.join(self.plugin_dir, 'i18n'))
            QgsApplication.instance().installTranslator(self.translator)
        else:
            fallback_locale_path = os.path.join(self.plugin_dir, 'i18n', 'azimuth_tool_en.qm')
            if os.path.exists(fallback_locale_path):
                self.translator.load('azimuth_tool_en.qm', os.path.join(self.plugin_dir, 'i18n'))
                QgsApplication.instance().installTranslator(self.translator)

    def tr(self, message):
        return QCoreApplication.translate('AzimuthToolDialog', message)

    def initGui(self):
        icon_path = os.path.join(os.path.dirname(__file__), 'icon.png')
        self.toolbar = QToolBar(self.tr('Azimuth Tool'))
        self.iface.addToolBar(self.toolbar)
        self.add_action(icon_path, self.tr('Azimuth Tool'), self.run, parent=self.toolbar)

    def add_action(self, icon_path, text, callback, parent=None):
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        parent.addAction(action)
        self.action = action

    def unload(self):
        if self.toolbar:
            self.iface.mainWindow().removeToolBar(self.toolbar)
        self.iface.removePluginMenu(self.tr('&Azimuth Tool'), self.action)

    def run(self):
        if not self.dialog:
            self.dialog = AzimuthToolDialog()
        self.dialog.show()