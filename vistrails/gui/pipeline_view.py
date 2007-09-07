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
""" This is a QGraphicsView for pipeline view, it also holds different
types of graphics items that are only available in the pipeline
view. It only handles GUI-related actions, the rest of the
functionalities are implemented at somewhere else,
e.g. core.vistrails

QGraphicsConnectionItem
QGraphicsPortItem
QGraphicsConfigureItem
QGraphicsModuleItem
QPipelineScene
QPipelineView
"""

from PyQt4 import QtCore, QtGui
from core.utils import VistrailsInternalError
from core.utils.uxml import named_elements
from core.modules.module_configure import DefaultModuleConfigurationWidget
from core.modules.module_registry import registry
from core.vistrail.connection import Connection
from core.vistrail.module import Module
from core.vistrail.pipeline import Pipeline
from core.vistrail.port import PortEndPoint
from core.vistrail.vistrail import Vistrail
from gui.graphics_view import (QInteractiveGraphicsScene,
                               QInteractiveGraphicsView,
                               QGraphicsItemInterface)
from gui.module_annotation import QModuleAnnotation
from gui.module_palette import QModuleTreeWidget
from gui.module_documentation import QModuleDocumentation
from gui.theme import CurrentTheme
from xml.dom.minidom import getDOMImplementation, parseString
import math

################################################################################
# QGraphicsPortItem

class QGraphicsPortItem(QtGui.QGraphicsRectItem):
    """
    QGraphicsPortItem is a small port shape drawing on top (a child)
    of QGraphicsModuleItem, it can either be rectangle or rounded
    
    """
    def __init__(self, parent=None, scene=None, optional=False):
        """ QGraphicsPortItem(parent: QGraphicsItem, scene: QGraphicsScene,
                              optional: bool)
                              -> QGraphicsPortItem
        Create the shape, initialize its pen and brush accordingly
        
        """
        QtGui.QGraphicsRectItem.__init__(self, parent, scene)
        self.setZValue(1)
        self.setFlags(QtGui.QGraphicsItem.ItemIsSelectable)
        self.setPen(CurrentTheme.PORT_PEN)
        self.setBrush(CurrentTheme.PORT_BRUSH)
        if not optional:
            self.paint = self.paintRect
        else:
            self.paint = self.paintEllipse
        self.setRect(QtCore.QRectF(0, 0,
                                   CurrentTheme.PORT_WIDTH,
                                   CurrentTheme.PORT_HEIGHT))
        self.controller = None
        self.port = None
        self.dragging = False
        self.connection = None
        self.ghosted = False

    def setGhosted(self, ghosted):
        """ setGhosted(ghosted: True) -> None
        Set this link to be ghosted or not
        
        """
        self.ghosted = ghosted
        if ghosted:
            self.setPen(CurrentTheme.GHOSTED_PORT_PEN)
            self.setBrush(CurrentTheme.GHOSTED_PORT_BRUSH)
        else:
            self.setPen(CurrentTheme.PORT_PEN)
            self.setBrush(CurrentTheme.PORT_BRUSH)

    def paintEllipse(self, painter, option, widget=None):
        """ paintEllipse(painter: QPainter, option: QStyleOptionGraphicsItem,
                  widget: QWidget) -> None
        Peform actual painting of the optional port
        
        """
        painter.setBrush(self.brush())
        painter.setPen(self.pen())
        painter.drawEllipse(self.rect())

    def paintRect(self, painter, option, widget=None):
        """ paintRect(painter: QPainter, option: QStyleOptionGraphicsItem,
                  widget: QWidget) -> None
        Peform actual painting of the regular port
        
        """
        QtGui.QGraphicsRectItem.paint(self, painter, option, widget)

    def setupPort(self, port):
        """ setupPort(port: Port) -> None
        Update the port tooltip, signatures, etc.
        
        """
        self.port = port
        self.setToolTip(port.toolTip())

    def mousePressEvent(self, event):
        """ mousePressEvent(event: QMouseEvent) -> None
        Prepare for dragging a connection
        
        """
        if self.controller and event.buttons() & QtCore.Qt.LeftButton:
            self.dragging = True
            self.setPen(CurrentTheme.PORT_SELECTED_PEN);
            event.accept()
        QtGui.QGraphicsRectItem.mousePressEvent(self, event)
        # super(QGraphicsPortItem, self).mousePressEvent(event)
        
    def mouseReleaseEvent(self, event):
        """ mouseReleaseEvent(event: QMouseEvent) -> None
        Apply the connection
        
        """
        if self.connection and self.connection.snapPort and self.controller:
            snapModuleId = self.connection.snapPort.parentItem().id
            if self.port.endPoint==PortEndPoint.Source:
                conn = Connection.fromPorts(self.port,
                                            self.connection.snapPort.port)
                conn.sourceId = self.parentItem().id
                conn.destinationId = snapModuleId
            else:
                conn = Connection.fromPorts(self.connection.snapPort.port,
                                            self.port)
                conn.sourceId = snapModuleId
                conn.destinationId = self.parentItem().id
            conn.id = self.controller.currentPipeline.fresh_connection_id()
            self.controller.add_connection(conn)
            # the add_connection call will trigger a chain of signals
            # that results ultimately in 'self' being deleted, so
            # we can't do anything else and must return right away.
            return
        if self.connection:
            self.scene().removeItem(self.connection)
            self.connection = None
        self.dragging = False
        self.setPen(CurrentTheme.PORT_PEN)
        QtGui.QGraphicsRectItem.mouseReleaseEvent(self, event)
        # super(QGraphicsPortItem, self).mouseReleaseEvent(event)
        
    def mouseMoveEvent(self, event):
        """ mouseMoveEvent(event: QMouseEvent) -> None
        Change the connection
        
        """
        if self.dragging:
            if not self.connection:
                self.connection = QtGui.QGraphicsLineItem(None, self.scene())
                self.connection.setPen(CurrentTheme.CONNECTION_SELECTED_PEN)
                modules = self.controller.currentPipeline.modules
                max_module_id = max([x for
                                     x in modules.iterkeys()])
                self.connection.setZValue(max_module_id + 1)
                self.connection.snapPort = None
            startPos = self.sceneBoundingRect().center()
            endPos = event.scenePos()
            # Return connected port to unselected color
            if (self.connection.snapPort):
                self.connection.snapPort.setPen(CurrentTheme.PORT_PEN)
            # Find new connected port
            self.connection.snapPort = self.findSnappedPort(endPos)
            if self.connection.snapPort:
                endPos = self.connection.snapPort.sceneBoundingRect().center()
                QtGui.QToolTip.showText(event.screenPos(),
                                        self.connection.snapPort.toolTip())
                # Change connected port to selected color
                self.connection.snapPort.setPen(
                    CurrentTheme.PORT_SELECTED_PEN)
            self.connection.prepareGeometryChange()
            self.connection.setLine(startPos.x(), startPos.y(),
                                    endPos.x(), endPos.y())
        QtGui.QGraphicsRectItem.mouseMoveEvent(self, event)
        # super(QGraphicsPortItem, self).mouseMoveEvent(event)

    def findModuleUnder(self, pos):
        """ findModuleUnder(pos: QPoint) -> QGraphicsItem
        Search all items under pos and return the top-most module item if any
        
        """
        itemsUnder = self.scene().items(pos)
        for item in itemsUnder:
            if type(item)==QGraphicsModuleItem:
                return item
        return None
        
    def findSnappedPort(self, pos):
        """ findSnappedPort(pos: QPoint) -> Port        
        Search all ports of the module under mouse cursor (if any) to
        find the closest matched port
        
        """
        snapModule = self.findModuleUnder(pos)
        if snapModule and snapModule!=self.parentItem():
            if self.port.endPoint==PortEndPoint.Source:
                return snapModule.getDestPort(pos, self.port)
            else:
                return snapModule.getSourcePort(pos, self.port)
        else:
            return None
        
    def itemChange(self, change, value):
        """ itemChange(change: GraphicsItemChange, value: QVariant) -> QVariant
        Do not allow port to be selected
        
        """
        if change==QtGui.QGraphicsItem.ItemSelectedChange and value.toBool():
            return QtCore.QVariant(False)
        return QtGui.QGraphicsRectItem.itemChange(self, change, value)


