import codecs
import csv
import datetime
import logging
import os
import webbrowser
from pathlib import Path

import numpy as np
import tables
from PyQt5.QtCore import pyqtSignal
from pymodaq_gui.parameter import ParameterTree
from pyqtgraph.parametertree import Parameter
from qtpy import QtCore, QtWidgets
from yawrap import Doc

from gevt.list_picker import ListPicker
from gevt.utils import getLineInfo, odd_even
from gevt.gui_utils import select_file


class VolunteerModel(QtCore.QAbstractTableModel):
    update_signal = QtCore.Signal()

    def __init__(self, h5file=None, Ndays=1, list_ids=None):
        super(VolunteerModel, self).__init__()
        self.list_ids = list_ids
        self.Ndays = Ndays
        self.day_list = [QtCore.QDateTime().fromSecsSinceEpoch(h5file.root._v_attrs['event_day']).addDays(day) for day
                         in range(Ndays)]
        if h5file is None:
            raise Exception('No valid pytables file')
        elif type(h5file) == str or type(h5file) == Path:
            self.h5file = tables.open_file(str(h5file), mode='a', title='List of Tasks and volunteers for RTA 2018')
        elif type(h5file) == tables.File:
            self.h5file = h5file

    def update_status(self, txt):
        logging.info(txt)

    def close(self):
        try:
            self.h5file.close()
        except Exception as e:
            self.update_status(getLineInfo() + str(e))

    def rowCount(self, index):
        if self.list_ids is not None:
            return len(self.list_ids)
        else:
            self.volunteer_table = self.h5file.get_node('/volunteers/volunteer_table')
            return self.volunteer_table.nrows

    def columnCount(self, index):
        if self.list_ids is not None:
            return self.Ndays+2
        else:
            return self.Ndays+5


    def data(self, index=QtCore.QModelIndex(), role=QtCore.Qt.DisplayRole):
        self.volunteer_table = self.h5file.get_node('/volunteers/volunteer_table')
        if role == QtCore.Qt.DisplayRole:
            if self.list_ids is not None:
                vol_row = \
                self.volunteer_table.get_where_list("""(idnumber == {:})""".format(self.list_ids[index.row()]))[0]
                if index.column() == 1:
                    return self.volunteer_table[vol_row][index.column()].decode()
                elif index.column() == 0:  # idnumber
                    return int(self.volunteer_table[vol_row][index.column()])

                else:
                    ind_time = index.column() - 2
                    start = self.volunteer_table[self.list_ids[index.row()]]['time_start'][ind_time]
                    stop = self.volunteer_table[self.list_ids[index.row()]]['time_end'][ind_time]
                    if not (start == -1 or stop == -1):
                        s = datetime.datetime.fromtimestamp(start).strftime(
                            '%H:%M') + ' -> ' + datetime.datetime.fromtimestamp(stop).strftime('%H:%M')
                        return s
                    else:
                        return QtCore.QVariant()
            else:

                if index.column() == 1 or index.column() == 2 or index.column() == 4:  # name or remarqs or telephone
                    dat = self.volunteer_table[index.row()][index.column()]
                    return dat.decode()

                elif index.column() == 0: # idnumber
                    dat = self.volunteer_table[index.row()][index.column()]
                    return int(dat)

                elif index.column() == 3: #affected tasks
                    return str([int(val) for val in self.volunteer_table[index.row()]['affected_tasks'] if val != -1])

                else:
                    ind_time = index.column() - 5
                    start = self.volunteer_table[index.row()]['time_start'][ind_time]
                    stop = self.volunteer_table[index.row()]['time_end'][ind_time]
                    if not (start == -1 or stop == -1):
                        s = datetime.datetime.fromtimestamp(start).strftime(
                            '%H:%M') + ' -> ' + datetime.datetime.fromtimestamp(stop).strftime('%H:%M')
                        return s
                    else:
                        return QtCore.QVariant()
        else:
            return QtCore.QVariant()

    def headerData(self, section, orientation, role):
        try:
            self.volunteer_table = self.h5file.get_node('/volunteers/volunteer_table')
            if role == QtCore.Qt.DisplayRole:
                if orientation == QtCore.Qt.Horizontal:
                    if self.list_ids is not None:
                        if section <= 1:
                            return col_volunteer_header[section]
                        else:
                            try:
                                return 'Day {:02d}:'.format(section - 2)
                            except:
                                return QtCore.QVariant()
                    else:
                        if section <= 4:
                            return col_volunteer_header[section]
                        else:
                            try:
                                return 'Day {:02d}:'.format(section - 4)
                            except:
                                return QtCore.QVariant()
                else:
                    return QtCore.QVariant()
            else:
                return QtCore.QVariant()
        except tables.exceptions.ClosedFileError:
            return QtCore.QVariant()

    def edit_data(self, index):
        self.volunteer_table = self.h5file.get_node('/volunteers/volunteer_table')
        vol_id = index.sibling(index.row(), self.volunteer_table.colnames.index('idnumber')).data()
        vol_row = self.volunteer_table.get_where_list("""(idnumber == {:})""".format(vol_id))[0]
        mapper = VolunteerWidgetMapper(self.h5file, vol_row)
        res = mapper.show_dialog()
        if res is not None:
            self.vol_param_to_row(res, vol_row)

    def vol_param_to_row(self, param, row_index=None):
        self.volunteer_table = self.h5file.get_node('/volunteers/volunteer_table')
        try:

            row_data = dict()
            row_data['idnumber'] = int(param.child('volunteer_settings', 'id').value())
            row_data['name'] = param.child('volunteer_settings', 'name').value().encode()
            row_data['remarqs'] = param.child('volunteer_settings', 'remarqs').value().encode()
            row_data['telephone'] = param.child('volunteer_settings', 'telephone').value().encode()

            row_data['present'] = np.array(
                [par.child(('present')).value() for par in param.child('volunteer_settings', 'day_list').children()],
                dtype='bool')

            row_data['time_start'] = np.array([int(QtCore.QDateTime(self.day_list[ind].date(), par.child(
                ('time_start')).value()).toMSecsSinceEpoch() / 1000) if par.child(('present')).value() else -1 for
                                               ind, par in
                                               enumerate(param.child('volunteer_settings', 'day_list').children())],
                                              dtype='int32')
            row_data['time_end'] = np.array([int(QtCore.QDateTime(self.day_list[ind].date(), par.child(
                ('time_end')).value()).toMSecsSinceEpoch() / 1000) if par.child(('present')).value() else -1 for
                                             ind, par in
                                             enumerate(param.child('volunteer_settings', 'day_list').children())],
                                            dtype='int32')

            try:
                row_data['affected_tasks'] = self.volunteer_table[row_index]['affected_tasks']
            except:
                row_data['affected_tasks'] = np.ones((50,), dtype='int64') * (-1)

            if row_index is None:
                row_index = self.volunteer_table.nrows + 1
                row = self.volunteer_table.row
                for k in self.volunteer_table.colnames:
                    row[k] = row_data[k]
                row.append()
                self.volunteer_table.flush()


            else:

                dat = [tuple([row_data[k] for k in self.volunteer_table.colnames if k in row_data])]
                self.volunteer_table.modify_rows(start=row_index, stop=row_index + 1, step=1, rows=dat)
                index_ul = self.createIndex(row_index, 0)
                index_br = self.createIndex(row_index, 9)
                self.dataChanged.emit(index_ul, index_br, [QtCore.Qt.DisplayRole for ind in range(10)])
                self.volunteer_table.flush()

            self.update_signal.emit()


        except Exception as e:
            self.update_status(getLineInfo() + str(e))

    def remove_data(self,index,rows_ids):
        self.volunteer_table = self.h5file.get_node('/volunteers/volunteer_table')
        self.task_table = self.h5file.get_node('/tasks/tasks_table')
        msgBox=QtWidgets.QMessageBox()
        msgBox.setText("You are about to delete rows!")
        msgBox.setInformativeText("Are you sure you want to delete rows with ids: {:}".format([row[1] for row in rows_ids]))
        msgBox.setStandardButtons(QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel)
        msgBox.setDefaultButton(QtWidgets.QMessageBox.Cancel)
        res = msgBox.exec()

        if res==QtWidgets.QMessageBox.Ok:
            for row,id in rows_ids:
                if len([task for task in self.volunteer_table[row]['affected_tasks'] if task != -1]) == 0:
                    self.beginRemoveRows(index.parent(),row,row)
                    self.volunteer_table.remove_row(self.volunteer_table.get_where_list("""(idnumber == {:})""".format(id))[0])
                    self.endRemoveRows()
                else:
                    msgBox = QtWidgets.QMessageBox()
                    msgBox.setText("Volunteer with id: {:} is affected to tasks.".format(id))
                    msgBox.setInformativeText("Do you still want to remove him/her?")
                    msgBox.setStandardButtons(QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel)
                    msgBox.setDefaultButton(QtWidgets.QMessageBox.Cancel)
                    res = msgBox.exec()
                    if res == QtWidgets.QMessageBox.Ok:
                        self.remove_task(self.createIndex(row,0),select= False)
                        self.beginRemoveRows(index.parent(), row, row)
                        self.volunteer_table.remove_row(self.volunteer_table.get_where_list("""(idnumber == {:})""".format(id))[0])
                        self.endRemoveRows()
                self.update_signal.emit()


    def append_row(self,index):
        self.insertRows(self.rowCount(index),1,index.parent())
        index_ul = self.createIndex(index.row()+1, 0)
        index_br = self.createIndex(index.row()+1, 9)
        self.dataChanged.emit(index_ul, index_br, [QtCore.Qt.DisplayRole for ind in range(10)])
        self.update_signal.emit()


    def insertRows(self, row: int, count: int, parent):
        if row == 0:
            self.beginInsertRows(parent, row, row)
        else:
            self.beginInsertRows(parent,row-1,row-1)
        mapper = VolunteerWidgetMapper(self.h5file)
        res = mapper.show_dialog()
        if res is not None:
            self.vol_param_to_row(res)
        self.endInsertRows()

        return True

    def add_task(self, index):
        self.volunteer_table = self.h5file.get_node('/volunteers/volunteer_table')
        self.task_table = self.h5file.get_node('/tasks/tasks_table')
        vol_id = index.sibling(index.row(), self.volunteer_table.colnames.index('idnumber')).data()
        vol_row = self.volunteer_table.get_where_list("""(idnumber == {:})""".format(vol_id))[0]
        time_start = self.volunteer_table[vol_row]['time_start']
        time_end = self.volunteer_table[vol_row]['time_end']

        list = ListPicker(vol_row, time_start, time_end, "task", self.h5file)

        ids = list.pick_dialog()


        idvol = self.volunteer_table[vol_row]['idnumber']
        for task_id in ids:
            task_row = self.task_table.get_where_list("""(idnumber == {:})""".format(task_id))[0]

            for ind_vol, vol_id in enumerate(self.task_table[task_row]['affected_volunteers']):
                if vol_id == -1:
                    break
            vols = self.task_table.cols.affected_volunteers[task_row]
            vols[ind_vol] = idvol
            self.task_table.cols.affected_volunteers[task_row]=vols
            self.task_table.cols.N_filled[task_row]+=1
            self.task_table.flush()

            for ind_task, task_id_tmp in enumerate(self.volunteer_table[vol_row]['affected_tasks']):
                if task_id_tmp == -1:
                    break
            tasks = self.volunteer_table.cols.affected_tasks[vol_row]
            tasks[ind_task] = task_id
            self.volunteer_table.cols.affected_tasks[idvol] = tasks
            self.volunteer_table.flush()
        self.update_signal.emit()

        index_ul = self.createIndex(index.row(), 0)
        index_br = self.createIndex(index.row(), len(self.volunteer_table.colnames)-1)
        self.dataChanged.emit(index_ul, index_br, [QtCore.Qt.DisplayRole for ind in range(len(self.volunteer_table.colnames))])

    def remove_task(self, index, select=True):
        """
        Remove tasks from the affected ones to a given volunteer
        Parameters
        ----------
        index (QtCore.QIndex): index pointing to the selected volunteer
        select (bool): if True, the user can select which task to remove else all are removed

        Returns
        -------

        """
        self.volunteer_table = self.h5file.get_node('/volunteers/volunteer_table')
        self.task_table = self.h5file.get_node('/tasks/tasks_table')
        idvol = int(index.sibling(index.row(), 0).data())
        row_vol = self.volunteer_table.get_where_list("""(idnumber == {:})""".format(idvol))[0]
        tasks = [task for task in self.volunteer_table[row_vol]['affected_tasks'] if task != -1]

        if select:
            list = ListPicker(picker_type="task", h5file=self.h5file, ids=tasks)
            ids = list.pick_dialog(connect=False)
        else:
            ids = tasks

        for task_id in ids:
            task_row = self.task_table.get_where_list("""(idnumber == {:})""".format(task_id))[0]

            vols = self.task_table.cols.affected_volunteers[task_row]
            # find the index corresponding to the picked name
            for ind_vol, vol_id in enumerate(self.task_table[task_row]['affected_volunteers']):
                if vol_id == idvol:
                    break
            vols[ind_vol] = -1
            self.task_table.cols.affected_volunteers[task_row] = vols
            self.task_table.cols.N_filled[task_row] -= 1
            self.task_table.flush()

            for ind_task, task_id_tmp in enumerate(self.volunteer_table[row_vol]['affected_tasks']):
                if task_id_tmp == task_id:
                    break
            tasks = self.volunteer_table.cols.affected_tasks[row_vol]
            tasks[ind_task] = -1
            self.volunteer_table.cols.affected_tasks[row_vol] = tasks
            self.volunteer_table.flush()
            self.update_signal.emit()

            index_ul = self.createIndex(index.row(), 0)
            index_br = self.createIndex(index.row(), len(self.task_table.colnames) - 1)
            self.dataChanged.emit(index_ul, index_br, [QtCore.Qt.DisplayRole for ind in range(10)])

    def export_csv(self):
        self.task_table = self.h5file.get_node('/tasks/tasks_table')
        path = os.path.split(os.path.abspath(self.h5file.filename))[0]
        filename = select_file(path, ext='csv')
        if filename != '':
            with open(filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile, delimiter=',')
                for vol in self.volunteer_table:
                    row = []
                    for name in self.volunteer_table.colnames:
                        if isinstance(vol[name], bytes):
                            row.append(vol[name].decode())
                        elif name == "day":
                            row.append(QtCore.QDateTime().fromSecsSinceEpoch(vol[name]).toString('dddd'))
                        elif 'time' in name:
                            row.append(QtCore.QDateTime().fromSecsSinceEpoch(vol[name][0]).toString('hh:mm'))
                            row.append(QtCore.QDateTime().fromSecsSinceEpoch(vol[name][1]).toString('hh:mm'))
                        elif isinstance(vol[name], int):
                            row.append(str(vol[name]))
                        elif isinstance(vol[name], np.ndarray):
                            names = []
                            for id in vol[name]:
                                if id != -1:
                                    task_row = self.task_table.get_where_list("""(idnumber == {:})""".format(id))[0]
                                    names.append('[{:d}, {:s}]'.format(id, self.task_table[task_row]['name'].decode()))
                            row.append(str(names))
                    #print(row)
                    writer.writerow(row)

    def export_html(self,index=None, export_all=False):

        self.volunteer_table = self.h5file.get_node('/volunteers/volunteer_table')
        self.task_table = self.h5file.get_node('/tasks/tasks_table')
        if index is not None:
            vol_id = int(index.sibling(index.row(), self.volunteer_table.colnames.index('idnumber')).data())
            vol_row = self.volunteer_table.get_where_list("""(idnumber == {:})""".format(vol_id))[0]
            vol = self.volunteer_table[vol_row]
            self.create_html_timeline(vol, vol_id)
        elif export_all:
            for ind_vol, vol in enumerate(self.volunteer_table):
                self.create_html_timeline(vol, ind_vol)

    def create_html_timeline(self,vol, vol_id):
        tasks = []
        for task_id in [v for v in vol['affected_tasks'] if v != -1]:
            task_row = self.task_table.get_where_list("""(idnumber == {:})""".format(task_id))[0]
            task = self.task_table[task_row]
            tasks.append(task)
        tasks.sort(key=lambda t: t['time_start'])

        path = os.path.split(os.path.abspath(self.h5file.filename))[0]
        doc, tag, text = Doc().tagtext()
        doc.asis('<!DOCTYPE html>')
        with tag('html', lang='fr'):
            with tag('head'):
                doc.asis('<meta http-equiv="Content-Type" content="text/html; charset=UTF-8"/>')
                with tag('title'):
                    text('fiche bénévole')
                with tag('style'):
                    doc.asis("""* {
                          box-sizing: border-box;
                        }

                        /* Set a background color */
                        body {
                          background-color: #474e5d;
                          font-family: Helvetica, sans-serif;
                        }

                        /* The actual timeline (the vertical ruler) */
                        .timeline {
                          position: relative;
                          max-width: 1200px;
                          margin: 0 auto;
                        }

                        /* The actual timeline (the vertical ruler) */
                        .timeline::after {
                          content: '';
                          position: absolute;
                          width: 6px;
                          background-color: white;
                          top: 0;
                          bottom: 0;
                          left: 50%;
                          margin-left: -3px;
                        }

                        /* Container around content */
                        .container {
                          padding: 10px 40px;
                          position: relative;
                          background-color: inherit;
                          width: 50%;
                        }

                        /* The circles on the timeline */
                        .container::after {
                          content: '';
                          position: absolute;
                          width: 25px;
                          height: 25px;
                          right: -17px;
                          background-color: white;
                          border: 4px solid #FF9F55;
                          top: 15px;
                          border-radius: 50%;
                          z-index: 1;
                        }

                        /* Place the container to the left */
                        .left {
                          left: 0;
                        }

                        /* Place the container to the right */
                        .right {
                          left: 50%;
                        }

                        /* Add arrows to the left container (pointing right) */
                        .left::before {
                          content: " ";
                          height: 0;
                          position: absolute;
                          top: 22px;
                          width: 0;
                          z-index: 1;
                          right: 30px;
                          border: medium solid white;
                          border-width: 10px 0 10px 10px;
                          border-color: transparent transparent transparent white;
                        }

                        /* Add arrows to the right container (pointing left) */
                        .right::before {
                          content: " ";
                          height: 0;
                          position: absolute;
                          top: 22px;
                          width: 0;
                          z-index: 1;
                          left: 30px;
                          border: medium solid white;
                          border-width: 10px 10px 10px 0;
                          border-color: transparent white transparent transparent;
                        }

                        /* Fix the circle for containers on the right side */
                        .right::after {
                          left: -16px;
                        }

                        /* The actual content */
                        .content {
                          padding: 20px 30px;
                          background-color: white;
                          position: relative;
                          border-radius: 6px;
                        }

                        /* Media queries - Responsive timeline on screens less than 600px wide */
                        @media screen and (max-width: 600px) {
                        /* Place the timelime to the left */
                          .timeline::after {
                            left: 31px;
                          }

                        /* Full-width containers */
                          .container {
                            width: 100%;
                            padding-left: 70px;
                            padding-right: 25px;
                          }

                        /* Make sure that all arrows are pointing leftwards */
                          .container::before {
                            left: 60px;
                            border: medium solid white;
                            border-width: 10px 10px 10px 0;
                            border-color: transparent white transparent transparent;
                          }

                        /* Make sure all circles are at the same spot */
                          .left::after, .right::after {
                            left: 15px;
                          }

                        /* Make all right containers behave like the left ones */
                          .right {
                            left: 0%;
                          }
                        }
                    """)
            with tag('body'):
                with tag('div', style=''):
                    with tag('h1'):
                        text(self.h5file.root._v_attrs['event_name'])
                    with tag('h2'):
                        text('du {:} au {:} à {:}'.format(
                            QtCore.QDateTime().fromSecsSinceEpoch(self.h5file.root._v_attrs['event_day']).toString(
                                'dd/MM/yyyy'),
                            QtCore.QDateTime().fromSecsSinceEpoch(self.h5file.root._v_attrs['event_day']).addDays(
                                self.h5file.root._v_attrs['Ndays']).toString('dd/MM/yyyy'),
                            self.h5file.root._v_attrs['event_place']))
                    with tag('h3'):
                        doc.asis('Fiche bénévole pour: {:}'.format(vol['name'].decode()))
                with tag('div', klass='timeline'):
                    for ind, task in enumerate(tasks):
                        if not odd_even(ind):
                            container = 'container left'
                        else:
                            container = 'container right'
                        with tag('div', klass=container):
                            with tag('div', klass='content'):
                                with tag('h2'):
                                    text('{:} de {:} à {:}'.format(
                                        QtCore.QDateTime().fromSecsSinceEpoch(task['time_start']).toString(
                                            'dddd dd/MM/yyyy'),
                                        QtCore.QDateTime().fromSecsSinceEpoch(task['time_start']).toString('hh:mm'),
                                        QtCore.QDateTime().fromSecsSinceEpoch(task['time_end']).toString('hh:mm')))
                                with tag('h3'):
                                    if task["localisation"].decode() != '':
                                        url = f'https://www.google.com/maps/search/?api=1&query={task["localisation"].decode()}'
                                        with tag(f'a href="{url}" '
                                                 f'target="_blank"'
                                                 ):
                                            text(task['name'].decode())
                                    else:
                                        text(task['name'].decode())


                                with tag('h4'):
                                    if task['responsable'] != -1:
                                        id_resp = self.volunteer_table.get_where_list("""(idnumber == {:})""".format(task['responsable']))[0]
                                    else:
                                        id_resp = -1
                                    text(f"Responsable: {self.volunteer_table[id_resp]['name'].decode() if id_resp != -1 else ''}:"
                                         f" {self.volunteer_table[id_resp]['telephone'].decode() if id_resp != -1 else ''}")
                                with tag('p'):
                                    text('Autres volontaires:')
                                with tag('p'):
                                    for id_tmp in [v for v in task['affected_volunteers'] if v != -1 and v != vol_id]:
                                        vol_row_tmp = \
                                        self.volunteer_table.get_where_list("""(idnumber == {:})""".format(id_tmp))[0]
                                        text(f"{self.volunteer_table[vol_row_tmp]['name'].decode()}: {self.volunteer_table[vol_row_tmp]['telephone'].decode()}")
                                with tag('p'):
                                    text('Choses à emmener: {:}'.format(task['stuff_needed'].decode()))
                                with tag('p'):
                                    text('Remarques: {:}'.format(task['remarqs'].decode()))

        path = os.path.join(path,'{:}.html'.format(vol['name'].decode()))
        url = 'file://' + path
        with codecs.open(path, 'wb', 'utf-8') as f:
            f.write(doc.getvalue())
        webbrowser.open(url)


    def create_html(self,vol, vol_id):
        path = os.path.split(os.path.abspath(self.h5file.filename))[0]
        doc, tag, text = Doc().tagtext()
        doc.asis('<!DOCTYPE html>')
        with tag('html', lang='fr'):
            with tag('head'):
                doc.asis('<meta http-equiv="Content-Type" content="text/html; charset=UTF-8"/>')
                with tag('title'):
                    text('fiche bénévole')
                with tag('style'):
                    doc.asis('.task {background-color: black;color: white;margin: 20px;padding: 20px;}')
                    doc.asis('.container {}')
                    doc.asis('.row {line-height:24pt;}')
                    doc.asis('div.container > div:nth-of-type(odd) {background: #cce0ff;}')
                    doc.asis('div.container > div:nth-of-type(even) {background: #ffff80;}')

            with tag('body'):
                with tag('div', style=''):
                    with tag('h1'):
                        text(self.h5file.root._v_attrs['event_name'])
                    with tag('h2'):
                        text('du {:} au {:} à {:}'.format(
                            QtCore.QDateTime().fromSecsSinceEpoch(self.h5file.root._v_attrs['event_day']).toString(
                                'dd/MM/yyyy'),
                            QtCore.QDateTime().fromSecsSinceEpoch(self.h5file.root._v_attrs['event_day']).addDays(
                                self.h5file.root._v_attrs['Ndays']).toString('dd/MM/yyyy'),
                            self.h5file.root._v_attrs['event_place']))
                    with tag('h3'):
                        doc.asis('Fiche bénévole pour: {:}'.format(vol['name'].decode()))
                tasks = []
                for task_id in [v for v in vol['affected_tasks'] if v != -1]:
                    task_row = self.task_table.get_where_list("""(idnumber == {:})""".format(task_id))[0]
                    task = self.task_table[task_row]
                    tasks.append(task)
                tasks.sort(key=lambda t: t['time_start'])
                with tag('div', klass='container'):
                    for task in tasks:
                        with tag('div', klass='row'):
                            with tag('h3'):
                                text(task['name'].decode())
                            with tag('p'):
                                text('{:} de {:} à {:}'.format(
                                    QtCore.QDateTime().fromSecsSinceEpoch(task['time_start']).toString(
                                        'dddd dd/MM/yyyy'),
                                    QtCore.QDateTime().fromSecsSinceEpoch(task['time_start']).toString('hh:mm'),
                                    QtCore.QDateTime().fromSecsSinceEpoch(task['time_end']).toString('hh:mm')))
                            with tag('p'):
                                vols = []
                                for id_tmp in [v for v in task['affected_volunteers'] if v != -1 and v != vol_id]:
                                    vol_row_tmp = \
                                    self.volunteer_table.get_where_list("""(idnumber == {:})""".format(id_tmp))[0]
                                    vols.append(self.volunteer_table[vol_row_tmp]['name'].decode())
                                text('Autres volontaires: {:}'.format(vols))
                            with tag('p'):
                                text('Choses à emmener: {:}'.format(task['stuff_needed'].decode()))
                            with tag('p'):
                                text('Remarques: {:}'.format(task['remarqs'].decode()))

        path = os.path.join(path,'{:}.html'.format(vol['name'].decode()))
        url = 'file://' + path
        with codecs.open(path, 'wb', 'utf-8') as f:
            f.write(doc.getvalue())
        webbrowser.open(url)


