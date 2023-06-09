import sys
import importlib

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
        self.setMinimumWidth(200)
        
        # Remove the ? from the dialog on Windows
        self.setWindowFlag(QtCore.Qt.WindowContextHelpButtonHint, False)
        
        # self.setWindowFlags(self.windowFlags() ^ QtCore.Qt.WindowContextHelpButtonHint)
        self.create_widgets()
        self.create_layouts()
        self.create_connections()
        
        ###
        self.undoable = True
        self.source_shape = None
        self.source_weight = None
        
    def create_widgets(self):
        self.undoable_cb = QtWidgets.QCheckBox("Undoable")
        self.undoable_cb.setChecked(True)
        self.copy_btn = QtWidgets.QPushButton("Copy")
        self.paste_btn = QtWidgets.QPushButton("Paste")
        self.paste_btn.setEnabled(False)

    
    def create_layouts(self):
        option_layout = QtWidgets.QHBoxLayout()
        option_layout.addStretch()
        option_layout.addWidget(self.undoable_cb)
        
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.copy_btn)
        button_layout.addWidget(self.paste_btn)
        
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.addLayout(option_layout)
        main_layout.addLayout(button_layout)
        
    def create_connections(self):
        self.undoable_cb.toggled.connect(self.undo_toggle)
        self.copy_btn.clicked.connect(self.copy_clicked)
        self.paste_btn.clicked.connect(self.paste_clicked)
        
    def undo_toggle(self, checked):
        self.undoable = checked
    
    def copy_clicked(self):
        try:
            shape, tool, paint = self.initialCheck()
        except:
            return
        
        if tool == 'artAttrSkinContext':
            self.querySkinWeights(shape, paint)
        elif tool == 'artAttrBlendShapeContext':
            self.queryBlendWeights()
        elif tool == 'artAttrNClothContext':
            self.queryNClothWeights()
        elif tool == 'artAttrContext':
            self.queryDeformerWeights()
        
        if tool and self.source_shape and self.source_weight:
            self.paste_btn.setEnabled(True)
        
        
    def paste_clicked(self):
        try:
            shape, tool, paint = self.initialCheck()
        except:
            return
        
        original_sel = om.MGlobal.getActiveSelectionList()
        cmds.undoInfo(openChunk=True)
        
        if tool == 'artAttrSkinContext':
            self.editSkinWeights(shape, paint)
        elif tool == 'artAttrBlendShapeContext':
            self.editBlendWeights()
        elif tool == 'artAttrNClothContext':
            self.editNClothWeights()
        elif tool == 'artAttrContext':
            self.editDeformerWeights()
            
        cmds.undoInfo(closeChunk=True)
        om.MGlobal.setActiveSelectionList(original_sel)

        
if __name__ == "__main__":
    try:
        test_dialog.close() # pylint: disable=E0601 # << removing the error message for this specific line
        test_dialog.deleteLater()
    except:
        pass
    test_dialog = WeightTransferDialog()
    test_dialog.show()
