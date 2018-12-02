#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Sep 24 21:50:38 2018

@author: avargues-weber
"""

from PyQt5 import QtGui, QtWidgets, QtCore
from PyQt5.QtCore import Qt,QObject, pyqtSlot, QThread, pyqtSignal, QLocale, QDateTime, QSize, QTimer, QDate, QTime
import sys
import tables
import numpy as np
import csv
import datetime
from dateutil.parser import parse

MAX_DAYS=2


#%%

class Volunteer(tables.IsDescription):

    idnumber = tables.Int64Col(pos=0)
    name = tables.StringCol(128,pos=1)
    remarqs = tables.StringCol(128, pos=2)  #
    time_start  = tables.Time32Col(pos=4,shape=MAX_DAYS)
    time_end    = tables.Time32Col(pos=5,shape=MAX_DAYS)
    affected_tasks = tables.Int64Col(pos=3,shape=50,dflt=-1)

volunteer_dict={'idnumber': tables.Int64Col(shape=(), dflt=0, pos=0),
 'name': tables.StringCol(itemsize=128, shape=(), dflt=b'', pos=1),
 'remarqs': tables.StringCol(itemsize=128, shape=(), dflt=b'', pos=2),
 'present': tables.BoolCol(shape=(MAX_DAYS,), dflt= False, pos =4),
 'time_start': tables.Time32Col(shape=(MAX_DAYS,), dflt=0, pos=5),
 'time_end': tables.Time32Col(shape=(MAX_DAYS,), dflt=0, pos=6),
 'affected_tasks': tables.Int64Col(shape=(50,), dflt=-1, pos=3)}
#%%
class Tasks(tables.IsDescription):
    name      = tables.StringCol(128,pos=3)
    day      = tables.Time32Col(pos=1) 
    idnumber  = tables.Int64Col(pos=0)     
    task_type = tables.EnumCol(['welcoming', 'balisage', 'logistics', 'security' , 'race', 'other'], 'welcoming', 'int32',pos=2)
    time_start  = tables.Time32Col(pos=4)
    time_end    = tables.Time32Col(pos=5)
    N_needed    = tables.Int8Col(pos=6)
    N_filled  = tables.Int8Col(pos=7)
    remarqs = tables.StringCol(128,pos=8)   #
    stuff_needed = tables.StringCol(128,pos=9)   #
    affected_volunteers = tables.Int64Col(pos=10,shape=50,dflt=-1)

#%%
h5file=tables.open_file('RTA_2018.gev',mode='a',title='List of Tasks and volunteers for RTA 2018')
h5file.root._v_attrs['event_save_name'] = ""
h5file.root._v_attrs['event_name'] = "Raid Tout Absolu"
d=datetime.datetime(2018,9,8)
h5file.root._v_attrs['event_day'] = int(d.timestamp())
h5file.root._v_attrs['event_place'] = 'Fenouillet'
h5file.root._v_attrs['Ndays'] = MAX_DAYS
#%%
task_group=h5file.create_group('/','tasks','Tasks related stuff')
volunter_group=h5file.create_group('/','volunteers','Volunteers related stuff')

task_table = h5file.create_table(task_group, 'tasks_table', Tasks, "List of tasks")
volunteer_table = h5file.create_table(volunter_group, 'volunteer_table', volunteer_dict, "List of tasks")

#%%
vol=volunteer_table.row

def fill_in_time(header_day,string,time='start'):
    if string=='X':
        if time=='start':
            return int(parse(header_day+' '+'00:00:00',dayfirst=True).timestamp())
        else:
            return int(parse(header_day+' '+'23:59:59',dayfirst=True).timestamp())
    elif string=='':
        return -1
    else:
        return int(parse(header_day+' '+string,dayfirst=True).timestamp())
#%%
ind=vol.nrow-1
with open('volunteers.csv') as tsvfile:
    reader = csv.reader(tsvfile)
    header_days=next(reader,None)
    next(reader,None)
    for row in reader:
        ind+=1
        vol['name']=row[0].encode()
        vol['remarqs'] = row[1].encode()
        vol['time_start']=[fill_in_time(header_days[ind],row[ind],time='start') for ind in range(2,2*MAX_DAYS+2,2) ]
        vol['time_end']=[fill_in_time(header_days[ind],row[ind],time='end') for ind in range(3,2*MAX_DAYS+2,2) ]
        vol['idnumber']=ind
        print(vol['name'])
        print(vol['time_start'])
        print(vol['time_end'])
        vol.append()
volunteer_table.flush()
#%%
task_table=h5file.get_node('/tasks/tasks_table')
task=task_table.row

ind=task.nrow-1
with open('tasks.csv') as tsvfile:
    reader = csv.reader(tsvfile)
    for row in reader:
        ind+=1
        task['day']=int(parse(row[3],dayfirst=True).timestamp())
        task['name']=row[1].encode()
        task['task_type']=task_table.get_enum('task_type')[row[0]]
        task['idnumber']=ind
        task['time_start']=int(parse(row[3]+' '+row[4],dayfirst=True).timestamp())
        task['N_needed']=int(row[2])
        task['time_end']=int(parse(row[3]+' '+row[5],dayfirst=True).timestamp())
        task.append()
task_table.flush()


#%%
h5file.close()
