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
from qtpy import QtCore, QtGui, QtWidgets
from yawrap import Doc

from gevt.list_picker import ListPicker
from gevt.utils import getLineInfo, get_overlap
from gevt.gui_utils import select_file


class TaskModel(QtCore.QAbstractTableModel):

    update_signal = QtCore.Signal()

    def __init__(self, h5file=None, list_ids=None):
        super(TaskModel, self).__init__()
        self.list_ids = list_ids
        if h5file is None:
            raise Exception('No valid pytables file')
        elif type(h5file) == str or type(h5file) == Path:
            self.h5file = tables.open_file(str(h5file), mode='a', title='List of Tasks and volunteers for RTA 2018')
        elif type(h5file) == tables.File:
            self.h5file = h5file

        self.task_table = self.h5file.get_node('/tasks/tasks_table')
        self.volunteer_table = self.h5file.get_node('/volunteers/volunteer_table')
        self.names = self.task_table.colnames

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

            try:
                self.task_table = self.h5file.get_node('/tasks/tasks_table')
                return self.task_table.nrows
            except tables.exceptions.ClosedFileError:
                return 0


    def columnCount(self,index):
        if self.list_ids is not None:
            return 6
        else:
            return len(self.task_table.colnames)

    def data(self, index=QtCore.QModelIndex(), role=QtCore.Qt.DisplayRole):
        try:
            if role == QtCore.Qt.DisplayRole:

                if index.isValid():
                    ind_col = self.names[index.column()]
                    if self.list_ids is not None:
                        task_row = self.task_table.get_where_list("""(idnumber == {:})""".format(self.list_ids[index.row()]))[0]
                        dat = self.task_table[task_row][ind_col]
                    else:
                        dat = self.task_table[index.row()][ind_col]
                    dat_type = self.task_table.coltypes[self.task_table.colnames[index.column()]]

                    if index.column() == 1:  # day
                        d = datetime.datetime.fromtimestamp(dat)
                        return d.strftime('%A')

                    if 'int' in dat_type:
                        if index.column() == 10 or index.column() == 11: #affected volunteers or responsable
                            if isinstance(dat, np.ndarray):
                                try:
                                    return str([self.volunteer_table[
                                                    self.volunteer_table.get_where_list(f"""(idnumber == {ind})""")[0]]['name'].decode() for ind
                                                in dat if ind != -1])
                                except:
                                    return ''
                            else:
                                return self.volunteer_table[self.volunteer_table.get_where_list("""(idnumber == {:})""".format(
                                                        dat))[0]]['name'].decode()
                        else:
                            return int(dat)
                    elif dat_type == 'string':
                        return dat.decode()
                    elif dat_type == 'time32':
                        d = datetime.datetime.fromtimestamp(dat)
                        return d.strftime('%H:%M')
                    elif dat_type == 'enum':
                        return self.task_table.get_enum('task_type')(dat)
                else:
                    return ''

            elif role == QtCore.Qt.BackgroundRole:
                if index.column() == self.task_table.colnames.index('N_filled'):
                    Nneeded = self.task_table[index.row()]['N_needed']
                    Nfilled = self.task_table[index.row()]['N_filled']



                    brush=QtGui.QBrush(QtCore.Qt.SolidPattern)
                    if Nfilled < Nneeded:
                        brush.setColor(QtGui.QColor(255,0,0))
                    else:
                        brush.setColor(QtGui.QColor(0,255,0))
                    return brush
                else:
                    return QtCore.QVariant()
            else:
                return QtCore.QVariant()
        except Exception as e:
            self.update_status(getLineInfo() + str(e))

    def edit_data(self, index):
        task_id = index.sibling(index.row(), self.task_table.colnames.index('idnumber')).data()
        task_row = self.task_table.get_where_list("""(idnumber == {:})""".format(task_id))[0]
        mapper = TaskWidgetMapper(self.h5file, task_row)
        res = mapper.show_dialog()
        if res is not None:
            if res.child('task_settings','time_start').value() !=\
                QtCore.QDateTime().fromSecsSinceEpoch(self.task_table[task_row]['time_start']).time() or\
                    res.child('task_settings', 'time_end').value() !=\
                    QtCore.QDateTime().fromSecsSinceEpoch(self.task_table[task_row]['time_end']).time():  #means time_start or time_end has been changed, so maybe not consistent anymore with affected tasks to other volunteers
                consistent, messg = self.check_consistency(res, task_row)
            else:
                consistent, messg = True, ''
            if consistent:
                self.task_param_to_row(res, task_row)
            else:
                messgbox = QtWidgets.QMessageBox()
                messgbox.setText(messg)
                messgbox.exec()

    def check_consistency(self,res,task_id):
        """
        Will check if the modified task times are still compatible with affected volunteers
        Returns
        -------
        (bool, str): tuple with a bool: True if consistent otherwise False, if False, returns also a message with the volunteer id for who the consistency is wrong
        """

        task_row = self.task_table[task_id]

        vols = [vol for vol in task_row['affected_volunteers'] if vol != -1]

        time_start = QtCore.QDateTime(res.child('task_settings', 'day').value(),res.child('task_settings', 'time_start').value()).toSecsSinceEpoch()
        time_end = QtCore.QDateTime(res.child('task_settings', 'day').value(),
                                      res.child('task_settings', 'time_end').value()).toSecsSinceEpoch()

        for vol_id in vols:
            # check if this modification is compatible with volunteer availability
            list = ListPicker(task_row, time_start, time_end, "volunteer", self.h5file)
            availlable_ids = list.check_availlable(vol_id, time_start, time_end, [], task_id)
            if vol_id not in availlable_ids:
                return False, 'The new times are not compatible with vol {:d}: {:s} and its availlability'.format(
                    vol_id, self.volunteer_table[vol_id]['name'].decode())

            #check if this modification is compatible with others affected tasks
            affected_tasks_ids = [task for task in self.volunteer_table[vol_id]['affected_tasks'] if task != -1]
            affected_tasks_ids.pop(affected_tasks_ids.index(task_id)) #do not include the one that has just been modified
            affected_tasks_times = [(task['time_start'], task['time_end']) for task in self.task_table if
                                    task['idnumber'] in affected_tasks_ids]
            for ind in range(len(affected_tasks_times)):
                #check if this modification is compatible with other affected tasks
                if get_overlap([affected_tasks_times[ind][0], affected_tasks_times[ind][1]], [time_start, time_end]) > 0:
                    return False, 'The new times are not compatible with vol {:d}: {:s} and its other task : {:d}'.format(vol_id, self.volunteer_table[vol_id]['name'].decode(),
                                                                                 affected_tasks_ids[ind])


        return True, ''

    def go_to(self, index):
        task_id = index.sibling(index.row(), self.task_table.colnames.index('idnumber')).data()
        task_row = self.task_table.get_where_list("""(idnumber == {:})""".format(task_id))[0]
        localisation = self.task_table[task_row]['localisation']

        url = f'https://www.google.com/maps/search/?api=1&query={localisation.decode()}'

        webbrowser.open(url)

    def add_volunteer(self, index, resp=False):
        task_id = index.sibling(index.row(), self.task_table.colnames.index('idnumber')).data()
        task_row = self.task_table.get_where_list("""(idnumber == {:})""".format(task_id))[0]
        time_start = self.task_table[task_row]['time_start']
        time_end = self.task_table[task_row]['time_end']

        list = ListPicker(task_row, time_start, time_end, "volunteer", self.h5file)

        volunteers = list.pick_dialog(add=True, select_extended=not resp)

        for idvol in volunteers:
            vol_row = self.volunteer_table.get_where_list("""(idnumber == {:})""".format(idvol))[0]

            for ind_vol, vol_id in enumerate(self.task_table[task_row]['affected_volunteers']):
                if vol_id == -1:
                    break
            vols = self.task_table.cols.affected_volunteers[task_row]
            vols[ind_vol] = idvol
            self.task_table.cols.affected_volunteers[task_row] = vols
            if resp:
                self.task_table.cols.responsable[task_row] = idvol
            self.task_table.cols.N_filled[task_row] = np.sum([1 for vol in vols if vol!=-1 ])
            self.task_table.flush()

            for ind_task, task_id_tmp in enumerate(self.volunteer_table[vol_row]['affected_tasks']):
                if task_id_tmp == -1:
                    break
            tasks = self.volunteer_table.cols.affected_tasks[vol_row]
            tasks[ind_task] = task_id
            self.volunteer_table.cols.affected_tasks[vol_row] = tasks
            self.volunteer_table.flush()
        self.update_signal.emit()

        index_ul = self.createIndex(index.row(), 0)
        index_br = self.createIndex(index.row(), len(self.task_table.colnames)-1)
        self.dataChanged.emit(index_ul, index_br, [QtCore.Qt.DisplayRole for ind in range(len(self.task_table.colnames))])

    def remove_volunteer(self,index,select=True):
        """
        Remove volunteers from the affected ones to a given task
        Parameters
        ----------
        index (QtCore.QIndex): index pointing to the selected task
        select (bool): if True, the user can select which volunteer to remove else all are removed

        Returns
        -------

        """
        task_id = index.sibling(index.row(), self.task_table.colnames.index('idnumber')).data()
        task_row = self.task_table.get_where_list("""(idnumber == {:})""".format(task_id))[0]
        volunteers = [ind for ind in self.task_table[task_row]['affected_volunteers'] if ind != -1]

        if select:
            list = ListPicker(picker_type="volunteer", h5file=self.h5file, ids=volunteers)
            ids = list.pick_dialog(connect=False, add=False)
        else:
            ids = volunteers
        for idvol in ids:
            vol_row = self.volunteer_table.get_where_list("""(idnumber == {:})""".format(idvol))[0]
            vols = self.task_table.cols.affected_volunteers[task_row]
            resp_id = self.task_table.cols.responsable[task_row]
            # find the index corresponding to the picked name
            for ind_vol, vol_id in enumerate(self.task_table[task_row]['affected_volunteers']):
                if vol_id == idvol:
                    break
            if resp_id == idvol:
                self.task_table.cols.responsable[task_row] = -1
            vols[ind_vol] = -1
            self.task_table.cols.affected_volunteers[task_row] = vols
            self.task_table.cols.N_filled[task_row] = np.sum([1 for vol in vols if vol!=-1 ])
            self.task_table.flush()

            for ind_task, task_id_tmp in enumerate(self.volunteer_table[vol_row]['affected_tasks']):
                if task_id_tmp == task_id:
                    break
            tasks = self.volunteer_table.cols.affected_tasks[vol_row]
            tasks[ind_task] = -1
            self.volunteer_table.cols.affected_tasks[vol_row] = tasks
            self.volunteer_table.flush()
            self.update_signal.emit()

        index_ul = self.createIndex(index.row(), 0)
        index_br = self.createIndex(index.row(), len(self.task_table.colnames)-1)
        self.dataChanged.emit(index_ul, index_br, [QtCore.Qt.DisplayRole for ind in range(10)])

    def remove_data(self,index,rows_ids):
        msgBox=QtWidgets.QMessageBox()
        msgBox.setText("You are about to delete rows!")
        msgBox.setInformativeText("Are you sure you want to delete rows with ids: {:}".format([row[1] for row in rows_ids]))
        msgBox.setStandardButtons(QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel)
        msgBox.setDefaultButton(QtWidgets.QMessageBox.Cancel)
        res = msgBox.exec()

        if res==QtWidgets.QMessageBox.Ok:
            for row,id in rows_ids:
                if self.task_table[row]['N_filled'] == 0:
                    self.beginRemoveRows(index.parent(),row,row)
                    self.task_table.remove_row(self.task_table.get_where_list("""(idnumber == {:})""".format(id))[0])
                    self.endRemoveRows()
                else:
                    msgBox = QtWidgets.QMessageBox()
                    msgBox.setText("Task with id: {:} has affected volunteers".format(id))
                    msgBox.setInformativeText("Do you still want to remove it?")
                    msgBox.setStandardButtons(QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel)
                    msgBox.setDefaultButton(QtWidgets.QMessageBox.Cancel)
                    res = msgBox.exec()
                    if res == QtWidgets.QMessageBox.Ok:
                        self.remove_volunteer(self.createIndex(row,0),select= False)
                        self.beginRemoveRows(index.parent(), row, row)
                        self.task_table.remove_row(self.task_table.get_where_list("""(idnumber == {:})""".format(id))[0])
                        self.endRemoveRows()
                self.update_signal.emit()

    def append_row(self,index):
        self.insertRows(self.rowCount(index),1,index.parent())
        self.update_signal.emit()

    def insertRows(self, row: int, count: int, parent):
        if row == 0:
            row = 1
        self.beginInsertRows(parent, row - 1, row - 1)
        mapper = TaskWidgetMapper(self.h5file)
        res = mapper.show_dialog()
        if res is not None:
            self.task_param_to_row(res)
        self.endInsertRows()

        return True

    def task_param_to_row(self, param, row_index=None):
        try:

            row_data = dict()
            row_data['idnumber'] = int(param.child('task_settings', 'id').value())
            row_data['day'] = int(
                QtCore.QDateTime(param.child('task_settings', 'day').value()).toMSecsSinceEpoch() / 1000)
            row_data['time_start'] = int(QtCore.QDateTime(param.child('task_settings', 'day').value(),
                                                          param.child('task_settings',
                                                                      'time_start').value()).toMSecsSinceEpoch() / 1000)
            row_data['time_end'] = int(QtCore.QDateTime(param.child('task_settings', 'day').value(),
                                                        param.child('task_settings',
                                                                    'time_end').value()).toMSecsSinceEpoch() / 1000)
            row_data['task_type'] = self.task_table.get_enum('task_type')[
                param.child('task_settings', 'task_type').value()]
            row_data['name'] = param.child('task_settings', 'name').value().encode()
            row_data['N_needed'] = int(param.child('task_settings', 'N_needed').value())
            row_data['N_filled'] = int(param.child('task_settings', 'N_filled').value())
            row_data['remarqs'] = param.child('task_settings', 'remarqs').value().encode()
            row_data['stuff_needed'] = param.child('task_settings', 'stuff').value().encode()
            row_data['localisation'] = param.child('task_settings', 'localisation').value().encode()
            #row_data['responsable'] = param.child('task_settings', 'responsable').value().encode()
            try:
                row_data['responsable'] = self.task_table[row_index]['responsable']
            except:
                row_data['responsable'] = -1
            try:
                row_data['affected_volunteers'] = self.task_table[row_index]['affected_volunteers']
            except:
                row_data['affected_volunteers'] = np.ones((50,), dtype='int64') * (-1)

            if row_index is None:
                row_index = self.task_table.nrows + 1
                row = self.task_table.row
                for k in self.task_table.colnames:
                    row[k] = row_data[k]
                row.append()
                self.task_table.flush()


            else:
                dat = [tuple([row_data[k] for k in self.task_table.colnames])]
                self.task_table.modify_rows(start=row_index, stop=row_index + 1, step=1, rows=dat)
                index_ul = self.createIndex(row_index, 0)
                index_br = self.createIndex(row_index, 9)
                self.dataChanged.emit(index_ul, index_br, [QtCore.Qt.DisplayRole for ind in range(10)])
                self.task_table.flush()

            self.update_signal.emit()

        except Exception as e:
            self.update_status(getLineInfo() + str(e))



    def headerData(self,section,orientation,role):
        if role==QtCore.Qt.DisplayRole:
            if orientation==QtCore.Qt.Horizontal:
                return col_task_header[section]
            else:
                return QtCore.QVariant()
        else:
            return QtCore.QVariant()

    def export_csv(self):
        path = os.path.split(os.path.abspath(self.h5file.filename))[0]
        filename = select_file(path, ext='csv')
        if filename != '':
            with codecs.open(filename, 'w', 'utf-8') as csvfile:
                writer = csv.writer(csvfile, delimiter=',')
                for task in self.task_table:
                    row = []
                    for name in self.task_table.colnames:
                        if name == "day":
                            row.append(QtCore.QDateTime().fromSecsSinceEpoch(task[name]).toString('dddd'))
                        elif 'time' in name:
                            row.append(QtCore.QDateTime().fromSecsSinceEpoch(task[name]).toString('hh:mm'))
                        elif name == 'responsable':
                            row.append(self.volunteer_table[task[name]]['name'].decode() if task[name] != -1 else '')
                        elif name == 'localisation':
                            url = f'https://www.google.com/maps/search/?api=1&query={task[name].decode()}' if task[name].decode() != '' else task[name].decode()
                            row.append(url)
                        elif isinstance(task[name], int):
                            row.append(str(task[name]))
                        elif isinstance(task[name], np.ndarray):
                            names = [self.volunteer_table[ind_row]['name'].decode() for ind_row in task[name] if
                                     ind_row != -1]
                            row.append(str(names))
                        elif isinstance(task[name], bytes):
                            row.append(task[name].decode())
                    print(row)
                    writer.writerow(row)

    def export_html(self):
        path = os.path.split(os.path.abspath(self.h5file.filename))[0]
        self.volunteer_table = self.h5file.get_node('/volunteers/volunteer_table')
        self.task_table = self.h5file.get_node('/tasks/tasks_table')


        doc, tag, text = Doc().tagtext()
        doc.asis('<!DOCTYPE html>')
        with tag('html', lang='fr'):
            with tag('head'):
                doc.asis('<meta charset="UTF-8"/>')
                with tag('title'):
                    text('Liste des tâches')
                with tag('style'):
                    text('table, th, td{border: 1px solid black;border-collapse: collapse;}')

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
                with tag('table'):
                    with tag('tr'):
                        for name in self.task_table.colnames:
                            with tag('th'):
                                text(name)
                    for task in self.task_table:
                        with tag('tr'):
                            for name in self.task_table.colnames:
                                with tag('td'):

                                    if name == "day":
                                        text(QtCore.QDateTime().fromSecsSinceEpoch(task[name]).toString('dddd'))
                                    elif 'time' in name:
                                        text(QtCore.QDateTime().fromSecsSinceEpoch(task[name]).toString('hh:mm'))
                                    elif name == 'responsable':
                                        text(self.volunteer_table[task[name]]['name'].decode() if task[name] != -1 else '')
                                    elif name == 'localisation':
                                        url = f'https://www.google.com/maps/search/?api=1&query={task[name].decode()}'
                                        with tag(f'a href="{url}"  target="_blank"'):
                                            text(task[name].decode())

                                    elif isinstance(task[name], int):
                                        text(str(task[name]))
                                    elif isinstance(task[name], np.ndarray):
                                        names = [self.volunteer_table[self.volunteer_table.get_where_list("""(idnumber == {:})""".format(id))[0]
                                                 ]['name'].decode() for id in task[name] if id!=-1]
                                        text(str(names))
                                    elif isinstance(task[name], bytes):
                                        text(task[name].decode())
        path = os.path.join(path,'tasks.html')
        url = 'file://' + path
        with codecs.open(path, 'wb', 'utf-8') as f:
            f.write(doc.getvalue())
        webbrowser.open(url)


