# -*- coding: utf-8 -*-
"""
/***************************************************************************
 ERS
                                 A QGIS plugin
 This plugin determines calculated polluant concentrations around sensible sites's perimeters
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2023-05-24
        git sha              : $Format:%H$
        copyright            : (C) 2023 by Truong Anh Huy LE
        email                : huymop.lee@gmail.com
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
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import QIcon, QColor
from qgis.PyQt.QtWidgets import QAction, QFileDialog, QMessageBox
import os
from qgis.core import *
from qgis.gui import *
from qgis.utils import iface
import processing
import tempfile
import numpy as np
from numpy import genfromtxt
import pandas as pd
import openpyxl
from osgeo import gdal, gdal_array
from openpyxl import load_workbook, Workbook
from openpyxl.utils.dataframe import dataframe_to_rows

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .ERS_dialog import ERSDialog
import os.path


class ERS:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'ERS_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&ERS')

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('ERS', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToVectorMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/ERS/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'ERS'),
            callback=self.run,
            parent=self.iface.mainWindow())

        # will be set False in run()
        self.first_start = True


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginVectorMenu(
                self.tr(u'&ERS'),
                action)
            self.iface.removeToolBarIcon(action)

    def select_aria_layer(self):
        filename, _filter = QFileDialog.getSaveFileName(
            self.dlg, "Select output file ", "", '*.shp')
        self.dlg.lineEdit.setText(filename)

    def select_output_layer(self):
        filename, _filter = QFileDialog.getSaveFileName(
            self.dlg, "Select output file ", "", '*.xlsx')
        self.dlg.lineEdit_2.setText(filename)


    def run(self):
        """Run method that performs all the real work"""

        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        if self.first_start == True:
            self.first_start = False
            self.dlg = ERSDialog()
            self.dlg.pushButton.clicked.connect(self.select_aria_layer)
            self.dlg.pushButton_2.clicked.connect(self.select_output_layer)
        layers = QgsProject.instance().layerTreeRoot().children()
        self.dlg.comboBox.clear()
        self.dlg.comboBox.addItems([layer.name() for layer in layers])

        # show the dialog
        self.dlg.show()
        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:

            #Select sensible site layer
            SelectedLayerIndex = self.dlg.comboBox.currentIndex()
            site_layer = layers[SelectedLayerIndex].layer()
            site_path = site_layer.dataProvider().dataSourceUri()

            #Select ARIA Impact shapefile folder
            shapefile = self.dlg.lineEdit.text()
            shapefolder = os.path.dirname(shapefile)

            #Read output file
            exit_file = self.dlg.lineEdit_2.text()
            exit_path = os.path.dirname(exit_file)

            #Determine pollutant concentrations at sensible sites
            data = []
            #Read shapefile
            shapeList = []
            name = []
            for root,folder, files in os.walk(shapefolder):
                for file in files:
                    if file.endswith('.shp'):
                        fullname = os.path.join(root, file)
                        name.append(file)
                        shapeList.append(fullname)

            #Shorten file's name
            for i in range(0, len(shapeList)):
                separator = '_R_'
                separator_index = name[i].index(separator)
                name[i] = name[i][separator_index + len(separator):]
                separator1 = '.'
                separator_index1 = name[i].index(separator1)
                name[i] = name[i][:separator_index1]

            #Join by location site layer and ARIA Impact layer
            temp_file_path = tempfile.NamedTemporaryFile(suffix = '.shp').name
            processing.run('native:joinattributesbylocation', {'DISCARD_NONMATCHING' : False,
                'INPUT' : site_path, 'JOIN' : shapeList[0], 'JOIN_FIELDS' : ['CONCAN'], 'METHOD' : 2,
                'OUTPUT' : temp_file_path, 'PREDICATE' : [0], 'PREFIX' : name[0]})

            exit = temp_file_path
            #Continue to join the rest of shapefolder
            for i in range(1, len(shapeList)):
                input1 = exit
                input2 = shapeList[i]
                exit = tempfile.NamedTemporaryFile(suffix = '.shp').name
                processing.run('native:joinattributesbylocation', {'DISCARD_NONMATCHING' : False,
                    'INPUT' : input1, 'JOIN' : input2, 'JOIN_FIELDS' : ['CONCAN'], 'METHOD' : 2,
                    'OUTPUT' : exit, 'PREDICATE' : [0], 'PREFIX' : name[i]})

            #Define column name
            column = ['numero', 'PM10_ABRCO', 'PM2_5_ABRC', 'NO2CONCAN', "_1_3_butad", "benzo_a_py", "ARSENICCON", "CHROMIUMCO", "NICKELCONC",
            "benzeneCON", "acenaphthe", "acenaphthy", "anthracene", "benzo_a_an", "benzo_b_fl", "benzo_k_fl", "benzo_ghi_", "chryseneCO", "dibenzo_ah",
            "fluoreneCO", "fluoranthe", "indeno_1_2", "phenanthre", "pyreneCONC", "benzo_j_fl"]


            #Create dataframe
            layer = QgsVectorLayer(exit, '', 'ogr')
            pv = layer.dataProvider()
            fields = layer.fields()
            data = [[] for i in range(25)]
            #Retrieve concentrations
            for f in layer.getFeatures():
                for u in range(25):
                    data[u].append(f[column[u]])
            #Dataframe
            df = pd.DataFrame(data)
            df = df.transpose()
            df.columns = column
            df.sort_values(by = ['numero'], inplace = True)
            df = df.transpose()

            #Write data to excel output file
            writer = pd.ExcelWriter(exit_file, engine = 'openpyxl')
            df.to_excel(writer, header = False, index = True)
            writer.save()
            writer.close()

            #Show message after running code
            self.iface.messageBar().pushMessage( "Success", "Output file written at "+ exit_file,level = Qgis.Success, duration = 3)

