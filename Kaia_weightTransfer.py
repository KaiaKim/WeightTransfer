### Weight transfer Tool ###
# Discription: Transfer single weight across skinCluster, blendShape, nCloth, and Deformers.
# Autuor: Kaia Kim
# Version: 0.5.0

# How to use: Select an influence inside any Paint Tool. Hit copy or paste

#-----------------------------------IMPORT--------------------------------------
import sys

import maya.api.OpenMaya as om
import maya.api.OpenMayaAnim as oma
import maya.OpenMayaUI as omui
import maya.cmds as cmds
import maya.mel as mel

from PySide2 import QtCore
from PySide2 import QtWidgets
from shiboken2 import wrapInstance

import time

#--------------------------------UTILITY CLASS--------------------------------------
class WeightTransferUtil():
    def initialCheck(self, sel, qCheck=False, eCheck=False):
        # We're doing the operation on one mesh.
        if sel.length() != 1:
            om.MGlobal.displayError("There must be only one selection.")
            return
            
        # We're doing the operation on poligon shape node.
        try:
            current_shape = sel.getDagPath(0).extendToShape() # dag
        except:
            om.MGlobal.displayError("Selection must have a shape node directly parented under.")
            return
        
        # Only poligon mesh! No Nurbs surface.
        if current_shape.apiType() != 296: 
            om.MGlobal.displayError("Selection must be a poligon mesh.")
            return
        
        # When pasting the weight, is the source mesh same to the current mesh?
        if self.source_shape and eCheck:   # if source shape is not None
            if self.source_shape != current_shape:
                om.MGlobal.displayWarning("The source mesh is not same to the target mesh. Users might get unexpected results.")
        
        # What tool are we using?
        tool_ctx = cmds.currentCtx() # context is the instance of the tool class
        current_tool = cmds.contextInfo(tool_ctx, q=True, c=True) # c is class type
        
        tool_ls = ["artAttrSkin","artAttrBlendShape", "artAttrNCloth", "artAttr"]
        tool_name_ls = ["Paint Skin Weight","Paint Blend Shape Weights","Paint nCloth Attributes", "Paint Attributes"]
        if current_tool not in tool_ls:
            om.MGlobal.displayError("Current tool must be either {0}, {1}, {2}, or {3}.".format(*tool_name_ls))
            return
        
        # What node & attribute are we painting?
        # example: 'deltaMush.deltaMush1.weights'
        attr_ctx = cmds.artAttrCtx(tool_ctx, q=True, asl=True)
        if attr_ctx == '':
            om.MGlobal.displayError("User must select an attribute to paint.")
            return
            
        current_type, current_node, current_paint = attr_ctx.split(".")
        
        # If the user painting skin weights, we must know the specific joint name. Overriding current_paint.
        # User might select multiple joints. 
        if current_tool == "artAttrSkin": #Paint Skin Weights Tool
            current_paint = mel.eval('string $selectedInfs[] = `treeView -q -si $gArtSkinInfluencesList`') # list
            if current_paint == []:
                om.MGlobal.displayError("An influence must be selected inside Paint Skin Weights Tool.")
                return
        
        return current_tool, current_shape, current_type, current_node, current_paint


    def querySkinWeights(self, shape_dag, skinclst, infs):
        # Get objects & function sets...
        skinclst_obj = om.MSelectionList().add(skinclst).getDependNode(0) # Mobject
        skinclst_fn = oma.MFnSkinCluster(skinclst_obj)
        
         # Create an empty array...
        weights = om.MDoubleArray()
        
        # Iterate over every vertices...
        itVerts = om.MItMeshVertex(shape_dag)
        while not itVerts.isDone():
            vert_obj = itVerts.currentItem() # MObject
            
            ###QUERY WEIGHTS
            weight = 0.0
            for inf in infs:
                # Get an index for each influence...
                inf_dag = om.MSelectionList().add(inf).getDagPath(0)
                inf_idx = skinclst_fn.indexForInfluenceObject(inf_dag) # int
                
                x = skinclst_fn.getWeights(shape_dag, vert_obj, inf_idx)[0] # float
                weight += x
                
            weights.append(weight)
            
            itVerts.next()

        # Store queried data...
        self.source_weights = weights
        self.source_shape = shape_dag
        
        om.MGlobal.displayInfo("Copy skin weights success!")
        
        
    def queryBlendWeights(self, shape_dag, blendShape, paint):
        # There is no dedicated function set for accessing blendshape deformer weights (not blendshape weights!)
        # Therefore we"re accessing those values using Mplug object.
        
        # Get blendshape node function set...
        blendShape_obj = om.MSelectionList().add(blendShape).getDependNode(0) # Mobject
        blendShape_fn = om.MFnDependencyNode(blendShape_obj)
        
        # Get the weight plug...
        inputTarget_plug = blendShape_fn.findPlug("inputTarget", True).elementByPhysicalIndex(0)
        # result: blendshape.inputTarget[0]
        if paint == 'baseWeights':
            paint_plug = inputTarget_plug.child(1)
            # result: blendshape.inputTarget[0].baseWeights
        elif paint == 'paintTargetWeights':
            paint_plug = inputTarget_plug.child(3)
            # result: blendshape.inputTarget[0].paintTargetWeights
        
        # Create an empty array...
        weights = om.MDoubleArray()
        
        # Iterate over every vertices...
        itVerts = om.MItMeshVertex(shape_dag)
        while not itVerts.isDone():
            i = itVerts.index()
            child_plug = paint_plug.elementByLogicalIndex(i) # MPlug
            
            ###QUERY WEIGHTS
            weight = child_plug.asFloat() # float
            weights.append(weight)
            
            itVerts.next()
        
        # update display (color feedback)...
        mel.eval("artAttrBlendShapeValues artAttrBlendShapeContext;")
        
        # Store queried data...
        self.source_shape = shape_dag
        self.source_weights = weights

        om.MGlobal.displayInfo("Copy blendshape weights success!")
        
        
    def queryNClothWeights(self):
        pass
    
        
    def queryDeformerWeights(self, shape_dag, deformer_name, deformer_type, paint):
        # Get deformer node
        deformer_obj = om.MSelectionList().add(deformer_name).getDependNode(0) # MObject
        
        if self.version >= 2024:
            # maya 2024 has MFnWeightGeometryFilter
            weightGeoFilter_fn = oma.MFnWeightGeometryFilter(deformer_obj)

        elif self.version < 2024:
            # maya 2022 doesn't have MFnWeightGeometryFilter
            geoFilter_fn = oma.MFnGeometryFilter(deformer_obj)
            # Get shape node
            shape_obj = om.MSelectionList().add(shape_dag).getDependNode(0)
            # Get plug index for connected shape
            i = geoFilter_fn.indexForOutputShape(shape_obj)
            #print('shape index', i)
            # Get the weight plug...
            weightList_plug = geoFilter_fn.findPlug("weightList", True).elementByPhysicalIndex(i)
            #print('weightList_plug', weightList_plug)
            weight_plug = weightList_plug.child(0)
            #print('weight_plug', weight_plug)
            
                
        # Create an empty array...
        weights = om.MDoubleArray()
        # Iterate over every vertices...
        itVerts = om.MItMeshVertex(shape_dag)
        ###QUERY WEIGHTS
        while not itVerts.isDone():
            if self.version >= 2024:
                vert_obj = itVerts.currentItem() # MObject
                weight = weightGeoFilter_fn.getWeights(shape_dag, vert_obj)[0] # float
                # * path (MDagPath) - The path of the DAG object that has the components.
                # * components (MObject) - The components whose weights are requested.
            elif self.version < 2024:
                i = itVerts.index()
                child_plug = weight_plug.elementByLogicalIndex(i) # MPlug
                # result example: ffd2.weightList[i].weights[j]
                weight = child_plug.asFloat() # float
                
            weights.append(weight)
            itVerts.next()

        # Store queried data...
        self.source_shape = shape_dag
        self.source_weights = weights

        om.MGlobal.displayInfo("Copy deformer({0}) weights success!".format(deformer_type))

        
        
    
    
    def editSkinWeights(self, shape_dag, skinclst, infs):
        # Get names & objects & function sets...
        shape_name = shape_dag.fullPathName() # str
        skinclst_obj = om.MSelectionList().add(skinclst).getDependNode(0) # Mobject
        skinclst_fn = oma.MFnSkinCluster(skinclst_obj)
        
        # if there's one inf selection get the first(and only) element
        # if there's multiple inf selection, we have to query last selected influence...
        if len(infs) == 1:
            inf = infs[0]
        elif len(infs) > 1:
            inf = mel.eval('string	$influence = $artSkinLastSelectedInfluence;')
            # Same to cmds.artAttrSkinPaintCtx(cmds.currentCtx(), q=True, inf=True) but faster
 
        # Get index for the influence...
        inf_dag = om.MSelectionList().add(inf).getDagPath(0) # dag
        inf_idx = skinclst_fn.indexForInfluenceObject(inf_dag) # int
        
        # Check for lock/unlock state for the influences...
        allInf_array = skinclst_fn.influenceObjects() # MDagPathArray
        unlock_count = 0
        for num, i in enumerate(allInf_array):
            if i == inf_dag:
                continue # skip the target influence. Doesn"t matter.
            locked = cmds.getAttr(skinclst+".lockWeights[{0}]".format(num))
            if not locked:
                unlock_count += 1
        
        # Display Warning if the unlock count is not 1 (except target inf)...
        if unlock_count == 0:
            om.MGlobal.displayWarning("None of influences is unlocked. Weights can't be normalized due to locked influences.")
        elif unlock_count > 1:
            om.MGlobal.displayWarning("Multiple influences are unlocked. Weights might leak into unwanted influences.")
        
        cmds.scriptEditorInfo(suppressWarnings = True)

        # Iterate over every vertices...
        itVerts = om.MItMeshVertex(shape_dag)
        while not itVerts.isDone():
            i = itVerts.index()
            vert_obj = itVerts.currentItem() #MObject
            try:
                weight = self.source_weights[i] # float
            except:
                weight = 0.0 # if source verts < target verts: index out of range. Set default value to 0.
            
            # Calculate add, scale, replace operation...
            old_weight = skinclst_fn.getWeights(shape_dag, vert_obj, inf_idx)[0] # MDoublearray > float
            if self.add_rb.isChecked():
                weight += old_weight
            elif self.scale_rb.isChecked():
                weight *= old_weight
                
            if weight > 1:
                weight = 1.0
            
            ###EDIT WEIGHTS
            # Those two method does the same thing. API is faster, but is not undoable.
            if self.undoable:
                vert = "{0}.vtx[{1}]".format(shape_name, i)
                cmds.skinPercent(skinclst, vert, tv=(inf, weight), normalize=True)

            elif not self.undoable:
                skinclst_fn.setWeights(shape_dag, vert_obj, inf_idx, weight, normalize=True)

            itVerts.next()
            
        cmds.scriptEditorInfo(suppressWarnings = False)
        om.MGlobal.displayInfo("Paste skin weight success!")
        
        
    def editBlendWeights(self, shape_dag, blendShape, paint):
        # Get blendshape node function set...
        blendShape_obj = om.MSelectionList().add(blendShape).getDependNode(0) # Mobject
        blendShape_fn = om.MFnDependencyNode(blendShape_obj)
        
        # Get the weight plug...
        inputTarget_plug = blendShape_fn.findPlug("inputTarget", True).elementByPhysicalIndex(0)
        # result: blendshape.inputTarget[0]
        if paint == 'baseWeights':
            paint_plug = inputTarget_plug.child(1)
            # result: blendshape.inputTarget[0].baseWeights
        elif paint == 'paintTargetWeights':
            paint_plug = inputTarget_plug.child(3)
            # result: blendshape.inputTarget[0].paintTargetWeights
        
        # Iterate over every vertices...
        itVerts = om.MItMeshVertex(shape_dag)
        while not itVerts.isDone():
            i = itVerts.index()
            child_plug = paint_plug.elementByLogicalIndex(i) # MPlug
            # result: blendShape.inputTarget[0].baseWeights[99]
            
            if child_plug.isLocked:
                om.MGlobal.displayError("{0} plug is locked. Abort pasting weights.".format(child_plug)) 
                return # might cause error when the loop is in process
            elif child_plug.isConnected:
                om.MGlobal.displayError("{0} plug is connected. Abort pasting weights.".format(child_plug))
                return

            try:
                weight = self.source_weights[i] # float
            except:
                weight = 0.0 # if source verts < target verts: index out of range... Set default value to 0.
            
            # Calculate add, scale, replace operation...
            old_weight = child_plug.asFloat()
            if self.add_rb.isChecked():
                weight += old_weight
            elif self.scale_rb.isChecked():
                weight *= old_weight
            
            ###EDIT WEIGHTS
            if self.undoable:
                attr = child_plug.name()
                cmds.setAttr(attr, weight)
            elif not self.undoable:
                child_plug.setFloat(weight)
            
            itVerts.next()
        
        # update display (color feedback)...
        mel.eval("artAttrBlendShapeValues artAttrBlendShapeContext;")
        
        om.MGlobal.displayInfo("Paste blendshape weights success!")
    
        
    def editNClothWeights(self):
        pass
    
        
    def editDeformerWeights(self, shape_dag, deformer_name, deformer_type, paint):
        deformer_obj = om.MSelectionList().add(deformer_name).getDependNode(0) # Mobject
        
        if self.version >= 2024:
            # maya 2024 has MFnWeightGeometryFilter
            weightGeoFilter_fn = oma.MFnWeightGeometryFilter(deformer_obj)
            sel = om.MSelectionList().add(shape_dag)
            plugs = weightGeoFilter_fn.getWeightPlugStrings(sel)
            
        elif self.version < 2024:
            # maya 2022 doesn't have MFnWeightGeometryFilter
            geoFilter_fn = oma.MFnGeometryFilter(deformer_obj)
            # Get shape node
            shape_obj = om.MSelectionList().add(shape_dag).getDependNode(0)
            # Get plug index for connected shape
            i = geoFilter_fn.indexForOutputShape(shape_obj)
            # Get the weight plug...
            weightList_plug = geoFilter_fn.findPlug("weightList", True).elementByPhysicalIndex(i)
            weight_plug = weightList_plug.child(0)

        # Iterate over every vertices...
        itVerts = om.MItMeshVertex(shape_dag)
        while not itVerts.isDone():
            i = itVerts.index()
            vert_obj = itVerts.currentItem() # MObject
            
            try:
                weight = self.source_weights[i] # float
            except:
                weight = 0.0 # if source verts < target verts: index out of range... Set default value to 0.
            
            if self.version >= 2024:
                old_weight = weightGeoFilter_fn.getWeights(shape_dag, vert_obj)[0] # float
            elif self.version < 2024:
                child_plug = weight_plug.elementByLogicalIndex(i) # MPlug
                old_weight = child_plug.asFloat() # float
                
            # Calculate add, scale, replace operation...
            if self.add_rb.isChecked():
                weight += old_weight
            elif self.scale_rb.isChecked():
                weight *= old_weight
                
            # Normalize weights
            if weight > 1:
                weight = 1.0
                    
            if self.version >= 2024:
                ###EDIT WEIGHTS
                if self.undoable:
                    attr = str(plugs[i])
                    cmds.setAttr(attr, weight)
                elif not self.undoable:
                    weightGeoFilter_fn.setWeights(shape_dag, vert_obj, weight) # float
            
            elif self.version < 2024:
                child_plug.setFloat(weight)

            itVerts.next()


        om.MGlobal.displayInfo("Paste deformer({0}) weights success!".format(deformer_type))


