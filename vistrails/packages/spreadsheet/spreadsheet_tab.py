############################################################################
##
## Copyright (C) 2006-2007 University of Utah. All rights reserved.
##
## This file is part of VisTrails.
##
## This file may be used under the terms of the GNU General Public
## License version 2.0 as published by the Free Software Foundation
## and appearing in the file LICENSE.GPL included in the packaging of
## this file.  Please review the following to ensure GNU General Public
## Licensing requirements will be met:
## http://www.opensource.org/licenses/gpl-license.php
##
## If you are unsure which license is appropriate for your use (for
## instance, you are interested in developing a commercial derivative
## of VisTrails), please contact us at vistrails@sci.utah.edu.
##
## This file is provided AS IS with NO WARRANTY OF ANY KIND, INCLUDING THE
## WARRANTY OF DESIGN, MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.
##
############################################################################
################################################################################
# This file contains classes controlling tabs in the spreadsheets. A tab is
# a container of a sheet:
#   SizeSpinBox
#   StandardTabDockWidget
#   StandardWidgetSheetTab
#   StandardWidgetTabBar
#   StandardWidgetTabBarEditor
#   StandardWidgetToolBar
################################################################################
from PyQt4 import QtCore, QtGui
from spreadsheet_registry import spreadsheetRegistry
from spreadsheet_sheet import StandardWidgetSheet
from spreadsheet_cell import QCellPresenter
import spreadsheet_rc
from core.interpreter.default import default_interpreter
from core.utils import DummyView
from core.vistrail.action import AddModuleAction, AddConnectionAction, \
     DeleteConnectionAction, ChangeParameterAction
from core.vistrail import module
from core.vistrail import connection
from core.modules.module_registry import registry
import copy

################################################################################

class SizeSpinBox(QtGui.QSpinBox):
    """
    SizeSpinBox is just an overrided spin box that will also emit
    'editingFinished()' signal when the user interact with mouse
    
    """    
    def __init__(self, initValue=0, parent=None):
        """ SizeSpinBox(initValue: int, parent: QWidget) -> SizeSpinBox
        Initialize with a default width of 50 and a value of 0
        
        """
        QtGui.QSpinBox.__init__(self, parent)
        self.setMinimum(1)
        self.setMinimumWidth(50)
        self.setMaximumWidth(50)
        self.setValue(initValue)

    def mouseReleaseEvent(self, event):
        """ mouseReleaseEvent(event: QMouseEvent) -> None
        Emit 'editingFinished()' signal when the user release a mouse button
        
        """
        QtGui.QSpinBox.mouseReleaseEvent(self, event)
        self.emit(QtCore.SIGNAL("editingFinished()"))        

class StandardWidgetToolBar(QtGui.QToolBar):
    """
    StandardWidgetToolBar: The default toolbar for each sheet
    ontainer. By default, only FitToWindow and Table resizing are
    included
    
    """
    def __init__(self, parent=None):
        """ StandardWidgetToolBar(parent: QWidget) -> StandardWidgetToolBar
        Init the toolbar with default actions
        
        """
        QtGui.QToolBar.__init__(self, parent)
        self.sheetTab = parent
        self.addAction(self.fitToWindowAction())
        self.addWidget(self.rowCountSpinBox())
        self.addWidget(self.colCountSpinBox())
        self.layout().setSpacing(2)
        
    def fitToWindowAction(self):
        """ fitToWindowAction() -> QAction
        Return the fit to window action
        
        """
        if not hasattr(self, 'fitAction'):
            icon = QtGui.QIcon(':/images/fittowindow.png')
            self.fitAction = QtGui.QAction(icon, 'Fit to window', self)
            self.fitAction.setStatusTip('Stretch spreadsheet cells '
                                        'to fit the window size')
            self.fitAction.setCheckable(True)
            self.fitAction.setChecked(self.sheetTab.sheet.fitToWindow)
            self.connect(self.fitAction,
                         QtCore.SIGNAL('toggled(bool)'),
                         self.fitActionToggled)
        return self.fitAction

    def fitActionToggled(self, checked):
        """ fitActionToggled(checked: boolean) -> None
        Handle fitToWindow Action toggled
        
        """
        self.sheetTab.sheet.setFitToWindow(checked)
    
    def rowCountSpinBox(self):
        """ rowCountSpinBox() -> SizeSpinBox
        Return the row spin box widget:
        
        """
        if not hasattr(self, 'rowSpinBox'):
            self.rowSpinBox = SizeSpinBox(self.sheetTab.sheet.rowCount())
            self.rowSpinBox.setToolTip('The number of rows')
            self.rowSpinBox.setStatusTip('Change the number of rows '
                                         'of the current sheet')
            self.connect(self.rowSpinBox,
                         QtCore.SIGNAL('editingFinished()'),
                         self.sheetTab.rowSpinBoxChanged)
        return self.rowSpinBox

    def colCountSpinBox(self):
        """ colCountSpinBox() -> SizeSpinBox
        Return the column spin box widget:
        
        """
        if not hasattr(self, 'colSpinBox'):
            self.colSpinBox = SizeSpinBox(self.sheetTab.sheet.columnCount())
            self.colSpinBox.setToolTip('The number of columns')
            self.colSpinBox.setStatusTip('Change the number of columns '
                                         'of the current sheet')
            self.connect(self.colSpinBox,
                         QtCore.SIGNAL('editingFinished()'),
                         self.sheetTab.colSpinBoxChanged)
        return self.colSpinBox

