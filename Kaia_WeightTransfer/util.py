import maya.api.OpenMaya as om
import maya.api.OpenMayaAnim as oma
import maya.cmds as cmds
import maya.mel as mel


### tool that transfer current influence weight to another (skinCluster or Deformer) influence
class WeightTransferCompute():
    def __init__(self):
        pass
    
    def initialCheck(self):
        original_sel = om.MGlobal.getActiveSelectionList()
        
        # We're doing the operation on one mesh.
        if original_sel.length() != 1:
            om.MGlobal.displayError("There must be only one selection.")
            
        # We're doing the operation on poligon shape node.
        try:
            current_shape = original_sel.getDagPath(0).extendToShape() # dag
        except:
            om.MGlobal.displayError("Selection must have a shape node directly parented under.")
            return
            
        if current_shape.apiType() != 296: 
            om.MGlobal.displayError("Selection must be a poligon mesh.")
            return
        
        # Is the source mesh same to the current mesh?
        if self.source_shape:   # if source shape is not None
            if self.source_shape != current_shape:
                om.MGlobal.displayWarning("The source mesh is not same to the target mesh. Users might get unexpected results.")
        
        # What tool are we using?
        current_tool = cmds.currentCtx()
        print('current tool:', current_tool)
        # current tool: artAttrCtx1
        # current tool: artAttrBlendShapeContext
        
        if current_tool == "artAttrSkinContext": #Paint Skin Weights Tool
            # maya 2024 supports multiple skinclst
            v = cmds.about(version=True) # str <- stupid
            v = int(v)
            if v < 2024:
                skinclst = cmds.ls(cmds.listHistory(current_shape.fullPathName()), type="skinCluster")
            elif v <= 2024:
                skinclst = cmds.textScrollList('skinClusterPaintList', q=True, si=True)[0] 
            current_deformer = skinclst
            
            # We need to get a 'context' of influence index
            current_paint = cmds.artAttrSkinPaintCtx(current_tool, q=True, inf=True) # string
            if current_paint == '':
                om.MGlobal.displayError("An influence must be selected inside Paint Skin Weights Tool.")
                return

        elif current_tool == 'artAttrBlendShapeContext':
            # There might be a smarter way to get blendshape node? Currently we're querying it from the context
            selected_attr = cmds.artAttrCtx(current_tool, q=True, asl=True)
            # result: blendShape.blendShape1.paintTargetWeights
            bsNode = selected_attr.split('.')[1]
            
            # We just have to know if we're painting base weight or not.
            # paintTargetWeights plug(below) will figure out which target we are painting.
            idx1, idx2 = mel.eval('artBlendShapeTargetIndex;')
            # result: base weight is 1, 0
            # result: target weight is 0, n
            
            current_deformer = bsNode
            current_paint = idx1 # int
                
        elif current_tool == 'artAttrNClothContext':
            pass
        elif current_tool == 'artAttrContext':
            pass
        else:
            om.MGlobal.displayError("Current tool must be either Paint Skin Weights Tool, Paint Blend Shape Weights Tool, Paint nCloth Attributes Tool, or Paint Attributes Tool.")
            return
        
        return current_shape, current_deformer, current_tool, current_paint
        

    def querySkinWeights(self, shape_dag, skinclst, inf):

        skinclst_obj = om.MSelectionList().add(skinclst).getDependNode(0) # Mobject
        skinclst_fn = oma.MFnSkinCluster(skinclst_obj)
        
        inf_dag = om.MSelectionList().add(inf).getDagPath(0)
        inf_idx = skinclst_fn.indexForInfluenceObject(inf_dag) # int
        
        ###QUERY WEIGHTS
        empty_object = om.MObject()
        self.source_weights = skinclst_fn.getWeights(shape_dag, empty_object, inf_idx) # MDoubleArray
        self.source_shape = shape_dag
        
        om.MGlobal.displayInfo("Copy skin weights success!")
        
        
    def queryBlendWeights(self, shape_dag, blendShape, target):
        # There is no dedicated function set for accessing blendshape deformer weights (not blendshape weights!)
        # Therefore we're accessing those values using Mplug object.
        
        # Get blendshape node function set...
        blendShape_obj = om.MSelectionList().add(blendShape).getDependNode(0) # Mobject
        blendShape_fn = om.MFnDependencyNode(blendShape_obj)
        
        # Get the weight plug...
        inputTarget_plug = blendShape_fn.findPlug('inputTarget', True).elementByPhysicalIndex(0)
        # result: blendshape.inputTarget[0]
        if target == 1:
            paint_plug = inputTarget_plug.child(1)
            # result: blendshape.inputTarget[0].baseWeights
        elif target == 0:
            paint_plug = inputTarget_plug.child(3)
            # result: blendshape.inputTarget[0].paintTargetWeights
        
        # Create empty array...
        self.source_weights = om.MDoubleArray()
        
        # Iterate over every vertices...
        itVerts = om.MItMeshVertex(shape_dag)
        while not itVerts.isDone():
            child_plug = paint_plug.elementByLogicalIndex(itVerts.index()) # MPlug
            weight = child_plug.asFloat() # float
            self.source_weights.append(weight)
            itVerts.next()
            
        self.source_shape = shape_dag
        
        om.MGlobal.displayInfo("Copy blendshape weights success!")
        
        
    def queryNClothWeights(self):
        pass
    
        
    def queryDeformerWeights(self):
        deformer = 'cluster1'
        deformer_obj = om.MSelectionList().add(deformer).getDependNode(0) # Mobject
        weightGeoFilter_fn = oma.MFnWeightGeometryFilter(deformer_obj)

        print('deformer:', deformer)
        print('deformer_obj:', deformer_obj, type(deformer_obj))
        print('weightGeoFilter_fn:', weightGeoFilter_fn, type(weightGeoFilter_fn))

        envelope_weights = weightGeoFilter_fn.name()
        print('envelope_weights:', envelope_weights, type(envelope_weights))
    
    
    def editSkinWeights(self, shape_dag, skinclst, inf):
        shape_fullPath = shape_dag.fullPathName() # str
        
        skinclst_obj = om.MSelectionList().add(skinclst).getDependNode(0) # Mobject
        skinclst_fn = oma.MFnSkinCluster(skinclst_obj)
        
        inf_dag = om.MSelectionList().add(inf).getDagPath(0) # dag
        inf_idx = skinclst_fn.indexForInfluenceObject(inf_dag) # int
        inf_dagArray = skinclst_fn.influenceObjects() # MDagPathArray
        
        # Check for lock/unlock state for the influences.
        locked_ls = []
        for num, i in enumerate(inf_dagArray):
            if i == inf_dag:
                continue # skip the target influence. Doesn't matter.
            locked = cmds.getAttr(skinclst+'.lockWeights[{0}]'.format(num))
            if locked == False:
                locked_ls.append(locked)
                
        if locked_ls == [False]:
            pass
        elif locked_ls == []:
            om.MGlobal.displayWarning("None of influences is unlocked. Weights can't be normalized due to locked influences.")
        else:
            om.MGlobal.displayWarning("Multiple influences are unlocked. Weights might leak into unwanted influences.")
        
        # Iterate over every vertices...
        itVerts = om.MItMeshVertex(shape_dag)
        while not itVerts.isDone():    
            vert_obj = itVerts.currentItem() #MObject
            try:
                weight = self.source_weights[itVerts.index()] # float
            except:
                weight = 0.0 # if source verts < target verts: index out of range... Set default value to 0.
            
            ###EDIT WEIGHTS
            # Those two method basically does the same thing. OpenMaya API is faster, but is not undoable.
            if self.undoable:
                vert = '{0}.vtx[{1}]'.format(shape_fullPath, itVerts.index())
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
        inputTarget_plug = blendShape_fn.findPlug('inputTarget', True).elementByPhysicalIndex(0)
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
            child_plug = paint_plug.elementByLogicalIndex(itVerts.index()) # MPlug
            # result: blendShape.inputTarget[0].baseWeights[99]
            
            if child_plug.isLocked:
                om.MGlobal.displayError("{0} plug is locked. Aborting set weights function.".format(child_plug)) 
                return # might cause error when the loop is in process
            elif child_plug.isConnected:
                om.MGlobal.displayError("{0} plug is connected. Aborting set weights function.".format(child_plug))
                return

            try:
                weight = self.source_weights[itVerts.index()] # float
            except:
                weight = 0.0 # if source verts < target verts: index out of range... Set default value to 0.
            
            if self.undoable:
                attr = child_plug.name()
                cmds.setAttr(attr, weight)
            elif not self.undoable:
                child_plug.setFloat(weight) # float
            
            itVerts.next()
        
        # update display (color feedback)...
        mel.eval("artAttrBlendShapeValues artAttrBlendShapeContext;")
        
        om.MGlobal.displayInfo("Paste blendshape weights success!")
    
        
    def editNClothWeights(self):
        pass
    
        
    def editDeformerWeights(self):
        pass
    
            
        

