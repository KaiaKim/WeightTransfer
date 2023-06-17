import maya.api.OpenMaya as om
import maya.api.OpenMayaAnim as oma
import maya.OpenMaya as om1
import maya.OpenMayaAnim as oma1
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
        
        if current_tool == "artAttrSkinContext": #Paint Skin Weights Tool
            # maya 2024 supports multiple skinclst
            v = cmds.about(version=True) # str <- stupid
            v = int(v)
            if v < 2024:
                skinclst = cmds.ls(cmds.listHistory(dag.fullPathName()), type="skinCluster")
            elif v <= 2024:
                skinclst = cmds.textScrollList('skinClusterPaintList', q=True, si=True)[0] 
            current_deformer = skinclst
            
            # We need to get a 'context' of influence index
            current_paint = cmds.artAttrSkinPaintCtx(current_tool, q=True, inf=True) 
            if current_paint == '':
                om.MGlobal.displayError("An influence must be selected inside Paint Skin Weights Tool.")
                return

        elif current_tool == 'artAttrBlendShapeContext':
            selected_attr = cmds.artAttrCtx(current_tool, q=True, asl=True)
            # print('asl:', selected_attr)
            # asl: blendShape.blendShape1.paintTargetWeights
            
            bsNode = selected_attr.split('.')[1]
            current_deformer = bsNode
            
            idx1, idx2 = mel.eval('artBlendShapeTargetIndex;') 
            print('idx1:', idx1) # 1 base weight, 0 target weight
            print('idx2:', idx2) # target index
            
            if idx1 == 1:
                current_paint = bsNode
                
            elif idx1 == 0:
                current_paint = mel.eval('blendShapeTargetNameFromIndex "{0}" {1};'.format(bsNode, idx2))
            
            print('current_paint:', current_paint)
            
                
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
        weights = skinclst_fn.getWeights(shape_dag, empty_object, inf_idx) # MDoubleArray
        
        self.source_shape = shape_dag
        self.source_weight = weights
        
        om.MGlobal.displayInfo("Copy skin weights success!")
        
    def queryBlendWeights(self, shape_dag, blendShape, inf):
        # MFnBlendShapeDeformer class is only available in Python API 1.0
        
        sel = om1.MSelectionList()
        sel.add(blendShape)
        blendShape_obj = om1.MObject()
        sel.getDependNode(0, blendShape_obj)
        blendShape_fn = oma1.MFnBlendShapeDeformer(blendShape_obj)
        
        print('blendShape:', blendShape)
        print('blendShape_obj:', blendShape_obj, type(blendShape_obj))
        print('blendShape_fn:', blendShape_fn, type(blendShape_fn))
        
        inf_dag = None
        inf_idx = None
        
        weights = blendShape_fn.weight(0)
        
        print('weights:', weights, type(weights))
        
        
    
        
    def queryNClothWeights(self):
        pass
    
        
    def queryDeformerWeights(self):
        pass
    
    
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
    
            
        

