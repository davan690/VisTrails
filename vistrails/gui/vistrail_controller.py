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
from PyQt4 import QtCore, QtGui
from core.common import *
import core.db.action
from core.data_structures.point import Point
from core.utils import VistrailsInternalError, ModuleAlreadyExists
from core.modules import module_registry
from core.modules.module_registry import ModuleRegistry
from core.vistrail.action import Action
# from core.vistrail.action import AddModuleAction, DeleteModuleAction, \
#     ChangeParameterAction, AddConnectionAction, DeleteConnectionAction, \
#     DeleteFunctionAction, ChangeAnnotationAction, DeleteAnnotationAction,\
#     AddModulePortAction, DeleteModulePortAction, MoveModuleAction
from core.query.version import TrueSearch
from core.query.visual import VisualQuery
from core.vistrail.abstraction import Abstraction
from core.vistrail.abstraction_module import AbstractionModule
from core.vistrail.annotation import Annotation
from core.vistrail.connection import Connection
from core.vistrail.location import Location
from core.vistrail.module import Module
from core.vistrail.module_function import ModuleFunction
from core.vistrail.module_param import ModuleParam
from core.vistrail.pipeline import Pipeline
from core.vistrail.port import Port, PortEndPoint
from core.vistrail.port_spec import PortSpec
from core.vistrail.vistrail import TagExists
from core.interpreter.default import get_default_interpreter
from core.inspector import PipelineInspector
from gui.utils import show_warning, show_question, YES_BUTTON, NO_BUTTON
# Broken right now
# from core.modules.sub_module import addSubModule, DupplicateSubModule
import core.analogy
import copy
import db.services.action
import os.path
import core.system

################################################################################