class TaskWidgetMapper(QtWidgets.QWidget):
    """ Widget presenting a Tree structure representing a task. If loaded from
    a row in a task table then use entries from task_table, could be used to
    update the task. Otherwise initialize and can be used to enter a new task

    ============== ========================================================================
    **Arguments:**
    task_table     Table type from pytables module containing tasks for this event
    row            Row index within the table. Used to initialize data of
                   the widget.
    """

    def __init__(self, h5file=None, row=None):
        super().__init__()
        self.h5file = h5file
        self.task_table = h5file.get_node('/tasks/tasks_table')
        self.row = row

    def update_status(self, txt):
        logging.info(txt)

    def show_dialog(self):
        if not not self.task_table and self.row is not None:
            names = self.task_table.colnames
            dat = self.task_table[self.row]
            idval = dat['idnumber']
            day = datetime.datetime.fromtimestamp(dat[names.index('day')])
            day = QtCore.QDate(day.year, day.month, day.day)
            ts = datetime.datetime.fromtimestamp(dat[names.index('time_start')])
            ts = QtCore.QTime(ts.hour, ts.minute)
            te = datetime.datetime.fromtimestamp(dat[names.index('time_end')])
            te = QtCore.QTime(te.hour, te.minute)
            name = dat[names.index('name')].decode()
            task_type = self.task_table.get_enum('task_type')(dat[names.index('task_type')])
            N_needed = dat[names.index('N_needed')]
            N_filled = dat[names.index('N_filled')]
            try:
                remarqs = dat[names.index('remarqs')].decode()
            except UnicodeDecodeError:
                remarqs = str(dat[names.index('remarqs')])
            stuff = dat[names.index('stuff_needed')].decode()
            #responsable = dat[names.index('responsable')]
            localisation = dat[names.index('localisation')].decode()

        else:
            try:
                idval = int(np.max(self.task_table[:]['idnumber']) + 1)
            except:
                idval = 0
            if self.row is not None:
                day = datetime.datetime.fromtimestamp(np.min(self.task_table[:]['day']))
                day = QtCore.QDate(day.year, day.month, day.day)
                ts = datetime.datetime.fromtimestamp(np.min(self.task_table[:]['time_start']))
                ts = QtCore.QTime(ts.hour, ts.minute)
                te = datetime.datetime.fromtimestamp(np.min(self.task_table[:]['time_end']))
                te = QtCore.QTime(te.hour, te.minute)
            else:
                day = datetime.datetime.fromtimestamp(self.h5file.root._v_attrs['event_day'])
                day = QtCore.QDate(day.year, day.month, day.day)
                ts = QtCore.QTime(6, 0)
                te = QtCore.QTime(22, 0)

            name = ''
            task_type = list(self.task_table.get_enum('task_type')._names.keys())[0]
            N_needed = 0
            N_filled = 0
            remarqs = ""
            stuff = ""
            localisation = ''
            responsable = ''

        self.params = [{'title': 'Task Settings:', 'name': 'task_settings', 'type': 'group', 'children': [
            {'title': 'Id:', 'name': 'id', 'type': 'int', 'value': idval, 'readonly': True},
            {'title': 'Day:', 'name': 'day', 'type': 'date', 'value': day},
            {'title': 'Time Start:', 'name': 'time_start', 'type': 'time', 'value': ts, 'minutes_increment': 30},
            {'title': 'Time End:', 'name': 'time_end', 'type': 'time', 'value': te, 'minutes_increment': 30},
            {'title': 'Task Type:', 'name': 'task_type', 'type': 'list', 'value': task_type,
             'limits': list(self.task_table.get_enum('task_type')._names.keys())},
            {'title': 'Name:', 'name': 'name', 'type': 'str', 'value': name},

            {'title': 'N needed:', 'name': 'N_needed', 'type': 'int', 'value': N_needed, 'min': 0},
            {'title': 'N filled:', 'name': 'N_filled', 'type': 'int', 'value': N_filled, 'min': 0, 'readonly': True},

            {'title': 'Remarqs:', 'name': 'remarqs', 'type': 'str', 'value': remarqs},
            {'title': 'Stuffs:', 'name': 'stuff', 'type': 'str', 'value': stuff},
            #{'title': 'Responsable:', 'name': 'responsable', 'type': 'str', 'value': responsable, 'readonly': True},
            {'title': 'Geolocalisation:', 'name': 'localisation', 'type': 'str', 'value': localisation,
                                        'tooltip': 'coordinates in the form (43.675548, 1.388145)'},
        ]}]

        dialog = QtWidgets.QDialog(self)
        vlayout = QtWidgets.QVBoxLayout()
        self.settings_tree = ParameterTree()
        vlayout.addWidget(self.settings_tree, 10)
        self.settings_tree.setMinimumWidth(300)
        self.settings = Parameter.create(name='task_settings', type='group', children=self.params)
        self.settings_tree.setParameters(self.settings, showTop=False)
        dialog.setLayout(vlayout)

        buttonBox = QtWidgets.QDialogButtonBox(parent=self);
        buttonBox.addButton('Apply', buttonBox.AcceptRole)
        buttonBox.accepted.connect(dialog.accept)
        buttonBox.addButton('Cancel', buttonBox.RejectRole)
        buttonBox.rejected.connect(dialog.reject)

        vlayout.addWidget(buttonBox)
        self.setWindowTitle('Fill in information about this task')
        res = dialog.exec()

        if res == dialog.Accepted:

            return self.settings
        else:
            return None


