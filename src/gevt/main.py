# -*- coding: utf-8 -*-
"""
Created on Mon Sep 24 21:50:38 2018

@author: Sébastien Weber
"""
import os
from pathlib import Path
import codecs

from gevt.gui_utils import select_file, FilterProxyDayTypeCustom, MyMainWindow
from gevt.tasks import TaskModel, TaskWidget
from gevt.timeline import TimeLineView, TimeLineModel
from gevt.utils import get_set_local_dir, getLineInfo, import_points_geojson
from gevt.volunteers import VolunteerModel, VolunteerWidget

path_here = Path(__file__)


from dateutil.parser import parse
import csv
from qtpy import QtWidgets, QtCore, QtGui
from qtpy.QtCore import Slot
from pymodaq_gui.utils import DockArea, Dock

from pymodaq_gui.parameter import ParameterTree, Parameter
import tables
import numpy as np
import datetime
from pathlib import Path

import logging


local_path = get_set_local_dir('gevt_dir')
now = datetime.datetime.now()
log_path = os.path.join(local_path,'logging')
if not os.path.isdir(log_path):
    os.makedirs(log_path)

for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)
logging.basicConfig(filename=os.path.join(log_path, 'gevt_{}.log'.format(now.strftime('%Y%m%d_%H_%M_%S'))), level=logging.DEBUG)