class VistrailController(QtCore.QObject):
    """
    VistrailController is the class handling all action control in
    VisTrails. It updates pipeline, vistrail and emit signals to
    update the view
    
    """

    def __init__(self, vis=None, auto_save=True, name=''):
        """ VistrailController(vis: Vistrail, name: str) -> VistrailController
        Create a controller from vis

        """
        QtCore.QObject.__init__(self)
        self.name = ''
        self.fileName = ''
        self.setFileName(name)
        self.vistrail = vis
        self.currentVersion = -1
        self.currentPipeline = None
        self.currentPipelineView = None
        self.vistrailView = None
        self.previousModuleIds = []
        self.resetPipelineView = False
        self.resetVersionView = True
        self.quiet = False
        self.search = None
        self.searchStr = None
        self.refine = False
        self.changed = False
        self.fullTree = False
        self.analogy = {}
        self._auto_save = auto_save
        self.locator = None
        self.timer = QtCore.QTimer(self)
        self.connect(self.timer, QtCore.SIGNAL("timeout()"), self.write_temporary)
        self.timer.start(1000 * 60 * 2) # Save every two minutes

    def invalidate_version_tree(self):
        #FIXME: in the future, rename the signal
        self.emit(QtCore.SIGNAL('vistrailChanged()'))

    def enable_autosave(self):
        self._auto_save = True

    def disable_autosave(self):
        self._auto_save = False

    def get_locator(self):
        from gui.application import VistrailsApplication
        if (self._auto_save and 
            VistrailsApplication.configuration.check('autosave')):
            return self.locator or core.system.untitled_locator()
        else:
            return None

    def cleanup(self):
        locator = self.get_locator()
        if locator:
            locator.clean_temporaries()
        self.disconnect(self.timer, QtCore.SIGNAL("timeout()"), self.write_temporary)
        self.timer.stop()

    def setVistrail(self, vistrail, locator):
        """ setVistrail(vistrail: Vistrail, locator: VistrailLocator) -> None
        Start controlling a vistrail
        
        """
        self.vistrail = vistrail
        self.currentVersion = -1
        self.currentPipeline = None
        if self.locator != locator and self.locator is not None:
            self.locator.clean_temporaries()
        self.locator = locator
        if locator != None:
            self.setFileName(locator.name)
        else:
            self.setFileName('')
        if locator and locator.has_temporaries():
            self.setChanged(True)
            
    def perform_action(self, action, quiet=None):        
        self.currentPipeline.perform_action(action)
        self.currentVersion = action.db_id
        self.setChanged(True)
        
        if quiet is None:
            if not self.quiet:
                self.invalidate_version_tree()
        else:
            if not quiet:
                self.invalidate_version_tree()
        return action.db_id

    def add_module(self, identifier, name, x, y):
        """ addModule(identifier, name: str, x: int, y: int) -> version id
        Add a new module into the current pipeline
        
        """
        self.emit(QtCore.SIGNAL("flushMoveActions()"))

        if self.currentPipeline:
            loc_id = self.vistrail.idScope.getNewId(Location.vtType)
            location = Location(id=loc_id,
                                x=x, 
                                y=y,
                                )
            module_id = self.vistrail.idScope.getNewId(Module.vtType)
            module = Module(id=module_id,
                            name=name,
                            package=identifier,
                            location=location,
                            )
            action = db.services.action.create_action([('add', module)])
            self.vistrail.add_action(action, self.currentVersion)
            self.perform_action(action)

            # FIXME we shouldn't have to return a module
            # we don't do it for any other type
            # doesn't match documentation either
            return module
        else:
            return None
            
    def get_module_connection_ids(self, module_ids, graph):
        # FIXME should probably use a Set here
        connection_ids = {}
        for module_id in module_ids:
            for v, id in graph.edges_from(module_id):
                connection_ids[id] = 1
            for v, id in graph.edges_to(module_id):
                connection_ids[id] = 1
        return connection_ids.keys()

    def deleteModule(self, module_id):
        """ deleteModule(module_id: int) -> version id
        Delete a module from the current pipeline
        
        """
        return self.deleteModuleList([moduleId])

    def deleteModuleList(self, module_ids):
        """ deleteModule(module_ids: [int]) -> [version id]
        Delete multiple modules from the current pipeline
        
        """
        self.emit(QtCore.SIGNAL("flushMoveActions()"))

        graph = self.currentPipeline.graph
        connect_ids = self.get_module_connection_ids(module_ids, graph)
        action_list = []
        for c_id in connect_ids:
            action_list.append(('delete', 
                                self.currentPipeline.connections[c_id]))
        for m_id in module_ids:
            action_list.append(('delete',
                                self.currentPipeline.modules[m_id]))
        action = db.services.action.create_action(action_list)
        self.vistrail.add_action(action, self.currentVersion)
        return self.perform_action(action)

    def moveModuleList(self, move_list):
        """ moveModuleList(move_list: [(id,x,y)]) -> [version id]        
        Move all modules to a new location. No flushMoveActions is
        allowed to to emit to avoid recursive actions
        
        """
        action_list = []
        for (id, x, y) in move_list:
            module = self.currentPipeline.get_module_by_id(id)
            loc_id = self.vistrail.idScope.getNewId(Location.vtType)
            location = Location(id=loc_id,
                                x=x, 
                                y=y,
                                )
            if module.location and module.location.id != -1:
                old_location = module.location
                action_list.append(('change', old_location, location,
                                    module.vtType, module.id))
            else:
                # probably should be an error
                action_list.append(('add', location, module.vtType, module.id))
        action = db.services.action.create_action(action_list)
        self.vistrail.add_action(action, self.currentVersion)        
        return self.perform_action(action)
            
    def add_connection(self, connection):
        """ add_connection(connection: Connection) -> version id
        Add a new connection 'connection' into Vistrail
        
        """
        self.emit(QtCore.SIGNAL("flushMoveActions()"))
        conn_id = self.vistrail.idScope.getNewId(Connection.vtType)
        connection.id = conn_id
        for port in connection.ports:
            port_id = self.vistrail.idScope.getNewId(Port.vtType)
            port.id = port_id
        action = db.services.action.create_action([('add', connection)])
        self.vistrail.add_action(action, self.currentVersion)
        return self.perform_action(action)
    
    def deleteConnection(self, id):
        """ deleteConnection(id: int) -> version id
        Delete a connection with id 'id'
        
        """
        return self.deleteConnectionList([id])

    def deleteConnectionList(self, connect_ids):
        """ deleteConnections(connect_ids: list) -> version id
        Delete a list of connections
        
        """
        self.emit(QtCore.SIGNAL("flushMoveActions()"))
        
        action_list = []
        for c_id in connect_ids:
            action_list.append(('delete', 
                                self.currentPipeline.connections[c_id]))
        action = db.services.action.create_action(action_list)
        self.vistrail.add_action(action, self.currentVersion)
        return self.perform_action(action)

    def deleteMethod(self, function_pos, module_id):
        """ deleteMethod(function_pos: int, module_id: int) -> version id
        Delete a method with function_pos from module module_id

        """
        self.emit(QtCore.SIGNAL("flushMoveActions()"))

        module = self.currentPipeline.get_module_by_id(module_id)
        function = module.functions[function_pos]
        action = db.services.action.create_action([('delete', function,
                                                    module.vtType, module.id)])
        self.vistrail.add_action(action, self.currentVersion)
        return self.perform_action(action)

    def addMethod(self, module_id, function):
        """ addMethod(module_id: int, function: ModuleFunction) -> version_id
        Add a new method into the module's function list
        
        """
        self.emit(QtCore.SIGNAL("flushMoveActions()"))

        module = self.currentPipeline.get_module_by_id(module_id)
        function_id = self.vistrail.idScope.getNewId(ModuleFunction.vtType)
        function.real_id = function_id
        
        # We can only touch the parameters property once during this loop.
        # Otherwise, ModuleFunction._get_params will sort the list from
        # under us and change all the indices.
        params = function.parameters[:]
        
        for i in xrange(len(params)):
            param = params[i]
            param_id = self.vistrail.idScope.getNewId(ModuleParam.vtType)
            param.real_id = param_id
            param.pos = i
        action = db.services.action.create_action([('add', function,
                                                    Module.vtType, module.id)])
        self.vistrail.add_action(action, self.currentVersion)
        return self.perform_action(action)

    def replace_method(self, module, function_pos, param_list):
        """ replace_method(module: Module, function_pos: int, param_list: list)
               -> version_id or None, if new parameter was equal to old one.
        Replaces parameters for a given function
        """
        self.emit(QtCore.SIGNAL("flushMoveActions()"))

        action_list = []
        must_change = False
        for i in xrange(len(param_list)):
            (p_val, p_type, p_alias) = param_list[i]
            function = module.functions[function_pos]
            old_param = function.params[i]
            param_id = self.vistrail.idScope.getNewId(ModuleParam.vtType)
            new_param = ModuleParam(id=param_id,
                                    pos=i,
                                    name='<no description>',
                                    alias=p_alias,
                                    val=p_val,
                                    type=p_type,
                                    )
            must_change |= (new_param != old_param)
            action_list.append(('change', old_param, new_param, 
                                function.vtType, function.real_id))
        if must_change:
            action = db.services.action.create_action(action_list)
            self.vistrail.add_action(action, self.currentVersion)
            return self.perform_action(action)
        else:
            return None

    def deleteAnnotation(self, key, module_id):
        """ deleteAnnotation(key: str, module_id: long) -> version_id
        Deletes an annotation from a module
        
        """
        self.emit(QtCore.SIGNAL("flushMoveActions()"))

        module = self.currentPipeline.get_module_by_id(module_id)
        annotation = module.get_annotation_with_key(key)
        action = db.services.action.create_action([('delete', annotation,
                                                    module.vtType, module.id)])
        self.vistrail.add_action(action, self.currentVersion)
        return self.perform_action(action)

    def addAnnotation(self, pair, module_id):
        """ addAnnotation(pair: (str, str), moduleId: int)        
        Add/Update a key/value pair annotation into the module of
        moduleId
        
        """
        self.emit(QtCore.SIGNAL("flushMoveActions()"))

        assert type(pair[0]) == type('')
        assert type(pair[1]) == type('')
        if pair[0].strip()=='':
            return

        module = self.currentPipeline.get_module_by_id(module_id)
        a_id = self.vistrail.idScope.getNewId(Annotation.vtType)
        annotation = Annotation(id=a_id,
                                key=pair[0], 
                                value=pair[1],
                                )
        if module.has_annotation_with_key(pair[0]):
            old_annotation = module.get_annotation_by_key(pair[0])
            action = \
                db.services.action.create_action([('change', old_annotation,
                                                   annotation,
                                                   module.vtType, module.id)])
        else:
            action = db.services.action.create_action([('add', annotation,
                                                        module.vtType, 
                                                        module.id)])
        self.vistrail.add_action(action, self.currentVersion)
        
        return self.perform_action(action)

    def hasModulePort(self, module_id, port_tuple):
        """ hasModulePort(module_id: int, port_tuple: (str, str)): bool
        Parameters
        ----------
        
        - module_id : 'int'        
        - port_tuple : (portType, portName)

        Returns true if there exists a module port in this module with given params

        """
        (type, name) = port_tuple
        module = self.currentPipeline.get_module_by_id(module_id)
        return len([x for x in module.db_portSpecs
                    if x.name == name and x.type == type]) > 0

    def addModulePort(self, module_id, port_tuple):
        """ addModulePort(module_id: int, port_tuple: (str, str, list)
        Parameters
        ----------
        
        - module_id : 'int'        
        - port_tuple : (portType, portName, portSpec)
        
        """
        self.emit(QtCore.SIGNAL("flushMoveActions()"))
        
        module = self.currentPipeline.get_module_by_id(module_id)
        p_id = self.vistrail.idScope.getNewId(PortSpec.vtType)
        port_spec = PortSpec(id=p_id,
                             type=port_tuple[0],
                             name=port_tuple[1],
                             spec=port_tuple[2],
                             )
        action = db.services.action.create_action([('add', port_spec,
                                                    module.vtType, module.id)])
        self.vistrail.add_action(action, self.currentVersion)
        return self.perform_action(action)

    def deleteModulePort(self, module_id, port_tuple):
        """
        Parameters
        ----------
        
        - module_id : 'int'
        - port_tuple : (portType, portName, portSpec)
        
        """
        self.emit(QtCore.SIGNAL("flushMoveActions()"))

        spec_id = -1
        module = self.currentPipeline.get_module_by_id(module_id)
        port_spec = module.get_portSpec_by_name(port_tuple[1])
        action_list = [('delete', port_spec, module.vtType, module.id)]
        for function in module.functions:
            if function.name == port_spec.name:
                action_list.append(('delete', function, 
                                    module.vtType, module.id))
        action = db.services.action.create_action(action_list)
        self.vistrail.add_action(action, self.currentVersion)
        return self.perform_action(action)

    def updateNotes(self,notes):
        """
        Parameters
        ----------

        - notes : 'QtCore.QString'
        
        """
        self.emit(QtCore.SIGNAL("flushMoveActions()"))
        
        self.vistrail.changenotes(str(notes),self.currentVersion)
        self.setChanged(True)

    def add_parameter_changes_from_execution(self, pipeline, version,
                                             parameter_changes):
        """add_parameter_changes_from_execution(pipeline, version,
        parameter_changes) -> int.

        Adds new versions to the current vistrail as a result of an
        execution. Returns the version number of the new version."""

        type_map = {float: 'Float',
                    int: 'Integer',
                    str: 'String',
                    bool: 'Boolean'}

        def convert_function_parameters(params):
            if (type(function_values) == tuple or
                type(function_values) == list):
                result = []
                for v in params:
                    result.extend(convert_function_parameters(v))
                return result
            else:
                t = type(function_values)
                assert t in type_map
                return [ModuleParam(type=type_map[t],
                                    val=str(function_values))]

        def add_aliases(m_id, f_index, params):
            function = pipeline.modules[m_id].functions[f_index]
            result = []
            for (index, param) in iter_with_index(params):
                result.append((param.strValue, param.type,
                               function.params[index].alias))
            return result

        for (m_id, function_name, function_values) in parameter_changes:
            params = convert_function_parameters(function_values)

            f_index = pipeline.find_method(m_id, function_name)
            if f_index == -1:
                new_method = ModuleFunction(name=function_name,
                                            parameters=params)
                self.addMethod(m_id, new_method)
            else:
                params = add_aliases(m_id, f_index, params)
                self.replace_method(pipeline.modules[m_id],
                                    f_index,
                                    params)

    def executeWorkflowList(self, vistrails):
        if self.currentPipeline:
            locator = self.get_locator()
            if locator:
                locator.clean_temporaries()
                locator.save_temporary(self.vistrail)
        interpreter = get_default_interpreter()
        changed = False
        old_quiet = self.quiet
        self.quiet = True
        for vis in vistrails:
            (locator, version, pipeline, view) = vis
            result = interpreter.execute(self, pipeline, locator, version, view)
            if result.parameter_changes:
                l = result.parameter_changes
                self.add_parameter_changes_from_execution(pipeline,
                                                          version, l)
                changed = True
        self.quiet = old_quiet
        if changed:
            self.invalidate_version_tree()

    def executeCurrentWorkflow(self):
        """ executeCurrentWorkflow() -> None
        Execute the current workflow (if exists)
        
        """
        if self.currentPipeline:
            self.executeWorkflowList([(self.locator,
                                       self.currentVersion,
                                       self.currentPipeline,
                                       self.currentPipelineView)])

    def changeSelectedVersion(self, newVersion):
        """ changeSelectedVersion(newVersion: int) -> None        
        Change the current vistrail version into newVersion and emit a
        notification signal
        
        """
        self.currentVersion = newVersion
        if newVersion>=0:
            try:
                self.currentPipeline = self.vistrail.getPipeline(newVersion)
                self.currentPipeline.ensure_connection_specs()
            except ModuleRegistry.MissingModulePackage, e:
                from gui.application import VistrailsApplication
                QtGui.QMessageBox.critical(VistrailsApplication.builderWindow,
                                           'Missing package',
                                           (('Cannot find module "%s" in \n' % e._name) +
                                             ('package "%s". Make sure package is \n' % e._identifier) +
                                             'enabled in the Preferences dialog.'))
                self.currentPipeline = None
                self.currentVersion = 0
        else:
            self.currentPipeline = None
        self.emit(QtCore.SIGNAL('versionWasChanged'), newVersion)
            
    def resendVersionWasChanged(self):
        """ resendVersionWasChanged() -> None
        Resubmit the notification signal of the current vistrail version
        
        """
        self.emit(QtCore.SIGNAL("flushMoveActions()"))
        self.resetPipelineView = False
        self.emit(QtCore.SIGNAL('versionWasChanged'), self.currentVersion)

    def setSearch(self, search, text=''):
        """ setSearch(search: SearchStmt, text: str) -> None
        Change the currrent version tree search statement
        
        """
        if self.search != search or self.searchStr != text:
            self.search = search
            self.searchStr = text
            if self.search:
                self.search.run(self.vistrail, '')
            self.invalidate_version_tree()
            self.emit(QtCore.SIGNAL('searchChanged'))

    def setRefine(self, refine):
        """ setRefine(refine: bool) -> None
        Set the refine state to True or False
        
        """
        if self.refine!=refine:
            self.refine = refine
            if self.refine:
                self.selectLatestVersion()
            self.invalidate_version_tree()

    def setFullTree(self, full):
        """ setFullTree(full: bool) -> None        
        Set if Vistrails should show a complete version tree or just a
        terse tree
        
        """
        self.fullTree = full
        self.invalidate_version_tree()

    def refineGraph(self):
        """ refineGraph(controller: VistrailController) -> (Graph, Graph)        
        Refine the graph of the current vistrail based the search
        status of the controller. It also return the full graph as a
        reference
        
        """
        if self.fullTree:
            terse = copy.copy(self.vistrail.getVersionGraph())
        else:
            terse = copy.copy(self.vistrail.getTerseGraph())
        full = self.vistrail.getVersionGraph()
        if (not self.refine) or (not self.search):
            return self.ensureCurrentVersion(terse, full)
        am = self.vistrail.actionMap
        
        x=[0]
        while len(x):
            current=x.pop()
            efrom = []
            eto = []
            for f in terse.edges_from(current):
                efrom.append(f)
            for t in terse.edges_to(current):
                eto.append(t)
            for (e1,e2) in efrom:
                x.append(e1)
            if (current !=0 and
                not self.search.match(self.vistrail, am[current]) and
                terse.vertices.__contains__(current)):
                to_me = eto[0][0]
                if terse.vertices.__contains__(to_me):
                    terse.delete_edge(to_me, current, None)
                for from_me in efrom:
                    f_me = from_me[0]
                    if terse.vertices.__contains__(f_me):
                        annotated = -1
                        if full.parent(f_me)==to_me:
                            annotated=0
                        terse.delete_edge(current, f_me, None)
                        terse.add_edge(to_me, f_me, annotated)
                terse.delete_vertex(current)
        self.vistrail.setCurrentGraph(terse)
        return self.ensureCurrentVersion(terse, full)

    def ensureCurrentVersion(self, terse, full):
        """ ensureCurrentVersion(terse: Graph, full: Graph) -> (terse, full)
        Make sure the current version is in the terse graph
        
        """
        prev = self.currentVersion
        if prev>=0 and (not terse.vertices.has_key(prev)):
            if not full.vertices.has_key(prev):
                self.changeSelectedVersion(-1)
                return (terse, full)
            terse = copy.copy(terse)
            # Up-Stream
            parent = prev
            while parent!=-1:
                parent = full.parent(parent)
                if terse.vertices.has_key(parent):
                    terse.add_edge(parent, prev)
                    break

            # Down-Stream
            child = prev
            while True:
                edges = full.edges_from(child)
                assert len(edges)<=1
                if len(edges)==0:
                    break
                child = edges[0][0]
                if terse.vertices.has_key(child):
                    terse.add_edge(prev, child)
                    terse.delete_edge(parent, child)
                    break
        return (terse, full)

    def showPreviousVersion(self):
        """ showPreviousVersion() -> None
        Go back one from the current version and display it
        
        """
        full = self.vistrail.getVersionGraph()
        prev = None
        v = self.currentVersion
        am = self.vistrail.actionMap
        while True:
            parent = full.parent(v)
            if parent==-1:
                prev = 0
                break
            if (self.refine and self.search and
                (not self.search.match(self.vistrail, am[parent]))):
                v = prev
            else:
                prev = parent
                break
        if prev!=None:
            self.changeSelectedVersion(prev)
            self.resetVersionView = False
            self.invalidate_version_tree()
            self.resetVersionView = True

    def pruneVersions(self, versions):
        """ pruneVersions(versions: list of version numbers) -> None
        Prune all versions in 'versions' out of the view
        
        """
        # We need to go up-stream to the highest invisible node
        current = self.vistrail.currentGraph
        if not current:
            (current, full) = self.refineGraph()
        else:
            full = self.vistrail.getVersionGraph()
        changed = False
        for v in versions:
            if v!=0: # not root
                highest = v
                while True:
                    p = full.parent(highest)
                    if p==-1:
                        break
                    if current.vertices.has_key(p):
                        break
                    highest = p
                if highest!=0:
                    changed = True
                self.vistrail.pruneVersion(highest)
        if changed:
            self.setChanged(True)
        self.invalidate_version_tree()

    def selectLatestVersion(self):
        """ selectLatestVersion() -> None
        Try to select the latest visible version on the tree
        
        """
        current = self.vistrail.currentGraph
        if not current:
            (current, full) = self.refineGraph()        
        self.changeSelectedVersion(max(current.iter_vertices()))

    def setSavedQueries(self, queries):
        """ setSavedQueries(queries: list of (str, str, str)) -> None
        Set the saved queries of a vistail
        
        """
        self.vistrail.setSavedQueries(queries)
        self.setChanged(True)
        
    def updateCurrentTag(self,tag):
        """ updateCurrentTag(tag: str) -> None
        Update the current vistrail tag
        
        """
        self.emit(QtCore.SIGNAL("flushMoveActions()"))