################################################################################
# QGraphicsConfigureItem

class QGraphicsConfigureItem(QtGui.QGraphicsPolygonItem):
    """
    QGraphicsConfigureItem is a small triangle shape drawing on top (a child)
    of QGraphicsModuleItem
    
    """
    def __init__(self, parent=None, scene=None):
        """ QGraphicsConfigureItem(parent: QGraphicsItem, scene: QGraphicsScene)
                              -> QGraphicsConfigureItem
        Create the shape, initialize its pen and brush accordingly
        
        """
        QtGui.QGraphicsPolygonItem.__init__(self, parent, scene)
        self.setZValue(1)
        self.setPen(CurrentTheme.CONFIGURE_PEN)
        self.setBrush(CurrentTheme.CONFIGURE_BRUSH)
        poly = QtGui.QPolygon(3)
        poly.setPoint(0, 0, 0)
        poly.setPoint(1, 0, CurrentTheme.CONFIGURE_HEIGHT)
        poly.setPoint(2, CurrentTheme.CONFIGURE_WIDTH,
                      CurrentTheme.CONFIGURE_HEIGHT/2)
        self.setPolygon(QtGui.QPolygonF(poly))
        self.ghosted = False
        self.controller = None
        self.moduleId = None
        self.createActions()

    def setGhosted(self, ghosted):
        """ setGhosted(ghosted: True) -> None
        Set this link to be ghosted or not
        
        """
        self.ghosted = ghosted
        if ghosted:
            self.setPen(CurrentTheme.GHOSTED_CONFIGURE_PEN)
            self.setBrush(CurrentTheme.GHOSTED_CONFIGURE_BRUSH)
        else:
            self.setPen(CurrentTheme.CONFIGURE_PEN)
            self.setBrush(CurrentTheme.CONFIGURE_BRUSH)

    def mousePressEvent(self, event):
        """ mousePressEvent(event: QMouseEvent) -> None
        Open the context menu
        
        """
        self.contextMenuEvent(event)

    def contextMenuEvent(self, event):
        """contextMenuEvent(event: QGraphicsSceneContextMenuEvent) -> None
        Captures context menu event.

        """
        menu = QtGui.QMenu()
        menu.addAction(self.configureAct)
        menu.addAction(self.annotateAct)
        menu.addAction(self.viewDocumentationAct)
        menu.exec_(event.screenPos())

    def createActions(self):
        """ createActions() -> None
        Create actions related to context menu 

        """
        self.configureAct = QtGui.QAction("Edit Configuration\tCtrl+E", self.scene())
        self.configureAct.setStatusTip("Edit the Configure of the module")
        QtCore.QObject.connect(self.configureAct, 
                               QtCore.SIGNAL("triggered()"),
                               self.configure)
        self.annotateAct = QtGui.QAction("Annotate", self.scene())
        self.annotateAct.setStatusTip("Annotate the module")
        QtCore.QObject.connect(self.annotateAct,
                               QtCore.SIGNAL("triggered()"),
                               self.annotate)
        self.viewDocumentationAct = QtGui.QAction("View Documentation", self.scene())
        self.viewDocumentationAct.setStatusTip("View module documentation")
        QtCore.QObject.connect(self.viewDocumentationAct,
                               QtCore.SIGNAL("triggered()"),
                               self.viewDocumentation)

    def configure(self):
        """ configure() -> None
        Open the modal configuration window
        """
        if self.moduleId>=0:
            self.scene().open_configure_window(self.moduleId)

    def annotate(self):
        """ anotate() -> None
        Open the annotations window
        """
        if self.moduleId>=0:
            self.scene().open_annotations_window(self.moduleId)

    def viewDocumentation(self):
        """ viewDocumentation() -> None
        Show the documentation for the module
        """
        assert self.moduleId >= 0
        self.scene().open_documentation_window(self.moduleId)
        
        
                                               
##############################################################################
# QGraphicsConnectionItem