class VolunteerWidgetMapper(QtWidgets.QWidget):
    day_params = [
        {'title': 'Present?:', 'name': 'present', 'type': 'bool', 'value': False},
        {'title': 'Time Start:', 'name': 'time_start', 'type': 'time', 'value': QtCore.QTime(), 'minutes_increment': 1},
        {'title': 'Time End:', 'name': 'time_end', 'type': 'time', 'value': QtCore.QTime(), 'minutes_increment': 1},
    ]

    params = [{'title': 'Volunteer Settings:', 'name': 'volunteer_settings', 'type': 'group', 'children': [
                {'title': 'Id:', 'name': 'id', 'type': 'int', 'value': -1, 'readonly': True},
                {'title': 'Name:', 'name': 'name', 'type': 'str', 'value': ''},
                {'title': 'Remarqs:', 'name': 'remarqs', 'type': 'str', 'value': ''},
                {'title': 'Telephone:', 'name': 'telephone', 'type': 'str', 'value': ''},
                {'title': 'Days','name': 'day_list', 'type': 'group'}

    ]}]


    def __init__(self, h5file=None, row=None):
        super(VolunteerWidgetMapper, self).__init__()
        self.h5file = h5file
        self.vol_table = h5file.get_node('/volunteers/volunteer_table')
        self.row = row

    def update_status(self, txt):
        logging.info(txt)

    def show_dialog(self):
        if not not self.vol_table and self.row is not None:
            names = self.vol_table.colnames
            dat = self.vol_table[self.row]

            name = dat[names.index('name')].decode()
            idval = dat['idnumber']
            remarqs = dat[names.index('remarqs')].decode()
            tss=[]
            tes=[]
            present=[]
            ts_s=dat[names.index('time_start')]
            te_s=dat[names.index('time_end')]

            for ind_day in range(self.h5file.root._v_attrs['Ndays']):
                if ts_s[ind_day] != -1:
                    present.append(True)
                    daytmp = QtCore.QDateTime()
                    daytmp.setSecsSinceEpoch(ts_s[ind_day])
                    tss.append(daytmp)
                    daytmp = QtCore.QDateTime()
                    daytmp.setSecsSinceEpoch(te_s[ind_day])
                    tes.append(daytmp)
                else:
                    present.append(False)
                    tss.append(QtCore.QDateTime())
                    tes.append(QtCore.QDateTime())




        else:
            try:
                idval = int(np.max(self.vol_table[:]['idnumber']) + 1)
            except:
                idval = 0
            name = ''
            remarqs = ""
            tss=[]
            tes=[]
            present=[True for ind in range(self.h5file.root._v_attrs['Ndays'])]
            for ind in range(self.h5file.root._v_attrs['Ndays']):
                day_tmp=QtCore.QDateTime()
                day_tmp.setSecsSinceEpoch(self.h5file.root._v_attrs['event_day'])
                day_tmp.setTime(QtCore.QTime(6,0))
                tss.append(day_tmp)
                day_tmp = QtCore.QDateTime()
                day_tmp.setSecsSinceEpoch(self.h5file.root._v_attrs['event_day'])
                day_tmp.setTime(QtCore.QTime(22, 0))
                tes.append(day_tmp)




        self.settings = Parameter.create(name='task_settings', type='group', children=self.params)
        self.settings.child('volunteer_settings','id').setValue(idval)
        self.settings.child('volunteer_settings','name').setValue(name)
        self.settings.child('volunteer_settings','remarqs').setValue(remarqs)

        for ind_day in range(self.h5file.root._v_attrs['Ndays']):
            new_par = Parameter.create(title='Day {:02d}:'.format(ind_day), name='day_{:02d}:'.format(ind_day), type='group', children=self.day_params)
            new_par.child(('present')).setValue(present[ind_day])
            new_par.child(('time_start')).setValue(tss[ind_day].time())
            new_par.child(('time_end')).setValue(tes[ind_day].time())
            self.settings.child('volunteer_settings','day_list').addChild(new_par)

        dialog = QtWidgets.QDialog(self)
        vlayout = QtWidgets.QVBoxLayout()
        self.settings_tree = ParameterTree()
        vlayout.addWidget(self.settings_tree, 10)
        self.settings_tree.setMinimumWidth(300)

        self.settings_tree.setParameters(self.settings, showTop=False)
        dialog.setLayout(vlayout)

        buttonBox = QtWidgets.QDialogButtonBox(parent=self);
        buttonBox.addButton('Apply', buttonBox.AcceptRole)
        buttonBox.accepted.connect(dialog.accept)
        buttonBox.addButton('Cancel', buttonBox.RejectRole)
        buttonBox.rejected.connect(dialog.reject)

        vlayout.addWidget(buttonBox)
        self.setWindowTitle('Fill in information about this Volunteer')
        res = dialog.exec()

        if res == dialog.Accepted:
            # save managers parameters in a xml file
            return self.settings
        else:
            return None