#         pInspector = PipelineInspector()
#         if self.currentPipeline:
#             pInspector.inspect_input_output_ports(self.currentPipeline)
            
        try:
            if self.vistrail.hasTag(self.currentVersion):
                self.vistrail.changeTag(tag, self.currentVersion)
            else:
                self.vistrail.addTag(tag, self.currentVersion)
        except TagExists:
            show_warning('Name Exists',
                         "There is already another version named '%s'.\n"
                         "Please enter a different one." % tag)
            return

#         if pInspector.is_sub_module() and tag!='':
#             ans = show_question("Add Sub-Module",
#                                 "'%s' can be used as a module in VisTrails. "
#                                 "Do you want to add it to VisTrails Modules?"
#                                 % tag,
#                                 [YES_BUTTON, NO_BUTTON], YES_BUTTON)
#             if ans==YES_BUTTON:
#                 self.addSubModule(tag, self.name, self.vistrail, self.fileName,
#                                   self.currentVersion, pInspector)
        self.setChanged(True)

        self.resetVersionView = False
        self.invalidate_version_tree()
        self.resetVersionView = True
        
    def performAction(self, action, quiet=None):
        """ performAction(action: Action, quiet=None) -> timestep
        Add version to vistrail, updates the current pipeline, and the
        rest of the UI know a new pipeline is selected.

        quiet and self.quiet controlds invalidation of version
        tree. If quiet is set to any value, it overrides the field
        value self.quiet.

        If the value is True, then no invalidation happens (gui is not
        updated.)
        
        """
        newTimestep = self.vistrail.getFreshTimestep()
        action.timestep = newTimestep
        action.parent = self.currentVersion
        action.date = self.vistrail.getDate()
        action.user = self.vistrail.getUser()
        self.vistrail.addVersion(action)

        action.perform(self.currentPipeline)
        self.currentVersion = newTimestep
        
        self.setChanged(True)

        if quiet is None:
            if not self.quiet:
                self.invalidate_version_tree()
        else:
            if not quiet:
                self.invalidate_version_tree()
        return newTimestep

    def performBulkActions(self, actions):
        """performBulkAction(actions: [Action]) -> timestep        
        Add version to vistrail, updates the current pipeline, and the
        rest of the UI know a new pipeline is selected only after all
        actions are performed
        
        """
        newTimestep = -1
        for action in actions:
            self.vistrail.add_action(action, self.currentVersion)
            self.currentPipeline.perform_action(action)
            newTimestep = action.db_id
            self.currentVersion = action.db_id

        if newTimestep != -1 and not self.quiet:
            self.setChanged(True)
            self.invalidate_version_tree()
        
        return newTimestep

    def copyModulesAndConnections(self, modules, connections):
        """copyModulesAndConnections(modules: [Module],
                                     connections: [Connection]) -> str
        Serializes a list of modules and connections
        """
        self.emit(QtCore.SIGNAL("flushMoveActions()"))

        pipeline = Pipeline()
        for module in modules:
            pipeline.add_module(module)
        for connection in connections:
            pipeline.add_connection(connection)
        return core.db.io.serialize(pipeline)
        
    def pasteModulesAndConnections(self, str):
        """ pasteModulesAndConnections(str) -> [id list]
        Paste a list of modules and connections into the current pipeline.

        Returns the list of module ids of added modules

        """
        self.emit(QtCore.SIGNAL("flushMoveActions()"))

        pipeline = core.db.io.unserialize(str, Pipeline)
        action = core.db.action.create_paste_action(pipeline, 
                                                    self.vistrail.idScope)
        modules = []
        for op in action.operations:
            if op.what == 'module':
                modules.append(op.objectId)
        self.vistrail.add_action(action, self.currentVersion)
        self.perform_action(action)
        return modules

    def create_abstraction(self, modules, connections):
        self.emit(QtCore.SIGNAL("flushMoveActions()"))

        abstraction = Abstraction(id=-1, name='')

        ops = []
        module_remap = {}
        avg_x = 0.0
        avg_y = 0.0
        for module in modules.itervalues():
            module = copy.copy(module)
            old_id = module.id
