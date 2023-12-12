import sys
import os
import face_alignment
import numpy as np
import imghdr
#import dlib
import cv2
from skimage import io
from PyQt5.QtGui import *
from PyQt5.Qt import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
import qdarkgraystyle
import json
import time
import data_handler as dh
import pickle as pkl


VER = "v1.0"
tickbox_colors = ["#00ffff", "#008080", "#00ff00", "#808040", "#808080","#8080ff","#ff8040","#8000ff"]
average_color = "#ffffff"
#contains name, points, pixmap image, paths, and landmarkpaths of image

class OperationsType:
    ADD_SKELETON = 0
    REMOVE_SKELETON = 1
    ADD_KEYPOINT = 2
    REMOVE_KEYPOINT = 3
    MOVE_KEYPOINT = 4



class Outputdata:
    '''
    For all operations, the output data should be stored in this class:
    Video > frame > pose/hand

    Save, load, querry
    Undo, redo
    '''
    def __init__(self) -> None:
        self.data = {}
        self.history = []
        self.history_pointer = 0

    def save(self, path):
        with open(path, 'wb') as f:
            pkl.dump(self.data, f)

    def load(self, path):
        with open(path, 'rb') as f:
            self.data = pkl.load(f)

    def get_skeleton(self, video, frame):
        return self.data[video][frame]
    
    def add_skeleton(self, video, frame, skeleton):
        if video not in self.data:
            self.data[video] = {}
        self.history.append((OperationsType.ADD_SKELETON, video, frame, skeleton))
        self.history_pointer += 1
        self.data[video][frame] = skeleton

        #only save the last 100 operations
        if len(self.history) > 100:
            self.history = self.history[-100:]
            self.history_pointer = 100
        

    def remove_skeleton(self, video, frame):
        self.history.append((OperationsType.REMOVE_SKELETON, video, frame, self.data[video][frame]))
        self.history_pointer += 1
        del self.data[video][frame]

    def undo_action(self):
        if self.history_pointer > 0:
            self.history_pointer -= 1
            operation, video, frame, data = self.history[self.history_pointer]
            if operation == OperationsType.ADD_SKELETON:
                self.add_skeleton(video, frame,data)
            elif operation == OperationsType.REMOVE_SKELETON:
                self.add_skeleton(video, frame,data)


    def redo_action(self):
        if self.history_pointer < len(self.history):
            operation, video, frame, data = self.history[self.history_pointer]
            if operation == OperationsType.ADD_SKELETON:
                self.add_skeleton(video, frame,data)
            self.history_pointer += 1
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
            self.setDragMode(QGraphicsView.NoDrag)

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

    def __init__(self, path, parent=None,moveable=True):
        super(Landmark_path, self).__init__()
        self.path = path
        self.setPath(path)
        pos = self.scenePos()
        self.x = pos.x()
        self.y = pos.y()
        self.moved = True
        self.parent = parent
        self.setFlag(QGraphicsItem.ItemIsMovable, moveable)
        self.setFlag(QGraphicsItem.ItemIsSelectable, moveable)

    def mousePressEvent(self, event):
        event.accept()
        super(Landmark_path, self).mousePressEvent(event)

    def mouseMoveEvent(self, event):
        event.accept()
        super(Landmark_path, self).mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        event.accept()
        super(Landmark_path, self).mouseReleaseEvent(event)
        pos = self.scenePos()
        point = self.mapToScene(pos.x(), pos.y())
        self.x = point.x()
        self.y = point.y()
        self.moved = True
        self.parent.update_skeleton()
    def reset(self):
        self.moved = False
    def is_moved(self):
        return self.moved
    def returnCoordinates(self):
        self.x = self.scenePos().x()
        self.y = self.scenePos().y()
        return np.array([self.x, self.y])


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
        self.drawn = False #whether landmarks are drawn or not
        self.data_path = self.get_data_path()  # get the path of metadata.json
        self.data_folder = os.path.dirname(self.data_path)  # get the path of data folder
        self.dataloader = dh.DataHandler(self.data_folder)  # initiate data handler
        self.video_list = self.dataloader.get_video_list()  # get the list of videos
        self.alt_names = self.dataloader.get_alt_name()
        self.playing_vid = False  # whether the video is playing or not
        self.current_frame = 0  # current frame
        self.gt_data = Outputdata()  # initiate output data
        self.initUI()  # initiate UI
        #maximize the window
        self.showMaximized()
        #show the window
        self.show()
        self.videoSourceChanged()








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

        
        # create detect label
        detectLb = QLabel("Info", buttonWidget)
        detectLb.setFont(QFont("Book Antiqua", 14, QFont.Bold))
        detectLb.move(buttonWidget.x(), buttonWidget.y() + 450)

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

        #create a timer to control the play/pause button
        self.timer = QTimer()
        self.timer.timeout.connect(self.timer_timeout)
        self.timer.setInterval(int(1000/30)) #30 fps

        #connect the buttons to corresponding functions
        pre_not_labeled_btn.clicked.connect(self.pre_not_labeled_btn_clicked)
        next_not_labeled_btn.clicked.connect(self.next_not_labeled_btn_clicked)
        pre_frame_btn.clicked.connect(self.pre_frame_btn_clicked)
        next_frame_btn.clicked.connect(self.next_frame_btn_clicked)
        play_btn.clicked.connect(self.play_btn_clicked)
        pause_btn.clicked.connect(self.pause_btn_clicked)
        #connect space key to play/pause button
        self.space_shortcut = QShortcut(Qt.Key_Space, buttonWidget)
        self.space_shortcut.activated.connect(self.space_pressed)

    def change_frame(self, frame=-1):
        
        #if frame is -1, change to the current frame
        if frame == -1:
            frame = self.current_frame
        self.dataloader.set_current_frame(frame)
        #update the viewer
        self.viewer.setPhoto(self.get_frame_pixmaps())
        #update the label
        self.update_label()
        #update the skeleton
        self.update_skeleton()
        #draw the points
        self.drawPoints(self.last_frame != self.current_frame)
        self.last_frame = self.current_frame
    def get_frame_pixmaps(self):
        cv_img = self.dataloader.get_frame()
        cv_img = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        #convert to pixmap
        height, width, channel = cv_img.shape
        bytesPerLine = 3 * width
        qImg = QImage(cv_img.data, width, height, bytesPerLine, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(qImg)
        return pixmap
    def update_skeleton(self):
        #get the tickboxes that are checked
        #if self.last_checked_methods != self.checked_methods:
            self.last_checked_methods = self.checked_methods
            self.landmarks_data = {}
            for method in self.checked_methods:
                pose,hand = self.dataloader.get_current_frame_skeleton(method)
                self.landmarks_data[method] = [pose, hand]
            #Todo: update average
            
            

    def drawPoints(self,next_frame=False):
        pixmapWidth, pixmapHeight = self.dataloader.get_video_dimension()
        pixmapSize = pixmapHeight * pixmapWidth

        EllipSize = int(pixmapSize /1000000) #TODO: change to z
        if next_frame:
            #if average tickbox is checked, only draw average
            is_average = self.average_tickbox.isChecked()
            for method in self.landmarks_data:
                pose = self.landmarks_data[method][0]
                hands = self.landmarks_data[method][1]
                #self.currentImage.landmarkPath
                #draw pose
                if method not in self.currentImage.landmarkPath:
                    self.currentImage.landmarkPath[method] = {'pose':[], 'hands':{}}
                method_color = tickbox_colors[self.dataloader.get_method_list().index(method)]
                for i, point in enumerate(pose):
                    #if the point is not drawn, draw it
                    if len(self.currentImage.landmarkPath[method]['pose']) <= i:
                        path = QPainterPath()
                        font = QFont('Times', 4)
                        font.setPointSize(EllipSize + 4)
                        font.setLetterSpacing(QFont.PercentageSpacing, 150)
                        #show text: P1:visibility.2f
                        path.addText(5, 5, font, f"P{i+1}")
                        path.addEllipse(0, 0, EllipSize*3, EllipSize*3)
                        qPen = QPen()
                        qPen.setColor(QColor(method_color))
                        landmark_path = Landmark_path(path, self,method!='average')
                        landmark_path.setPos(int(point[0]*pixmapWidth), int(point[1]*pixmapHeight))
                        landmark_path.setPen(qPen)
                        self.currentImage.landmarkPath[method]['pose'].append(landmark_path)
                        self.viewer.addItem(landmark_path)
                    else:
                        #if the point is already drawn, update it
                        landmark_path = self.currentImage.landmarkPath[method]['pose'][i]
                        landmark_path.setPos(int(point[0]*pixmapWidth), int(point[1]*pixmapHeight))
                        #update label

                        landmark_path.reset()
                        #if the number of points is less than the number of tickboxes, remove the extra points
                        if len(self.currentImage.landmarkPath[method]['pose']) > len(pose):
                            for i in range(len(pose), len(self.currentImage.landmarkPath[method]['pose'])):
                                self.viewer.scene().removeItem(self.currentImage.landmarkPath[method]['pose'][i])
                            self.currentImage.landmarkPath[method]['pose'] = self.currentImage.landmarkPath[method]['pose'][:len(pose)]


#TODO: UI show accuracy of each method
                    

    

   

    def detectClButClicked(self):
        #Pending for deletion
        if not self.viewer.hasPhoto():
            self.clickMethod3()

        else:
            for landmarkPath in self.currentImage.landmarkPath: #remove landmarkpath in image
                self.viewer.scene().removeItem(landmarkPath)

            self.drawn = False


    def _create_menu_bar(self):
        self.menu_bar = self.menuBar()
        self.file_menu = self.menu_bar.addMenu("File")
        self.edit_menu = self.menu_bar.addMenu("Edit")
        self.help_menu = self.menu_bar.addMenu("Help")

        self._create_file_menu_actions()
        self._create_edit_menu_actions()
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

    def _create_help_menu_actions(self):
        self.about_action = QAction("About", self)
        self.about_action.triggered.connect(self.about_action_triggered)
        self.help_menu.addAction(self.about_action)

    def open_action_triggered(self):
        pass

    def save_action_triggered(self):
        pass

    def undo_action_triggered(self):
        pass

    def redo_action_triggered(self):
        pass

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
        self.change_frame()
        
    def calculate_average_btn_clicked(self):
        pass


    def pre_not_labeled_btn_clicked(self):
        self.labeled_frame_count, self.labeled_frames = self.gt_data.get_all_labeled_frames(self.current_video)
        #loop from current frame to when the next not labeled frame is found
        desired_frame = self.current_frame
        found = False
        while desired_frame > 0 and not found:
            if desired_frame not in self.labeled_frames:
                found = True
                break
            desired_frame -= 1
        #find backword if not found
        if not found:
            desired_frame = self.current_frame
            while desired_frame < self.dataloader.get_total_frames() - 1 and not found:
                if desired_frame not in self.labeled_frames:
                    found = True
                    break
                desired_frame += 1
        #if not found, show a message box
        if not found:
            QMessageBox.about(self, "Info", "All frames have been labeled")
            return
        #set desired frame
        self.current_frame = desired_frame
        self.change_frame()
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
        #find backword if not found
        if not found:
            desired_frame = self.current_frame
            while desired_frame > 0 and not found:
                if desired_frame not in self.labeled_frames:
                    found = True
                    break
                desired_frame -= 1
        #if not found, show a message box
        if not found:
            QMessageBox.about(self, "Info", "All frames have been labeled")
            return
        #set desired frame
        self.current_frame = desired_frame
        self.change_frame()

    def pre_frame_btn_clicked(self):
        #if the current frame is the first frame, show a message box
        if self.current_frame == 0:
            QMessageBox.about(self, "Warning", "First frame reached")
            return
        self.current_frame -= 1
        self.change_frame()
    def next_frame_btn_clicked(self):
        #if the current frame is the last frame, show a message box
        if self.current_frame == self.dataloader.get_total_frames() - 1:
            QMessageBox.about(self, "Warning", "Last frame reached")
            return
        self.current_frame += 1
        self.change_frame()
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
        self.change_frame()



if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyleSheet(qdarkgraystyle.load_stylesheet())
    window = MainWindow()
    window.show()
    app.exec()