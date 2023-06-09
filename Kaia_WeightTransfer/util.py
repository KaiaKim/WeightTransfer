import maya.api.OpenMaya as om
import maya.api.OpenMayaAnim as oma
import maya.cmds as cmds

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
        
        if current_tool == "artAttrSkinContext": #Paint Skin Weights Tool
            current_paint = cmds.artAttrSkinPaintCtx(cmds.currentCtx(), q=True, inf=True) # We need to get a 'context' of influence index
            if current_paint == '':
                om.MGlobal.displayError("An influence must be selected inside Paint Skin Weights Tool.")
                return

        elif current_tool == 'artAttrBlendShapeContext':
            pass
        elif current_tool == 'artAttrNClothContext':
            pass
        elif current_tool == 'artAttrContext':
            pass
        else:
            om.MGlobal.displayError("Current tool must be either Paint Skin Weights Tool, Paint Blend Shape Weights Tool, Paint nCloth Attributes Tool, or Paint Attributes Tool.")
            return
        
        return current_shape, current_tool, current_paint
        

    def querySkinWeights(self, shape_dag, inf):
        skinclst = cmds.textScrollList('skinClusterPaintList', q=True, si=True)[0]
        skinclst_obj = om.MSelectionList().add(skinclst).getDependNode(0) # Mobject
        skinclst_fn = oma.MFnSkinCluster(skinclst_obj)
        
        inf_dag = om.MSelectionList().add(inf).getDagPath(0)
        inf_idx = skinclst_fn.indexForInfluenceObject(inf_dag) # int
        
        ###QUERY WEIGHTS
        empty_object = om.MObject()
        weights = skinclst_fn.getWeights(shape_dag, empty_object, inf_idx) # MDoubleArray
        
        self.source_shape = shape_dag
        self.source_weight = weights
        
        om.MGlobal.displayInfo("Copy skin weights success!")
        
    def queryBlendWeights(self):
        pass
    
        
    def queryNClothWeights(self):
        pass
    
        
    def queryDeformerWeights(self):
        pass
    
    
    def editSkinWeights(self, shape_dag, inf):
        shape_fullPath = shape_dag.fullPathName() # str
        
        skinclst = cmds.textScrollList('skinClusterPaintList', q=True, si=True)[0]
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
        
        # get the selected mesh and components
        cmds.select(cmds.polyListComponentConversion(toVertex=True))
        dagpath, selected_components = om.MGlobal.getActiveSelectionList().getComponent(0)
        
        # iterate over the selected verts
        itVerts = om.MItMeshVertex(shape_dag, selected_components)
        while not itVerts.isDone():    
            vert_obj = itVerts.currentItem() #MObject
            try:
                weight = self.source_weight[itVerts.index()] # float
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
        
        
    def editBlendWeights(self):
        pass
    
        
    def editNClothWeights(self):
        pass
    
        
    def editDeformerWeights(self):
        pass
    
            
        