# set this to True to have old sine-wave connections
__old_connection = True
if __old_connection:
    class QGraphicsConnectionItem(QGraphicsItemInterface,
                                  QtGui.QGraphicsPolygonItem):
        """
        QGraphicsConnectionItem is a connection shape connecting two port items

        """
        def __init__(self, parent=None, scene=None):
            """ QGraphicsConnectionItem(parent: QGraphicsItem,
                                        scene: QGraphicsScene)
                                        -> QGraphicsConnectionItem
            Create the shape, initialize its pen and brush accordingly

            """
            QtGui.QGraphicsPolygonItem.__init__(self, parent, scene)
            self.setFlags(QtGui.QGraphicsItem.ItemIsSelectable)
            self.setZValue(2)
            self.connectionPen = CurrentTheme.CONNECTION_PEN
            self.startPos = QtCore.QPointF()
            self.endPos = QtCore.QPointF()
            self.visualPolygon = QtGui.QPolygonF()
            self.connectingModules = (None, None)
            self.id = -1
            self.ghosted = False
            self.connection = None
            self.useSelectionRules = True

        def setupConnection(self, startPos, endPos):
            """ setupConnection(startPos: QPointF, endPos: QPointF) -> None
            Setup curve ends and store info

            """
            self.startPos = startPos
            self.endPos = endPos

            # Generate the polygon passing through two points
            steps = CurrentTheme.CONNECTION_CONTROL_POINTS
            polygon = QtGui.QPolygonF()
            self.visualPolygon = QtGui.QPolygonF()
            p1 = self.startPos
            p2 = self.endPos
            r = p2-p1
            horizontal = False        
            if p2.y() > p1.y() and p2.x() > p1.x():
                horizontal = True
            p1x = p1.x()
            p1y = p1.y()
            rx = r.x()
            ry = r.y()
            points = []
            for i in xrange(steps):
                t = float(i)/float(steps-1)
                s = (0.5+math.sin(math.pi*(t-0.5))*0.5)
                if horizontal:
                    x = p1x+rx*t
                    y = p1y+ry*s
                    polygon.append(QtCore.QPointF(x,y-2))
                    self.visualPolygon.append(QtCore.QPointF(x,y))
                    points.append(QtCore.QPointF(x, y+2))
                else:
                    x = p1x+rx*s
                    y = p1y+ry*t
                    polygon.append(QtCore.QPointF(x-2, y))
                    self.visualPolygon.append(QtCore.QPointF(x, y))
                    points.append(QtCore.QPointF(x+2, y))

            for p in reversed(points):
                polygon.append(p)
            polygon.append(polygon.at(0))
            self.setPolygon(polygon)

        def setGhosted(self, ghosted):
            """ setGhosted(ghosted: True) -> None
            Set this link to be ghosted or not

            """
            self.ghosted = ghosted
            if ghosted:
                self.connectionPen = CurrentTheme.GHOSTED_CONNECTION_PEN
            else:
                self.connectionPen = CurrentTheme.CONNECTION_PEN

        def paint(self, painter, option, widget=None):
            """ paint(painter: QPainter, option: QStyleOptionGraphicsItem,
                      widget: QWidget) -> None
            Peform actual painting of the connection

            """
            if self.isSelected():
                painter.setPen(CurrentTheme.CONNECTION_SELECTED_PEN)
            else:
                painter.setPen(self.connectionPen)
            painter.drawPolyline(self.visualPolygon)

        def itemChange(self, change, value):
            """ itemChange(change: GraphicsItemChange, value: QVariant) -> QVariant
            Do not allow connection to be selected unless both modules 
            are selected

            """
            # Selection rules to be used only when a module isn't forcing 
            # the update
            if (change==QtGui.QGraphicsItem.ItemSelectedChange and 
                self.useSelectionRules):
                # Check for a selected module
                selectedItems = self.scene().selectedItems()
                selectedModules = False
                for item in selectedItems:
                    if type(item)==QGraphicsModuleItem:
                        selectedModules = True
                        break
                if selectedModules:
                    # Don't allow a connection between selected
                    # modules to be deselected
                    if (self.connectingModules[0].isSelected() and
                        self.connectingModules[1].isSelected()):
                        if not value.toBool():
                            return QtCore.QVariant(True)
                    # Don't allow a connection to be selected if
                    # it is not between selected modules
                    else:
                        if value.toBool():
                            return QtCore.QVariant(False)
            self.useSelectionRules = True
            return QtGui.QGraphicsPolygonItem.itemChange(self, change, value)
else:
    class QGraphicsConnectionItem(QGraphicsItemInterface,
                                  QtGui.QGraphicsPathItem):
        """
        QGraphicsConnectionItem is a connection shape connecting two port items

        """
        def __init__(self, parent=None, scene=None):
            """ QGraphicsConnectionItem(parent: QGraphicsItem,
                                        scene: QGraphicsScene)
                                        -> QGraphicsConnectionItem
            Create the shape, initialize its pen and brush accordingly

            """
            QtGui.QGraphicsPolygonItem.__init__(self, parent, scene)
            self.setFlags(QtGui.QGraphicsItem.ItemIsSelectable)
            self.setZValue(2)
            self.connectionPen = CurrentTheme.CONNECTION_PEN
            self.startPos = QtCore.QPointF()
            self.endPos = QtCore.QPointF()
            self.connectingModules = (None, None)
            self.id = -1
            self.ghosted = False
            self.connection = None
            # Keep a flag for changing selection state during module selection
            self.useSelectionRules = True

        def setupConnection(self, startPos, endPos):
            """ setupConnection(startPos: QPointF, endPos: QPointF) -> None
            Setup curve ends and store info

            """
            self.startPos = startPos
            self.endPos = endPos

            dx = abs(self.endPos.x() - self.startPos.x())
            dy = (self.startPos.y() - self.endPos.y())

            # This is reasonably ugly logic to get reasonably nice
            # curves. Here goes: we use a cubic bezier p0,p1,p2,p3, where:

            # p0 is the source port center
            # p3 is the destination port center
            # p1 is a control point displaced vertically from p0
            # p2 is a control point displaced vertically from p3

            # We want most curves to be "straight": they shouldn't bend
            # much.  However, we want "inverted" connections (connections
            # that go against the natural up-down flow) to bend a little
            # as they go out of the ports. So the logic is:

            # As dy/dx -> oo, we want the control point displacement to go
            # to max(dy/2, m) (m is described below)

            # As dy/dx -> 0, we want the control point displacement to go
            # to m 

            # As dy/dx -> -oo, we want the control point displacement to go
            # to max(-dy/2, m)

            # On points away from infinity, we want some smooth transition.
            # I'm using f(x) = 2/pi arctan (x) as the mapping, since:

            # f(-oo) = -1
            # f(0) = 0
            # f(oo) = 1

            # m is the monotonicity breakdown point: this is the minimum
            # displacement when dy/dx is low
            m = float(CurrentTheme.MODULE_LABEL_MARGIN[0]) * 3.0

            # positive_d and negative_d are the displacements when dy/dx is
            # large positive and large negative
            positive_d = max(m/3.0, dy / 2.0)
            negative_d = max(m/3.0, -dy / 4.0)

            if dx == 0.0:
                v = 0.0
            else:
                w = math.atan(dy/dx) * (2 / math.pi)
                if w < 0:
                    w = -w
                    v = w * negative_d + (1.0 - w) * m
                else:
                    v = w * positive_d + (1.0 - w) * m

            displacement = QtCore.QPointF(0.0, v)
            self._control_1 = startPos - displacement
            self._control_2 = endPos + displacement

            path = QtGui.QPainterPath(self.startPos)
            path.cubicTo(self._control_1, self._control_2, self.endPos)

            self.setPath(path)

        def setGhosted(self, ghosted):
            """ setGhosted(ghosted: True) -> None
            Set this link to be ghosted or not

            """
            self.ghosted = ghosted
            if ghosted:
                self.connectionPen = CurrentTheme.GHOSTED_CONNECTION_PEN
            else:
                self.connectionPen = CurrentTheme.CONNECTION_PEN

        def paint(self, painter, option, widget=None):
            """ paint(painter: QPainter, option: QStyleOptionGraphicsItem,
                      widget: QWidget) -> None
            Peform actual painting of the connection

            """
            if self.isSelected():
                painter.setPen(CurrentTheme.CONNECTION_SELECTED_PEN)
            else:
                painter.setPen(self.connectionPen)
            painter.drawPath(self.path())

        def itemChange(self, change, value):
            """ itemChange(change: GraphicsItemChange, value: QVariant) -> QVariant
            If modules are selected, only allow connections between 
            selected modules 

            """
            # Selection rules to be used only when a module isn't forcing 
            # the update
            if (change==QtGui.QGraphicsItem.ItemSelectedChange and 
                self.useSelectionRules):
                # Check for a selected module
                selectedItems = self.scene().selectedItems()
                selectedModules = False
                for item in selectedItems:
                    if type(item)==QGraphicsModuleItem:
                        selectedModules = True
                        break
                if selectedModules:
                    # Don't allow a connection between selected
                    # modules to be deselected
                    if (self.connectingModules[0].isSelected() and
                        self.connectingModules[1].isSelected()):
                        if not value.toBool():
                            return QtCore.QVariant(True)
                    # Don't allow a connection to be selected if
                    # it is not between selected modules
                    else:
                        if value.toBool():
                            return QtCore.QVariant(False)
            self.useSelectionRules = True
            return QtGui.QGraphicsPathItem.itemChange(self, change, value)    