#-------------------------------------UI CLASS-----------------------------------------
def maya_main_window():
    """Return the Maya main window widget as a Python object"""
    main_window_ptr = omui.MQtUtil.mainWindow()
    
    if sys.version_info.major >= 3: # Python 3 or higher
        return wrapInstance(int(main_window_ptr), QtWidgets.QWidget)
    else:
        return wrapInstance(long(main_window_ptr), QtWidgets.QWidget)



class WeightTransferDialog(QtWidgets.QDialog, WeightTransferUtil):
    def __init__(self, parent=maya_main_window()):
        super().__init__(parent)
        
        ###
        self.version = int( cmds.about(version=True) )
        self.undoable = True
        self.source_shape = None
        self.source_weights = None
        
        self.setWindowTitle("Weight Transfer Tool")
        self.setMinimumWidth(250)
        
        # Remove the ? from the dialog on Windows
        self.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)
        
        # self.setWindowFlags(self.windowFlags() ^ QtCore.Qt.WindowContextHelpButtonHint)
        self.create_widgets()
        self.create_layouts()
        self.create_connections()
        
        
        
    def create_widgets(self):
        t1 = "Transfer single weight across \nskinCluster, blendShape, nCloth, deformers."
        t2 = "Select an influence inside any Paint Tool."
        self.discription = QtWidgets.QLabel( t1 + "\n\n" + t2 + "\n")
        self.timer_lb = QtWidgets.QLabel("timer:")
        
        self.undoable_cb = QtWidgets.QCheckBox("Undoable")
        self.undoable_cb.setChecked(True)
        
        self.copy_btn = QtWidgets.QPushButton("Copy")
        self.paste_btn = QtWidgets.QPushButton("Paste")
        self.paste_btn.setEnabled(False)
        
        self.replace_rb = QtWidgets.QRadioButton("Replace")
        self.add_rb = QtWidgets.QRadioButton("Add")
        self.scale_rb = QtWidgets.QRadioButton("Scale")
        self.replace_rb.setChecked(True)

    
    def create_layouts(self):
        
        disc_layout = QtWidgets.QHBoxLayout()
        disc_layout.addWidget(self.discription)
        
        option_layout = QtWidgets.QHBoxLayout()
        option_layout.addWidget(self.replace_rb)
        option_layout.addWidget(self.add_rb)
        option_layout.addWidget(self.scale_rb)
        
        undoable_layout = QtWidgets.QHBoxLayout()
        undoable_layout.addStretch()
        undoable_layout.addWidget(self.undoable_cb)
        
        
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addWidget(self.timer_lb)
        button_layout.addStretch()
        button_layout.addWidget(self.copy_btn)
        button_layout.addWidget(self.paste_btn)

        
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.addLayout(disc_layout)
        main_layout.addLayout(option_layout)
        main_layout.addLayout(undoable_layout)
        main_layout.addLayout(button_layout)
        
    def create_connections(self):
        self.undoable_cb.toggled.connect(self.undo_toggle)
        self.copy_btn.clicked.connect(self.copy_clicked)
        self.paste_btn.clicked.connect(self.paste_clicked)
        
    def undo_toggle(self, checked):
        self.undoable = checked
    
    def copy_clicked(self):
        # start timer
        start = time.time()
        # get selection
        sel = om.MGlobal.getActiveSelectionList()
        # error check & get data
        try:
            tool, shape, node_type, node_name, paint = self.initialCheck(sel, qCheck=True)
        except:
            return
        
        if tool == "artAttrSkin":
            self.querySkinWeights(shape, node_name, paint)
        elif tool == "artAttrBlendShape":
            self.queryBlendWeights(shape, node_name, paint)
        elif tool == "artAttrNCloth":
            self.queryNClothWeights()
        elif tool == "artAttr":
            self.queryDeformerWeights(shape, node_name, node_type, paint)
        # restore selection
        om.MGlobal.setActiveSelectionList(sel)
        
        # If successfully get the shape & weights, enable paste button
        if tool and self.source_shape and self.source_weights:
            self.paste_btn.setEnabled(True)
        
        # print time(speed)
        t = 'timer: {:.3f}s\n'.format(time.time()-start)
        self.timer_lb.setText(t)
        
        
    def paste_clicked(self):
        # start timer
        start = time.time()
        # get selection
        sel = om.MGlobal.getActiveSelectionList()
        # error check & get data
        try:
            tool, shape, node_type, node_name, paint = self.initialCheck(sel, eCheck=True)
        except:
            return
        
        cmds.undoInfo(openChunk=True)
        
        if tool == "artAttrSkin":
            # Performance warning for high poly mesh. Continue? [y] [n]
            shape_name = shape.fullPathName()
            vCount = cmds.polyEvaluate(shape_name, v=True)
            if vCount > 9999:
                self.show_warning_dialog()
                if self.ret == self.qm.No:
                    cmds.undoInfo(closeChunk=True)
                    return
            self.editSkinWeights(shape, node_name, paint)
        elif tool == "artAttrBlendShape":
            self.editBlendWeights(shape, node_name, paint)
        elif tool == "artAttrNCloth":
            self.editNClothWeights()
        elif tool == "artAttr":
            self.editDeformerWeights(shape, node_name, node_type, paint)
            
        cmds.undoInfo(closeChunk=True)
        
        # restore selection
        om.MGlobal.setActiveSelectionList(sel)
        # print time(speed)
        t = 'timer: {:.3f}s\n'.format(time.time()-start)
        self.timer_lb.setText(t)
    
    
    def show_warning_dialog(self):
        self.qm = QtWidgets.QMessageBox()
        qm_title = "Performance Warning"
        qm_text = "Pasting skin weight might take long time, because of normalization.\nContinue?"
        self.ret = self.qm.warning(self, qm_title, qm_text, self.qm.Yes | self.qm.No)



        
if __name__ == "__main__":
    try:
        test_dialog.close() # pylint: disable=E0601 # << removing the error message for this specific line
        test_dialog.deleteLater()
    except:
        pass
    test_dialog = WeightTransferDialog()
    test_dialog.show()
