import sys
import importlib

import time

import maya.api.OpenMaya as om
import maya.OpenMayaUI as omui
import maya.cmds as cmds

from PySide2 import QtCore
from PySide2 import QtWidgets
from shiboken2 import wrapInstance

from Kaia_WeightTransfer import util
importlib.reload(util)
###--------------------------------CLASS--------------------------------------

def maya_main_window():
    """Return the Maya main window widget as a Python object"""
    main_window_ptr = omui.MQtUtil.mainWindow()
    
    if sys.version_info.major >= 3: # Python 3 or higher
        return wrapInstance(int(main_window_ptr), QtWidgets.QWidget)
    else:
        return wrapInstance(long(main_window_ptr), QtWidgets.QWidget)
    
class WeightTransferDialog(QtWidgets.QDialog, util.WeightTransferCompute):
    def __init__(self, parent=maya_main_window()):
        super().__init__(parent)
        
        self.setWindowTitle("Weight Transfer Tool")
        self.setMinimumWidth(250)
        
        # Remove the ? from the dialog on Windows
        self.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)
        
        # self.setWindowFlags(self.windowFlags() ^ QtCore.Qt.WindowContextHelpButtonHint)
        self.create_widgets()
        self.create_layouts()
        self.create_connections()
        
        ###
        self.undoable = True
        self.source_shape = None
        self.source_weights = None
        
    def create_widgets(self):
        self.discription = QtWidgets.QLabel("Transfer single weight across \nskinCluster, blendShape, nCloth, deformers.\n\nSelect an influence inside any Paint Tool.\n")
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
            # if vert count is high(over 10000) paste Skin weights operation might take some time. Continue? [v]
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