##############################################################################
# QGraphicsModuleItem

class QGraphicsModuleItem(QGraphicsItemInterface, QtGui.QGraphicsItem):
    """
    QGraphicsModuleItem knows how to draw a Vistrail Module into the
    pipeline view. It is usually a rectangular shape with a bold text
    in the center. It also has its input/output port shapes as its
    children. Another remark is that connections are also children of
    module shapes. Each connection belongs to its source module
    ('output port' end of the connection)
    
    """
    def __init__(self, parent=None, scene=None):
        """ QGraphicsModuleItem(parent: QGraphicsItem, scene: QGraphicsScene)
                                -> QGraphicsModuleItem
        Create the shape, initialize its pen and brush accordingly
        
        """
        self.paddedRect = QtCore.QRectF()
        QtGui.QGraphicsItem.__init__(self, parent, scene)
        self.setFlags(QtGui.QGraphicsItem.ItemIsSelectable |
                      QtGui.QGraphicsItem.ItemIsMovable)
        self.setZValue(0)
        self.labelFont = CurrentTheme.MODULE_FONT
        self.labelFontMetric = CurrentTheme.MODULE_FONT_METRIC
        self.descFont = CurrentTheme.MODULE_DESC_FONT
        self.descFontMetric = CurrentTheme.MODULE_DESC_FONT_METRIC
        self.modulePen = CurrentTheme.MODULE_PEN
        self.moduleBrush = CurrentTheme.MODULE_BRUSH
        self.labelPen = CurrentTheme.MODULE_LABEL_PEN
        self.labelRect = QtCore.QRectF()
        self.descRect = QtCore.QRectF()
        self.id = -1
        self.label = ''
        self.description = ''
        self.inputPorts = {}
        self.outputPorts = {}
        self.dependingConnectionItems = []
        self.controller = None
        self.module = None
        self.ghosted = False
        self._module_shape = None

    def computeBoundingRect(self):
        """ computeBoundingRect() -> None
        Adjust the module size according to the text size
        
        """
        labelRect = self.labelFontMetric.boundingRect(self.label)
        labelRect.translate(-labelRect.center().x(), -labelRect.center().y())
        if self.description:
            descRect = self.descFontMetric.boundingRect(self.description)
            descRect.adjust(0, 0, 0, CurrentTheme.MODULE_PORT_MARGIN[3])
        else:
            descRect = QtCore.QRectF(0, 0, 0, 0)
        self.paddedRect = QtCore.QRectF(
            labelRect.adjusted(-CurrentTheme.MODULE_LABEL_MARGIN[0],
                              -CurrentTheme.MODULE_LABEL_MARGIN[1]
                              -descRect.height()/2,
                              CurrentTheme.MODULE_LABEL_MARGIN[2],
                              CurrentTheme.MODULE_LABEL_MARGIN[3]
                              +descRect.height()/2))
        self.description = self.descFontMetric.elidedText(
            self.description, QtCore.Qt.ElideRight, labelRect.width())
        self.description.prepend('(').append(')')
        
        self.labelRect = QtCore.QRectF(
            self.paddedRect.left(),
            -(labelRect.height()+descRect.height())/2,
            self.paddedRect.width(),
            labelRect.height())
        self.descRect = QtCore.QRectF(
            self.paddedRect.left(),
            self.labelRect.bottom(),
            self.paddedRect.width(),
            descRect.height())

    def boundingRect(self):
        """ boundingRect() -> QRectF
        Returns the bounding box of the module
        
        """
        return self.paddedRect.adjusted(-2, -2, 2, 2)

    def setGhosted(self, ghosted):
        """ setGhosted(ghosted: True) -> None
        Set this link to be ghosted or not
        
        """
        self.ghosted = ghosted
        if ghosted:
            self.modulePen = CurrentTheme.GHOSTED_MODULE_PEN
            self.moduleBrush = CurrentTheme.GHOSTED_MODULE_BRUSH
            self.labelPen = CurrentTheme.GHOSTED_MODULE_LABEL_PEN
        else:
            self.modulePen = CurrentTheme.MODULE_PEN
            self.moduleBrush = CurrentTheme.MODULE_BRUSH
            self.labelPen = CurrentTheme.MODULE_LABEL_PEN
            
    def paint(self, painter, option, widget=None):
        """ paint(painter: QPainter, option: QStyleOptionGraphicsItem,
                  widget: QWidget) -> None
        Peform actual painting of the module
        
        """
        def setModulePen():
            if self.isSelected():
                painter.setPen(CurrentTheme.MODULE_SELECTED_PEN)
            else:
                painter.setPen(self.modulePen)
        def setLabelPen():
            if self.isSelected():
                painter.setPen(CurrentTheme.MODULE_LABEL_SELECTED_PEN)
            else:
                painter.setPen(self.labelPen)
            
        def drawCustomShape():
            painter.setBrush(self.moduleBrush)
            painter.drawPolygon(self._module_shape)
            setModulePen()
            painter.drawPolyline(self._module_shape)

        def drawStandardShape():
            painter.fillRect(self.paddedRect, self.moduleBrush)
            setModulePen()
            painter.drawRect(self.paddedRect)

        if self._module_shape:
            drawCustomShape()
        else:
            drawStandardShape()
    
        setLabelPen()
        painter.setFont(self.labelFont)
        painter.drawText(self.labelRect, QtCore.Qt.AlignCenter, self.label)
        if self.descRect:
            painter.setFont(self.descFont)
            painter.drawText(self.descRect, QtCore.Qt.AlignCenter,
                             self.description)

    def adjustWidthToMin(self, minWidth):
        """ adjustWidthToContain(minWidth: int) -> None
        Resize the module width to at least be minWidth
        
        """
        if minWidth>self.paddedRect.width():
            diff = minWidth - self.paddedRect.width() + 1
            self.paddedRect.adjust(-diff/2, 0, diff/2, 0)

    def setupModule(self, module):
        """ setupModule(module: Module) -> None
        Set up the item to reflect the info in 'module'
        
        """
        # Update module info and visual
        self.id = module.id
        self.setZValue(float(self.id))
        self.module = module
        self.label = module.name
        # self.description = module.annotations.get('__desc__', '').strip()
        if module.has_annotation_with_key('__desc__'):
            self.description = \
                module.get_annotation_by_key('__desc__').value.strip()
        else:
            self.description = ''
        self.setToolTip(self.description)
        self.computeBoundingRect()
        self.resetMatrix()
        self.translate(module.center.x, -module.center.y)
        c = registry.get_module_color(module.package, module.name)
        if c:
            ic = [int(cl*255) for cl in c]
            b = QtGui.QBrush(QtGui.QColor(ic[0], ic[1], ic[2]))
            self.moduleBrush = b

        # Check to see which ports will be shown on the screen
        visibleOptionalPorts = []
        inputPorts = []
        self.optionalInputPorts = []
        for p in module.destinationPorts():
            if not p.optional:
                inputPorts.append(p)
            elif (PortEndPoint.Destination, p.name) in module.portVisible:
                visibleOptionalPorts.append(p)
            else:
                self.optionalInputPorts.append(p)
        inputPorts += visibleOptionalPorts
        
        visibleOptionalPorts = []
        outputPorts = []
        self.optionalOutputPorts = []
        for p in module.sourcePorts():
            if not p.optional:
                outputPorts.append(p)
            elif (PortEndPoint.Source, p.name) in module.portVisible:
                visibleOptionalPorts.append(p)
            else:
                self.optionalOutputPorts.append(p)
        outputPorts += visibleOptionalPorts

        # Adjust the width to fit all ports
        maxPortCount = max(len(inputPorts), len(outputPorts))
        minWidth = (CurrentTheme.MODULE_PORT_MARGIN[0] +
                    CurrentTheme.PORT_WIDTH*maxPortCount +
                    CurrentTheme.MODULE_PORT_SPACE*(maxPortCount-1) +
                    CurrentTheme.MODULE_PORT_MARGIN[2] +
                    CurrentTheme.MODULE_PORT_PADDED_SPACE)
        self.adjustWidthToMin(minWidth)

        # Update input ports
        y = self.paddedRect.y() + CurrentTheme.MODULE_PORT_MARGIN[1]
        x = self.paddedRect.x() + CurrentTheme.MODULE_PORT_MARGIN[0]
        self.inputPorts = {}
        for port in inputPorts:
            self.inputPorts[port] = self.createPortItem(port, x, y)
            x += CurrentTheme.PORT_WIDTH + CurrentTheme.MODULE_PORT_SPACE
        self.nextInputPortPos = [x,y]

        # Update output ports
        y = (self.paddedRect.bottom() - CurrentTheme.PORT_HEIGHT
             - CurrentTheme.MODULE_PORT_MARGIN[3])
        x = (self.paddedRect.right() - CurrentTheme.PORT_WIDTH
             - CurrentTheme.MODULE_PORT_MARGIN[2])
        self.outputPorts = {}
        for port in outputPorts:            
            self.outputPorts[port] = self.createPortItem(port, x, y)
            x -= CurrentTheme.PORT_WIDTH + CurrentTheme.MODULE_PORT_SPACE
        self.nextOutputPortPos = [x, y]

        # Add a configure button
        y = self.paddedRect.y() + CurrentTheme.MODULE_PORT_MARGIN[1]
        x = (self.paddedRect.right() - CurrentTheme.CONFIGURE_WIDTH
             - CurrentTheme.MODULE_PORT_MARGIN[2])
        self.createConfigureItem(x, y)
        
        # Update module shape, if necessary
        fringe = registry.get_module_fringe(module.package, module.name)
        if fringe:
            left_fringe, right_fringe = fringe
            if left_fringe[0] != (0.0, 0.0):
                left_fringe = [(0.0, 0.0)] + left_fringe
            if left_fringe[-1] != (0.0, 1.0):
                left_fringe = left_fringe + [(0.0, 1.0)]

            if right_fringe[0] != (0.0, 0.0):
                right_fringe = [(0.0, 0.0)] + right_fringe
            if right_fringe[-1] != (0.0, 1.0):
                right_fringe = right_fringe + [(0.0, 1.0)]

            P = QtCore.QPointF
            self._module_shape = QtGui.QPolygonF()
            height = self.paddedRect.height()

            # right side of shape
            for (px, py) in right_fringe:
                p = P(px, -py)
                p *= height
                p += self.paddedRect.bottomRight()
                self._module_shape.append(p)

            # left side of shape
            for (px, py) in reversed(left_fringe):
                p = P(px, -py)
                p *= height
                p += self.paddedRect.bottomLeft()
                self._module_shape.append(p)
            # close polygon
            self._module_shape.append(self._module_shape[0])

    def createPortItem(self, port, x, y):
        """ createPortItem(port: Port, x: int, y: int) -> QGraphicsPortItem
        Create a item from the port spec
        
        """
        portShape = QGraphicsPortItem(self, self.scene(), port.optional)
        portShape.controller = self.controller
        portShape.setGhosted(self.ghosted)
        portShape.setupPort(port)
        portShape.translate(x, y)
        return portShape

    def createConfigureItem(self, x, y):
        """ createConfigureItem(x: int, y: int) -> QGraphicsConfigureItem
        Create a item from the configure spec
        
        """
        configureShape = QGraphicsConfigureItem(self, self.scene())
        configureShape.controller = self.controller
        configureShape.moduleId = self.id
        configureShape.setGhosted(self.ghosted)
        configureShape.translate(x, y)
        return configureShape

    def getPortPosition(self, port, portDict):
        """ getPortPosition(port: Port,
                            portDict: {Port:QGraphicsPortItem})
                            -> QRectF
        Return the scene position of a port matched 'port' in portDict
        
        """
        for (p, item) in portDict.iteritems():
            if registry.is_port_sub_type(port, p):
                return item.sceneBoundingRect().center()
        return None

    def getInputPortPosition(self, port):
        """ getInputPortPosition(port: Port} -> QRectF
        Just an overload function of getPortPosition to get from input ports
        
        """
        pos = self.getPortPosition(port, self.inputPorts)
        if pos==None:
            for p in self.optionalInputPorts:
                if registry.is_port_sub_type(port, p):
                    portShape = self.createPortItem(p,*self.nextInputPortPos)
                    self.inputPorts[port] = portShape
                    self.nextInputPortPos[0] += (CurrentTheme.PORT_WIDTH +
                                                 CurrentTheme.MODULE_PORT_SPACE)
                    return portShape.sceneBoundingRect().center()
            raise VistrailsInternalError("Error: did not find input port")
        return pos
        
    def getOutputPortPosition(self, port):
        """ getOutputPortPosition(port: Port} -> QRectF
        Just an overload function of getPortPosition to get from output ports
        
        """
        pos = self.getPortPosition(port, self.outputPorts)
        if pos==None:
            for p in self.optionalOutputPorts:
                if registry.is_port_sub_type(port, p):
                    portShape = self.createPortItem(p,*self.nextOutputPortPos)
                    self.outputPorts[port] = portShape
                    self.nextOutputPortPos[0] += (CurrentTheme.PORT_WIDTH +
                                                  CurrentTheme.MODULE_PORT_SPACE)
                    return portShape.sceneBoundingRect().center()
            raise VistrailsInternalError("Error: did not find output port")
        return pos

    def addConnectionItem(self, connectionItem, start):
        """ addConnectionItem(connectionItem: QGraphicsConnectionItem,
                              start: bool) -> None                              
        Add connectionItem into dependency list to adjust it when this
        module is moved. If start=True the depending point is the
        start point, else it is the end point
        
        """
        self.dependingConnectionItems.append((connectionItem, start))

    def removeConnectionItem(self, connectionItem):
        """ removeConnectionItem(connectionItem: QGraphicsConnectionItem)-> None
        Remove connectionItem from its dependency list

        """
        found = None
        for c in self.dependingConnectionItems:
            if c[0] == connectionItem:
                found = c
        if found:
            self.dependingConnectionItems.remove(found)

    def itemChange(self, change, value):
        """ itemChange(change: GraphicsItemChange, value: QVariant) -> QVariant
        Capture move event to also move the connections.  Also unselect any
        connections between unselected modules
        
        """
        # Move connections with modules
        if change==QtGui.QGraphicsItem.ItemPositionChange:
            oldPos = self.pos()
            newPos = value.toPointF()
            dis = newPos - oldPos
            for (connectionItem, start) in self.dependingConnectionItems:
                (srcModule, dstModule) = connectionItem.connectingModules
                if srcModule.isSelected() and dstModule.isSelected():
                    if srcModule==self:
                        connectionItem.moveBy(dis.x(), dis.y())
                else:
                    connectionItem.prepareGeometryChange()
                    if start:
                        connectionItem.setupConnection(
                            connectionItem.startPos+dis,
                            connectionItem.endPos)
                    else:
                        connectionItem.setupConnection(
                            connectionItem.startPos,
                            connectionItem.endPos+dis)
        # Do not allow lone connections to be selected with modules.
        # Also autoselect connections between selected modules.  Thus the
        # selection is always the subgraph
        elif change==QtGui.QGraphicsItem.ItemSelectedChange:
            # Unselect any connections between modules that are not selected
            for item in self.scene().selectedItems():
                if isinstance(item,QGraphicsConnectionItem):
                    (srcModule, dstModule) = item.connectingModules
                    if (not srcModule.isSelected() or 
                        not dstModule.isSelected()):
                        item.useSelectionRules = False
                        item.setSelected(False)
            # Handle connections from self
            for (item, start) in self.dependingConnectionItems:
                # Select any connections between self and other selected modules
                (srcModule, dstModule) = item.connectingModules
                if value.toBool():
                    if (srcModule==self and dstModule.isSelected() or
                        dstModule==self and srcModule.isSelected()):
                        # Because we are setting a state variable in the
                        # connection, do not make the change unless it is
                        # actually going to be performed
                        if not item.isSelected():
                            item.useSelectionRules = False
                            item.setSelected(True)
                # Unselect any connections between self and other modules
                else:
                    if item.isSelected():
                        item.useSelectionRules = False
                        item.setSelected(False)
            # Capture only selected modules + or - self for selection signal
            selectedItems = []
            selectedId = -1
            if value.toBool():
                selectedItems = [m for m in self.scene().selectedItems() 
                                 if isinstance(m,QGraphicsModuleItem)]
                selectedItems.append(self)
            else:
                selectedItems = [m for m in self.scene().selectedItems()
                                 if (isinstance(m,QGraphicsModuleItem) and 
                                     m != self)]
            if len(selectedItems)==1:
                selectedId = selectedItems[0].id
            self.scene().emit(QtCore.SIGNAL('moduleSelected'),
                              selectedId, selectedItems)
        return QtGui.QGraphicsItem.itemChange(self, change, value)

    def getDestPort(self, pos, srcPort):
        """ getDestPort(self, pos: QPointF, srcPort: Port) -> QGraphicsPortItem
        Look for the destination port match 'port' and closest to pos
        
        """
        result = None
        minDis = None
        for (dstPort, dstItem) in self.inputPorts.items():
            if (registry.ports_can_connect(srcPort, dstPort) and
                dstItem.isVisible()):                
                vector = (pos - dstItem.sceneBoundingRect().center())
                dis = vector.x()*vector.x() + vector.y()*vector.y()
                if result==None or dis<minDis:
                    minDis = dis
                    result = dstItem
        return result

    def getSourcePort(self, pos, dstPort):
        """ getSourcePort(self, pos: QPointF, dstPort: Port)
                          -> QGraphicsPortItem
        Look for the source port match 'port' and closest to pos
        
        """
        result = None
        minDis = None
        for (srcPort, srcItem) in self.outputPorts.items():
            if (registry.ports_can_connect(srcPort, dstPort) and
                srcItem.isVisible()):
                vector = (pos - srcItem.sceneBoundingRect().center())
                dis = vector.x()*vector.x() + vector.y()*vector.y()
                if result==None or dis<minDis:
                    minDis = dis
                    result = srcItem
        return result


