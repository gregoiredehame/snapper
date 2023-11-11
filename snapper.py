"""
SNAPPER. (c)

Author:  Gregoire Dehame
Created: Nov 01, 2023
Module:  snapper
Purpose: wrappering Maya's snapper functionality.
Execute: from kata.snapper import snapper; snapper.run()
"""

import maya.cmds as cmds
import maya.api.OpenMaya as om2
import maya.api.OpenMayaUI as omui2

import os
import platform
import logging
import subprocess
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class Viewport(object):
    def __init__(self, filepath=''):
        self.snapper = 'snapper'
        self.filesnap = filepath if os.path.exists(filepath) else os.path.join(self.folder(), 'snap.jpeg')
    
    def folder(self):
        import ctypes.wintypes
        buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf)
        documents = buf.value
        if os.path.exists(documents):
            snappers = os.path.join(buf.value, self.snapper)
            if not os.path.exists(snappers):
                os.makedirs(snappers)
            return snappers
    
    def snap(self):
        if self.filesnap:
            self.viewport = omui2.M3dView.active3dView()
            cmds.setAttr("defaultRenderGlobals.imageFormat", 8)
            cmds.playblast(completeFilename=self.filesnap, startTime=cmds.currentTime(query=True), endTime=cmds.currentTime(query=True),
                           forceOverwrite=True, viewer=0, format='image', percent=100, framePadding=0,
                           width=self.viewport.portWidth(), height=self.viewport.portHeight())
            return self.filesnap      
        else:
            logger.exception('- "%s" does not exists'%self.filesnap)
            return None
        
    
class Dragging(object):
    def __init__(self):
        self.snapper = 'snapper'
        self.coordinates = [[],[]]
        self.selection = cmds.ls(sl=1)
        self.current = cmds.currentCtx(query=True)
        self.color = 13
        self.width = 1
        self.PIL = True
        try: from PIL import Image
        except ImportError:
            self.PIL = None
            Viewport().snap()
            logger.warning('PIL python package is missing. dragging snappers wont work.')

    def snap(self):
        if self.PIL:
            self.delete()
            cmds.draggerContext(self.snapper, pressCommand=self.press, dragCommand=self.drag, releaseCommand=self.release, cursor='crossHair')
            cmds.setToolTo(self.snapper)
        
    def delete(self):
        if cmds.draggerContext(self.snapper, ex=True):
            cmds.deleteUI(self.snapper)
    
    def press(self):
        self.curve = cmds.curve(point=[(0,0,0),(0,0,0),(0,0,0),(0,0,0),(0,0,0)], degree=1)
        cmds.parent(self.curve, self.camera(True))
        self.prepare()
        self.coordinates[0] = cmds.draggerContext(self.snapper, query=True, anchorPoint=True)
        ptn = self.world(self.coordinates[0])
        [cmds.move(ptn[0],ptn[1],ptn[2], f"{self.curve}.cv[%s]"%str(i), relative=True, objectSpace=True, worldSpaceDistance=True) for i in range(5)]
        cmds.select(self.selection) if self.selection else None
        self.view().refresh(True, True)
        
    def drag(self):
        cmds.select(cl=1)
        drag_point = cmds.draggerContext(self.snapper, query=True, dragPoint=True)
        x = self.world([self.coordinates[0][0], drag_point[1], drag_point[2]])
        y = self.world([drag_point[0], self.coordinates[0][1], drag_point[2]])
        d = self.world(drag_point)
        cmds.setAttr(self.shape + '.controlPoints[1].xValue', x[0])
        cmds.setAttr(self.shape + '.controlPoints[1].yValue', x[1])
        cmds.setAttr(self.shape + '.controlPoints[1].zValue', x[2])
        cmds.setAttr(self.shape + '.controlPoints[2].xValue', d[0])
        cmds.setAttr(self.shape + '.controlPoints[2].yValue', d[1])
        cmds.setAttr(self.shape + '.controlPoints[2].zValue', d[2])
        cmds.setAttr(self.shape + '.controlPoints[3].xValue', y[0])
        cmds.setAttr(self.shape + '.controlPoints[3].yValue', y[1])
        cmds.setAttr(self.shape + '.controlPoints[3].zValue', y[2])
        self.coordinates[1] = drag_point
        self.view().refresh(True, True)

    def release(self):
        self.delete()
        cmds.setToolTo(self.current)
        cmds.delete(self.curve)
        self.crop(filesnap=Viewport().snap())
    
    def prepare(self):
        self.shape = cmds.listRelatives(self.curve, s=True)[0]
        cmds.setAttr(f'{self.curve}.translate', 0,0,-0.001, type='float3')
        cmds.setAttr(f'{self.curve}.rotate', 0,0,0, type='float3')
        cmds.setAttr(f'{self.curve}.scale', 1,1,1, type='float3')
        cmds.setAttr(f"{self.shape}.overrideEnabled", 1)
        cmds.setAttr(f"{self.shape}.overrideColor", self.color)
        cmds.setAttr(f"{self.shape}.lineWidth", self.width)
        
    def camera(self, edit=False):
        camera = om2.MDagPath(self.view().getCamera())
        camera_shape = om2.MFnDagNode(camera).name()
        if edit: 
            try: cmds.setAttr(f"{camera_shape}.nearClipPlane", 0.001)
            except: pass
        camera_transform = om2.MFnDagNode(camera.transform()).name()  
        try: [cmds.setAttr(f"{camera_transform}.{attribute}", 1) for attribute in ['visibility', 'lodVisibility']]
        except: pass
        return om2.MFnDagNode(camera.transform()).name()
        
    def view(self):
        return omui2.M3dView.active3dView()
        
    def world(self, truple):
        camera_matrix = om2.MMatrix(cmds.xform(self.curve, query=True, worldSpace=True, matrix=True))
        pos, ray = om2.MPoint(), om2.MVector()
        self.view().viewToObjectSpace(int(truple[0]), int(truple[1]), camera_matrix.inverse(), pos, ray)
        return [pos[i] for i in range(3)] 
            
    def crop(self, filesnap=None):
        try: 
            from PIL import Image
            logger.info(filesnap)
            im = Image.open(filesnap)
                
            X = [self.coordinates[0][0], self.coordinates[1][0]]
            Y = [self.coordinates[0][1], self.coordinates[1][1]]
            im1 = im.crop((min(X), min(Y), max(X), max(Y)))
            im1.save(filesnap)
            im1.show()
        except:
            logger.info('- unable to crop snap')