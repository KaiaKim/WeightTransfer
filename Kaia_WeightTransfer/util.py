import maya.api.OpenMaya as om
import maya.api.OpenMayaAnim as oma
import maya.cmds as cmds
import maya.mel as mel


### tool that transfer current influence weight to another (skinCluster or Deformer) influence
class WeightTransferCompute():
    def __init__(self):
        pass
    
    def initialCheck(self, sel, qCheck=False, eCheck=False):
        # We're doing the operation on one mesh.
        if sel.length() != 1:
            om.MGlobal.displayError("There must be only one selection.")
            
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
        context = cmds.currentCtx() # context is the instance of the tool class
        current_tool = cmds.contextInfo(context, q=True, c=True) # c is class type
        
        if current_tool == "artAttrSkin": #Paint Skin Weights Tool
            # Get maya version...
            v = cmds.about(version=True) # str <- stupid
            v = int(v)
            # Get skincluster node...
            if v < 2024:
                skinclst = cmds.ls(cmds.listHistory(current_shape.fullPathName()), type="skinCluster")
            elif v >= 2024:
                skinclst = cmds.textScrollList("skinClusterPaintList", q=True, si=True)[0] 
                # maya 2024 supports multiple skinclst
            
            # Get selected influences...
            selected_inf = mel.eval('string $selectedInfs[] = `treeView -q -si $gArtSkinInfluencesList`') # list
            if selected_inf == []:
                om.MGlobal.displayError("An influence must be selected inside Paint Skin Weights Tool.")
                return
            
            ###
            current_deformer = skinclst
            current_paint = selected_inf 
            
        elif current_tool == "artAttrBlendShape":
            # There might be a smarter way to get blendshape node? Currently we"re querying it from the context
            selected_attr = cmds.artAttrCtx(context, q=True, asl=True)
            # result: blendShape.blendShape1.paintTargetWeights
            bsNode = selected_attr.split(".")[1]
            
            # We just have to know if we"re painting base weight or not.
            # paintTargetWeights plug(below) will figure out which target we are painting.
            idx1, idx2 = mel.eval("artBlendShapeTargetIndex;") # int, int
            # result: base weight is 1, 0
            # result: target weight is 0, n
            
            ###
            current_deformer = bsNode
            current_paint = idx1 
                
        elif current_tool == "artAttrNCloth":
            pass
        elif current_tool == "artAttr":
            pass
        else:
            om.MGlobal.displayError("Current tool must be either Paint Skin Weights Tool, Paint Blend Shape Weights Tool, Paint nCloth Attributes Tool, or Paint Attributes Tool.")
            return
        
        return current_shape, current_deformer, current_tool, current_paint
        

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
        
        
    def queryBlendWeights(self, shape_dag, blendShape, target):
        # There is no dedicated function set for accessing blendshape deformer weights (not blendshape weights!)
        # Therefore we"re accessing those values using Mplug object.
        
        # Get blendshape node function set...
        blendShape_obj = om.MSelectionList().add(blendShape).getDependNode(0) # Mobject
        blendShape_fn = om.MFnDependencyNode(blendShape_obj)
        
        # Get the weight plug...
        inputTarget_plug = blendShape_fn.findPlug("inputTarget", True).elementByPhysicalIndex(0)
        # result: blendshape.inputTarget[0]
        if target == 1:
            paint_plug = inputTarget_plug.child(1)
            # result: blendshape.inputTarget[0].baseWeights
        elif target == 0:
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
    
        
    def queryDeformerWeights(self):
        deformer = "cluster1"
        deformer_obj = om.MSelectionList().add(deformer).getDependNode(0) # Mobject
        weightGeoFilter_fn = oma.MFnWeightGeometryFilter(deformer_obj)

        print("deformer:", deformer)
        print("deformer_obj:", deformer_obj, type(deformer_obj))
        print("weightGeoFilter_fn:", weightGeoFilter_fn, type(weightGeoFilter_fn))

        envelope_weights = weightGeoFilter_fn.name()
        print("envelope_weights:", envelope_weights, type(envelope_weights))
    
    
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
            
            ###EDIT WEIGHTS
            # Those two method does the same thing. API is faster, but is not undoable.
            if self.undoable:
                vert = "{0}.vtx[{1}]".format(shape_name, i)
                cmds.skinPercent(skinclst, vert, tv=(inf, weight))
            elif not self.undoable:
                skinclst_fn.setWeights(shape_dag, vert_obj, inf_idx, weight, normalize=True)
            
            itVerts.next()
            
        om.MGlobal.displayInfo("Paste skin weight success!")
        
        
    def editBlendWeights(self, shape_dag, blendShape, target):
        # Get blendshape node function set...
        blendShape_obj = om.MSelectionList().add(blendShape).getDependNode(0) # Mobject
        blendShape_fn = om.MFnDependencyNode(blendShape_obj)
        
        # Get the weight plug...
        inputTarget_plug = blendShape_fn.findPlug("inputTarget", True).elementByPhysicalIndex(0)
        # result: blendshape.inputTarget[0]
        if target == 1:
            paint_plug = inputTarget_plug.child(1) # MPlug
            # result: blendshape.inputTarget[0].baseWeights    
        elif target == 0:
            paint_plug = inputTarget_plug.child(3)
            # result: blendshape.inputTarget[0].paintTargetWeights
        
        # Iterate over every vertices...
        itVerts = om.MItMeshVertex(shape_dag)
        while not itVerts.isDone():
            i = itVerts.index()
            child_plug = paint_plug.elementByLogicalIndex(i) # MPlug
            # result: blendShape.inputTarget[0].baseWeights[99]
            
            if child_plug.isLocked:
                om.MGlobal.displayError("{0} plug is locked. Aborting set weights function.".format(child_plug)) 
                return # might cause error when the loop is in process
            elif child_plug.isConnected:
                om.MGlobal.displayError("{0} plug is connected. Aborting set weights function.".format(child_plug))
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
    
        
    def editDeformerWeights(self):
        pass
    
            
        