class FilterDeferredDeleteObject(QtCore.QObject):
    
    def eventFilter(self, obj, event):
        """ eventFilter(obj: QObject, event: QEvent) -> bool
        Prevent the cell widget to be deleted by DeferredDelete Event
        
        """
        if event.type()==QtCore.QEvent.DeferredDelete:
            return True
        else:
            return QtGui.QWidget.eventFilter(self, obj, event)
    
        
class StandardWidgetSheetTabInterface(object):
    """
    StandardWidgetSheetTabInterface is the interface for tab
    controller to call for manipulating a tab
    
    """
    ### Belows are API Wrappers to connect to self.sheet

    def isSheetTabWidget(self):
        """ isSheetTabWidget() -> boolean
        Return True if this is a sheet tab widget
        """
        return True

    def getDimension(self):
        """ getDimension() -> tuple
        Get the sheet dimensions
        
        """
        return (0,0)
            
    def setDimension(self, rc, cc):
        """ setDimension(rc: int, cc: int) -> None
        Set the sheet dimensions
        
        """
        pass
            
    def getCell(self, row, col):
        """ getCell(row: int, col: int) -> QWidget
        Get cell at a specific row and column.
        
        """
        return None

    def getCellToolBar(self, row, col):
        """ getCellToolBar(row: int, col: int) -> QWidget
        Return the toolbar widget at cell location (row, col)
        
        """
        return None

    def getCellRect(self, row, col):
        """ getCellRect(row: int, col: int) -> QRect
        Return the rectangle surrounding the cell at location (row, col)
        in parent coordinates
        
        """
        return QtCore.QRect()

    def getCellGlobalRect(self, row, col):
        """ getCellGlobalRect(row: int, col: int) -> QRect
        Return the rectangle surrounding the cell at location (row, col)
        in global coordinates
        
        """
        return QtCore.QRect()

    def getFreeCell(self):
        """ getFreeCell() -> tuple
        Get a free cell location (row, col) on the spreadsheet 

        """
        (rowCount, colCount) = self.getDimension()
        for r in range(rowCount):
            for c in range(colCount):
                w = self.getCell(r, c)
                row = self.sheet.verticalHeader().logicalIndex(r)
                col = self.sheet.horizontalHeader().logicalIndex(c)
                if w==None or (type(w)==QCellPresenter and w.cellWidget==None):
                    return (r,c)
        return (0, 0)

    def setCellByType(self, row, col, cellType, inputPorts):
        """ setCellByType(row: int,
                          col: int,
                          cellType: a type inherits from QWidget,
                          inpurPorts: tuple) -> None                          
        Replace the current location (row, col) with a cell of
        cellType. If the current type of that cell is the same as
        cellType, only the contents is updated with inputPorts.
        
        """
        pass

    def showHelpers(self, ctrl, globalPos):
        """ showHelpers(ctrl: boolean, globalPos: QPoint) -> None
        Show the helpers (toolbar, resizer) when the Control key
        status is ctrl and the mouse is at globalPos
        
        """
        pass

    def setCellPipelineInfo(self, row, col, info):
        """ setCellPipelineInfo(row: int, col: int, info: any type) -> None        
        Provide a way for the spreadsheet to store vistrail
        information, info, for the cell (row, col)
        
        """
        if not (row,col) in self.pipelineInfo:
            self.pipelineInfo[(row,col)] = {}
        self.pipelineInfo[(row,col)] = info

    def getCellPipelineInfo(self, row, col):
        """ getCellPipelineInfo(row: int, col: int) -> any type        
        Provide a way for the spreadsheet to extract vistrail
        information, info, for the cell (row, col)
        
        """        
        if not (row,col) in self.pipelineInfo:
            return None
        return self.pipelineInfo[(row,col)]

    def getSelectedLocations(self):
        """ getSelectedLocations() -> tuple
        Return the selected locations (row, col) of the current sheet
        
        """
        return []

    def deleteAllCells(self):
        """ deleteAllCells() -> None
        Delete all cells in the sheet
        
        """
        (rowCount, columnCount) = self.getDimension()
        for r in range(rowCount):
            for c in range(columnCount):
                self.setCellByType(r, c, None, None)

    def takeCell(self, row, col):
        """ takeCell(row, col) -> QWidget        
        Free the cell widget at (row, col) from the tab and return as
        the result of the function. If there is no widget at (row,
        col). This returns None. The ownership of the widget is passed
        to the caller.
        
        """
        cell = self.getCell(row, col)
        if cell:
            obj = FilterDeferredDeleteObject()
            cell.installEventFilter(obj)
            self.setCellByWidget(row, col, None)
            QtCore.QCoreApplication.processEvents(
                QtCore.QEventLoop.DeferredDeletion)
            cell.removeEventFilter(obj)
            obj.deleteLater()
        return cell

    def setCellByWidget(self, row, col, cellWidget):
        """ setCellByWidget(row: int,
                            col: int,                            
                            cellWidget: QWidget) -> None 
        Replace the current location (row, col) with a cell widget
        
        """
        pass

    def setCellEditingMode(self, r, c, editing=True):
        """ setCellEditingMode(r: int, c: int, editing: bool) -> None
        Turn on/off the editing mode of a single cell
        
        """
        if editing:
            cellWidget = self.getCell(r, c)
            if type(cellWidget)==QCellPresenter:
                return
            presenter = QCellPresenter()
            presenter.assignCell(self, r, c)
            cellWidget = self.takeCell(r, c)
            self.setCellByWidget(r, c, presenter)
            if cellWidget:
                cellWidget.hide()
        else:
            presenter = self.getCell(r, c)
            if type(presenter)!=QCellPresenter:
                return
            if presenter:
                cellWidget = presenter.releaseCellWidget()
                self.setCellByWidget(r, c, cellWidget)
        
    
    def setEditingMode(self, editing=True):
        """ setEditingMode(editing: bool) -> None
        Turn on/off the editing mode of the tab
        
        """
        # Go over all the cells and set the editing widget up
        (rowCount, colCount) = self.getDimension()
        for r in range(rowCount):
            for c in range(colCount):
                self.setCellEditingMode(r, c, editing)
        QtCore.QCoreApplication.processEvents()

    def swapCell(self, row, col, newSheet, newRow, newCol):
        """ swapCell(row, col: int, newSheet: Sheet,
                     newRow, newCol: int) -> None
        Swap the (row, col) of this sheet to (newRow, newCol) of newSheet
        
        """
        myWidget = self.takeCell(row, col)
        theirWidget = newSheet.takeCell(newRow, newCol)
        self.setCellByWidget(row, col, theirWidget)
        newSheet.setCellByWidget(newRow, newCol, myWidget)
        info = self.getCellPipelineInfo(row, col)
        self.setCellPipelineInfo(row, col,
                                 newSheet.getCellPipelineInfo(newRow, newCol))
        newSheet.setCellPipelineInfo(newRow, newCol, info)        

    def copyCell(self, row, col, newSheet, newRow, newCol):
        """ copyCell(row, col: int, newSheet: Sheet,
                     newRow, newCol: int) -> None
        Copy the (row, col) of this sheet to (newRow, newCol) of newSheet
        
        """
        info = self.getCellPipelineInfo(row, col)
        if info:
            info = info[0]
            mId = info['moduleId']
            pipeline = newSheet.setPipelineToLocateAt(newRow, newCol,
                                                      info['pipeline'], [mId])

            totalProgress = len(pipeline.graph.inverse().bfs(mId))+1
            progress = QtGui.QProgressDialog('Copying...',
                                             '&Cancel',
                                             0, totalProgress)
            progress.setWindowTitle('Copy Cell')
            progress.setWindowModality(QtCore.Qt.WindowModal)
            progress.show()
            interpreter = default_interpreter.get()
            def moduleExecuted(objId):
                if not progress.wasCanceled():
                    progress.setValue(progress.value()+1)
                    QtCore.QCoreApplication.processEvents()
            interpreter.execute(pipeline,
                                info['vistrailName'],
                                info['version'],
                                DummyView(),
                                moduleExecutedHook = [moduleExecuted],
                                reason=info['reason'],
                                actions=info['actions'],
                                sinks=[mId])
            progress.setValue(totalProgress)

    def executePipelineToCell(self, pInfo, row, col, reason=''):
        """ executePipelineToCell(p: tuple, row: int, col: int) -> None
        p: (vistrailName, version, actions, pipeline)
        
        Execute a pipeline and put all of its cell to (row, col). This
        need to be fixed to layout all cells inside the pipeline
        
        """        
        pipeline = self.setPipelineToLocateAt(row, col, pInfo[3])

        totalProgress = len(pipeline.modules)
        progress = QtGui.QProgressDialog('Executing...',
                                         '&Cancel',
                                         0, totalProgress)
        progress.setWindowTitle('Execute Cell')
        progress.setWindowModality(QtCore.Qt.WindowModal)
        progress.show()
        def moduleExecuted(objId):
            if not progress.wasCanceled():
                progress.setValue(progress.value()+1)
                QtCore.QCoreApplication.processEvents()
        interpreter = default_interpreter.get()
        interpreter.execute(pipeline,
                            pInfo[0], pInfo[1],
                            DummyView(),
                            moduleExecutedHook = [moduleExecuted],
                            actions=pInfo[2],
                            reason=reason)
        progress.setValue(totalProgress)

    def setPipelineToLocateAt(self, row, col, inPipeline, cellIds=[]):
        """ setPipelineToLocateAt(row: int, col: int, inPipeline: Pipeline,
                                  cellIds: [ids]) -> Pipeline                                  
        Modify the pipeline to have its cells (provided by cellIds) to
        be located at (row, col) of this sheet
        
        """
        sheetName = str(self.tabWidget.tabText(self.tabWidget.indexOf(self)))
        pipeline = copy.copy(inPipeline)
        if cellIds==[]:
            cellIds = pipeline.modules.keys()
        SpreadsheetCell = registry.getDescriptorByName('SpreadsheetCell').module
        for mId in cellIds:
            md = pipeline.modules[mId]
            moduleClass = registry.getDescriptorByName(md.name).module
            if not issubclass(moduleClass, SpreadsheetCell):
                continue
            # Walk through all connection and remove all
            # CellLocation connected to this spreadsheet cell
            delConn = DeleteConnectionAction()
            for (cId,c) in pipeline.connections.iteritems():
                if (c.destinationId==mId and
                    pipeline.modules[c.sourceId].name=="CellLocation"):
                    delConn.addId(cId)
            delConn.perform(pipeline)

            # Add a sheet reference with a specific name
            sheetReference = module.Module()
            sheetReference.id = pipeline.fresh_module_id()
            sheetReference.name = "SheetReference"
            addModule = AddModuleAction()
            addModule.module = sheetReference
            addModule.perform(pipeline)
            addParam = ChangeParameterAction()
            addParam.addParameter(sheetReference.id, 0, 0,
                                  "SheetName", "", sheetName, "String", "" )
            addParam.addParameter(sheetReference.id, 1, 0,
                                  "MinRowCount", "",
                                  str(row+1), "Integer", "" )
            addParam.addParameter(sheetReference.id, 2, 0,
                                  "MinColumnCount", "",
                                  str(col+1), "Integer", "" )
            addParam.perform(pipeline)

            # Add a cell location module with a specific row and column
            cellLocation = module.Module()
            cellLocation.id = pipeline.fresh_module_id()
            cellLocation.name = "CellLocation"
            addModule = AddModuleAction()
            addModule.module = cellLocation
            addModule.perform(pipeline)

            addParam = ChangeParameterAction()                
            addParam.addParameter(cellLocation.id, 0, 0,
                                  "Row", "", str(row+1),
                                  "Integer", "" )
            addParam.addParameter(cellLocation.id, 1, 0,
                                  "Column", "", str(col+1),
                                  "Integer", "" )
            addParam.perform(pipeline)

            # Then connect the SheetReference to the CellLocation
            conn = connection.Connection()
            conn.id = pipeline.fresh_connection_id()
            conn.source.moduleId = sheetReference.id
            conn.source.moduleName = sheetReference.name
            conn.source.name = "self"
            conn.source.spec = registry.getOutputPortSpec(
                sheetReference, "self")
            conn.connectionId = conn.id
            conn.destination.moduleId = cellLocation.id
            conn.destination.moduleName = cellLocation.name
            conn.destination.name = "SheetReference"
            conn.destination.spec = registry.getInputPortSpec(
                cellLocation, "SheetReference")
            addConnection = AddConnectionAction()
            addConnection.connection = conn
            addConnection.perform(pipeline)

            # Then connect the CellLocation to the spreadsheet cell
            conn = connection.Connection()
            conn.id = pipeline.fresh_connection_id()
            conn.source.moduleId = cellLocation.id
            conn.source.moduleName = cellLocation.name
            conn.source.name = "self"
            conn.source.spec = registry.getOutputPortSpec(
                cellLocation, "self")
            conn.connectionId = conn.id
            conn.destination.moduleId = mId
            conn.destination.moduleName = pipeline.modules[mId].name
            conn.destination.name = "Location"
            conn.destination.spec = registry.getInputPortSpec(
                cellLocation, "Location")
            addConnection = AddConnectionAction()
            addConnection.connection = conn
            addConnection.perform(pipeline)
        return pipeline

    def getPipelineInfo(self, row, col):
        """ getPipelineInfo(row: int, col: int) -> tuple
        Return (vistrailName, versionNumber, actions, pipeline) for a cell
        
        """
        info = self.getCellPipelineInfo(row, col)
        if info:
            return (info[0]['vistrailName'],
                    info[0]['version'],
                    info[0]['actions'],
                    info[0]['pipeline'])
        return None

