import sys
import os

import numpy as np
import cv2

from PyQt5.QtGui import *
from PyQt5.Qt import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
import qdarkgraystyle
import data_handler as dh
import pickle as pkl
import copy


VER = "v1.0"
tickbox_colors = ["#00ffff", "#008080", "#00ff00", "#808040", "#808080","#8080ff","#ff8040","#8000ff"]
average_color = "#ffffff"
#contains name, points, pixmap image, paths, and landmarkpaths of image

#TODO v1.1: ADD LOCK/UNLOCK FUNCTIONALITY
class OperationsType:
    ADD_SKELETON = 0
    REMOVE_SKELETON = 1
    ADD_KEYPOINT = 2
    REMOVE_KEYPOINT = 3
    MOVE_KEYPOINT = 4

HAND_LINES = [[0,1],[1,2],[2,3],[3,4],
              [0,5],[5,6],[6,7],[7,8],
              [0,9],[9,10],[10,11],[11,12],
              [0,13],[13,14],[14,15],[15,16],
              [0,17],[17,18],[18,19],[19,20]]

POSE_LINES = [[8,6],[6,5],[5,4],[4,0],[0,1],[1,2],[2,3],[3,7],[9,10]]

class Outputdata:
    '''
    For all operations, the output data should be stored in this class:
    Video > frame > pose/hand

    Save, load, querry
    Undo, redo
    '''
    def __init__(self) -> None:
        self.data = {}
        self.history = {}
        self.history_pointer = 0
        self.history_frame_count = 0
        #this to store the most recent frame index of each video. For the purpose of delete the old history
        self.history_frame_indexs = []
        self.last_video = None

    def save(self, path):
        with open(path, 'wb') as f:
            pkl.dump(self.data, f)

    def load(self, path):
        with open(path, 'rb') as f:
            self.data = pkl.load(f)

    def get_skeleton(self, video, frame):
        if video not in self.data:
            return None
        if frame not in self.data[video]:
            return None
        return self.data[video][frame]
    
    
    def add_skeleton(self, video, frame, skeleton):
        if video not in self.data:
            self.data[video] = {}
        if self.last_video != video:
            self.history = {}
            self.history_pointer = 0
            self.history_frame_count = 0
            self.history_frame_indexs = []
            self.last_video = video
        self._add_to_history(frame, skeleton)
        self.data[video][frame] = skeleton

    def remove_skeleton(self, video, frame):
        self.history.append((OperationsType.REMOVE_SKELETON, video, frame, self.data[video][frame]))
        self.history_pointer += 1
        del self.data[video][frame]

    def _add_to_history(self,  frame, data):
        if frame not in self.history:
            self.history[frame] = []
        #if current frame history is more than 50, delete the oldest frame
        if len(self.history[frame]) > 50:
            del self.history[frame][0]


        self.history[frame].append(copy.deepcopy(data))
        self.history_pointer  = len(self.history[frame])
        self.history_frame_count += 1
        #change the index of the history_frame_indexs
        #tranverse the history_frame_indexs, if the frame is found then move it to the end
        #if not found, add it to the end
        
        

        if frame in self.history_frame_indexs:
            self.history_frame_indexs.remove(frame)
        self.history_frame_indexs.append(frame)
        #only save the last 10 operations, so delete the oldest frame
        if len(self.history_frame_indexs) > 10:
            self.history[ self.history_frame_indexs.pop(0)] = []
        print(f"Added to history: {frame}/{self.history_pointer}/{len(self.history[frame])}")
        

    def undo_action(self,video, frame):
        self.history_pointer = self.history_pointer if self.history_pointer >= 0 and self.history_pointer <= len(self.history[frame]) else len(self.history[frame])
        if self.history_pointer > 0:
            self.history_pointer -= 1
            _temp_data = self.history[frame][self.history_pointer]
            self.data[video][frame] = copy.deepcopy(_temp_data)
            print(f"Undo: {frame}/{self.history_pointer}/{len(self.history[frame])}")
            return frame
        return None


    def redo_action(self,video, frame):
        if self.history_pointer < len(self.history):
            _temp_data = self.history[frame][self.history_pointer]
            self.data[video][frame] = copy.deepcopy(_temp_data)
            self.history_pointer += 1
            print(f"Redo: {frame}/{self.history_pointer}/{len(self.history[frame])}")
            return frame
        return None
    def get_undo_redo_status(self,frame):
        if frame not in self.history:
            return False, False
        self.history_pointer = self.history_pointer if self.history_pointer >= 0 and self.history_pointer <= len(self.history[frame]) else len(self.history[frame])
        
        #return if can undo, redo
        return self.history_pointer > 0, self.history_pointer < len(self.history)
    def get_all_labeled_frames(self, video):
        #check if video exists
        if video not in self.data:
            return 0,[]
        else:
            #return the number of labeled frames and a list of labeled frames
            return len(self.data[video]), list(self.data[video].keys())










class ImageSet:
    def __init__(self):
        self.__pixmslap = None
        self.__path = ""
        self.__point = {}
        self.__landmarkPath = {}
        self.__name = ""

    @property  # get pixmap
    def pixmap(self):
        return self.__pixmslap

    @pixmap.setter  # set pixmap
    def pixmap(self, pixmap):
        self.__pixmap = pixmap

    @property  # get path
    def path(self):
        return self.__path

    @path.setter  # set path
    def path(self, path):
        self.__path = path

    @property  # get point
    def point(self):
        return self.__point
    @point.setter  # set point
    def point(self, point):
        self.__point = point

    @property  # get landmarkPath
    def landmarkPath(self):
        return self.__landmarkPath

    @landmarkPath.setter  # set landmarkPath
    def landmarkPath(self, landmarkPath):
        print("set landmarkPath")
        self.__landmarkPath = landmarkPath

    @property  # get name
    def name(self):
        return self.__name

    @name.setter  # set name
    def name(self, name):
        self.__name = name


#upload the image to viewer and add landmarks on it
class PhotoViewer(QGraphicsView):

    def __init__(self):
        super(PhotoViewer, self).__init__()
        self._zoom = 0  # size of zoom
        self._empty = True  # whether viwer is empty
        self._scene = QGraphicsScene(self)  # scene to be uploaded
        self._photo = QGraphicsPixmapItem()  # photo that goes into scene
        self._scene.addItem(self._photo)  # add photo into scene
        self.setScene(self._scene)  # set scene into viwer
        self.pixmap = QPixmap()
        self.realPixmap = QPixmap()
        self.highReso = False #whether the image set is high resolution or not.

        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.setDragMode(QGraphicsView.RubberBandDrag)
    def hasPhoto(self):
        return not self._empty

    def fitInView2(self):
        rect = QRectF(self._photo.pixmap().rect())
        if not rect.isNull():
            self._scene.setSceneRect(rect)

            if self.hasPhoto():
                unity = self.transform().mapRect(QRectF(0, 0, 1, 1))
                self.scale(1 / unity.width(), 1 / unity.height())

                if self.highReso:
                    self.fitInView(rect, Qt.KeepAspectRatio)

            self._zoom = 0

    def setPhoto(self, pixmap=None,changeVideo=False):
        if changeVideo:
            self._zoom = 0

        if pixmap and not pixmap.isNull():

            dw = QDesktopWidget()
            dwWidth = dw.width()
            dwHeight = dw.height()

            pixmapWidth = pixmap.width()
            pixmapHeight = pixmap.height()

            self.realPixmap = pixmap

            if (pixmapWidth > dwWidth) or (pixmapHeight > dwHeight):

                if(pixmapWidth > 10000) or (pixmapHeight > 10000):
                    self.pixmap = pixmap.scaled(pixmapWidth / 100, pixmapHeight / 100, Qt.KeepAspectRatio)
                else:
                    self.pixmap = pixmap.scaled(pixmapWidth / 10, pixmapHeight / 10, Qt.KeepAspectRatio)

                self.highReso = True
            else:
                self.highReso = False

            self._empty = False
            self._photo.setPixmap(pixmap)

        else:
            self._empty = True
            self._photo.setPixmap(QPixmap())
        if changeVideo:
            self.fitInView2()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Control:
            self.setDragMode(QGraphicsView.ScrollHandDrag)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Control:
            self.setDragMode(QGraphicsView.RubberBandDrag)

    def wheelEvent(self, event):
        if self.hasPhoto():
            modifiers = QApplication.keyboardModifiers()
            if modifiers == Qt.ControlModifier:  # if ctrl key is pressed
                if event.angleDelta().y() > 0:  # if scroll wheel forward
                    factor = 1.25
                    self._zoom += 1
                else:
                    factor = 0.8  # if scroll wheel backward
                    self._zoom -= 1
                if self._zoom > 0:
                    self.scale(factor, factor)
                elif self._zoom == 0:
                    self.fitInView2()
                else:
                    self._zoom = 0
            elif modifiers == Qt.ShiftModifier:
                #if shift key is pressed, scroll horizontally
                if event.angleDelta().y() > 0:  # if scroll wheel forward
                    self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - int(10*self._zoom))
                else:
                    self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() + int(10*self._zoom))
            else:
                #if no key is pressed, scroll vertically
                if event.angleDelta().y() > 0:
                    self.verticalScrollBar().setValue(self.verticalScrollBar().value() - int(10*self._zoom))
                else:
                    self.verticalScrollBar().setValue(self.verticalScrollBar().value() + int(10*self._zoom))


    def addItem(self, item):
        return self._scene.addItem(item)