##############################################################################
# QPipelineScene

class QPipelineScene(QInteractiveGraphicsScene):
    """
    QPipelineScene inherits from QInteractiveGraphicsScene to keep track of the
    pipeline scenes, i.e. modules, connections, selection
    
    """

    def __init__(self, parent=None):
        """ QPipelineScene(parent: QWidget) -> QPipelineScene
        Initialize the graphics scene with no shapes
        
        """
        QInteractiveGraphicsScene.__init__(self, parent)
        self.setBackgroundBrush(CurrentTheme.PIPELINE_VIEW_BACKGROUND_BRUSH)
        self.setSceneRect(QtCore.QRectF(-5000, -5000, 10000, 10000))
        self.controller = None
        self.modules = {}
        self.noUpdate = False
        self.installEventFilter(self)


#        menu = QtGui.QMenu()
#        self._create_abstraction = QtGui.QAction("Create abstraction", self)
#        menu.addAction(self._create_abstraction)
#        self._context_menu = menu
#        self.connect(self._create_abstraction,
#                     QtCore.SIGNAL("triggered()"),
#                     self.create_abstraction)

    def addModule(self, module, moduleBrush=None):
        """ addModule(module: Module, moduleBrush: QBrush) -> QGraphicsModuleItem
        Add a module to the scene
        
        """
        moduleItem = QGraphicsModuleItem(None)
        if self.controller and self.controller.search:
            moduleQuery = (self.controller.currentVersion, module)
            matched = self.controller.search.matchModule(*moduleQuery)
            moduleItem.setGhosted(not matched)
        moduleItem.controller = self.controller
        moduleItem.setupModule(module)
        if moduleBrush:
            moduleItem.moduleBrush = moduleBrush
        self.addItem(moduleItem)
        self.modules[module.id] = moduleItem
        return moduleItem

    def addConnection(self, connection):
        """ addConnection(connection: Connection) -> QGraphicsConnectionItem
        Add a connection to the scene
        
        """
        srcModule = self.modules[connection.source.moduleId]
        dstModule = self.modules[connection.destination.moduleId]
        srcPoint = srcModule.getOutputPortPosition(connection.source)
        dstPoint = dstModule.getInputPortPosition(connection.destination)
        connectionItem = QGraphicsConnectionItem(None)
        connectionItem.setupConnection(dstPoint, srcPoint)
        connectionItem.id = connection.id
        # Bump it slightly higher than the highest module
        connectionItem.setZValue(max(srcModule.id,
                                     dstModule.id) + 0.1)
        connectionItem.connection = connection
        connectionItem.connectingModules = (srcModule, dstModule)
        srcModule.addConnectionItem(connectionItem, False)
        dstModule.addConnectionItem(connectionItem, True)
        self.addItem(connectionItem)
        return connectionItem

    def selected_subgraph(self):
        """Returns the subgraph containing the selected modules and its
mutual connections."""
        items = self.selectedItems()
        modules = [x.id
                   for x in items
                   if type(x) == QGraphicsModuleItem]
        return self.controller.currentPipeline.graph.subgraph(modules)

    def create_abstraction(self):
        subgraph = self.selected_subgraph()
        try:
            self.controller.create_abstraction(subgraph)
        except Vistrail.InvalidAbstraction, e:
            dlg = QtGui.QMessageBox.warning(None,
                                            "Invalid Abstraction",
                                            str(e))