class StandardWidgetSheetTab(QtGui.QWidget, StandardWidgetSheetTabInterface):
    """
    StandardWidgetSheetTab is a container of StandardWidgetSheet with
    a toolbar on top. This will be added directly to a QTabWidget for
    displaying the spreadsheet.
    
    """
    def __init__(self, tabWidget, row=2, col=3):
        """ StandardWidgetSheet(tabWidget: QTabWidget,
                                row: int,
                                col: int) -> StandardWidgetSheet
        Initialize with a toolbar and a sheet widget
                                
        """
        QtGui.QWidget.__init__(self, None)
        self.type = 'StandardWidgetSheetTab'
        self.tabWidget = tabWidget
        self.sheet = StandardWidgetSheet(row, col, self)
        self.sheet.setFitToWindow(True)
        self.toolBar = StandardWidgetToolBar(self)
        self.vLayout = QtGui.QVBoxLayout()
        self.vLayout.setSpacing(0)
        self.vLayout.setMargin(0)
        self.vLayout.addWidget(self.toolBar, 0)
        self.vLayout.addWidget(self.sheet, 1)
        self.setLayout(self.vLayout)
        self.pipelineInfo = {}

    def rowSpinBoxChanged(self):
        """ rowSpinBoxChanged() -> None
        Handle the number of row changed
        
        """
        if self.toolBar.rowSpinBox.value()!=self.sheet.rowCount():
            self.sheet.setRowCount(self.toolBar.rowSpinBox.value())
            self.sheet.stretchCells()
            self.setEditingMode(self.tabWidget.editingMode)
        
    def colSpinBoxChanged(self):
        """ colSpinBoxChanged() -> None
        Handle the number of row changed
        
        """
        if self.toolBar.colSpinBox.value()!=self.sheet.columnCount():
            self.sheet.setColumnCount(self.toolBar.colSpinBox.value())
            self.sheet.stretchCells()
            self.setEditingMode(self.tabWidget.editingMode)

    ### Belows are API Wrappers to connect to self.sheet

    def getDimension(self):
        """ getDimension() -> tuple
        Get the sheet dimensions
        
        """
        return (self.sheet.rowCount(), self.sheet.columnCount())
            
    def setDimension(self, rc, cc):
        """ setDimension(rc: int, cc: int) -> None
        Set the sheet dimensions
        
        """
        self.toolBar.rowCountSpinBox().setValue(rc)
        self.toolBar.colCountSpinBox().setValue(cc)
            
    def getCell(self, row, col):
        """ getCell(row: int, col: int) -> QWidget
        Get cell at a specific row and column.
        
        """
        return self.sheet.getCell(row, col)

    def getCellToolBar(self, row, col):
        """ getCellToolBar(row: int, col: int) -> QWidget
        Return the toolbar widget at cell location (row, col)
        
        """
        return self.sheet.getCellToolBar(row, col)

    def getCellRect(self, row, col):
        """ getCellRect(row: int, col: int) -> QRect
        Return the rectangle surrounding the cell at location (row, col)
        in parent coordinates
        
        """
        return self.sheet.getCellRect(row, col)

    def getCellGlobalRect(self, row, col):
        """ getCellGlobalRect(row: int, col: int) -> QRect
        Return the rectangle surrounding the cell at location (row, col)
        in global coordinates
        
        """
        return self.sheet.getCellGlobalRect(row, col)

    def setCellByType(self, row, col, cellType, inputPorts):
        """ setCellByType(row: int,
                          col: int,
                          cellType: a type inherits from QWidget,
                          inpurPorts: tuple) -> None                          
        Replace the current location (row, col) with a cell of
        cellType. If the current type of that cell is the same as
        cellType, only the contents is updated with inputPorts.
        
        """
        self.sheet.setCellByType(row, col, cellType, inputPorts)

    def showHelpers(self, ctrl, globalPos):
        """ showHelpers(ctrl: boolean, globalPos: QPoint) -> None
        Show the helpers (toolbar, resizer) when the Control key
        status is ctrl and the mouse is at globalPos
        
        """
        localPos = self.sheet.viewport().mapFromGlobal(QtGui.QCursor.pos())
        row = self.sheet.rowAt(localPos.y())
        col = self.sheet.columnAt(localPos.x())
        self.sheet.showHelpers(ctrl, row, col)
        
    def getSelectedLocations(self):
        """ getSelectedLocations() -> tuple
        Return the selected locations (row, col) of the current sheet
        
        """
        indexes = self.sheet.selectedIndexes()
        return [(idx.row(), idx.column()) for idx in indexes]

    def setCellByWidget(self, row, col, cellWidget):
        """ setCellByWidget(row: int,
                            col: int,                            
                            cellWidget: QWidget) -> None                            
        Replace the current location (row, col) with a cell widget
        
        """
        if cellWidget:
            # Relax the size constraint of the widget
            cellWidget.setMinimumSize(QtCore.QSize(0, 0))
            cellWidget.setMaximumSize(QtCore.QSize(16777215, 16777215))
        self.sheet.setCellByWidget(row, col, cellWidget)

