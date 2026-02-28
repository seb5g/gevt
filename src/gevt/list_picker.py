import logging

import numpy as np
from qtpy import QtCore, QtWidgets

from gevt.gui_utils import TableView_clickonly

from gevt.utils import get_overlap



class ListPicker(QtCore.QObject):

    def __init__(self, row=None, ts=None, te=None, picker_type='task', h5file=None, ids=None):
        super(ListPicker, self).__init__()
        self.picker_type = picker_type  # either 'task' or 'volunteer'
        self.h5file = h5file
        self.selected_ids = []
        self.row = row
        self.ts = ts
        self.te = te
        self.add = True  # True if pick dialog is called to add some element of the list,

        if h5file is not None:
            self.task_table = self.h5file.get_node('/tasks/tasks_table')
            self.volunteer_table = self.h5file.get_node('/volunteers/volunteer_table')
        else:
            raise Exception('No valid h5 file')
        if row is not None and ts is not None and te is not None:
            self.list_ids = self.check_availlable(row, ts, te)
        else:
            self.list_ids = ids

    def update_status(self, txt):
        logging.info(txt)

    def check_availlable(self,vol_row,time_start,time_end,selected_ids=[], id_to_not_check=None):

        id_list=[]
        if self.picker_type == 'task':
            affected_tasks_ids=[task for task in self.volunteer_table[vol_row]['affected_tasks'] if task!=-1]+selected_ids
            affected_tasks_times=[(task['time_start'],task['time_end']) for task in self.task_table if task['idnumber'] in affected_tasks_ids]

            for task_row in self.task_table:
                if task_row['N_filled']<task_row['N_needed']:

                    test = []
                    for ind in range(len(time_start)):
                        overlap = get_overlap([time_start[ind],time_end[ind]],[task_row['time_start'],task_row['time_end']])
                        test.append(overlap >= (task_row['time_end']-task_row['time_start']))
                        #test.append([time_start[ind]<=task_row['time_start'],time_end[ind]>=task_row['time_end']]) #test if this task (time_start,time_send) is compatible with volunteer presence

                    #test = np.any(np.all(test, 1))  # there is one slot available (but ùaybe other tasks collide....
                    test = np.any(test)
                    if test:
                        flag = False
                        for atime in affected_tasks_times:
                            if get_overlap([task_row['time_start'],task_row['time_end']],[atime[0], atime[1]]) > 0:
                                flag = True
                            #if task_row['time_start']<atime[1] and task_row['time_end']>atime[0]:
                                #flag = True
                        if not flag:
                            id_list.append(task_row['idnumber'])
        else:
            for vol_row in self.volunteer_table:
                affected_tasks_ids = [task for task in vol_row['affected_tasks'] if task != -1]
                if id_to_not_check is not None and id_to_not_check in affected_tasks_ids:
                    affected_tasks_ids.pop(affected_tasks_ids.index(id_to_not_check))
                affected_tasks_times = [(task['time_start'], task['time_end']) for task in self.task_table if
                                        task['idnumber'] in affected_tasks_ids]
                #TODO check if below is correct in differents  cases
                test = []
                for ind in range(vol_row['time_start'].size):
                    overlap = get_overlap([time_start, time_end], [vol_row['time_start'][ind], vol_row['time_end'][ind]])
                    test.append(overlap >= (time_end - time_start))
                #µtest = np.stack((time_start >= vol_row['time_start'], time_end <= vol_row['time_end']))  # test if this task (time_start,time_send) is compatible with volunteer presence
                test = np.any(test)  # there is one slot available (but ùaybe other tasks collide....

                test_other_tasks = [test]
                for atime in affected_tasks_times:
                    test_other_tasks.append(get_overlap([time_start, time_end], [atime[0], atime[1]]) <= 0)
                if np.all(test_other_tasks):
                    id_list.append(vol_row['idnumber'])

        return id_list

    def update_table(self, index):
        if self.picker_type == 'task':
            from gevt.tasks import TaskModel
            selected_indexes=self.table_view.selectedIndexes()
            selected_ids = [ind.data() for ind in selected_indexes if ind.column()==0]

            valid_tasks_ids=self.check_availlable(self.row,self.ts,self.te,selected_ids)+selected_ids
            valid_tasks_ids.sort()
            model = TaskModel(self.h5file, valid_tasks_ids)
            self.table_view.setModel(model)

            for row in range(len(valid_tasks_ids)):
                if int(self.table_view.model().createIndex(row,0).data()) in selected_ids:
                    self.table_view.selectRow(row)

        elif self.picker_type == 'volunteer':
            selected_cols = set([index.row() for index in self.table_view.selectedIndexes()])
            if self.add:
                N_more_needed = self.task_table[self.row]['N_needed'] - len(selected_cols) - self.task_table[self.row]['N_filled']
                self.Nmore_needed_sb.setValue(N_more_needed)
                if N_more_needed <= 0:
                    self.Nmore_needed_sb.setStyleSheet("background-color: rgba(0,255,0,255)")
                else:
                    self.Nmore_needed_sb.setStyleSheet("background-color: red")

        else:
            raise Exception('invalid picker type')


    def pick_dialog(self,connect=True, add=True, select_extended=True):

        self.add = add
        self.dialog = QtWidgets.QDialog()
        self.dialog.setMinimumWidth(500)
        vlayout = QtWidgets.QVBoxLayout()
        form = QtWidgets.QWidget()
        hlayout = QtWidgets.QHBoxLayout()
        if self.picker_type == 'task':
            pick_type_label = QtWidgets.QLabel('Pick some tasks for your volunteer (Ctrl+left click to select/deselect)')
        else:
            pick_type_label = QtWidgets.QLabel('Pick some volunteers for this task (Ctrl+left click to select/deselect)')
        hlayout.addWidget(pick_type_label)
        if self.picker_type != 'task' and self.add:
            N_more_needed = self.task_table[self.row]['N_needed'] - self.task_table[self.row]['N_filled']
            self.Nmore_needed_sb = QtWidgets.QSpinBox()
            self.Nmore_needed_sb.setMaximumWidth(100)
            self.Nmore_needed_sb.setToolTip('Remaining number of volunteers to pick')
            self.Nmore_needed_sb.setValue(N_more_needed)
            if N_more_needed <= 0:
                self.Nmore_needed_sb.setStyleSheet("background-color: rgba(0,255,0,255)")
            else:
                self.Nmore_needed_sb.setStyleSheet("background-color: red")
            hlayout.addWidget(self.Nmore_needed_sb)

        form.setLayout(hlayout)
        vlayout.addWidget(form)

        self.table_view=TableView_clickonly()
        self.table_view.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        if self.picker_type == 'task':
            from gevt.tasks import TaskModel
            model = TaskModel(self.h5file, self.list_ids)
        else:
            from gevt.volunteers import VolunteerModel
            model = VolunteerModel(self.h5file, self.h5file.root._v_attrs['Ndays'], self.list_ids)

        sortproxy = QtCore.QSortFilterProxyModel()
        sortproxy.setSourceModel(model)
        self.table_view.setModel(sortproxy)
        self.table_view.setSortingEnabled(True)

        if select_extended:
            self.table_view.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        else:
            self.table_view.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)

        self.table_view.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)

        if connect:
            self.table_view.clicked.connect(self.update_table)


        vlayout.addWidget(self.table_view, 10)
        self.dialog.setLayout(vlayout)

        buttonBox = QtWidgets.QDialogButtonBox();
        buttonBox.addButton('Apply', buttonBox.AcceptRole)
        buttonBox.accepted.connect(self.dialog.accept)
        buttonBox.addButton('Cancel', buttonBox.RejectRole)
        buttonBox.rejected.connect(self.dialog.reject)

        vlayout.addWidget(buttonBox)
        if self.picker_type == 'task':
            self.dialog.setWindowTitle('Select available tasks')
        else:
            self.dialog.setWindowTitle('Select available volunteers')
        res = self.dialog.exec()

        pass
        if res == self.dialog.Accepted:
            # save managers parameters in a xml file
            return  [int(ind.data()) for ind in self.table_view.selectedIndexes() if ind.column()==0]
        else:
            return []