#    def contextMenuEvent(self, event):
#        selectedItems = self.selectedItems()
#        if len(selectedItems) == 0:
#            return QInteractiveGraphicsScene.contextMenuEvent(self, event)
#        else:
#            self._context_menu.exec_(event.screenPos())

    def clear(self):
        """ clear() -> None
        Clear the whole scene
        
        """
        self.modules = {}
        self.clearItems()

    def setupScene(self, pipeline):
        """ setupScene(pipeline: Pipeline) -> None
        Construct the scene to view a pipeline
        
        """
        if self.noUpdate: return
        needReset = len(self.items())==0        
        # Clean the previous scene
        self.clear()

        if pipeline:
            # Create module shapes
            for mId, module in pipeline.modules.iteritems():
                self.addModule(module)
                    
            pipeline.ensure_connection_specs()
            # Create connection shapes
            for connection in pipeline.connections.itervalues():
                self.addConnection(connection)

        # Update bounding rects and fit to all view
        self.updateSceneBoundingRect()        

        if needReset and len(self.items())>0:
            self.fitToAllViews()

    def dragEnterEvent(self, event):
        """ dragEnterEvent(event: QDragEnterEvent) -> None
        Set to accept drops from the module palette
        
        """
        if (self.controller and
            type(event.source())==QModuleTreeWidget):
            data = event.mimeData()
            if hasattr(data, 'items'):
                event.accept()
        else:
            event.ignore()
        
    def dragMoveEvent(self, event):
        """ dragMoveEvent(event: QDragMoveEvent) -> None
        Set to accept drag move event from the module palette
        
        """
        if (self.controller and
            type(event.source())==QModuleTreeWidget):

            data = event.mimeData()
            if hasattr(data, 'items'):
                event.accept()

    def unselect_all(self):
        selected = self.selectedItems()[:]
        for item in selected:
            item.setSelected(False)

    def dropEvent(self, event):
        """ dropEvent(event: QDragMoveEvent) -> None
        Accept drop event to add a new module
        
        """
        if (self.controller and
            type(event.source())==QModuleTreeWidget):
            data = event.mimeData()
            if hasattr(data, 'items'):
                event.accept()
                assert len(data.items) == 1
                if self.controller.currentVersion==-1:
                    self.controller.changeSelectedVersion(0)
                item = data.items[0]
                self.controller.resetPipelineView = False
                self.noUpdate = True
                module = self.controller.add_module(
                    item.descriptor.identifier,
                    item.descriptor.name,
                    event.scenePos().x(),
                    -event.scenePos().y())
                graphics_item = self.addModule(module)
                graphics_item.update()
                self.unselect_all()
                # Change selection
                graphics_item.setSelected(True)
                
                # We are assuming the first view is the real pipeline view                
                self.views()[0].setFocus()
                
                self.noUpdate = False

    def keyPressEvent(self, event):
        """ keyPressEvent(event: QKeyEvent) -> None
        Capture 'Del', 'Backspace' for deleting modules.
        Ctrl+C, Ctrl+V, Ctrl+A for copy, paste and select all
        
        """        
        if (self.controller and
            event.key() in [QtCore.Qt.Key_Backspace, QtCore.Qt.Key_Delete]):
            selectedItems = self.selectedItems()
            if len(selectedItems)>0:
                modules = []
                for m in selectedItems:
                    if type(m)==QGraphicsModuleItem:
                        modules.append(m)
                if len(modules)>0:
                    self.noUpdate = True
                    idList = [m.id for m in modules]
                    connections = []
                    for m in modules:
                        connections += [c[0] for c in m.dependingConnectionItems]
                    #update the dependency list on the other side of connections
                    for conn in connections:
                        if conn.connection.source:
                            mid = conn.connection.source.moduleId 
                            m = self.modules[mid]
                            if m not in modules:
                                m.removeConnectionItem(conn)
                        if conn.connection.destination:
                            mid = conn.connection.destination.moduleId
                            m = self.modules[mid]
                            if m not in modules:
                                m.removeConnectionItem(conn)
                    self.controller.deleteModuleList(idList)
                    self.removeItems(connections)
                    for (mId, item) in self.modules.items():
                        if item in selectedItems:
                            del self.modules[mId]
                    self.removeItems(selectedItems)
                    self.updateSceneBoundingRect()
                    self.update()
                    self.noUpdate = False
                    # Notify that no module is selected
                    self.emit(QtCore.SIGNAL('moduleSelected'),
                              -1, selectedItems)
                else:
                    self.controller.resetPipelineView = False
                    idList = [conn.id for conn in selectedItems]
                    self.controller.deleteConnectionList(idList)
        elif (event.key()==QtCore.Qt.Key_C and
              event.modifiers()==QtCore.Qt.ControlModifier):
            self.copySelection()
        elif (event.key()==QtCore.Qt.Key_V and
              event.modifiers()==QtCore.Qt.ControlModifier):
            self.pasteFromClipboard()
        elif (event.key()==QtCore.Qt.Key_A and
              event.modifiers()==QtCore.Qt.ControlModifier):
            self.selectAll()
        elif (event.key()==QtCore.Qt.Key_E and
              event.modifiers()==QtCore.Qt.ControlModifier):
            selected_items = self.selectedItems()
            module_id = -1
            module_count = 0
            for i in selected_items:
                if isinstance(i,QGraphicsModuleItem):
                    module_count+=1
                    module_id = i.id
            if module_count==1:
                self.open_configure_window(module_id)

        else:
            QInteractiveGraphicsScene.keyPressEvent(self, event)
            # super(QPipelineScene, self).keyPressEvent(event)

    def copySelection(self):
        """ copySelection() -> None
        Copy the current selected modules into clipboard
        
        """
        selectedItems = self.selectedItems()
        if len(selectedItems)>0:
            cb = QtGui.QApplication.clipboard()