class StandardWidgetTabBarEditor(QtGui.QLineEdit):    
    """
    StandardWidgetTabBarEditor overrides QLineEdit to enable canceling
    edit when Esc is pressed
    
    """
    def __init__(self, text='', parent=None):
        """ StandardWidgetTabBarEditor(text: str, parent: QWidget)
                                       -> StandardWidgetTabBarEditor
        Store the original text at during initialization
        
        """
        QtGui.QLineEdit.__init__(self, text, parent)
        self.originalText = text

    def keyPressEvent(self, e):
        """ keyPressEvent(e: QKeyEvent) -> None
        Override keyPressEvent to handle Esc key
        
        """
        if e.key()==QtCore.Qt.Key_Escape:
            e.ignore()
            self.setText(self.originalText)
            self.clearFocus()
        else:
            QtGui.QLineEdit.keyPressEvent(self, e)

class StandardWidgetTabBar(QtGui.QTabBar):
    """
    StandardWidgetTabBar: a customized QTabBar to allow double-click
    to change tab name
    
    """
    def __init__(self, parent=None):
        """ StandardWidgetTabBar(parent: QWidget) -> StandardWidgetTabBar
        Initialize like the original QTabWidget TabBar
        
        """
        QtGui.QTabBar.__init__(self, parent)
        self.setAcceptDrops(True)
        self.setStatusTip('Move the sheet in, out and around'
                          'by dragging the tabs')
        self.setDrawBase(False)
        self.editingIndex = -1
        self.editor = None        
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.connect(self, QtCore.SIGNAL('currentChanged(int)'),
                     self.updateTabText)
        self.startDragPos = None
        self.dragging = False
        self.targetTab = -1
        self.innerRubberBand = QtGui.QRubberBand(QtGui.QRubberBand.Rectangle,
                                                 self)
        self.outerRubberBand = QtGui.QRubberBand(QtGui.QRubberBand.Rectangle,
                                                 None)

    def mouseDoubleClickEvent(self, e):
        """ mouseDoubleClickEvent(e: QMouseEvent) -> None
        Handle Double-Click event to start the editor
        
        """
        if e.buttons()!=QtCore.Qt.LeftButton or self.editor: return
        
        # Update the current editing tab widget
        self.editingIndex = self.currentIndex()
        
        # A hack to capture the rect of the triangular tab from commonstyle.cpp
        rect = self.tabRect(self.editingIndex)
        h = rect.height()-2
        dx = h/3 + 3
        rect.adjust(dx+1,1,-dx,-1)

        # Display the editor inplace of the tab text
        text = self.tabText(self.editingIndex)
        self.editor = StandardWidgetTabBarEditor(text, self)
        self.editor.setFont(self.font())
        self.editor.setFrame(False)
        self.editor.setGeometry(rect)
        self.editor.setAlignment(QtCore.Qt.AlignHCenter)
        self.editor.selectAll()
        self.connect(self.editor, QtCore.SIGNAL('editingFinished()'),
                     self.updateTabText)
        self.editor.show()
        self.editor.setFocus(QtCore.Qt.MouseFocusReason)

    def updateTabText(self, idx=0):
        """ updateTabText(idx: int) -> None
        Update the tab text after editing has been finished
        
        """
        if self.editingIndex>=0 and self.editor:
            self.setTabText(self.editingIndex, self.editor.text())
            self.emit(QtCore.SIGNAL('tabTextChanged(int,QString)'),
                      self.editingIndex,self.editor.text())
            self.editor.deleteLater()
            self.editingIndex = -1
            self.editor = None

    def indexAtPos(self, p):
        """ indexAtPos(p: QPoint) -> int Reimplement of the private
        indexAtPos to find the tab index under a point
        
        """
        if self.tabRect(self.currentIndex()).contains(p):
            return self.currentIndex()
        for i in range(self.count()):
            if self.isTabEnabled(i) and self.tabRect(i).contains(p):                
                return i
        return -1;

    def mousePressEvent(self, e):
        """ mousePressEvent(e: QMouseEvent) -> None
        Handle mouse press event to see if we should start to drag tabs or not
        
        """
        QtGui.QTabBar.mousePressEvent(self, e)
        if e.buttons()==QtCore.Qt.LeftButton and self.editor==None:
            self.startDragPos = QtCore.QPoint(e.x(), e.y())

    def getGlobalRect(self, index):
        """ getGlobalRect(self, index: int)
        Get the rectangle of a tab in global coordinates
        
        """
        if index<0: return None
        rect = self.tabRect(index)
        rect.moveTo(self.mapToGlobal(rect.topLeft()))
        return rect

    def highlightTab(self, index):
        """ highlightTab(index: int)
        Highlight the rubber band of a tab
        
        """
        if index==-1:
            self.innerRubberBand.hide()
        else:
            self.innerRubberBand.setGeometry(self.tabRect(index))
            self.innerRubberBand.show()
            
    def mouseMoveEvent(self, e):
        """ mouseMoveEvent(e: QMouseEvent) -> None
        Handle dragging tabs in and out or around
        
        """
        QtGui.QTabBar.mouseMoveEvent(self, e)
        if self.startDragPos:
            # We already move more than 4 pixels
            if (self.startDragPos-e.pos()).manhattanLength()>=4:
                self.startDragPos = None
                self.dragging = True
        if self.dragging:
            t = self.indexAtPos(e.pos())
            if t!=-1:
                if t!=self.targetTab:                    
                    self.targetTab = t
                    self.outerRubberBand.hide()
                    self.highlightTab(t)
            else:
                self.highlightTab(-1)
                if t!=self.targetTab:
                    self.targetTab = t
                if self.count()>0:
                    if not self.outerRubberBand.isVisible():
                        index = self.getGlobalRect(self.currentIndex())
                        self.outerRubberBand.setGeometry(index)
                        self.outerRubberBand.move(e.globalPos())
                        self.outerRubberBand.show()
                    else:
                        self.outerRubberBand.move(e.globalPos())

    def mouseReleaseEvent(self, e):
        """ mouseReleaseEvent(e: QMouseEvent) -> None
        Make sure the tab moved at the end
        
        """
        QtGui.QTabBar.mouseReleaseEvent(self, e)
        if self.dragging:
            if self.targetTab!=-1 and self.targetTab!=self.currentIndex():
                self.emit(QtCore.SIGNAL('tabMoveRequest(int,int)'),
                          self.currentIndex(),
                          self.targetTab)
            elif self.targetTab==-1:
                self.emit(QtCore.SIGNAL('tabSplitRequest(int,QPoint)'),
                          self.currentIndex(),
                          e.globalPos())
            self.dragging = False
            self.targetTab = -1
            self.highlightTab(-1)
            self.outerRubberBand.hide()
            
    def slotIndex(self, pos):
        """ slotIndex(pos: QPoint) -> int
        Return the slot index between the slots at the cursor pos
        
        """
        p = self.mapFromGlobal(pos)
        for i in range(self.count()):
            r = self.tabRect(i)
            if self.isTabEnabled(i) and r.contains(p):
                if p.x()<(r.x()+r.width()/2):
                    return i
                else:
                    return i+1
        return -1
        
    def slotGeometry(self, idx):
        """ slotGeometry(idx: int) -> QRect
        Return the geometry between the slots at cursor pos
        
        """
        if idx<0 or self.count()==0: return None
        if idx<self.count():
            rect = self.getGlobalRect(idx)
            rect = QtCore.QRect(rect.x()-5, rect.y(), 5*2, rect.height())
            return rect
        else:
            rect = self.getGlobalRect(self.count()-1)
            rect = QtCore.QRect(rect.x()+rect.width()-5, rect.y(),
                                5*2, rect.height())
            return rect

    def dragEnterEvent(self, event):
        """ dragEnterEvent(event: QDragEnterEvent) -> None
        Set to accept drops from the other cell info
        
        """
        mimeData = event.mimeData()
        if hasattr(mimeData, 'cellInfo'):
            event.setDropAction(QtCore.Qt.MoveAction)
            event.accept()
            idx = self.indexAtPos(event.pos())
            if idx>=0:
                self.setCurrentIndex(idx)
        else:
            event.ignore()
            
    def dragMoveEvent(self, event):
        """ dragMoveEvent(event: QDragMoveEvent) -> None
        Set to accept drops from the other cell info
        
        """
        idx = self.indexAtPos(event.pos())
        if idx>=0:
            self.setCurrentIndex(idx)
            
            