class Landmark_path(QGraphicsPathItem):

    def __init__(self, path,id ,keypoint_class, parent=None,method='',line_color=QColor(255, 255, 255)):
        super(Landmark_path, self).__init__()
        moveable= method == 'average'
        self.method = method
        self.path = path
        self.setPath(path)
        pos = self.scenePos()
        self.x = pos.x()
        self.y = pos.y()
        self.id = id
        self.keypoint_class = keypoint_class
        self._z = 0
        self.moved = True
        self.parent = parent
        self.line_color = line_color
        self.setFlag(QGraphicsItem.ItemIsMovable, moveable)
        self.setFlag(QGraphicsItem.ItemIsSelectable, moveable)
        self._locked = False
        self.target_line,self.parent_line = self.get_target()
        
        if self.target_line is not None:
            self.drawLine(self.target_line.x, self.target_line.y)
    
    def setPos(self, x, y):
        self.x = x
        self.y = y
        super(Landmark_path, self).setPos(x, y)


    def get_target(self):
        result_target = None
        result_parent = None
        #get the target point of this point
        if self.keypoint_class == 'pose':
            target_index = None
            parent_index = None
            for pair in POSE_LINES:
                if pair[0] == self.id:
                    target_index = pair[1]
                elif pair[1] == self.id:
                    parent_index = pair[0]
            #find the target point in parent viewer
            for item in self.parent.currentImage.landmarkPath[self.method]['pose']:
                if item.id == target_index:
                    result_target = item
                elif item.id == parent_index:
                    result_parent = item
            return result_target, result_parent
        elif 'hands' in self.keypoint_class:
            target_index = None
            parent_index = None
            for pair in HAND_LINES:
                if pair[0] == self.id:
                    target_index = pair[1]
                elif pair[1] == self.id:
                    parent_index = pair[0]
            #find the target point in parent viewer
            for item in self.parent.currentImage.landmarkPath[self.method]['hands'][self.keypoint_class.replace('hands','')]:
                if item.id == target_index:
                    result_target = item
                elif item.id == parent_index:
                    result_parent = item
            return result_target, result_parent
    




    def drawLine(self, target_x, target_y):
        # check if line already exists, if so, modify it; otherwise, create a new line from current position to target position
        self.removeLine()
        if not self.parent.show_skeleton:
            return
        if hasattr(self, 'line'):
            self.line.setLine(self.x, self.y, target_x, target_y)
            self.line.setPen(QPen(self.line_color, 2, Qt.SolidLine, Qt.RoundCap))
        else:
            self.line = QGraphicsLineItem(self.x, self.y, target_x, target_y)
            self.line.setPen(QPen(self.line_color, 2, Qt.SolidLine, Qt.RoundCap))
            self.parent.viewer.scene().addItem(self.line)

    def removeLine(self):
        if hasattr(self, 'line'):
            self.parent.viewer.scene().removeItem(self.line)
            del self.line


    def setZ(self, z):
        self._z = z
    def getZ(self):
        return self._z

    def setLocked(self, locked):
        self._locked = locked
        self.setFlag(QGraphicsItem.ItemIsMovable, not locked)
        #change the color of the point to orange if locked
        if locked:
            self.setBrush(QBrush(QColor(255, 165, 0)))
        else:
            #transparent
            self.setBrush(QBrush(QColor(0, 0, 0, 0)))

    def mousePressEvent(self, event):
        event.accept()
        if event.button() == Qt.RightButton:
            print('right')
        else:
            super(Landmark_path, self).mousePressEvent(event)
            

    def mouseMoveEvent(self, event):
        if self._locked:
            print("trying to move locked point")
        self.setFlag(QGraphicsItem.ItemIsMovable, not self._locked)
        event.accept()
        super(Landmark_path, self).mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        event.accept()
        super(Landmark_path, self).mouseReleaseEvent(event)
        pos = self.scenePos()
        #point = self.mapToScene(pos.x(), pos.y())

        #print moved point from (x,y) to (point.x(), point.y())
        print(f"Moved point {self.id} from ({self.x},{self.y}) to ({pos.x()},{pos.y()})")
        self.x = pos.x()
        self.y = pos.y()
        self.moved = True
        #self.removeLine()
        self.target_line,self.parent_line = self.get_target()
        if self.target_line is not None:
            self.drawLine(self.target_line.x, self.target_line.y)
        if self.parent_line is not None:
            self.parent_line.drawLine(self.x, self.y)
        self.parent.update_skeleton()
        if self.parent.recording:
            self.parent.save_current_frame_points()
    def reset(self):
        self.moved = False
    def is_moved(self):
        return self.moved
    def is_locked(self):
        return self._locked
    def returnCoordinates(self):
        self.x = self.scenePos().x()
        self.y = self.scenePos().y()
        return np.array([self.x, self.y, self._z])