#             dom = getDOMImplementation().createDocument(None, 'network', None)
#             root = dom.documentElement
            connections = {}
            modules = {}
            for item in selectedItems:
                if type(item)==QGraphicsModuleItem:
                    module = item.module
#                   module.dumpToXML(dom,root)
                    modules[module.id] = module
            for item in selectedItems:
                if type(item)==QGraphicsModuleItem:
                    for (connItem, start) in item.dependingConnectionItems:
                        conn = connItem.connection
                        if ((not connections.has_key(conn)) and
                            modules.has_key(conn.sourceId) and
                            modules.has_key(conn.destinationId)):
#                           conn.serialize(dom, root)
                            connections[conn.id] = conn
            text = self.controller.copyModulesAndConnections(modules.values(), 
                                                          connections.values())
            cb.setText(text)
            
    def pasteFromClipboard(self):
        """ pasteFromClipboard() -> None
        Paste modules/connections from the clipboard into this pipeline view
        
        """
        if self.controller:
            cb = QtGui.QApplication.clipboard()        
            text = str(cb.text())
            if text=='': return
            ids = self.controller.pasteModulesAndConnections(text)
            if len(ids) > 0:
                self.unselect_all()
            for moduleId in ids:
                self.modules[moduleId].setSelected(True)

#             dom = parseString(str(cb.text()))
#             root = dom.documentElement
#             modules = []
#             connections = []
#             for xmlmodule in named_elements(root, 'module'):
#                 module = Module.loadFromXML(xmlmodule)
#                 modules.append(module)
	