class VolunteerWidget(QtWidgets.QTableView):
    index_changed_signal=QtCore.Signal(QtCore.QModelIndex)

    def currentChanged(self, current: QtCore.QModelIndex, previous: QtCore.QModelIndex):
        self.index_changed_signal.emit(current)

    def __init__(self):
        super(VolunteerWidget, self).__init__()
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.menu = QtWidgets.QMenu()
        self.menu.addAction('Add new volunteer', self.add_new)
        self.menu.addAction('Edit current row', self.edit_task)
        self.menu.addAction('Remove selected rows', self.remove_volunteer)
        self.menu.addSeparator()
        self.menu.addAction('Affect tasks', self.add_task)
        self.menu.addAction('Remove tasks', self.remove_task)
        self.menu.addSeparator()
        self.import_action = self.menu.addAction('Import from csv')
        self.menu.addSeparator()
        self.menu.addAction('Export to html', self.export_html)
        export_all_action = self.menu.addAction('Export all to html', lambda: self.export_html(True))
        self.menu.addAction('Export all to csv', self.export_csv)

        self.doubleClicked.connect(self.edit_task)

    def update_status(self, txt):
        logging.info(txt)

    def export_csv(self):
        self.model().sourceModel().export_csv()

    def export_html(self, export_all=False):
        if export_all:
            self.model().sourceModel().export_html(export_all=export_all)
        else:
            indexes = self.selectedIndexes()
            for index in indexes:
                if index.column() == 0:
                    if index.row() != -1:
                        index_source = index.model().mapToSource(index)
                    else:
                        index_source = index
                    self.model().sourceModel().export_html(index_source)

    def add_new(self):
        index = self.currentIndex()
        if index.row() != -1:
            index_source = index.model().mapToSource(index)
        else:
            index_source = index
        self.model().sourceModel().append_row(index_source)

    def edit_task(self):
        index = self.currentIndex()
        index_source = index.model().mapToSource(index)
        index_source.model().edit_data(index_source)

    def remove_volunteer(self):
        indexes = self.selectedIndexes()
        rows_ids = [(index.model().mapToSource(index).row(), index.data()) for index in indexes if index.column() == 0]
        indexes[0].model().mapToSource(indexes[0]).model().remove_data(indexes[0].model().mapToSource(indexes[0]),
                                                                       rows_ids)
    def add_task(self):
        index = self.currentIndex()
        index_source = index.model().mapToSource(index)
        index_source.model().add_task(index_source)

    def remove_task(self):
        index = self.currentIndex()
        index_source = index.model().mapToSource(index)
        index_source.model().remove_task(index_source)

    def contextMenuEvent(self, event):
        self.menu.exec(event.globalPos())


col_volunteer_header = ['Vol. Id', 'name', 'remarqs', 'affected tasks', 'telephone']