#             if module.location is not None:
#                 loc_id = self.vistrail.idScope.getNewId(Location.vtType)
#                 module.location = Location(id=loc_id,
#                                            x=module.location.x,
#                                            y=module.location.y,
#                                            )
            avg_x += module.location.x
            avg_y += module.location.y
            mops = db.services.action.create_copy_op_chain(object=module,
                                               id_scope=abstraction.idScope)
            module_remap[old_id] = mops[0].db_objectId
            ops.extend(mops)
        for connection in connections.itervalues():
            # if a connection has an "external" connection, we need to
            # create an input port or output port module
            connection = copy.copy(connection)
            for port in connection.ports:
                if module_remap.has_key(port.moduleId):
                    # internal connection
                    port.moduleId = module_remap[port.moduleId]
                else:
                    # external connection
                    if port.endPoint == PortEndPoint.Source:
                        port_type = InputPort.__class__.__name__
                    elif port.endPoint == PortEndPoint.Destination:
                        port_type = OutputPort.__class__.__name__
                    
                    loc_id = abstraction.idScope.getNewId(Location.vtType)
                    # FIXME get better location
                    location = Location(id=loc_id,
                                        x=0.0,
                                        y=0.0,
                                        )
                    new_id = abstraction.idScope.getNewId(Module.vtType)
                    module = Module(id=new_id,
                                    abstraction=-1,
                                    name=port_type,
                                    location=location,
                                    )
                    port.moduleId=new_id
            ops.extend( \
                db.services.action.create_copy_op_chain(object=connection,
                                               id_scope=abstraction.idScope))
        action = db.services.action.create_action_from_ops(ops)
        abstraction.add_action(action)
        self.vistrail.add_abstraction(abstraction)

        # now add module encoding abstraction reference to vistrail
        loc_id = self.vistrail.idScope.getNewId(Location.vtType)
        location = Location(id=loc_id,
                            x=avg_x, 
                            y=avg_y,
                            )
        module_id = self.vistrail.idScope.getNewId(Module.vtType)
        module = Module(id=module_id,
                        abstraction=abstraction.id,
                        version='1',
                        name=name, 
                        location=location,
                        )
        action = db.services.action.create_action([('add', module)])
        self.vistrail.add_action(action, self.currentVersion)
        self.perform_action(action)

        # FIXME we shouldn't have to return a module
        # we don't do it for any other type
        # doesn't match documentation either
        return module

    def setVersion(self, newVersion):
        """ setVersion(newVersion: int) -> None
        Change the controller to newVersion

        """
        if not self.vistrail.hasVersion(newVersion):
            raise VistrailsInternalError("Can't change VistrailController "
                                         "to a non-existant version")
        self.currentVersion = newVersion

        self.emit(QtCore.SIGNAL("versionWasChanged"), newVersion)

    def setChanged(self, changed):
        """ setChanged(changed: bool) -> None
        Set the current state of changed and emit signal accordingly
        
        """
        if changed!=self.changed:
            self.changed = changed
            self.emit(QtCore.SIGNAL('stateChanged'))

    def setFileName(self, fileName):
        """ setFileName(fileName: str) -> None
        Change the controller file name
        
        """
        if fileName == None:
            fileName = ''
        if self.fileName!=fileName:
            self.fileName = fileName
            self.name = os.path.split(fileName)[1]
            if self.name=='':
                self.name = 'Untitled.xml'
            self.emit(QtCore.SIGNAL('stateChanged'))

    def checkAlias(self, name):
        """checkAlias(alias) -> Boolean 
        Returns True if current pipeline has an alias named name """
        return self.currentPipeline.has_alias(name)

    def write_temporary(self):
        if self.vistrail and self.changed:
            locator = self.get_locator()
            if locator:
                locator.save_temporary(self.vistrail)

    def write_vistrail(self, locator):
        if self.vistrail and (self.changed or
                              self.locator != locator):
            old_locator = self.get_locator()
            self.locator = locator
            self.locator.save(self.vistrail)
            self.setChanged(False)
            self.setFileName(locator.name)
            if old_locator:
                old_locator.clean_temporaries()

    def queryByExample(self, pipeline):
        """ queryByExample(pipeline: Pipeline) -> None
        Perform visual query on the current vistrail
        
        """
        if len(pipeline.modules)==0:
            search = TrueSearch()
        else:
            search = VisualQuery(pipeline)

        self.setSearch(search, '') # pipeline.dump_to_string())

    def addSubModule(self, moduleName, packageName, vistrail,
                     fileName, version, inspector):
        """ addSubModule(moduleName: str,
                         packageName: str,
                         vistrail: Vistrail,
                         fileName: str,
                         version: int,
                         inspector: PipelineInspector) -> SubModule
        Wrap sub_module.addSubModule to show GUI dialogs
        
        """
        raise VistrailsInternalError("Currently broken")