#             for xmlconnection in named_elements(root, 'connect'):
#                 conn = Connection.loadFromXML(xmlconnection)
#                 connections.append(conn)
#             self.controller.pasteModulesAndConnections(modules, connections)
            
    def eventFilter(self, object, e):
        """ eventFilter(object: QObject, e: QEvent) -> None        
        Catch all the set module color events through self-event
        filter. Using the standard event cause some ambiguity in
        converting between QGraphicsSceneEvent and QEvent
        
        """
        if e.type()==QModuleStatusEvent.TYPE:
            if e.moduleId>=0:
                item = self.modules.get(e.moduleId, None)
                if not item:
                    return True
                item.setToolTip(e.toolTip)
                if e.status==0:
                    item.moduleBrush = CurrentTheme.SUCCESS_MODULE_BRUSH
                elif e.status==1:
                    item.moduleBrush = CurrentTheme.ERROR_MODULE_BRUSH
                elif e.status==2:
                    item.moduleBrush = CurrentTheme.NOT_EXECUTED_MODULE_BRUSH
                elif e.status==3:
                    item.moduleBrush = CurrentTheme.ACTIVE_MODULE_BRUSH
                elif e.status==4:
                    item.moduleBrush = CurrentTheme.COMPUTING_MODULE_BRUSH                    
                item.update()
            return True
        return False

    def selectAll(self):
        """ selectAll() -> None
        Select all module items in the scene
        
        """
        for item in self.items():
            item.setSelected(True)

    def open_configure_window(self, id):
        """ open_configure_window(int) -> None
        Open the modal configuration window for module with given id
        """
        if self.controller:
            module = self.controller.currentPipeline.modules[id]
            getter = registry.get_configuration_widget
            widgetType = getter(module.package, module.name)
            if not widgetType:
                widgetType = DefaultModuleConfigurationWidget
            global widget
            widget = widgetType(module, self.controller, None)
            widget.setAttribute(QtCore.Qt.WA_DeleteOnClose)
            widget.exec_()
            self.controller.previousModuleIds = [id]
            self.controller.resendVersionWasChanged()

    def open_documentation_window(self, id):
        """ open_documentation_window(int) -> None
        Opens the modal module documentation window for module with given id
        """
        if self.controller:
            module = self.controller.currentPipeline.modules[id]
            descriptor = registry.get_descriptor_by_name(module.package, module.name)
            widget = QModuleDocumentation(descriptor, None)
            widget.setAttribute(QtCore.Qt.WA_DeleteOnClose)
            widget.exec_()

    def open_annotations_window(self, id):
        """ open_annotations_window(int) -> None
        Opens the modal annotations window for module with given id
        """
        if self.controller:
            module = self.controller.currentPipeline.modules[id]
            widget = QModuleAnnotation(module, self.controller, None)
            widget.setAttribute(QtCore.Qt.WA_DeleteOnClose)
            widget.exec_()

    def set_module_success(self, moduleId):
        """ set_module_success(moduleId: int) -> None
        Post an event to the scene (self) for updating the module color
        
        """
        QtGui.QApplication.postEvent(self,
                                     QModuleStatusEvent(moduleId, 0, ''))
        QtCore.QCoreApplication.processEvents()

    def set_module_error(self, moduleId, error):
        """ set_module_error(moduleId: int, error: str) -> None
        Post an event to the scene (self) for updating the module color
        
        """
        QtGui.QApplication.postEvent(self,
                                     QModuleStatusEvent(moduleId, 1, error))
        QtCore.QCoreApplication.processEvents()
        
    def set_module_not_executed(self, moduleId):
        """ set_module_not_executed(moduleId: int) -> None
        Post an event to the scene (self) for updating the module color
        
        """
        QtGui.QApplication.postEvent(self,
                                     QModuleStatusEvent(moduleId, 2, ''))
        QtCore.QCoreApplication.processEvents()

    def set_module_active(self, moduleId):
        """ set_module_active(moduleId: int) -> None
        Post an event to the scene (self) for updating the module color
        
        """
        QtGui.QApplication.postEvent(self,
                                     QModuleStatusEvent(moduleId, 3, ''))
        QtCore.QCoreApplication.processEvents()

    def set_module_computing(self, moduleId):
        """ set_module_computing(moduleId: int) -> None
        Post an event to the scene (self) for updating the module color
        
        """
        QtGui.QApplication.postEvent(self,
                                     QModuleStatusEvent(moduleId, 4, ''))
        QtCore.QCoreApplication.processEvents()


class QModuleStatusEvent(QtCore.QEvent):
    """
    QModuleStatusEvent is trying to handle thread-safe real-time
    module updates in the scene through post-event
    
    """
    TYPE = QtCore.QEvent.Type(QtCore.QEvent.User)
    def __init__(self, moduleId, status, toolTip):
        """ QModuleStatusEvent(type: int) -> None        
        Initialize the specific event with the module status. Status 0
        for success, 1 for error and 2 for not execute, 3 for active,
        and 4 for computing
        
        """
        QtCore.QEvent.__init__(self, QModuleStatusEvent.TYPE)
        self.moduleId = moduleId
        self.status = status
        self.toolTip = toolTip
            
class QPipelineView(QInteractiveGraphicsView):
    """
    QPipelineView inherits from QInteractiveGraphicsView that will
    handle drawing of module, connection shapes and selecting
    mechanism.
    
    """

    def __init__(self, parent=None):
        """ QPipelineView(parent: QWidget) -> QPipelineView
        Initialize the graphics view and its properties
        
        """
        QInteractiveGraphicsView.__init__(self, parent)
        self.setWindowTitle('Pipeline')
        self.setScene(QPipelineScene(self))

################################################################################

# if __name__=="__main__":
    
#     # Initialize the Vistrails Application and Theme
#     import sys
#     from gui import qt, theme
#     from gui import vis_application
#     vis_application.start_application()
#     app = vis_application.VistrailsApplication

#     # Get the pipeline
#     from core.xml_parser import XMLParser    
#     parser = XMLParser()
#     parser.openVistrail('d:/hvo/vgc/src/vistrails/trunk/examples/vtk.xml')
#     vistrail = parser.getVistrail()
#     version = vistrail.get_tag_by_name('Single Renderer').id
#     pipeline = vistrail.getPipeline(version)

#     # Now visually test QPipelineView
#     pv = QPipelineView(None)
#     pv.scene().setupScene(pipeline)
#     pv.show()
#     sys.exit(app.exec_())
