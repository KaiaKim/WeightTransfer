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
        if current_tool not in tool_ls:
            om.MGlobal.displayError("Current tool must be either Paint Skin Weights Tool, Paint Blend Shape Weights Tool, Paint nCloth Attributes Tool, or Paint Attributes Tool.")
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
    
            
        