class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.title = f'Hand Landmark Editing Tool {VER}'
        self.dw = QDesktopWidget()  # fit to the size of desktop
        self.x = 0
        self.y = 0
        self.width = self.dw.width()  # width of the desktop
        self.height = self.dw.height()  # height of the desktop
        self._label = QLabel()  # labels that show no photo uploaded warnings
        self.last_frame = -1
        self.currentImage = ImageSet()  # current image
        self.landmarks_data = {}  # landmarks data of current frame
        self.last_checked_methods = []
        self.checked_methods = []
        self.methods_accuracy = {}
        self.drawn = False #whether landmarks are drawn or not
        self.data_path = self.get_data_path()  # get the path of metadata.json
        self.data_folder = os.path.dirname(self.data_path)  # get the path of data folder
        self.dataloader = dh.DataHandler(self.data_folder)  # initiate data handler
        self.video_list = self.dataloader.get_video_list()  # get the list of videos
        self.alt_names = self.dataloader.get_alt_name()
        self.playing_vid = False  # whether the video is playing or not
        self.current_frame = 0  # current frame
        self.view_landmark_name = True  # whether the landmark name is shown or not
        self.recording = False
        self.skeleton_source = 'average'
        self.playback_speed = 0.5
        self.show_skeleton = True
        self.reset_lock_every_frame = False
        self.gt_data = Outputdata()  # initiate output data
        self.initUI()  # initiate UI
        #maximize the window
        self.showMaximized()
        #show the window
        self.show()
        self.videoSourceChanged()
        self.get_accuracy()
        self.viewer.setContextMenuPolicy(Qt.CustomContextMenu)
        self.viewer.customContextMenuRequested.connect(self.showContextMenu)
        self.record_btn.setEnabled(self.playback_speed != 1)

    def showContextMenu(self, pos):
        _locked = False
        selectedItems = self.viewer.items()
        selected_points = []
        for item in selectedItems:
            if item.isSelected():
                selected_points.append(item)
                _locked = item.is_locked()
        # Get the position of the right-click event
        globalPos = self.viewer.mapToGlobal(pos)
        menu = QMenu(self.viewer)
        # Get the selected items at the right-click position
        
        lockAction = menu.addAction("Lock")
        # Create a context menu
        
        lockAction.setEnabled(True)
        
        # Check if any selected item is right-clicked
        
        lockAction.setCheckable(True)
        lockAction.setChecked(_locked)
        
        if len(selected_points) > 0:
            
            # Add a "Lock" option to the context menu, with a tick mark if the item is locked
            
            #when clicked, loop through all the selected points and lock/unlock them
            lockAction.triggered.connect(lambda: [self.lockItem(item) for item in selected_points])
        else:
            #disable
            lockAction.setEnabled(False)

                



        # Show the context menu at the right-click position
        menu.exec_(globalPos)
    def lockItem(self, item):
        # Update the item's locked property or flag
        item.setLocked(not item.is_locked())




    def get_data_path(self):
        #Check if "D:\2023-2024\Research\Skeleton-ed\metadata.json" exists then use it
        if os.path.exists("D:\\2023-2024\\Research\\Outskeleton\\Skeleton-ed\\metadata.json"):
            return "D:\\2023-2024\\Research\\Outskeleton\\Skeleton-ed\\metadata.json"
        #show a dialog to get the data path, by choosing a file name "metadata.json"
        data_path = QFileDialog.getOpenFileName(self, "Open metadata.json", "metadata.json", "metadata.json file (metadata.json)")[0]

        #if the user did not choose any file, exit the program
        if data_path == "":
            sys.exit()

        return data_path
    def initUI(self):
        # resize the size of window
        self.setWindowTitle(self.title)
        self.setGeometry(self.x, self.y, self.width, self.height)
        #set icon
        self.setWindowIcon(QIcon('Icons/Nahida_1.ico'))
        

        # create menu bar
        self._create_menu_bar()

        # add graphic View into centralWidget
        self.viewer = PhotoViewer()
        self.setCentralWidget(self.viewer)
        self.viewer.setStyleSheet("background-color:#3C3530")

        # create Widget and layout for buttons on the right
        buttonWidget = QWidget()

        #create radioButton for detector
        groupBox = QGroupBox("Available Method", buttonWidget)
        groupBox.move(buttonWidget.x() + 5, buttonWidget.y() + 10)
        
        #groupBox.setStyleSheet("background-color:#F16B6F")

        


        self.methods_tickbox = {}
        for i, method in enumerate(self.dataloader.get_method_list()):
            self.methods_tickbox[method] = QCheckBox(method, groupBox)
            self.methods_tickbox[method].move(buttonWidget.x() + 5, buttonWidget.y() + 25 + i*20)
            self.methods_tickbox[method].clicked.connect(self.checkboxClicked)
            self.methods_tickbox[method].setChecked(False)
            #set color for each tickbox
            self.methods_tickbox[method].setStyleSheet("color:" + tickbox_colors[i])
            #bind each tickbox with corresponding 1,2,3,4,5,6,7,8 key
            if i < 8:
                self.methods_tickbox[method].setShortcut(str(i+1))
                

        #resize the groupBox to fit all the tickboxes
        groupBox.resize(250, 25 + len(self.dataloader.get_method_list())*20)

        #Create a average checkbox
        self.average_tickbox = QCheckBox("Show average only", buttonWidget)
        self.average_tickbox.move(buttonWidget.x() + 5, buttonWidget.y() + 40 + len(self.dataloader.get_method_list())*20)
        self.average_tickbox.clicked.connect(self.checkboxClicked)
        self.average_tickbox.setChecked(False)
        self.average_tickbox.setStyleSheet("color:" + average_color)
        self.average_tickbox.setShortcut("`")

        #create a btn to Calculate average
        self.calculate_average_btn = QPushButton("Calculate missing skeleton", buttonWidget)
        self.calculate_average_btn.move(buttonWidget.x() + 5, buttonWidget.y() + 65 + len(self.dataloader.get_method_list())*20)
        self.calculate_average_btn.clicked.connect(self.calculate_average_btn_clicked)




        # create video source label
        videoSourceLb = QLabel("Video Source", buttonWidget)
        videoSourceLb.setFont(QFont("Book Antiqua", 14, QFont.Bold))
        videoSourceLb.move(buttonWidget.x(), buttonWidget.y() + 200)

        #create a dropdown list for video source
        self.videoSource = QComboBox(buttonWidget)
        self.videoSource.move(buttonWidget.x() + 5, buttonWidget.y() + 235) 
        self.videoSource.resize(250, 50)
        alt_names = [self.alt_names[video] for video in self.alt_names]
        self.videoSource.addItems(alt_names)
        self.videoSource.currentIndexChanged.connect(self.videoSourceChanged)

        #Add a text label below, show:
        #Video name
        #Labeled %d out of %d frames (x.xx%)

        self.videoNameLb = QLabel("Video Name", buttonWidget)
        #self.videoNameLb.setFont(QFont("Book Antiqua", 14, QFont.Bold))
        self.videoNameLb.move(buttonWidget.x(), buttonWidget.y() + 300)

        self.videoProgressLb = QLabel("Labeled 0 out of 0 frames (0.00%)", buttonWidget)
        self.videoProgressLb.setFont(QFont("Book Antiqua", 10, QFont.Bold))
        self.videoProgressLb.move(buttonWidget.x(), buttonWidget.y() + 335)

        # red (Recording) if recording
        self.recordingLb = QLabel("                              ", buttonWidget)
        self.recordingLb.setFont(QFont("Book Antiqua", 10, QFont.Bold))
        self.recordingLb.move(buttonWidget.x() , buttonWidget.y() + 365)
        self.recordingLb.setStyleSheet("color:red")


        
        # create detect label
        self.detectLb = QLabel("Frame 0: Not labeled       ", buttonWidget)
        self.detectLb.setStyleSheet("color:red")
        self.detectLb.setFont(QFont("Book Antiqua", 14, QFont.Bold))
        self.detectLb.move(buttonWidget.x(), buttonWidget.y() + 450)

        #Add a text label below, show:
        #Frame %d out of %d (%f.2%)

        self.frameInfoLb = QLabel("Frame 0 out of 0 (0.00%)", buttonWidget)
        self.frameInfoLb.setFont(QFont("Book Antiqua", 14, QFont.Bold))
        self.frameInfoLb.move(buttonWidget.x(), buttonWidget.y() + 485)

        #Create a slider to control the frame
        
        navLb = QLabel("Navigation", buttonWidget)
        navLb.setFont(QFont("Book Antiqua", 14, QFont.Bold))
        navLb.move(buttonWidget.x(), buttonWidget.y() + 550)

        self.frameSlider = QSlider(Qt.Horizontal, buttonWidget)
        self.frameSlider.setTracking(True)
        self.frameSlider.move(buttonWidget.x() + 5, buttonWidget.y() + 585)
        self.frameSlider.resize(250, 50)
        self.frameSlider.setMinimum(0)
        self.frameSlider.setMaximum(200)
        self.frameSlider.setValue(0)
        self.frameSlider.setTickPosition(QSlider.TicksBelow)
        self.frameSlider.setTickInterval(200)
        self.frameSlider.valueChanged.connect(self.frameSliderChanged)

        # create qdockwidget and add the button widget to it
        self.qDockWidget = QDockWidget("")
        self.qDockWidget.setWidget(buttonWidget)
        self.qDockWidget.setFloating(False)
        self.qDockWidget.setFeatures(QDockWidget.NoDockWidgetFeatures)
        self.addDockWidget(Qt.RightDockWidgetArea, self.qDockWidget)
        self.qDockWidget.setFixedSize(300, self.dw.height())

        #Add 4 btns: Nav to pre not labeled frame, Nav to next not labeled frame, Nav to pre frame, Nav to next frame, using icons
        #add 2 btns: play and pause, using icons
        
        #nav to pre not labeled frame
        pre_not_labeled_pixmap = QPixmap('Icons/pre_not_labeled.png')
        pre_not_labeled_icon = QIcon(pre_not_labeled_pixmap)
        pre_not_labeled_btn = QPushButton(buttonWidget)
        pre_not_labeled_btn.setIcon(pre_not_labeled_icon)
        pre_not_labeled_btn.resize(50, 50)
        pre_not_labeled_btn.move(buttonWidget.x() + 5, buttonWidget.y() + 650)
        #set tooltip
        pre_not_labeled_btn.setToolTip("Navitage to previous not labeled frame")
        #set shortcut to upper arrow
        pre_not_labeled_btn.setShortcut(Qt.Key_Up)

        #nav to pre frame
        pre_frame_pixmap = QPixmap('Icons/pre_frame.png')
        pre_frame_icon = QIcon(pre_frame_pixmap)
        pre_frame_btn = QPushButton(buttonWidget)
        pre_frame_btn.setIcon(pre_frame_icon)
        pre_frame_btn.resize(50, 50)
        pre_frame_btn.move(buttonWidget.x() + 60, buttonWidget.y() + 650)
        #set tooltip
        pre_frame_btn.setToolTip("Navitage to previous frame")
        #set shortcut to left arrow
        pre_frame_btn.setShortcut(Qt.Key_Left)
        #nav to next frame
        next_frame_pixmap = QPixmap('Icons/next_frame.png')
        next_frame_icon = QIcon(next_frame_pixmap)
        next_frame_btn = QPushButton(buttonWidget)
        next_frame_btn.setIcon(next_frame_icon)
        next_frame_btn.resize(50, 50)
        next_frame_btn.move(buttonWidget.x() + 115, buttonWidget.y() + 650)
        #set tooltip
        next_frame_btn.setToolTip("Navitage to next frame")
        #set shortcut to right arrow
        next_frame_btn.setShortcut(Qt.Key_Right)

          #nav to next not labeled frame
        next_not_labeled_pixmap = QPixmap('Icons/next_not_labeled.png')
        next_not_labeled_icon = QIcon(next_not_labeled_pixmap)
        next_not_labeled_btn = QPushButton(buttonWidget)
        next_not_labeled_btn.setIcon(next_not_labeled_icon)
        next_not_labeled_btn.resize(50, 50)
        next_not_labeled_btn.move(buttonWidget.x() + 170, buttonWidget.y() + 650)
        #set tooltip
        next_not_labeled_btn.setToolTip("Navitage to next not labeled frame")
        #set shortcut to down arrow
        next_not_labeled_btn.setShortcut(Qt.Key_Down)

        #Record
        record_pixmap = QPixmap('Icons/videocamera.png')
        record_icon = QIcon(record_pixmap)
        self.record_btn = QPushButton(buttonWidget)
        self.record_btn.setIcon(record_icon)
        self.record_btn.resize(50, 50)
        self.record_btn.move(buttonWidget.x() + 5, buttonWidget.y() + 705)
        #set tooltip
        self.record_btn.setToolTip("Record")
        #set shortcut to r
        self.record_btn.setShortcut(Qt.Key_R)

        #Select skeleton mode
        skeleton_source_pixmap = QPixmap('Icons/cache.png')
        skeleton_source_icon = QIcon(skeleton_source_pixmap)
        self.skeleton_source_btn = QPushButton(buttonWidget)
        self.skeleton_source_btn.setIcon(skeleton_source_icon)
        self.skeleton_source_btn.resize(50, 50)
        self.skeleton_source_btn.move(buttonWidget.x() + 170, buttonWidget.y() + 705)
        #set tooltip
        self.skeleton_source_btn.setToolTip("Skeleton source: default")
        #set shortcut to t
        self.skeleton_source_btn.setShortcut(Qt.Key_T)
        self.skeleton_source_btn.setEnabled(False)


        #play
        play_pixmap = QPixmap('Icons/play.png')
        play_icon = QIcon(play_pixmap)
        play_btn = QPushButton(buttonWidget)
        play_btn.setIcon(play_icon)
        play_btn.resize(50, 50)
        play_btn.move(buttonWidget.x() + 60, buttonWidget.y() + 705)

        #pause
        pause_pixmap = QPixmap('Icons/pause.png')
        pause_icon = QIcon(pause_pixmap)
        pause_btn = QPushButton(buttonWidget)
        pause_btn.setIcon(pause_icon)
        pause_btn.resize(50, 50)
        pause_btn.move(buttonWidget.x() + 115, buttonWidget.y() + 705)

        accuracyLb = QLabel("Method accuracy", buttonWidget)
        accuracyLb.setFont(QFont("Book Antiqua", 14, QFont.Bold))
        accuracyLb.move(buttonWidget.x(), buttonWidget.y() + 770)

        #create a table to show accuracy of each method
        self.accuracyTable = QTableWidget(buttonWidget)
        self.accuracyTable.move(buttonWidget.x() + 5, buttonWidget.y() + 805)
        self.accuracyTable.resize(250, 150)
        self.accuracyTable.setColumnCount(2)
        self.accuracyTable.setHorizontalHeaderLabels(["Method", "Accuracy"])
        self.accuracyTable.setRowCount(len(self.dataloader.get_method_list()))
        self.accuracyTable.verticalHeader().setVisible(False)
        self.accuracyTable.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.accuracyTable.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.accuracyTable.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.accuracyTable.setSelectionMode(QAbstractItemView.SingleSelection)
        self.accuracyTable.setShowGrid(False)
        self.accuracyTable.setAlternatingRowColors(True)
        self.accuracyTable.setSortingEnabled(True)
        self.accuracyTable.setColumnWidth(0, 150)
        self.accuracyTable.setColumnWidth(1, 100)
        self.accuracyTable.setRowCount(len(self.dataloader.get_method_list()))
        

        #create a timer to control the play/pause button
        self.timer = QTimer()
        self.timer.timeout.connect(self.timer_timeout)
        self.timer.setInterval(int(1000/int(30*self.playback_speed))) #30 fps

        #connect the buttons to corresponding functions
        pre_not_labeled_btn.clicked.connect(self.pre_not_labeled_btn_clicked)
        next_not_labeled_btn.clicked.connect(self.next_not_labeled_btn_clicked)
        pre_frame_btn.clicked.connect(self.pre_frame_btn_clicked)
        next_frame_btn.clicked.connect(self.next_frame_btn_clicked)
        self.record_btn.clicked.connect(self.record_btn_clicked)
        self.skeleton_source_btn.clicked.connect(self.skeleton_source_btn_clicked)
        play_btn.clicked.connect(self.play_btn_clicked)
        pause_btn.clicked.connect(self.pause_btn_clicked)
        #connect space key to play/pause button
        self.space_shortcut = QShortcut(Qt.Key_Space, buttonWidget)
        self.space_shortcut.activated.connect(self.space_pressed)

    def update_frame(self, frame=-1):
        
        #if frame is -1, change to the current frame
        if frame == -1:
            frame = self.current_frame
        if self.last_frame != self.current_frame:
            if self.recording and 'average' in self.currentImage.landmarkPath:
                self.save_current_frame_points()
        self.dataloader.set_current_frame(frame)
        #update the viewer
        self.viewer.setPhoto(self.get_frame_pixmaps())
        #update the label
        self.update_label()

        if self.last_frame != self.current_frame:
            self.get_accuracy()
            if self.reset_lock_every_frame:
                self.reset_lock()
            self.update_skeleton_source_btn()

        #update undo/redo btn
        undo_status,redo_status = self.gt_data.get_undo_redo_status(self.dataloader.get_current_frame())
        self.undo_action.setEnabled(undo_status)
        self.redo_action.setEnabled(redo_status)

        #update the skeleton
        self.update_skeleton()
        #draw the points
        self.drawPoints(self.last_frame != self.current_frame)
        
        
        self.last_frame = self.current_frame
    def update_skeleton_source_btn(self):
        #if this frame is labeled, enable the button, else force to average and disable the button
        if self.gt_data.get_skeleton(self.dataloader.get_current_video(), self.dataloader.get_current_frame()) is not None:
            self.skeleton_source_btn.setEnabled(True)
            if self.skeleton_source != 'saved':
                self.skeleton_source_btn_clicked()
        else:
            if self.skeleton_source != 'average':
                self.skeleton_source_btn_clicked()
            self.skeleton_source_btn.setEnabled(False)
    def get_frame_pixmaps(self):
        cv_img = self.dataloader.get_frame()
        cv_img = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        #convert to pixmap
        height, width, channel = cv_img.shape
        bytesPerLine = 3 * width
        qImg = QImage(cv_img.data, width, height, bytesPerLine, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qImg)
        return pixmap
    
    def get_accuracy(self):
        d = {}
        for method in self.dataloader.get_current_method_list():
            d[method] = []
            pose,hands = self.dataloader.get_current_frame_skeleton(method)
            for point in pose:
                d[method].append(point[3])
            for hand in hands:
                for i in range(21):
                    d[method].append(hands[hand]['score'])
            avg = np.mean(np.array(d[method], dtype=np.float32))
            #formart to 100.00%
            self.methods_accuracy[method] = f"{avg*100:.2f}%"
        #update the table
        self.update_accuracy_table()
    def update_accuracy_table(self):
        for i, method in enumerate(self.methods_accuracy):
            self.accuracyTable.setItem(i, 0, QTableWidgetItem(method))
            self.accuracyTable.setItem(i, 1, QTableWidgetItem(self.methods_accuracy[method]))

    def update_skeleton(self):
            
        #get the tickboxes that are checked
        #if self.last_checked_methods != self.checked_methods:
            pose_len = 0
            hand_len = 0
            self.last_checked_methods = self.checked_methods
            self.landmarks_data = {}
            for method in self.checked_methods:
                pose,hand = self.dataloader.get_current_frame_skeleton(method)
                pose_len = len(pose)
                _hand = {hand[idx]['class']:hand[idx]['landmarks'] for idx in hand}
                hand_len = 21
                self.landmarks_data[method] = [pose, _hand]

            #Update when: point moved, chage frame, change video, change method
            #Loop through all the points, if the point have is_moved() == True, update the skeleton
            # for method in self.currentImage.landmarkPath:
            #     for i,_pose in enumerate(self.currentImage.landmarkPath[method]['pose']):
            #         if _pose.is_moved():
            #             self.landmarks_data[method][0][i] = _pose.returnCoordinates()
            current_frame_gt = self.gt_data.get_skeleton(self.dataloader.get_current_video(), self.dataloader.get_current_frame())
            if current_frame_gt and self.skeleton_source == 'saved':
                self.landmarks_data['average'] = self.load_frame_points(self.dataloader.get_current_frame())
            elif len(self.checked_methods) > 0:
                tmp_average = []
                tmp_count = []
                for method in self.checked_methods:
                    #calculate the average of all the points, ignore the 0,0 points
                    pose,hand = self.landmarks_data[method]
                    if len(tmp_average) == 0:
                        tmp_average = [np.zeros((33, 4)), np.zeros((21, 4)), np.zeros((21, 4))]
                        tmp_count = [np.zeros(_.shape) for _ in tmp_average]
                        
                    
                    tmp_average[0] += np.array(pose)
                    if 'Right' in hand:
                        tmp_average[1] += np.array(hand['Right'])
                        tmp_count[1] += (np.array(hand['Right']) != 0) * 1
                    if 'Left' in hand:
                        tmp_average[2] += np.array(hand['Left'])
                        tmp_count[2] += (np.array(hand['Left']) != 0) * 1
                    tmp_count[0] += (np.array(pose) != 0) * 1
                    
                    
                        
                tmp_average[0] /= tmp_count[0]
                tmp_average[1] /= tmp_count[1]
                tmp_average[2] /= tmp_count[2]
                #replace all inf with 0
                tmp_average[0][np.isinf(tmp_average[0])] = 0
                tmp_average[1][np.isinf(tmp_average[1])] = 0
                tmp_average[2][np.isinf(tmp_average[2])] = 0

                tmp_average[0][np.isnan(tmp_average[0])] = 0
                tmp_average[1][np.isnan(tmp_average[1])] = 0
                tmp_average[2][np.isnan(tmp_average[2])] = 0
                self.landmarks_data['average'] = [tmp_average[0].tolist(), {'Right':tmp_average[1].tolist(), 'Left':tmp_average[2].tolist()}]
    def save_current_frame_points(self):
        pixmapWidth, pixmapHeight = self.dataloader.get_video_dimension()
        _t = np.array([pixmapWidth, pixmapHeight, 1])
        #get the pos of all the points
        landmarks = [np.zeros((33, 3)), np.zeros((21, 3)), np.zeros((21, 3))]
        #loop thr the viewer and get the pos of all the points
        if not 'average' in self.landmarks_data:
            return
        if not self.landmarks_data['average']:
            return
        #pose
        for i,_pose_point in enumerate(self.currentImage.landmarkPath['average']['pose']):
            pos = _pose_point.returnCoordinates()
            landmarks[0][i] = pos / _t
        #hands
        for hand in self.currentImage.landmarkPath['average']['hands']:
            for i,_hand_point in enumerate(self.currentImage.landmarkPath['average']['hands'][hand]):
                pos = _hand_point.returnCoordinates()
                landmarks[1 if hand == 'Right' else 2][i] = pos / _t
        #save the points to the output data
        self.gt_data.add_skeleton(self.dataloader.get_current_video(), self.dataloader.get_current_frame(), landmarks)
    def load_frame_points(self, frame):
        #get the points of the frame from the output data, format simmilar to self.landmarks_data['average']
        #return None if the frame is not labeled
        _landmarks = self.gt_data.get_skeleton(self.dataloader.get_current_video(), frame)
        if _landmarks is None:
            return None
        return [_landmarks[0].tolist(), {'Right':_landmarks[1].tolist(), 'Left':_landmarks[2].tolist()}]
    



                    
    def reset_lock(self):
        for method in self.currentImage.landmarkPath:
            for _pose in self.currentImage.landmarkPath[method]['pose']:
                _pose.setLocked(False)
            for hand in self.currentImage.landmarkPath[method]['hands']:
                for _hand in self.currentImage.landmarkPath[method]['hands'][hand]:
                    _hand.setLocked(False)

    def drawPoints(self,next_frame=False):
        pixmapWidth, pixmapHeight = self.dataloader.get_video_dimension()
        pixmapSize = pixmapHeight * pixmapWidth
        EllipSize = int(pixmapSize /1000000) 
        
        if next_frame:
            #if average tickbox is checked, only draw average
            is_average_only_ = self.average_tickbox.isChecked()
            #if if method in self.currentImage.landmarkPath but not in self.landmarks_data, loop through all the points and remove them
            for method in self.currentImage.landmarkPath:
                self.methods_accuracy[method] = 0
                if method not in self.landmarks_data or is_average_only_:
                    #set the method accuracy to 0
                    if is_average_only_ and method == 'average':
                        continue
                    for i in range(len(self.currentImage.landmarkPath[method]['pose'])):
                        self.currentImage.landmarkPath[method]['pose'][i].removeLine()
                        self.viewer.scene().removeItem(self.currentImage.landmarkPath[method]['pose'][i])
                    self.currentImage.landmarkPath[method]['pose'] = []
                    for hand in self.currentImage.landmarkPath[method]['hands']:
                        for i in range(len(self.currentImage.landmarkPath[method]['hands'][hand])):
                            self.currentImage.landmarkPath[method]['hands'][hand][i].removeLine()
                            self.viewer.scene().removeItem(self.currentImage.landmarkPath[method]['hands'][hand][i])
                        self.currentImage.landmarkPath[method]['hands'][hand] = []
            for method in self.landmarks_data:
                if is_average_only_ and method != 'average':
                    continue
                pose = self.landmarks_data[method][0]
                hands = self.landmarks_data[method][1]
                #self.currentImage.landmarkPath
                #draw pose
                if method not in self.currentImage.landmarkPath:
                    self.currentImage.landmarkPath[method] = {'pose':[], 'hands':{}}
                method_color = average_color if method == 'average' else tickbox_colors[self.dataloader.get_method_list().index(method)]
                for i, point in enumerate(pose):
                    #if the point is not drawn, draw it
                    if len(self.currentImage.landmarkPath[method]['pose']) <= i:
                        path = QPainterPath()
                        font = QFont('Times', 1)
                        font.setPointSize(EllipSize + 4)
                        font.setLetterSpacing(QFont.PercentageSpacing, 150)
                        #show text: P1:visibility.2f
                        if self.view_landmark_name:
                            path.addText(6, 5, font, f"P{i+1}")
                        z = (point[2]*1.2 + 1)
                        rect = QRectF(-2, -2, 4 + z, 4 + z)
                        path.addEllipse(rect)
                        qPen = QPen()
                        qPen.setColor(QColor(method_color))
                        landmark_path = Landmark_path(path,i,'pose', self,method,QColor(method_color))
                        landmark_path.setPos(int(point[0]*pixmapWidth), int(point[1]*pixmapHeight))
                        landmark_path.setZ(point[2])
                        landmark_path.setPen(qPen)
                        self.currentImage.landmarkPath[method]['pose'].append(landmark_path)
                        self.viewer.addItem(landmark_path)
                    else:
                        #if the point is already drawn, update it
                        landmark_path = self.currentImage.landmarkPath[method]['pose'][i]
                        if not landmark_path.is_locked() or (point[0] != 0 and point[1] != 0):
                            landmark_path.setPos(int(point[0]*pixmapWidth), int(point[1]*pixmapHeight))
                            landmark_path.setZ(point[2])
                            if not self.show_skeleton:
                                landmark_path.removeLine()
                            #update label

                            landmark_path.reset()
                            #if the number of points is less than the number of tickboxes, remove the extra points
                            if len(self.currentImage.landmarkPath[method]['pose']) > len(pose):
                                for i in range(len(pose), len(self.currentImage.landmarkPath[method]['pose'])):
                                    self.currentImage.landmarkPath[method]['pose'][i].removeLine()
                                    self.viewer.scene().removeItem(self.currentImage.landmarkPath[method]['pose'][i])
                                self.currentImage.landmarkPath[method]['pose'] = self.currentImage.landmarkPath[method]['pose'][:len(pose)]
                for keypoint in self.currentImage.landmarkPath[method]['pose']:
                    target_line,_ = keypoint.get_target()
                    if target_line is not None:
                        keypoint.drawLine(target_line.x, target_line.y)
                #draw hands
                for hand in hands:
                    if hand not in self.currentImage.landmarkPath[method]['hands']:
                        self.currentImage.landmarkPath[method]['hands'][hand] = []
                    for i, point in enumerate(hands[hand]):
                        #if the point is not drawn, draw it
                        if len(self.currentImage.landmarkPath[method]['hands'][hand]) <= i:
                            path = QPainterPath()
                            font = QFont('Times', 1)
                            font.setPointSize(EllipSize + 4)
                            font.setLetterSpacing(QFont.PercentageSpacing, 150)
                            #show text: P1:visibility.2f
                            if self.view_landmark_name:
                                path.addText(6, 5, font, f"{'L' if hand == 'Left' else 'R'}{i+1}")
                            z = (point[2]*1.2 + 1)
                            rect = QRectF(-2, -2, 4 + z, 4 + z)
                            path.addEllipse(rect)
                            qPen = QPen()
                            qPen.setColor(QColor(method_color))
                            landmark_path = Landmark_path(path, i,'hands'+hand, self,method,QColor(method_color))
                            landmark_path.setPos(int(point[0]*pixmapWidth), int(point[1]*pixmapHeight))
                            landmark_path.setZ(point[2])
                            landmark_path.setPen(qPen)
                            self.currentImage.landmarkPath[method]['hands'][hand].append(landmark_path)
                            self.viewer.addItem(landmark_path)
                        else:
                            #if the point is already drawn, update it
                            landmark_path = self.currentImage.landmarkPath[method]['hands'][hand][i]
                            if not landmark_path.is_locked():
                                landmark_path.setPos(int(point[0]*pixmapWidth), int(point[1]*pixmapHeight))
                                landmark_path.setZ(point[2])
                                if not self.show_skeleton:
                                    landmark_path.removeLine()
                                #update label
                                landmark_path.reset()
                                #if the number of points is less than the number of tickboxes, remove the extra points
                                if len(self.currentImage.landmarkPath[method]['hands'][hand]) > len(hands[hand]):
                                    for i in range(len(hands[hand]), len(self.currentImage.landmarkPath[method]['hands'][hand])):
                                        self.currentImage.landmarkPath[method]['hands'][hand][i].removeLine()
                                        self.viewer.scene().removeItem(self.currentImage.landmarkPath[method]['hands'][hand][i])
                                    self.currentImage.landmarkPath[method]['hands'][hand] = self.currentImage.landmarkPath[method]['hands'][hand][:len(hands[hand])]
                for hand in self.currentImage.landmarkPath[method]['hands']:
                    for keypoint in self.currentImage.landmarkPath[method]['hands'][hand]:
                        target_line,_ = keypoint.get_target()
                        if target_line is not None:
                            keypoint.drawLine(target_line.x, target_line.y)
    def _create_menu_bar(self):
        self.menu_bar = self.menuBar()
        self.file_menu = self.menu_bar.addMenu("File")
        self.edit_menu = self.menu_bar.addMenu("Edit")
        self.view_menu = self.menu_bar.addMenu("View")
        self.help_menu = self.menu_bar.addMenu("Help")

        self._create_file_menu_actions()
        self._create_edit_menu_actions()
        self._create_view_menu_actions()
        self._create_help_menu_actions()

    def _create_file_menu_actions(self):
        self.open_action = QAction("Open", self)
        self.open_action.setShortcut("Ctrl+O")
        self.open_action.triggered.connect(self.open_action_triggered)
        self.file_menu.addAction(self.open_action)

        self.save_action = QAction("Save", self)
        self.save_action.setShortcut("Ctrl+S")
        self.save_action.triggered.connect(self.save_action_triggered)
        self.file_menu.addAction(self.save_action)

        self.exit_action = QAction("Exit", self)
        self.exit_action.setShortcut("Ctrl+Q")
        self.exit_action.triggered.connect(self.close)
        self.file_menu.addAction(self.exit_action)

    def _create_edit_menu_actions(self):
        self.undo_action = QAction("Undo", self)
        self.undo_action.setShortcut("Ctrl+Z")
        self.undo_action.triggered.connect(self.undo_action_triggered)
        self.edit_menu.addAction(self.undo_action)

        self.redo_action = QAction("Redo", self)
        self.redo_action.setShortcut("Ctrl+Y")
        self.redo_action.triggered.connect(self.redo_action_triggered)
        self.edit_menu.addAction(self.redo_action)

        #add a separator, below a select playback speed, with option to tick: 1x, 0.5x, 0.25x, 0.1x
        self.edit_menu.addSeparator()

        #add a tick: reset lock: a tick box
        self.reset_lock_action = QAction("Reset lock", self)
        self.reset_lock_action.setShortcut("Ctrl+L")
        self.reset_lock_action.setCheckable(True)
        self.reset_lock_action.setChecked(self.reset_lock_every_frame)
        self.reset_lock_action.triggered.connect(self.reset_lock_action_triggered)
        self.edit_menu.addAction(self.reset_lock_action)




        self.playback_speed_menu = QMenu("Playback speed", self)
        self.playback_speed_menu.setTearOffEnabled(True)
        self.edit_menu.addMenu(self.playback_speed_menu)
        #for
        playback_options = [2 , 1, 0.5, 0.25, 0.1]
        self.playback_speed_actions = {}
        for i, option in enumerate(playback_options):
            self.playback_speed_actions[option] = QAction(str(option) + "x", self)
            self.playback_speed_actions[option].setCheckable(True)
            self.playback_speed_actions[option].setChecked(option == 0.5)
            self.playback_speed_actions[option].triggered.connect(self.playback_speed_action_triggered)
            self.playback_speed_menu.addAction(self.playback_speed_actions[option])
        
    

    def _create_view_menu_actions(self):
        # a boolean to draw text on landmarks or not (Landmarks label)
        self.landmarks_label_action = QAction("Show landmarks name", self)
        self.landmarks_label_action.setCheckable(True)
        self.landmarks_label_action.setChecked(True)
        self.landmarks_label_action.triggered.connect(self.landmarks_label_action_triggered)
        self.view_menu.addAction(self.landmarks_label_action)

        # a boolean to show or hide the skeleton
        self.show_skeleton_action = QAction("Show skeleton", self)
        self.show_skeleton_action.setCheckable(True)
        self.show_skeleton_action.setChecked(True)
        self.show_skeleton_action.triggered.connect(self.show_skeleton_action_triggered)
        self.view_menu.addAction(self.show_skeleton_action)

    def _create_help_menu_actions(self):
        self.about_action = QAction("About", self)
        self.about_action.triggered.connect(self.about_action_triggered)
        self.help_menu.addAction(self.about_action)

    def open_action_triggered(self):
        #open a dialog to select the input data
        #then call the open function from gt
        open_dialog = QFileDialog(self)
        open_dialog.setFileMode(QFileDialog.AnyFile)
        open_dialog.setAcceptMode(QFileDialog.AcceptOpen)
        open_dialog.setNameFilter("Ground truth landmark files (*.glmks)")
        if open_dialog.exec_():
            filename = open_dialog.selectedFiles()[0]
            self.gt_data.load(filename)
            self.update_frame()

    def reset_lock_action_triggered(self):
        self.reset_lock_every_frame = self.reset_lock_action.isChecked()


    def save_action_triggered(self):
        #open a dialog to save the output data with .lmks extension
        #then call the save function from gt
        save_dialog = QFileDialog(self)
        save_dialog.setFileMode(QFileDialog.AnyFile)
        save_dialog.setAcceptMode(QFileDialog.AcceptSave)
        save_dialog.setNameFilter("Ground truth landmark files (*.glmks)")
        save_dialog.setDefaultSuffix("glmks")
        if save_dialog.exec_():
            filename = save_dialog.selectedFiles()[0]
            self.gt_data.save(filename)

    def undo_action_triggered(self):
        #call the undo function from gt and update the viewer
        undo_frame = self.gt_data.undo_action(self.dataloader.get_current_video(), self.dataloader.get_current_frame())

        #if frame, change to that frame
        if undo_frame:
            self.update_frame(undo_frame)

        #change skeleton source to saved if not
        if self.skeleton_source != 'saved':
            self.skeleton_source_btn_clicked()
        self.landmarks_data['average'] = self.load_frame_points(self.dataloader.get_current_frame())
        
        
        self.update_frame()
        self.drawPoints(True)
        

    def redo_action_triggered(self):
        #call the redo function from gt and update the viewer
        redo_frame = self.gt_data.redo_action( self.dataloader.get_current_video(), self.dataloader.get_current_frame())
        if redo_frame:
            self.update_frame(redo_frame)
        if self.skeleton_source != 'saved':
            self.skeleton_source_btn_clicked()
        self.landmarks_data['average'] = self.load_frame_points(self.dataloader.get_current_frame())
        self.update_frame()
        self.drawPoints(True)
    def playback_speed_action_triggered(self):
        for option in self.playback_speed_actions:
            if self.playback_speed_actions[option].isChecked() and not self.playback_speed == option:
                self.playback_speed = option
                self.timer.setInterval(int(1000/int(30*self.playback_speed))) #30 fps
                #disable all other options
                for _option in self.playback_speed_actions:
                    if _option != option:
                        self.playback_speed_actions[_option].setChecked(False)
        #if 1x is selected, disable the record button
        self.record_btn.setEnabled(self.playback_speed < 1)
    def landmarks_label_action_triggered(self):
        self.view_landmark_name = self.landmarks_label_action.isChecked()
        for method in self.landmarks_data:
            #if average tickbox is checked, only draw average
            is_average = self.average_tickbox.isChecked()
            if is_average and method != 'average':
                continue
            for i in range(len(self.currentImage.landmarkPath[method]['pose'])):
                            self.viewer.scene().removeItem(self.currentImage.landmarkPath[method]['pose'][i])
            self.currentImage.landmarkPath[method]['pose'] = []
            for hand in self.currentImage.landmarkPath[method]['hands']:
                for i in range(len(self.currentImage.landmarkPath[method]['hands'][hand])):
                    self.viewer.scene().removeItem(self.currentImage.landmarkPath[method]['hands'][hand][i])
                self.currentImage.landmarkPath[method]['hands'][hand] = []
        self.drawPoints(True)
    def show_skeleton_action_triggered(self):
        self.show_skeleton = self.show_skeleton_action.isChecked()
        self.update_skeleton()
        self.drawPoints(True)

    def about_action_triggered(self):
        
        #show a message box
        QMessageBox.about(self, "About", "Hand Landmark Editing Tool " + VER + "\n\n" + "Developed by dtungpka\n" +  "Phenikaa University -" + "2023" + "\n\n" + "https://github.com/dtungpka/")
        
                                                    
        


    #show which radio button was clicked
    def checkboxClicked(self):
        self.checked_methods = []
        for method in self.methods_tickbox:
            if self.methods_tickbox[method].isChecked():
                self.checked_methods.append(method)
        print(self.checked_methods)
        self.update_skeleton()
        self.drawPoints(True)
    def videoSourceChanged(self):
        #if timer is running, stop it
        if self.timer.isActive():
            self.timer.stop()
        
        if self.sender() == None:
            selected_alt = self.videoSource.currentText()
        else:
            selected_alt = self.sender().currentText()

        #show loading dialog
        self.loading_dialog = QProgressDialog(f"Loading {selected_alt}...", None, 0, 0, self)
        self.loading_dialog.setWindowTitle("Loading")
        self.loading_dialog.setWindowModality(Qt.WindowModal)
        self.loading_dialog.setCancelButton(None)
        self.loading_dialog.show()
        self.current_frame = 0
        
        #update the loading dialog
        QApplication.processEvents()
        self.loading_dialog.setValue(100)
        
        for video in self.alt_names:
            if self.alt_names[video] == selected_alt:
                self.current_video = video
                break
        self.dataloader.set_video(self.current_video)
        self.videoNameLb.setText(selected_alt)
        self.videoNameLb.adjustSize()
        self.labeled_frame_count, self.labeled_frames = self.gt_data.get_all_labeled_frames(self.current_video)

        #end the loading dialog
        self.loading_dialog.close()
        self.frameSlider.setMaximum(self.dataloader.get_total_frames())
        self.frameSlider.setValue(0)
        self.frameSlider.setTickInterval(self.dataloader.get_total_frames())



        msg = "\n".join(["Selected " + selected_alt + " as video source,",
               "Duration: " + str(self.dataloader.get_total_frames()) + " frames (" + str(self.dataloader.get_duration()) + ")",
               f"Labeled {self.labeled_frame_count} out of {self.dataloader.get_total_frames()} frames ({self.labeled_frame_count/self.dataloader.get_total_frames():.2%})",
               f"Avaliable method(s) for this video: {', '.join(self.dataloader.get_current_method_list())}"])
        
        #loop through all the tickboxes and set them to unchecked, and disable them if not in the current method list
        for method in self.methods_tickbox:
            self.methods_tickbox[method].setChecked(False)
            if method in self.dataloader.get_current_method_list():
                self.methods_tickbox[method].setEnabled(True)
            else:
                self.methods_tickbox[method].setEnabled(False)
    

        #show a message box
        QMessageBox.about(self, "Message", msg)
        
        self.current_frame = 0
        self.dataloader.set_current_frame(self.current_frame)
        self.viewer.setPhoto(self.get_frame_pixmaps(),True)
        self.update_label()
        self.update_skeleton()
        self.drawPoints(True)

    def update_label(self):

        


        #update self.videoProgressLb
        self.labeled_frame_count, self.labeled_frames = self.gt_data.get_all_labeled_frames(self.current_video)
        _txt = f"Labeled {self.labeled_frame_count} out of {self.dataloader.get_total_frames()} frames ({self.labeled_frame_count/self.dataloader.get_total_frames():.2%})"
        self.videoProgressLb.setText(_txt)
        self.videoProgressLb.adjustSize()

        #update self.detectLb
        ske = self.gt_data.get_skeleton(self.current_video, self.current_frame)
        #if the current frame is labeled, show Labeld, else show Not labeled
        if ske is not None:
            #set color to green
            self.detectLb.setStyleSheet("color:green")
            self.detectLb.setText(f"Frame {self.current_frame}: Labeled               ")
        else:
            #set color to red
            self.detectLb.setStyleSheet("color:red")
            self.detectLb.setText(f"Frame {self.current_frame}: Not labeled           ")

        #update self.frameInfoLb
        _txt = '\n'.join([f"Frame {self.current_frame} out of {self.dataloader.get_total_frames()} ({self.current_frame/self.dataloader.get_total_frames():.2%})",
                          f'{self.dataloader.get_current_duration()} / {self.dataloader.get_duration()}'])
        self.frameInfoLb.setText(_txt)
        self.frameInfoLb.adjustSize()

        #update the slider
        self.frameSlider.blockSignals(True)
        self.frameSlider.setValue(self.current_frame)
        self.frameSlider.blockSignals(False)






    def frameSliderChanged(self):
        #check if user interacted with the slider
        # if self.playing_vid:
        #     self.playing_vid = False
        #     return
        
        #get value from slider
        value = self.frameSlider.value()
        #get desired frame
        desired_frame = int(value)
        #set desired frame
        self.current_frame = max(0, min(desired_frame, self.dataloader.get_total_frames() - 1))
        self.update_frame()
        
    def calculate_average_btn_clicked(self):
        #show a 3 button dialog:
        #1. From previous frame
        #2. Average of previous and next frame
        #3. From next frame
        #if the current frame is the first frame, disable the first button
        #if the current frame is the last frame, disable the third button

        #Create a dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Calculate average")
        dialog.setWindowModality(Qt.WindowModal)
        dialog.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        dialog.setFixedSize(300, 100)
        dialog.setModal(True)
        dialog.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        dialog.setWindowFlag(Qt.MSWindowsFixedSizeDialogHint, True)
        dialog.setWindowFlag(Qt.WindowTitleHint, True)
        dialog.setWindowFlag(Qt.WindowSystemMenuHint, False)
        dialog.setWindowFlag(Qt.WindowMinimizeButtonHint, False)
        dialog.setWindowFlag(Qt.WindowMaximizeButtonHint, False)


        #Create 3 buttons
        btn1 = QPushButton("From previous frame", dialog)
        btn2 = QPushButton("Average of previous and next frame", dialog)
        btn3 = QPushButton("From next frame", dialog)
        btn1.move(10, 10)
        btn2.move(10, 40)
        btn3.move(10, 70)
        btn1.clicked.connect(lambda: self.calculate_average_btn_clicked_action(1))
        btn2.clicked.connect(lambda: self.calculate_average_btn_clicked_action(2))
        btn3.clicked.connect(lambda: self.calculate_average_btn_clicked_action(3))
        #if the current frame is the first frame, disable the first button
        if self.current_frame == 0:
            btn1.setEnabled(False)
        #if the current frame is the last frame, disable the third button
        if self.current_frame == self.dataloader.get_total_frames() - 1:
            btn3.setEnabled(False)
        dialog.exec()

    def get_average_skeleton(self, skeletons):
        tmp_average = []
        tmp_count = []
        for (pose,hand) in skeletons:
            #calculate the average of all the points, ignore the 0,0 points
            if len(tmp_average) == 0:
                tmp_average = [np.zeros((33, 4)), np.zeros((21, 4)), np.zeros((21, 4))]
                tmp_count = [np.zeros(_.shape) for _ in tmp_average]
                
            
            tmp_average[0] += np.array(pose)
            if 'Right' in hand:
                tmp_average[1] += np.array(hand['Right'])
                tmp_count[1] += (np.array(hand['Right']) != 0) * 1
            if 'Left' in hand:
                tmp_average[2] += np.array(hand['Left'])
                tmp_count[2] += (np.array(hand['Left']) != 0) * 1
            tmp_count[0] += (np.array(pose) != 0) * 1
            
            
                
        tmp_average[0] /= tmp_count[0]
        tmp_average[1] /= tmp_count[1]
        tmp_average[2] /= tmp_count[2]
        #replace all inf with 0
        tmp_average[0][np.isinf(tmp_average[0])] = 0
        tmp_average[1][np.isinf(tmp_average[1])] = 0
        tmp_average[2][np.isinf(tmp_average[2])] = 0

        tmp_average[0][np.isnan(tmp_average[0])] = 0
        tmp_average[1][np.isnan(tmp_average[1])] = 0
        tmp_average[2][np.isnan(tmp_average[2])] = 0
        return [tmp_average[0].tolist(), {'Right':tmp_average[1].tolist(), 'Left':tmp_average[2].tolist()}]
    def get_average_skeleton_from_multiple_frame(self, frames):
        pass
    def calculate_average_btn_clicked_action(self, action):
        print(f"Action {action} clicked")
        #close the dialog
        self.sender().parent().close()
        #get the desired frame
        desired_frame = self.current_frame
        


    def pre_not_labeled_btn_clicked(self):
        self.labeled_frame_count, self.labeled_frames = self.gt_data.get_all_labeled_frames(self.current_video)
        desired_frame = self.current_frame
        found = False
        while desired_frame > 0 and not found:
            if desired_frame not in self.labeled_frames:
                found = True
                break
            desired_frame -= 1
        #if not found, show a message box
        if not found:
            QMessageBox.about(self, "Info", "All frames before this have been labeled")
            return
        #set desired frame
        self.current_frame = desired_frame
        self.update_frame()
    def next_not_labeled_btn_clicked(self):
        self.labeled_frame_count, self.labeled_frames = self.gt_data.get_all_labeled_frames(self.current_video)
        #loop from current frame to when the next not labeled frame is found
        desired_frame = self.current_frame

        found = False
        while desired_frame < self.dataloader.get_total_frames() - 1 and not found:
            if desired_frame not in self.labeled_frames:
                found = True
                break
            desired_frame += 1
        #if not found, show a message box
        if not found:
            QMessageBox.about(self, "Info", "All frames after this have been labeled")
            return
        #set desired frame
        self.current_frame = desired_frame
        self.update_frame()

    def pre_frame_btn_clicked(self):
        #if the current frame is the first frame, show a message box
        if self.current_frame == 0:
            QMessageBox.about(self, "Warning", "First frame reached")
            return
        self.current_frame -= 1
        self.update_frame()
    def next_frame_btn_clicked(self):
        #if the current frame is the last frame, show a message box
        if self.current_frame == self.dataloader.get_total_frames() - 1:
            QMessageBox.about(self, "Warning", "Last frame reached")
            return
        self.current_frame += 1
        self.update_frame()
    def record_btn_clicked(self):
        #set the recording label to (Recording)
        if self.recording:
            self.recording = False
            self.recordingLb.setText("                              ")
            #set the image of btn to record
            record_pixmap = QPixmap('Icons/videocamera.png')
            record_icon = QIcon(record_pixmap)
            self.sender().setIcon(record_icon)
            #if playing, stop the timer
            if self.timer.isActive():
                self.timer.stop()
            
            self.save_current_frame_points()
        else:
            self.recording = True
            self.recordingLb.setText("(Recording)")
            #set the image of btn to stop
            record_pixmap = QPixmap('Icons/videocamera-record.png')
            record_icon = QIcon(record_pixmap)
            self.sender().setIcon(record_icon)
    def skeleton_source_btn_clicked(self):
        if self.skeleton_source == 'saved':
            self.skeleton_source = 'average'
            self.skeleton_source_btn.setToolTip("Skeleton source: average")
            #set the image of btn to record
            skeleton_source_pixmap = QPixmap('Icons/cache.png')
            skeleton_source_icon = QIcon(skeleton_source_pixmap)
            self.skeleton_source_btn.setIcon(skeleton_source_icon)
        else:
            self.skeleton_source = 'saved'
            self.skeleton_source_btn.setToolTip("Skeleton source: default")
            #set the image of btn to stop
            skeleton_source_pixmap = QPixmap('Icons/saved.png')
            skeleton_source_icon = QIcon(skeleton_source_pixmap)
            self.skeleton_source_btn.setIcon(skeleton_source_icon)
        self.update_skeleton()
        self.drawPoints(True)
    def space_pressed(self):
        #play or pause the video when space is pressed
        if self.timer.isActive():
            self.timer.stop()
        else:
            self.timer.start()
    def play_btn_clicked(self):
        self.timer.start()
    def pause_btn_clicked(self):
        self.timer.stop()
    def timer_timeout(self):
        #if the current frame is the last frame, stop the timer
        if self.current_frame == self.dataloader.get_total_frames() - 1:
            self.timer.stop()
            return
        self.current_frame += 1
        self.update_frame()



if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyleSheet(qdarkgraystyle.load_stylesheet())
    window = MainWindow()
    window.show()
    app.exec()