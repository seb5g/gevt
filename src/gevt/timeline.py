import datetime
import logging
from pathlib import Path

import numpy as np
import tables

from dateutil.parser import parse
from pyqtgraph import ColorMap
from qtpy import QtWidgets, QtCore, QtGui

from gevt.utils import getLineInfo


class TimeLineView(QtWidgets.QTableView):

    def __init__(self,task_view=None):
        super(TimeLineView, self).__init__()
        self.task_view=task_view
        self.menu = QtWidgets.QMenu()
        show_tasks = self.menu.addAction('Show These Tasks')

        show_tasks.triggered.connect(self.show_tasks)
        self.doubleClicked.connect(self.show_tasks)

    def update_status(self, txt):
        logging.info(txt)

    def show_tasks(self):
        index = self.currentIndex()
        target_time_stamp=int(parse(index.model().headerData(index.column(), QtCore.Qt.Horizontal, QtCore.Qt.DisplayRole),
                  dayfirst=True).timestamp())
        day=index.model().headerData(index.row(),QtCore.Qt.Vertical,QtCore.Qt.DisplayRole)
        self.task_view.model().setDayFilter(day)
        self.task_view.model().setTimeStampFilter(target_time_stamp)


    def contextMenuEvent(self, event):
        self.menu.exec(event.globalPos())