#         try:
#             return addSubModule(moduleName, packageName, vistrail, fileName,
#                                 version, inspector)
#         except ModuleAlreadyExists:
#             show_warning('Module Exists',
#                          "Failed to registered '%s' as a module "
#                          "because there is already another module with "
#                          "the same name. Please change the version name "
#                          "and manually add it later." % moduleName)
#         except DupplicateSubModule:
#             show_warning('Module Exists',
#                          "Failed to registered '%s' as a module "
#                          "because it is already registered." % moduleName)

    def inspectAndImportModules(self):
        """ inspectAndImportModules() -> None        
        Go through all named pipelines and ask user to import them
        
        """

        # Currently broken
        pass
#         importModule = False
#         inspector = PipelineInspector()
#         for version in sorted(self.vistrail.inverseTagMap.keys()):
#             tag = self.vistrail.inverseTagMap[version]
#             if tag!='':
#                 pipeline = self.vistrail.getPipeline(version)
#                 inspector.inspect(pipeline)
#                 if inspector.is_sub_module():
#                     if importModule==False:
#                         res = show_question('Import Modules',
#                                             "'%s' contains importable modules. "
#                                             "Do you want to import all of them?"
#                                             % self.name,
#                                             [YES_BUTTON, NO_BUTTON], YES_BUTTON)
#                         if res==YES_BUTTON:
#                             importModule = True
#                         else:
#                             return
#                     if importModule:
#                         self.addSubModule(tag, self.name, self.vistrail,
#                                           self.fileName, version,
#                                           inspector)

    def create_abstraction(self, subgraph):
        self.vistrail.create_abstraction(self.currentVersion,
                                         subgraph,
                                         'FOOBAR')

    ##########################################################################
    # analogies

    def add_analogy(self, analogy_name, version_from, version_to):
        assert type(analogy_name) == str
        assert type(version_from) == int
        assert type(version_to) == int
        if analogy_name in self.analogy:
            raise VistrailsInternalError("duplicated analogy name '%s'" %
                                         analogy_name)
        self.analogy[analogy_name] = (version_from, version_to)

    def remove_analogy(self, analogy_name):
        if analogy_name not in self.analogy:
            raise VistrailsInternalError("missing analogy '%s'" %
                                         analogy_name)
        del self.analogy[analogy_name]

    def perform_analogy(self, analogy_name, analogy_target, invalidate=True):
        if analogy_name not in self.analogy:
            raise VistrailsInternalError("missing analogy '%s'" %
                                         analogy_name)
        (a, b) = self.analogy[analogy_name]
        c = analogy_target
        core.analogy.perform_analogy_on_vistrail(self.vistrail,
                                                 a, b, c)
        self.setChanged(True)
        if invalidate:
            self.invalidate_version_tree()