class GeVT(QtCore.QObject):
    """
    GeB: Gestion of volunteers user interface
    """


    def __init__(self,mainwindow):
        super(GeVT, self).__init__()
        cwd = os.getcwd()
        params = [{'title': 'Event Name:', 'name': 'event_name', 'type': 'str' , 'value': 'Mon_raid'},
                  {'title': 'Event Place:', 'name': 'event_place', 'type': 'str', 'value': 'Chez ouam'},
                  {'title': 'Event Start Date:', 'name': 'event_day', 'type': 'date'},
                  {'title': 'Ndays:', 'name': 'event_ndays', 'type': 'int', 'min':1, 'tooltip': 'Event duration in number of days'},
                  {'title': 'Save directory:', 'name': 'event_save_dir', 'type': 'browsepath', 'filetype': False, 'value': cwd},
        ]
        self.gev_settings = Parameter.create(name='gev_settings', type='group', children=params)


        self.mainwindow = mainwindow
        self.area = DockArea()
        self.mainwindow.setCentralWidget(self.area)

        self.mainwindow.closing.connect(self.do_stuff_before_closing)
        self.h5file = None

        res=self.show_dialog()
        if res:
            self.load_file()
        else:
            self.new_file()

        self.setup_ui()

    def update_status(self, txt):
        logging.info(txt)


    def show_dialog(self):
        dialog = QtWidgets.QMessageBox()
        dialog.setText("Welcome to GeVT: tasks and volunteers manager!")
        dialog.setInformativeText("Do you want to create a new file or load an existing one?");
        dialog.addButton('New File',QtWidgets.QMessageBox.AcceptRole)
        dialog.addButton('Load File',QtWidgets.QMessageBox.RejectRole)


        res = dialog.exec()
        return res

    def do_stuff_before_closing(self,event):
        if self.h5file.isopen:
            self.h5file.flush()
            self.h5file.close()
        event.setAccepted(True)

    def quit(self):
        if self.h5file.isopen:
            self.h5file.close()

        self.mainwindow.close()


    def define_models(self):
        self.volunteer_model = VolunteerModel(self.h5file, self.gev_settings['event_ndays'])
        self.volunteer_sortproxy = QtCore.QSortFilterProxyModel()
        self.volunteer_sortproxy.setSourceModel(self.volunteer_model)
        self.volunteer_view.setModel(self.volunteer_sortproxy)
        self.volunteer_view.setSortingEnabled(True)

        self.task_model = TaskModel(self.h5file)
        self.proxymodel = FilterProxyDayTypeCustom()
        self.proxymodel.setSourceModel(self.task_model)
        self.task_view.setModel(self.proxymodel)
        self.task_view.setSortingEnabled(True)

        self.update_time_line_model()

        self.volunteer_view.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        self.task_view.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        self.timeline_needed.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.timeline_filled.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.timeline_vol.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)

        self.volunteer_view.index_changed_signal.connect(self.update_vol_label)

        self.volunteer_model.update_signal.connect(self.timeline_model_needed.update)
        self.volunteer_model.update_signal.connect(self.timeline_model_filled.update)
        self.volunteer_model.update_signal.connect(self.timeline_model_vol.update)
        self.task_model.update_signal.connect(self.update_time_line_model)
        self.task_model.update_signal.connect(self.update_time_line_model)
        self.task_model.update_signal.connect(self.update_time_line_model)

    def update_time_line_model(self):
        self.timeline_model_needed = TimeLineModel(self.h5file, view_type='N_needed')
        self.timeline_model_filled = TimeLineModel(self.h5file, view_type='N_filled')
        if self.volunteer_table.nrows != 0:
            if self.volunteer_view.currentIndex().isValid():
                index_model_row = self.volunteer_view.currentIndex().model().mapToSource(self.volunteer_view.currentIndex()).row()
                self.vol_name=self.volunteer_table[index_model_row]['name'].decode()
            else:
                self.vol_name = self.volunteer_table[0]['name'].decode()
        else:
            self.vol_name = ''
        self.timeline_model_vol = TimeLineModel(self.h5file, view_type=self.vol_name)


        self.timeline_needed.setModel(self.timeline_model_needed)
        self.timeline_filled.setModel(self.timeline_model_filled)
        self.timeline_vol.setModel(self.timeline_model_vol)

    def setup_ui(self):

        self.menubar=self.mainwindow.menuBar()
        self.create_menu(self.menubar)


        self.toolbar=QtWidgets.QToolBar()
        self.create_toolbar()
        self.mainwindow.addToolBar(self.toolbar)

        dock_time_line=Dock('TimeLine',size=(500,100))
        dock_task=Dock('List of Tasks', size=(600, 400))
        dock_volunteer=Dock('List of Volunteers', size=(400, 400))
        dock_html = Dock('Html', size=(400, 400))

        self.volunteer_view= VolunteerWidget()
        self.volunteer_view.import_action.triggered.connect(self.import_volunteer_csv)
        self.volunteer_view.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.volunteer_view.horizontalHeader().setMinimumWidth(50)


        self.task_view = TaskWidget()
        self.task_view.import_action.triggered.connect(self.import_task_csv)
        self.task_view.import_action_geojson.triggered.connect(self.import_geojson)
        self.task_view.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.task_view.horizontalHeader().setMinimumWidth(50)
        self.timeline_needed = TimeLineView(task_view=self.task_view)
        self.timeline_filled = TimeLineView(task_view=self.task_view)
        self.timeline_vol = TimeLineView(task_view=self.task_view)

        self.define_models()



        layout=QtWidgets.QHBoxLayout()
        filter_widget=QtWidgets.QWidget()

        self.day_edit=QtWidgets.QLineEdit()
        self.day_edit.setPlaceholderText("Day filter")

        self.type_edit=QtWidgets.QLineEdit()
        self.type_edit.setPlaceholderText("Type filter")

        self.remove_filters_pb=QtWidgets.QPushButton('Reset Filters from TimeLine')

        layout.addWidget(self.day_edit)
        layout.addWidget(self.type_edit)
        layout.addWidget(self.remove_filters_pb)
        layout.addStretch(1)
        filter_widget.setLayout(layout)





        dock_task.addWidget(filter_widget)
        dock_task.addWidget(self.task_view)
        dock_volunteer.addWidget(self.volunteer_view)

        dock_time_line.addWidget(QtWidgets.QLabel('Needed Volunteers during day'))
        dock_time_line.addWidget(self.timeline_needed  )
        dock_time_line.addWidget(QtWidgets.QLabel('Filled Volunteers during day'))
        dock_time_line.addWidget(self.timeline_filled)
        self.vol_name_label=QtWidgets.QLabel(self.vol_name)
        dock_time_line.addWidget(self.vol_name_label)
        dock_time_line.addWidget(self.timeline_vol)

        #self.html=QtWebEngineWidgets.QWebEngineView()
        #
        # self.html.setHtml('temp.html')
        # self.html.show()
        #dock_html.addWidget(self.html)

        self.area.addDock(dock_time_line, 'top')
        self.area.addDock(dock_task,'bottom',dock_time_line)
        self.area.addDock(dock_volunteer,'right',dock_time_line)
        #self.area.addDock(dock_html,'below',dock_task)
        self.day_edit.textChanged.connect(self.proxymodel.setDayFilter)
        self.type_edit.textChanged.connect(self.proxymodel.setTypeFilter)
        self.remove_filters_pb.clicked.connect(lambda: self.proxymodel.setTimeStampFilter(None)) #timestamp will be set to None and will be rendered ineficient


    Slot(QtCore.QModelIndex)
    def update_vol_label(self,index):
        try:
            row = index.model().mapToSource(index).row()
            name = self.volunteer_table[row]['name'].decode()
            self.vol_name_label.setText(name)
            self.timeline_model_vol.update_view_type(name)
        except Exception as e:
            self.update_status(getLineInfo() + str(e))

    def show_log(self):
        import webbrowser
        webbrowser.open(logging.getLoggerClass().root.handlers[0].baseFilename)

    def create_menu(self,menubar):
        # %% create Settings menu
        file_menu = menubar.addMenu('File')
        file_menu.addAction('New file', self.new_file)
        file_menu.addAction('Load file', self.load_file)
        file_menu.addAction('Save', self.save_file)
        file_menu.addAction('Save as', self.save_file_as)
        file_menu.addSeparator()
        file_menu.addAction('Show log file', self.show_log)
        file_menu.addSeparator()
        file_menu.addAction('Quit', self.quit)

        settings_menu = menubar.addMenu('Settings')
        settings_menu.addAction('Event configuration', self.update_event_settings)

        tools_menu = menubar.addMenu('Tools')
        tools_menu.addAction('Import Tasks from csv', self.import_task_csv)
        tools_menu.addAction('Import Volunteers from csv', self.import_volunteer_csv)
        tools_menu.addSeparator()
        tools_menu.addAction('Geojson to csv', self.convert_geojson)


    def get_task_description(self):
        return {'name': tables.StringCol(itemsize=2048, shape=(), dflt=b'', pos=3),
             'day': tables.Time32Col(shape=(), dflt=0, pos=1),
             'idnumber': tables.Int64Col(shape=(), dflt=0, pos=0),
             'task_type': tables.EnumCol(enum=tables.Enum({'welcoming': 0, 'balisage': 1, 'logistics': 2, 'security': 3, 'race': 4, 'other': 5, 'unknown': 6, 'raid':7, 'trail':8, 'canoe':9, 'CO':10, 'VTT':11, 'rando':12}), dflt='welcoming', base=tables.Int32Atom(shape=(), dflt=0), shape=(), pos=2),
             'time_start': tables.Time32Col(shape=(), dflt=0, pos=4),
             'time_end': tables.Time32Col(shape=(), dflt=0, pos=5),
             'N_needed': tables.Int8Col(shape=(), dflt=0, pos=6),
             'N_filled': tables.Int8Col(shape=(), dflt=0, pos=7),
             'remarqs': tables.StringCol(itemsize=2048, shape=(), dflt=b'', pos=8),
             'stuff_needed': tables.StringCol(itemsize=1024, shape=(), dflt=b'', pos=9),
             'affected_volunteers': tables.Int64Col(shape=(50,), dflt=-1, pos=10),
             'responsable': tables.Int16Col(shape=(), dflt=-1, pos=11),
             'localisation': tables.StringCol(itemsize=128, shape=(), dflt=b'', pos=12),}

    def get_volunteer_description(self,Ndays):
        return {'idnumber': tables.Int64Col(shape=(), dflt=0, pos=0),
             'name': tables.StringCol(itemsize=128, shape=(), dflt=b'', pos=1),
             'remarqs': tables.StringCol(itemsize=2048, shape=(), dflt=b'', pos=2),
             'affected_tasks': tables.Int64Col(shape=(50,), dflt=-1, pos=3),
             'telephone': tables.StringCol(itemsize=128, shape=(), dflt=b'', pos=4),
             'time_start': tables.Time32Col(shape=(Ndays,), dflt=0, pos=5),
             'time_end': tables.Time32Col(shape=(Ndays,), dflt=0, pos=6),}


    def show_event_dialog(self):
        dialog = QtWidgets.QDialog()
        vlayout = QtWidgets.QVBoxLayout()
        self.settings_tree = ParameterTree()
        vlayout.addWidget(self.settings_tree, 10)
        self.settings_tree.setMinimumWidth(300)

        self.settings_tree.setParameters(self.gev_settings, showTop=True)
        dialog.setLayout(vlayout)

        buttonBox = QtWidgets.QDialogButtonBox(parent=dialog);
        buttonBox.addButton('Apply', buttonBox.AcceptRole)
        buttonBox.accepted.connect(dialog.accept)


        vlayout.addWidget(buttonBox)
        dialog.setWindowTitle('Fill in information about this Event')
        res = dialog.exec()

        if res == dialog.Accepted:
            # save managers parameters in a xml file
            return self.gev_settings
        else:
            return None

    def update_event_settings(self):
        res= self.show_event_dialog()
        if res is not None:
            event_save_dir = self.gev_settings.child(('event_save_dir')).value()
            event_name = self.gev_settings.child(('event_name')).value()
            event_place = self.gev_settings.child(('event_place')).value()
            event_day = QtCore.QDateTime(
                self.gev_settings.child(('event_day')).value()).toSecsSinceEpoch()  # stored as seconds from Epoch
            Ndays = self.gev_settings.child(('event_ndays')).value()

            self.h5file.root._v_attrs['event_save_dir'] = event_save_dir
            self.h5file.root._v_attrs['event_name'] = event_name
            self.h5file.root._v_attrs['event_place'] = event_place
            self.h5file.root._v_attrs['event_day'] = event_day
            if self.h5file.root._v_attrs['Ndays'] != Ndays:
                self.h5file.root._v_attrs['Ndays'] = Ndays
                self.h5file.remove_node('/volunteers','volunteer_table')
                self.volunteer_table = self.h5file.create_table('/volunteers', 'volunteer_table', self.get_volunteer_description(Ndays), "List of volunteers")
                for row in self.task_table:
                    self.task_table.cols.N_filled[row.nrow] = 0
                    self.task_table.cols.affected_volunteers[row.nrow] = -1*np.ones((50,))
                self.define_models()



    def new_file(self):
        if self.h5file is not None:
            if self.h5file.isopen:
                self.h5file.close()

        res= self.show_event_dialog()
        if res is not None:
            event_save_dir = self.gev_settings.child(('event_save_dir')).value()
            event_place = self.gev_settings.child(('event_place')).value()
            event_name = self.gev_settings.child(('event_name')).value()
            event_day = QtCore.QDateTime(self.gev_settings.child(('event_day')).value()).toSecsSinceEpoch() #stored as seconds from Epoch
            Ndays = self.gev_settings.child(('event_ndays')).value()

            event_save_dir = Path(event_save_dir)


            self.h5file = tables.open_file(str(event_save_dir.joinpath(event_name+'.gev')), mode='w', title='List of Tasks and volunteers for '+
                                           event_name)
            self.h5file.root._v_attrs['event_save_dir'] = event_save_dir
            self.h5file.root._v_attrs['event_name'] = event_name
            self.h5file.root._v_attrs['event_place'] = event_place
            self.h5file.root._v_attrs['event_day'] = event_day
            self.h5file.root._v_attrs['Ndays'] = Ndays
            # %%
            task_group = self.h5file.create_group('/', 'tasks', 'Tasks related stuff')
            volunter_group = self.h5file.create_group('/', 'volunteers', 'Volunteers related stuff')

            self.task_table = self.h5file.create_table(task_group, 'tasks_table', self.get_task_description(), "List of tasks")
            self.volunteer_table = self.h5file.create_table(volunter_group, 'volunteer_table', self.get_volunteer_description(Ndays), "List of volunteers")

    def load_file(self):

        if self.h5file is not None:
            if self.h5file.isopen:
                self.h5file.close()
                
        file_path = select_file(start_path=f"{os.environ['HOMEPATH']}\\Documents",
                                save=False, ext='gev')
        if file_path != '':
            self.h5file = tables.open_file(str(file_path), mode='a', title='List of Tasks and volunteers for RTA 2018')
            self.task_table = self.h5file.get_node('/tasks/tasks_table')
            self.volunteer_table=self.h5file.get_node('/volunteers/volunteer_table')

            event_save_dir = self.h5file.root._v_attrs['event_save_dir']
            event_name = self.h5file.root._v_attrs['event_name']
            event_place = self.h5file.root._v_attrs['event_place']
            event_day = self.h5file.root._v_attrs['event_day']
            Ndays = self.h5file.root._v_attrs['Ndays'] #stored as seconds from Epoch

            self.gev_settings.child(('event_save_dir')).setValue(event_save_dir)
            self.gev_settings.child(('event_name')).setValue(event_name)
            self.gev_settings.child(('event_place')).setValue(event_place)
            day=QtCore.QDateTime()
            day.setSecsSinceEpoch(event_day)
            self.gev_settings.child(('event_day')).setValue(day.date())
            self.gev_settings.child(('event_ndays')).setValue(Ndays)

            if hasattr(self,'volunteer_view'): #this is the first step at initial load (before views are defined in init)
                self.define_models()

    def save_file(self):
        if self.h5file.isopen:
            self.h5file.flush()


    def save_file_as(self):
        try:
            fname = select_file(save=True, ext='gev')
            if fname != '':
                self.h5file.copy_file(str(fname))
        except Exception as e:
            self.update_status(getLineInfo() + str(e))

    def convert_geojson(self):

        file_path = select_file(save=False, ext=['geojson'])
        if file_path != '':
            file_path = Path(file_path)
            path = file_path.parent
            filename = file_path.stem

            points = import_points_geojson(str(file_path))

            header = ['Type', 'Nom', 'Nneeded', 'day', 'start', 'stop', 'remarks',
                      'stuff', 'localisation']

            with codecs.open(str(path.joinpath(f'{filename}.csv')), 'wb', 'utf-8') as csvfile:
                writer = csv.writer(csvfile, delimiter=',')
                writer.writerow(header)
                d = QtCore.QDateTime()
                day = d.fromSecsSinceEpoch(self.h5file.root._v_attrs['event_day']).date().toString('dd/MM/yy')

                for point in points:
                    if 'S' in point:
                        pt_type = 'security'
                    else:
                        pt_type = 'logistics'
                    row = [pt_type, point, 1, day, '08:00', '18:00', '', '', points[point]]
                    writer.writerow(row)


    def import_geojson(self):
        try:
            file_path = select_file(save=False, ext=['geojson'])
            if file_path != '':

                task = self.task_table.row
                ids = self.task_table.col('idnumber')
                if ids.size != 0:
                    ind = max(self.task_table.col('idnumber'))
                else:
                    ind = -1

                day_int, result = QtWidgets.QInputDialog.getInt(None,
                                                                'Which day of the event should these tasks applied?',
                                              'Pick an day', value=1, min=1, max=self.h5file.root._v_attrs['Ndays'])
                if not result:
                    day_int = 1

                points = import_points_geojson(file_path)

                d = QtCore.QDateTime()
                day = d.fromSecsSinceEpoch(self.h5file.root._v_attrs['event_day']).date()
                day = day.addDays(day_int - 1)
                day = day.toString('dd/MM/yy')

                for point in points:
                    ind += 1


                    task['day'] = int(parse(day, dayfirst=True).timestamp())
                    task['name'] = point['name'].encode()
                    if 'S' in point['name']:
                        pt_type = 'security'
                    else:
                        pt_type = 'logistics'
                    task['task_type'] = self.task_table.get_enum('task_type')[pt_type]
                    task['idnumber'] = ind
                    task['time_start'] = task['day']
                    task['N_needed'] = 1
                    stop = '23h00'
                    task['time_end'] = int(parse(day + ' ' + stop, dayfirst=True).timestamp())
                    task['remarqs'] = point['description'].encode()
                    task['stuff_needed'] = ''.encode()
                    task['responsable'] = -1
                    task['localisation'] = point['coordinates'].encode()
                    task.append()

                self.task_table.flush()
                self.define_models()
                self.proxymodel = FilterProxyDayTypeCustom()
                self.proxymodel.setSourceModel(self.task_model)
                self.task_view.setModel(self.proxymodel)
                self.task_view.horizontalHeader().setMinimumWidth(50)
                self.task_view.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Interactive)

        except Exception as e:
            self.update_status(getLineInfo() + str(e))

    def import_task_csv(self):
        try:
            file_path = select_file(save=False, ext=['csv', 'txt'])
            if file_path != '':
                task = self.task_table.row
                ids = self.task_table.col('idnumber')
                if ids.size != 0:
                    ind = max(self.task_table.col('idnumber'))
                else:
                    ind = -1
                with codecs.open(str(file_path), 'rb', 'utf-8') as csvfile:
                    reader = csv.reader(csvfile)
                    # reader = csv.reader(tsvfile, dialect='excel-tab')
                    header = next(reader, None)
                    if len(header) != 9:
                        msgBox = QtWidgets.QMessageBox()
                        msgBox.setText(
                            "The number of columns in file ({:}) is not adequate with the definition of tasks (9 columns)".format(len(header)))
                        msgBox.exec()
                        return

                    for row in reader:
                        if row[0].lower() in self.task_table.get_enum('task_type'):
                            ind += 1
                            if row[3] == '':
                                d = QtCore.QDateTime()
                                row[3] = d.fromSecsSinceEpoch(self.h5file.root._v_attrs['event_day']).date().toString('dd/MM/yy')

                            task['day'] = int(parse(row[3], dayfirst=True).timestamp())
                            task['name'] = row[1].encode()
                            if row[0] == '':
                                row[0] = 'unknown'
                            task['task_type'] = self.task_table.get_enum('task_type')[row[0].lower()]
                            task['idnumber'] = ind
                            if row[4] == '':
                                row[4] = '6h00'
                            task['time_start'] = int(parse(row[3] + ' ' + row[4], dayfirst=True).timestamp())
                            if row[2] == '':
                                row[2] = 1
                            task['N_needed'] = int(row[2])
                            if row[5] == ' ':
                                row[5] = '23h59'
                            task['time_end'] = int(parse(row[3] + ' ' + row[5], dayfirst=True).timestamp())
                            task['remarqs'] = row[6].encode()
                            task['stuff_needed'] = row[7].encode()
                            task['responsable'] = -1
                            task['localisation'] = row[8].encode()
                            task.append()
                    self.task_table.flush()

                if QtCore.QDateTime(self.gev_settings.child(('event_day')).value()).toSecsSinceEpoch() != min(self.task_table[:]['day']):
                    msgBox = QtWidgets.QMessageBox()
                    msgBox.setText("The day filled in the table is not compatible with the starting date of the event")
                    msgBox.exec()
                    self.task_table.remove_rows(0, self.task_table.nrows, 1)
                    return

                self.define_models()
                self.proxymodel = FilterProxyDayTypeCustom()
                self.proxymodel.setSourceModel(self.task_model)
                self.task_view.setModel(self.proxymodel)
                self.task_view.horizontalHeader().setMinimumWidth(50)
                self.task_view.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Interactive)

        except Exception as e:
            self.update_status(getLineInfo() + str(e))

    def import_volunteer_csv(self):
        try:
            file_path = select_file(save=False, ext=['csv', 'txt'])
            Ndays = self.gev_settings.child(('event_ndays')).value()
            if file_path != '':
                vol = self.volunteer_table.row
                ids = self.volunteer_table.col('idnumber')
                if ids.size != 0:
                    ind = max(self.volunteer_table.col('idnumber'))
                else:
                    ind = -1
                with codecs.open(str(file_path), 'rb', 'utf-8') as csvfile:  # data = codecs.open(..., "rb", "utf-8")
                    # reader = csv.reader(tsvfile, dialect='excel-tab')
                    reader = csv.reader(csvfile, dialect='excel', )
                    header_days = next(reader, None)
                    flag = True
                    if len(header_days) != 2 * Ndays + 3:
                        flag = False
                        msgBox = QtWidgets.QMessageBox()
                        msgBox.setText(
                            "The number of columns in file is not adequate with the number of days selected for the event")
                        msgBox.exec()

                    if int(parse(header_days[3] + ' ' + '00:00:00', dayfirst=True).timestamp()) != QtCore.QDateTime(
                            self.gev_settings.child(('event_day')).value()).toSecsSinceEpoch():
                        flag = False
                        msgBox = QtWidgets.QMessageBox()
                        msgBox.setText(
                            "The days filled in the table are not compatible with the starting date of the event")
                        msgBox.exec()

                    if not flag:
                        return

                    next(reader, None)
                    for row in reader:
                        if row[0] != "":
                            ind += 1
                            #print(row[0])
                            vol['name'] = row[0].encode()
                            vol['telephone'] = row[1].encode()
                            vol['remarqs'] = row[2].encode()
                            vol['time_start'] = [self.fill_in_time(header_days[ind], row[ind], time='start') for ind in
                                                 range(3, 2 * Ndays + 2, 2)]
                            vol['time_end'] = [self.fill_in_time(header_days[ind], row[ind], time='end') for ind in
                                               range(4, 2 * Ndays + 3, 2)]
                            vol['idnumber'] = ind
                            # print(vol['name'])
                            # print(vol['time_start'])
                            # print(vol['time_end'])
                            vol.append()
                self.volunteer_table.flush()

            self.define_models()
            self.volunteer_sortproxy = QtCore.QSortFilterProxyModel()
            self.volunteer_sortproxy.setSourceModel(self.volunteer_model)
            self.volunteer_view.setModel(self.volunteer_sortproxy)
            self.volunteer_view.setSortingEnabled(True)
            self.volunteer_view.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        except Exception as e:
            self.update_status(getLineInfo() + str(e))

    def fill_in_time(self, header_day, string, time='start'):
        if string.upper() == 'X':
            if time == 'start':
                return int(parse(header_day + ' ' + '00:00:00', dayfirst=True).timestamp())
            else:
                return int(parse(header_day + ' ' + '23:59:59', dayfirst=True).timestamp())
        elif string == '':
            return -1
        else:
            try:
                return int(parse(header_day + ' ' + string, dayfirst=True).timestamp())
            except:
                return -1
                # if time == 'start':
                #     return int(parse(header_day + ' ' + '00:00:00', dayfirst=True).timestamp())
                # else:
                #     return int(parse(header_day + ' ' + '23:59:59', dayfirst=True).timestamp())

    # %%

    def create_toolbar(self):
        iconload = QtGui.QIcon()
        iconload.addPixmap(QtGui.QPixmap(":/Icons/Icons/Open.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.loadaction = QtWidgets.QAction(iconload, "Load GeV file (.gev)", None)
        self.toolbar.addAction(self.loadaction)
        self.loadaction.triggered.connect(self.load_file)

        iconsave = QtGui.QIcon()
        iconsave.addPixmap(QtGui.QPixmap(":/Icons/Icons/Save_32.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.saveaction = QtWidgets.QAction(iconsave, "Save", None)
        self.toolbar.addAction(self.saveaction)
        self.saveaction.triggered.connect(self.save_file)

        iconsaveas = QtGui.QIcon()
        iconsaveas.addPixmap(QtGui.QPixmap(":/Icons/Icons/SaveAs_32.png"), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.saveasaction = QtWidgets.QAction(iconsaveas, "Save As", None)
        self.toolbar.addAction(self.saveasaction)
        self.saveasaction.triggered.connect(self.save_file_as)


def start_gevt():
    import sys
    from pymodaq_gui.utils.utils import mkQApp
    app = mkQApp('GeVT')

    win = MyMainWindow()
    prog = GeVT(win)
    win.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    start_gevt()


