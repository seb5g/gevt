from pathlib import Path

from dateutil.parser import parse
from qtpy import QtWidgets, QtCore, QtGui


def select_file(start_path=None, save=True, ext=None):
    """
        Save or open a file with Qt5 file dialog, to be used within an Qt5 loop.

        =============== ======================================= ===========================================================================
        **Parameters**     **Type**                              **Description**

        *start_path*       Path object or str or None, optional  the path Qt5 will open in te dialog
        *save*             bool, optional                        * if True, a savefile dialog will open in order to set a savefilename
                                                                 * if False, a openfile dialog will open in order to open an existing file
        *ext*              str, optional                         the extension of the file to be saved or opened
        =============== ======================================= ===========================================================================

        Returns
        -------
        Path object
            the Path object pointing to the file



    """
    if ext is None:
        ext = '*'
    if not save:
        if type(ext) != list:
            ext = [ext]

        filter = "Data files ("
        for ext_tmp in ext:
            filter += '*.' + ext_tmp + " "
        filter += ")"
    if start_path is not None:
        if type(start_path) is not str:
            start_path = str(start_path)
    if save:
        fname = QtWidgets.QFileDialog.getSaveFileName(None, 'Enter a .' + ext + ' file name', start_path,
                                                      ext + " file (*." + ext + ")")
    else:
        fname = QtWidgets.QFileDialog.getOpenFileName(None, 'Select a file name', start_path, filter)

    fname = fname[0]
    if fname != '':  # execute if the user didn't cancel the file selection
        fname = Path(fname)
        if save:
            parent = fname.parent
            filename = fname.stem
            fname = parent.joinpath(filename + "." + ext)  # forcing the right extension on the filename
    return fname  # fname is a Path object


class TableView_clickonly(QtWidgets.QTableView):
    def __init__(self):
        super().__init__()

    def mouseMoveEvent(self, event):
        event.accept()


class FilterProxyDayTypeCustom(QtCore.QSortFilterProxyModel):

    def __init__(self,parent=None):
        super(FilterProxyDayTypeCustom,self).__init__(parent)

        self.target_timestamp=None

        self.dayRegExp=QtCore.QRegExp()
        self.typeRegExp=QtCore.QRegExp()

        self.dayRegExp.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.dayRegExp.setPatternSyntax(QtCore.QRegExp.Wildcard)

        self.typeRegExp.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.typeRegExp.setPatternSyntax(QtCore.QRegExp.Wildcard)

    def filterAcceptsRow(self,sourceRow, parent_index):
        dayIndex= self.sourceModel().index(sourceRow, 1, parent_index)
        typeIndex= self.sourceModel().index(sourceRow, 2, parent_index)
        id_index= self.sourceModel().index(sourceRow, 0, parent_index)
        ts_index= self.sourceModel().index(sourceRow, 4, parent_index)
        te_index = self.sourceModel().index(sourceRow, 5, parent_index)
        try:
            day= self.sourceModel().data(dayIndex)
            type_task= self.sourceModel().data(typeIndex)
            ts=int(parse(self.sourceModel().data(ts_index),dayfirst=True).timestamp())
            te = int(parse(self.sourceModel().data(te_index), dayfirst=True).timestamp())
            if self.target_timestamp is not None:
                return self.dayRegExp.pattern() in day and self.typeRegExp.pattern() in type_task and self.target_timestamp >= ts and self.target_timestamp < te
            else:
                return self.dayRegExp.pattern() in day and self.typeRegExp.pattern() in type_task
        except:
            return True

    def setTimeStampFilter(self,target_timestamp=None):
        self.target_timestamp=target_timestamp
        self.invalidateFilter()

    def setDayFilter(self,regexp):
        self.dayRegExp.setPattern(regexp)
        self.invalidateFilter()

    def setTypeFilter(self,regexp):
        self.typeRegExp.setPattern(regexp)
        self.invalidateFilter()


class MyMainWindow(QtWidgets.QMainWindow):
    closing = QtCore.Signal(QtGui.QCloseEvent)

    def __init__(self):
        super(MyMainWindow, self).__init__()

    def closeEvent(self, event):
        self.closing.emit(event)