class TaskWidget(QtWidgets.QTableView):

    def __init__(self):
        super(TaskWidget, self).__init__()
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.menu = QtWidgets.QMenu()
        self.menu.addAction('Add new task', self.add_new)
        self.menu.addAction('Edit current row', self.edit_task)
        self.menu.addAction('Remove selected rows', self.remove_task)
        self.menu.addSeparator()
        self.menu.addAction('Affect Responsable', lambda: self.add_volunteer(resp=True))
        self.menu.addAction('Affect volunteers', self.add_volunteer)
        self.menu.addAction('Remove volunteers', self.remove_volunteer)
        self.menu.addSeparator()
        self.menu.addAction('Show localisation', self.go_to_localisation)
        self.menu.addSeparator()
        self.import_action = self.menu.addAction('Import from csv')
        self.import_action_geojson = self.menu.addAction('Import from geojson')
        self.menu.addAction('Export to html', self.export_html)
        self.menu.addAction('Export to csv', self.export_csv)

        self.doubleClicked.connect(self.edit_task)

    def update_status(self, txt):
        logging.info(txt)

    def export_csv(self):
        self.model().sourceModel().export_csv()

    def export_html(self):
        self.model().sourceModel().export_html()

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

    def remove_task(self):
        indexes = self.selectedIndexes()
        rows_ids = [(index.model().mapToSource(index).row(), index.data()) for index in indexes if index.column() == 0]
        indexes[0].model().mapToSource(indexes[0]).model().remove_data(indexes[0].model().mapToSource(indexes[0]),
                                                                       rows_ids)

    def add_volunteer(self, resp=False):
        index = self.currentIndex()
        index_source = index.model().mapToSource(index)
        index_source.model().add_volunteer(index_source, resp=resp)

    def remove_volunteer(self):
        index = self.currentIndex()
        index_source = index.model().mapToSource(index)
        index_source.model().remove_volunteer(index_source)

    def go_to_localisation(self):
        index = self.currentIndex()
        index_source = index.model().mapToSource(index)
        index_source.model().go_to(index_source)

    def contextMenuEvent(self, event):
        self.menu.exec(event.globalPos())


col_task_header = ['Task Id', 'day', 'type', 'name', 'time start', 'time end', 'N needed', 'N filled', 'remarqs',
                   'stuff needed', 'affected volunteers', 'responsable', 'localisation']
