# -*- coding: utf-8 -*-
"""
/***************************************************************************
 SpaceTracePlugin
                                 A QGIS plugin
 Draws the spacecraft's flight path over the Earth's surface
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2025-02-14
        git sha              : $Format:%H$
        copyright            : (C) 2025 by Yuriy Malyshev
        email                : yuaren@yandex.ru
***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import QgsVectorLayer, QgsProject
import os.path
from datetime import datetime, date, timedelta
import numpy as np
from pyorbital.orbital import Orbital
from pyorbital import astronomy

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .Space_trace_dialog import SpaceTracePluginDialog
# Import the orbital logic module which encapsulates file creation functions
from . import orbital_logic


class SpaceTracePlugin:
    """QGIS Plugin Implementation."""
    def __init__(self, iface):
        """
        Constructor for the plugin.

        :param iface: QGIS interface instance.
        """
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        # Initialize localization settings
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(self.plugin_dir, 'i18n', 'SpaceTracePlugin_{}.qm'.format(locale))
        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)
        # Initialize plugin attributes
        self.actions = []
        self.menu = self.tr(u'&Space trace')
        self.first_start = None

    def tr(self, message):
        """
        Translate a message using Qt translation API.

        :param message: The message to translate.
        :return: Translated message.
        """
        return QCoreApplication.translate('SpaceTracePlugin', message)

    def add_action(self, icon_path, text, callback, enabled_flag=True, add_to_menu=True,
                   add_to_toolbar=True, status_tip=None, whats_this=None, parent=None):
        """
        Add an action to the QGIS toolbar and menu.

        :param icon_path: Path to the icon.
        :param text: Text for the action.
        :param callback: Function to call when the action is triggered.
        :param enabled_flag: Whether the action is enabled.
        :param add_to_menu: Whether to add the action to the menu.
        :param add_to_toolbar: Whether to add the action to the toolbar.
        :param status_tip: Status tip for the action.
        :param whats_this: 'What's This' text for the action.
        :param parent: Parent widget.
        :return: The created QAction.
        """
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)
        if status_tip:
            action.setStatusTip(status_tip)
        if whats_this:
            action.setWhatsThis(whats_this)
        if add_to_toolbar:
            self.iface.addToolBarIcon(action)
        if add_to_menu:
            self.iface.addPluginToVectorMenu(self.menu, action)
        self.actions.append(action)
        return action

    def initGui(self):
        """Initialize the GUI by creating menu entries and toolbar icons."""
        icon_path = ':/plugins/Space_trace/icon.png'
        self.add_action(icon_path,
                        text=self.tr(u'Draw flight path lines'),
                        callback=self.run,
                        parent=self.iface.mainWindow())
        self.first_start = True

    def unload(self):
        """Remove the plugin menu items and icons from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginVectorMenu(self.tr(u'&Space trace'), action)
            self.iface.removeToolBarIcon(action)

    def run(self):
        """
        Main execution method for the plugin.

        Depending on whether an output file path is provided in the dialog,
        this function creates persistent shapefile layers on disk or temporary
        in-memory layers by delegating the file creation logic to the orbital_logic module.
        """
        if self.first_start:
            self.first_start = False
            self.dlg = SpaceTracePluginDialog()
        self.dlg.show()
        if not self.dlg.exec_():
            return  # User cancelled the dialog

        try:
            # Retrieve user inputs from the dialog
            sat_id_text = self.dlg.lineEditSatID.text().strip()
            if not sat_id_text:
                raise Exception("Please enter the satellite NORAD ID.")
            sat_id = int(sat_id_text)
            track_day = self.dlg.dateEdit.date().toPyDate()
            step_minutes = self.dlg.spinBoxStepMinutes.value()
            output_path = self.dlg.lineEditOutputPath.text().strip()
            add_layer = self.dlg.checkBoxAddLayer.isChecked()

            if output_path:
                # Persistent mode: Create shapefiles on disk using orbital_logic functions
                orbital_logic.create_persistent_orbital_track(sat_id, track_day, step_minutes, output_path)
                line_output_path = output_path.replace('.shp', '_line.shp')
                self.iface.messageBar().pushMessage("Success", "Shapefile created successfully", level=0)
                if add_layer:
                    # Load and add point layer to the project
                    point_layer_name = os.path.splitext(os.path.basename(output_path))[0]
                    point_layer = QgsVectorLayer(output_path, point_layer_name, "ogr")
                    if not point_layer.isValid():
                        self.iface.messageBar().pushMessage("Error", "Failed to load point layer", level=3)
                    else:
                        QgsProject.instance().addMapLayer(point_layer)
                    # Load and add line layer to the project
                    line_layer_name = os.path.splitext(os.path.basename(line_output_path))[0]
                    line_layer = QgsVectorLayer(line_output_path, line_layer_name, "ogr")
                    if not line_layer.isValid():
                        self.iface.messageBar().pushMessage("Error", "Failed to load line layer", level=3)
                    else:
                        QgsProject.instance().addMapLayer(line_layer)
            else:
                # Temporary mode: Create in-memory layers using orbital_logic functions
                point_layer, line_layer = orbital_logic.create_in_memory_orbital_layers(sat_id, track_day, step_minutes)
                if add_layer:
                    QgsProject.instance().addMapLayer(point_layer)
                    QgsProject.instance().addMapLayer(line_layer)
                self.iface.messageBar().pushMessage("Success", "Temporary layers created successfully", level=0)
        except Exception as e:
            self.iface.messageBar().pushMessage("Error", str(e), level=3)