class TimeLineModel(QtCore.QAbstractTableModel):
    def __init__(self, h5file=None, time_step=30, view_type='N_needed'):
        super(TimeLineModel, self).__init__()
        self.colors = ColorMap([0, 1], [[0, 255, 0], [255, 0, 0]])
        self.view_type = view_type  # could be 'N_needed', 'N_filled' or a volunteer name
        self.time_step = time_step
        self.Nsteps = None
        self.days = None
        if h5file is None:
            raise Exception('No valid pytables file')
        elif type(h5file) == str or type(h5file) == Path:
            self.h5file = tables.open_file(str(h5file), mode='a', title='List of Tasks and volunteers for RTA 2018')
        elif type(h5file) == tables.File:
            self.h5file = h5file

        self.update_steps()

    def update_status(self, txt):
        logging.info(txt)

    def update_view_type(self,view_type):
        self.view_type = view_type
        self.update()

    def update(self, *args, **kwargs):
        self.update_steps()
        index_ul = self.createIndex(0, 0)
        index_br = self.createIndex(len(self.days) - 1, self.Nsteps - 1)
        self.dataChanged.emit(index_ul, index_br,
                              [QtCore.Qt.DisplayRole for ind in range(self.Nsteps * len(self.days))])

    def update_steps(self):
        try:
            self.task_table = self.h5file.get_node('/tasks/tasks_table')
            self.days = list(set(self.task_table[:]['day']))
            day_datetime = datetime.datetime.fromtimestamp(min(self.days))

            self.time_start=min([datetime.datetime.fromtimestamp(x).replace(year=day_datetime.year,month=day_datetime.month,day=day_datetime.day)for x in self.task_table[:]['time_start']]).timestamp()
            self.time_end = max([datetime.datetime.fromtimestamp(x).replace(year=day_datetime.year,month=day_datetime.month,day=day_datetime.day)for x in self.task_table[:]['time_end']]).timestamp()

            self.Nsteps=int((self.time_end-self.time_start)/(self.time_step*60)+1)
            self.time_steps=np.linspace(self.time_start,self.time_end,self.Nsteps).astype('int')
            self.names=self.task_table.colnames

            self.N_needed=np.zeros((len(self.days),self.Nsteps)).astype('int')
            self.N_filled = np.zeros((len(self.days), self.Nsteps)).astype('int')
            for ind_day,day in enumerate(self.days):
                for ind_time in range(len(self.time_steps)):
                    time_s=self.time_steps[ind_time]
                    if time_s==self.time_steps[-1]:
                        time_e=time_s
                    else:
                        time_e=self.time_steps[ind_time+1]
                    day_datetime=datetime.datetime.fromtimestamp(day)
                    time_s_datetime=datetime.datetime.fromtimestamp(time_s)
                    time_s=int(time_s_datetime.replace(year=day_datetime.year,month=day_datetime.month,day=day_datetime.day).timestamp())
                    time_e_datetime=datetime.datetime.fromtimestamp(time_e)
                    time_e=int(time_e_datetime.replace(year=day_datetime.year,month=day_datetime.month,day=day_datetime.day).timestamp())
                    self.N_needed[ind_day,ind_time] = int(np.sum([ x['N_needed'] for x in self.task_table.where("""(day == {:0d}) & (time_start <= {:0d}) & (time_end >= {:0d})""".format(day,time_s,time_e)) ]))
                    self.N_filled[ind_day,ind_time] = int(np.sum([ x['N_filled'] for x in self.task_table.where("""(day == {:0d}) & (time_start <= {:0d}) & (time_end >= {:0d})""".format(day,time_s,time_e)) ]))
        except Exception as e:
            self.update_status(getLineInfo() + str(e))

    def close(self):
        self.h5file.close()

    def rowCount(self,index):
        if self.days is not None:
            return len(self.days)
        else: return 0

    def columnCount(self,index):
        if self.Nsteps is not None:
            return self.Nsteps
        else: return 0

    def data(self,index=QtCore.QModelIndex(),role=QtCore.Qt.DisplayRole):
        try:
            self.volunteer_table = self.h5file.get_node('/volunteers/volunteer_table')
            self.task_table = self.h5file.get_node('/tasks/tasks_table')

            if role==QtCore.Qt.DisplayRole:
                if self.view_type == 'N_needed':
                    return int(self.N_needed[index.row(),index.column()])
                elif self.view_type == 'N_filled':
                    return int(self.N_filled[index.row(), index.column()])
                elif self.view_type == '':
                    return QtCore.QVariant()
                else:
                    return QtCore.QVariant()




            elif role==QtCore.Qt.BackgroundRole:
                Nneeded = self.N_needed[index.row(), index.column()]
                Nfilled = self.N_filled[index.row(), index.column()]



                brush=QtGui.QBrush(QtCore.Qt.SolidPattern)
                if self.view_type == 'N_needed':
                    Ntot = np.max(self.N_needed[index.row(), :])
                    if Ntot==0:
                        Ntot=1
                    brush.setColor(self.colors.map(Nneeded/Ntot,mode='qcolor'))
                elif self.view_type == 'N_filled':
                    if Nneeded == 0:
                        Nneeded=1
                        Nfilled = 1
                        ratio = 0
                    else:
                        if Nfilled < Nneeded:
                            ratio = 1
                        else:
                            ratio = 0
                    brush.setColor(self.colors.map(ratio, mode='qcolor'))
                elif self.view_type == '':
                    return QtCore.QVariant()
                else:
                    vol_row = self.volunteer_table.get_where_list("""(name == {:})""".format(self.view_type.encode()))[
                        0]
                    tasks_row = [self.task_table.get_where_list("""(idnumber == {:})""".format(id))[0] for id in
                                 self.volunteer_table[vol_row]['affected_tasks'] if id != -1]
                    ts = []
                    te = []
                    flag = False
                    time_step = QtCore.QDateTime().fromSecsSinceEpoch(self.time_steps[index.column()]).addDays(
                        index.row()).toSecsSinceEpoch()
                    #Check in affected tasks if this timestep is used or not
                    for row in tasks_row:
                        if time_step >= self.task_table[row]['time_start'] and time_step < self.task_table[row]['time_end']:
                            flag = True
                            break
                    #check if this time step is available in the volunteer schedule
                    if  not(time_step >= self.volunteer_table[vol_row]['time_start'][index.row()] and time_step < self.volunteer_table[vol_row]['time_end'][index.row()]):
                        flag = True
                    if flag:
                        brush.setColor(QtGui.QColor(255,0,0))
                    else:
                        brush.setColor(QtGui.QColor(0,255,0))


                return brush
            else:
                return QtCore.QVariant()
        except Exception as e:
            return QtCore.QVariant()

    def headerData(self, section, orientation, role):
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                d = datetime.datetime.fromtimestamp(self.time_start + 60 * section * self.time_step)
                return d.strftime('%H:%M')
            else:
                d = datetime.datetime.fromtimestamp(self.days[section])
                return d.strftime('%A')
        else:
            return QtCore.QVariant()