class StandardTabDockWidget(QtGui.QDockWidget):
    """
    StandardTabDockWidget inherits from QDockWidget to contain a sheet
    widget floating around that can be merge back to tab controller
    
    """
    def __init__(self, title, tabWidget, tabBar, tabController):
        """ StandardTabDockWidget(title: str,
                                  tabWidget: QTabWidget,
                                  tabBar: QTabBar,
                                  tabController: StandardWidgetTabController)
                                  -> StandardTabDockWidget
        Initialize the dock widget to override the floating button
        
        """
        QtGui.QDockWidget.__init__(self, title, tabBar,
                                   QtCore.Qt.FramelessWindowHint)
        self.tabBar = tabBar
        self.tabController = tabController
        self.setFeatures(QtGui.QDockWidget.DockWidgetMovable|
                         QtGui.QDockWidget.DockWidgetFloatable)
        self.setFloating(True)
        self.floatingButton = self.findFloatingButton()
        if self.floatingButton:
            self.floatingButton.blockSignals(True)
            self.floatingButton.installEventFilter(self)
        self.startDragPos = None
        self.startDragging = False
        self.windowRubberBand = QtGui.QRubberBand(QtGui.QRubberBand.Rectangle,
                                                  None)
        tabWidget.setParent(self)
        self.setWidget(tabWidget)
        tabWidget.show()
        self.resize(tabWidget.size())

    def findFloatingButton(self):
        """ findFloatingButton() -> QAbstractButton        
        Hack to find the private Floating Button. Since there is only
        one button exists, we just need to find QAbstractButton
        
        """
        for c in self.children():
            if type(c)==QtGui.QAbstractButton:
                return c
        return None

    def eventFilter(self, q, e):
        """ eventFilter(q: QObject, e: QEvent) -> depends on event type
        Event filter the floating button to makes it merge to the tab controller
        
        """
        if q and q==self.floatingButton:
            if (e.type()==QtCore.QEvent.MouseButtonRelease and
                e.button()&QtCore.Qt.LeftButton):
                if self.isMaximized():
                    self.showNormal()
                else:
                    self.showMaximized()
                return False
        return QtGui.QDockWidget.eventFilter(self, q, e)

    def event(self, e):
        """ event(e: QEvent) -> depends on event type
        Handle movement of the dock widget to snap to the tab controller
        
        """
        if e.type()==QtCore.QEvent.MouseButtonPress:
            # Click on the title bar
            if e.y()<self.widget().y() and e.buttons()&QtCore.Qt.LeftButton:
                self.startDragPos = QtCore.QPoint(e.globalPos().x(),
                                                  e.globalPos().y())
        elif e.type()==QtCore.QEvent.MouseMove:
            if not (e.buttons()&QtCore.Qt.LeftButton):
                self.windowRubberBand.hide()
                self.setMouseTracking(False)
                return QtGui.QDockWidget.event(self, e)
            if (not self.startDragging and
                self.startDragPos and
                (self.startDragPos-e.globalPos()).manhattanLength()>=4):
                self.startDragging = True
                self.windowRubberBand.setGeometry(self.geometry())
                self.startDragPos = self.pos()-e.globalPos()
                self.windowRubberBand.show()
                self.setMouseTracking(True)
            if self.startDragging:
                tb = QtGui.QApplication.widgetAt(e.globalPos())
                if tb==self.tabBar:
                    idx = tb.slotIndex(e.globalPos())
                    if idx>=0:
                        self.windowRubberBand.setGeometry(tb.slotGeometry(idx))
                else:
                    rect = QtCore.QRect(self.startDragPos+e.globalPos(),
                                        self.size())
                    self.windowRubberBand.setGeometry(rect)
        elif e.type()==QtCore.QEvent.MouseButtonRelease and self.startDragging:
            self.setMouseTracking(False)
            self.windowRubberBand.hide()
            self.startDragPos = None
            self.startDragging = False
            tb = QtGui.QApplication.widgetAt(e.globalPos())
            if tb==self.tabBar:
                idx = tb.slotIndex(e.globalPos())
                if idx>=0:
                    self.hide()
                    self.tabController.mergeTab(self, idx)
                    return False
            else:
                self.move(self.windowRubberBand.pos())
        elif (e.type()==QtCore.QEvent.MouseButtonDblClick and
              e.button()&QtCore.Qt.LeftButton):
            self.hide()
            self.tabController.mergeTab(self, self.tabController.count())
            return False
            
        return QtGui.QDockWidget.event(self, e)

spreadsheetRegistry.registerSheet('StandardWidgetSheetTab',
                                  StandardWidgetSheetTab)
