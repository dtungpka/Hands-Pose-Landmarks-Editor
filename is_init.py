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

    def redo_action(self):
        if self.history_pointer < len(self.history):
            operation, video, frame, data = self.history[self.history_pointer]
            if operation == OperationsType.ADD_SKELETON:
                self.add_skeleton(video, frame,data)
            self.history_pointer += 1












class ImageSet:
    def __init__(self):
        self.__pixmslap = None
        self.__path = ""
        self.__point = []
        self.__landmarkPath = []
        self.__name = ""

    @property  # get pixmap
    def pixmap(self):
        return self.__pixmap

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

    def setPhoto(self, pixmap=None):
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

    def addItem(self, item):
        return self._scene.addItem(item)


class Landmark_path(QGraphicsPathItem):

    def __init__(self, path):
        super(Landmark_path, self).__init__()
        self.path = path
        self.setPath(path)
        pos = self.scenePos()
        self.x = pos.x()
        self.y = pos.y()
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)

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

    def returnCoordinates(self):
        self.x = self.scenePos().x()
        self.y = self.scenePos().y()
        return np.array([self.x, self.y])


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.title = 'Hand Landmark Editing Tool v1.0'
        self.dw = QDesktopWidget()  # fit to the size of desktop
        self.x = 0
        self.y = 0
        self.width = self.dw.width()  # width of the desktop
        self.height = self.dw.height()  # height of the desktop
        self._label = QLabel()  # labels that show no photo uploaded warnings

        self.currentImage = ImageSet()  # current image
        
        

        self.drawn = False #whether landmarks are drawn or not
        self.data_path = self.get_data_path()  # get the path of metadata.json
        self.data_folder = os.path.dirname(self.data_path)  # get the path of data folder
        self.dataloader = dh.DataHandler(self.data_folder)  # initiate data handler
        self.video_list = self.dataloader.get_video_list()  # get the list of videos
        self.alt_names = self.dataloader.get_alt_name()
        self.initUI()  # initiate UI




    def get_data_path(self):
        #show a dialog to get the data path, by choosing a file name "metadata.json"
        data_path = QFileDialog.getOpenFileName(self, "Open metadata.json", "metadata.json", "metadata.json file (metadata.json)")[0]
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
        self.average_tickbox = QCheckBox("Average", buttonWidget)
        self.average_tickbox.move(buttonWidget.x() + 5, buttonWidget.y() + 40 + len(self.dataloader.get_method_list())*20)
        self.average_tickbox.clicked.connect(self.checkboxClicked)
        self.average_tickbox.setChecked(False)
        self.average_tickbox.setStyleSheet("color:" + average_color)
        self.average_tickbox.setShortcut("`")




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
        self.videoNameLb.setFont(QFont("Book Antiqua", 14, QFont.Bold))
        self.videoNameLb.move(buttonWidget.x(), buttonWidget.y() + 300)

        self.videoProgressLb = QLabel("Labeled 0 out of 0 frames (0.00%)", buttonWidget)
        self.videoProgressLb.setFont(QFont("Book Antiqua", 14, QFont.Bold))
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
        self.frameSlider.move(buttonWidget.x() + 5, buttonWidget.y() + 585)
        self.frameSlider.resize(250, 50)
        self.frameSlider.setMinimum(0)
        self.frameSlider.setMaximum(100)
        self.frameSlider.setValue(0)
        self.frameSlider.setTickPosition(QSlider.TicksBelow)
        self.frameSlider.setTickInterval(1)
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

        #nav to next not labeled frame
        next_not_labeled_pixmap = QPixmap('Icons/next_not_labeled.png')
        next_not_labeled_icon = QIcon(next_not_labeled_pixmap)
        next_not_labeled_btn = QPushButton(buttonWidget)
        next_not_labeled_btn.setIcon(next_not_labeled_icon)
        next_not_labeled_btn.resize(50, 50)
        next_not_labeled_btn.move(buttonWidget.x() + 170, buttonWidget.y() + 650)

        #nav to pre frame
        pre_frame_pixmap = QPixmap('Icons/pre_frame.png')
        pre_frame_icon = QIcon(pre_frame_pixmap)
        pre_frame_btn = QPushButton(buttonWidget)
        pre_frame_btn.setIcon(pre_frame_icon)
        pre_frame_btn.resize(50, 50)
        pre_frame_btn.move(buttonWidget.x() + 60, buttonWidget.y() + 650)

        #nav to next frame
        next_frame_pixmap = QPixmap('Icons/next_frame.png')
        next_frame_icon = QIcon(next_frame_pixmap)
        next_frame_btn = QPushButton(buttonWidget)
        next_frame_btn.setIcon(next_frame_icon)
        next_frame_btn.resize(50, 50)
        next_frame_btn.move(buttonWidget.x() + 115, buttonWidget.y() + 650)

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
        self.timer.setInterval(1000/30) #30 fps

        #connect the buttons to corresponding functions
        pre_not_labeled_btn.clicked.connect(self.pre_not_labeled_btn_clicked)
        next_not_labeled_btn.clicked.connect(self.next_not_labeled_btn_clicked)
        pre_frame_btn.clicked.connect(self.pre_frame_btn_clicked)
        next_frame_btn.clicked.connect(self.next_frame_btn_clicked)
        play_btn.clicked.connect(self.play_btn_clicked)
        pause_btn.clicked.connect(self.pause_btn_clicked)
        






        # upload button connection
        # uploadImBut.clicked.connect(self.uploadImButClicked)
        # uploadImBut.setShortcut("ctrl+i")
        # uploadTeBut.clicked.connect(self.uploadTeButClicked)
        # uploadTeBut.setShortcut("ctrl+t")
        # uploadFoBut.clicked.connect(self.uploadFoButClicked)
        # uploadFoBut.setShortcut("ctrl+f")

        # detection button connection
        # detectBut.clicked.connect(self.detectButClicked)
        # detectBut.setShortcut("ctrl+d")
        # detectClBut.clicked.connect(self.detectClButClicked)
        # detectClBut.setShortcut("ctrl+c")

        # # save button connectoin
        # saveBut.clicked.connect(self.saveButClicked)
        # saveBut.setShortcut("ctrl+s")

        #initiate detector
        #self.dlib_detector = dlib.get_frontal_face_detector()
        #self.dlib_predictor = dlib.shape_predictor(
        #    "./shape_predictor_68_face_landmarks.dat"
        #)

        self.torch_detector = face_alignment.FaceAlignment(face_alignment.LandmarksType.TWO_D, device='cpu')

    def drawPoints(self, points):

        # create Painterpath with text and circle and add them to the viewer

        if len(self.currentImage.landmarkPath) != 0:
            self.detectClButClicked()
            self.currentImage.landmarkPath.clear()

        index = 1

        pixmapWidth = self.currentImage.pixmap.width()
        pixmapHeight = self.currentImage.pixmap.height()
        pixmapSize = pixmapHeight * pixmapWidth

        EllipSize = pixmapSize / 1000000

        for x, y in points:

            if index > 68:
                index = 1

            path = QPainterPath()
            font = QFont('Times', 2)  # font
            font.setPointSize(EllipSize + 2)
            font.setWeight(0.1)  # make font thinner
            font.setLetterSpacing(QFont.PercentageSpacing, 150)
            path.addText(5, 5, font, str(index))

            path.addEllipse(0, 0, EllipSize, EllipSize)
            qPen = QPen()

            # set color for each landmarkPath
            if index <= 17:
                qPen.setColor(QColor(150, 0, 0))
            elif 18 <= index and index <= 26:
                qPen.setColor(QColor(0, 150, 0))
            elif 28 <= index and index <= 35:
                qPen.setColor(QColor(0, 0, 150))
            elif 37 <= index and index <= 47:
                qPen.setColor(QColor(100, 100, 100))
            elif 49 <= index and index <= 68:
                qPen.setColor(QColor(50, 50, 50))

            # create landmark_point and add them to viwer
            landmark_path = Landmark_path(path)
            landmark_path.setPos(x, y)
            landmark_path.setPen(qPen)

            self.currentImage.landmarkPath.append(landmark_path)
            self.viewer.addItem(landmark_path)

            index += 1

        self.drawn = True

    def rightArrowButClicked(self):

        # if imageFolder empty, rightArrowBut does not operate
        if len(self.imageFolder) == 0:
            pass
        else:  # if imageFolder is not empty

            # if there is landmark path on scene
            if self.drawn:
                self.detectClButClicked()

            if self.imageFolderIndex >= len(self.imageFolder) - 1:
                self.imageFolderIndex = 0
            else:
                self.imageFolderIndex += 1

            # get corresponding image from folder
            self.currentImage = self.imageFolder[self.imageFolderIndex]
            self.viewer.setPhoto(self.currentImage.pixmap)

            # if there is text file with points to the image
            if self.currentImage.name in self.imageFolderText:

                numbers = []

                for line in self.imageFolderText[self.currentImage.name]:
                    numbers.append(line.split())

                for j in range(0, 2):
                    for i in range(0, 68):
                        numbers[i][j] = float(numbers[i][j])

                self.drawPoints(numbers)

            self.textLb.setText('Image :' + str(self.currentImage.name))
            self.textLb.adjustSize()

    def leftArrowButClicked(self):

        # if imageFolder empty, rightArrowBut does not operate
        if len(self.imageFolder) == 0:
            pass
        else:  # if imageFolder is not empty

            # if there is landmark path on scene
            if self.drawn:
                self.detectClButClicked()

            if self.imageFolderIndex <= 0:
                self.imageFolderIndex = len(self.imageFolder) - 1
            else:
                self.imageFolderIndex -= 1

            # get corresponding image from folder
            self.currentImage = self.imageFolder[self.imageFolderIndex]
            self.viewer.setPhoto(self.currentImage.pixmap)

            # if there is text file with points to the image
            if self.currentImage.name in self.imageFolderText:

                numbers = []

                for line in self.imageFolderText[self.currentImage.name]:
                    numbers.append(line.split())

                for j in range(0, 2):
                    for i in range(0, 68):
                        numbers[i][j] = float(numbers[i][j])

                self.drawPoints(numbers)

            self.textLb.setText('Image :' + str(self.currentImage.name))
            self.textLb.adjustSize()

    def saveButClicked(self):
        ##
        if self.currentImage.landmarkPath != []:
        # get the path of directory where image is located at

            filepath_full = os.path.splitext(self.currentImage.path)[0] + '.txt'

            f = open(filepath_full, 'w')
            temp = []

            for point in self.currentImage.landmarkPath:
                f.write(str(point.returnCoordinates()).replace('[', '').replace(']', '') + '\n')
                temp.append(str(point.returnCoordinates()).replace('[', '').replace(']', '') + '\n')

            if len(self.imageFolder) != 0: #if there is folder
                if self.currentImage.name in self.imageFolderText: #if there is already corresponding text file, save the changes
                    self.imageFolderText[self.currentImage.name] = temp
                else: #if there is no corresponding text file, add it
                    self.imageFolderText[self.currentImage.name] = temp
            f.close()
        else:
            self.clickMethod()

    def uploadImButClicked(self):
        # if imageFolder is not empty, empty it
        if len(self.imageFolder) != 0:
            self.imageFolder.clear()

        # get the path of file
        fNamePath = QFileDialog.getOpenFileName(self, "Open Image", "Image Files (*.png *.jpg *.bmp *.jpeg *.gif)")
        #fNamePath = QFileDialog.getOpenFileName(self, 'Open file', '/home')
        self.currentImage.path = fNamePath[0]

        if self.currentImage.path == "": #if esc was pressed or no image was chosen, do not set empty path as current image path
            pass
        else:
            # upload images on grpahicView
            self.currentImage.pixmap = QPixmap(self.currentImage.path)
            self.viewer.setPhoto(self.currentImage.pixmap)
            self.textLb.setText('Image :' + str(os.path.basename(self.currentImage.path)))
            self.textLb.adjustSize()

    def uploadFoButClicked(self):
        # get the path of selected directory
        dir_ = QFileDialog.getExistingDirectory(None, 'Open folder:', 'QDir.homePath()', QFileDialog.ShowDirsOnly)

        # if not choose any directory, just pass
        if not dir_:
            pass
        else:
            # if imageFolder is not empty, empty it
            if len(self.imageFolder) != 0:
                self.imageFolder.clear()

            # put each corresponding image into imageFolder
            for files_ext in sorted(os.listdir(dir_)):

                imagePath = dir_ + '/' + files_ext
                self.textLb.setText('Image : ' + str(files_ext))
                self.textLb.adjustSize()

                try:
                    if imghdr.what(imagePath) is "jpg" or imghdr.what(imagePath) is "png" or imghdr.what(imagePath) is "jpeg" or imghdr.what(imagePath) is "gif":
                        imagePixmap = QPixmap(imagePath)
                        image = ImageSet()
                        image.pixmap = imagePixmap
                        image.path = imagePath
                        image.name = files_ext

                        #self.nameLb.setText(image.name)
                        #self.nameLb.adjustSize()

                        self.imageFolder.append(image)
                    elif files_ext.endswith(".txt"):
                        imagePath = dir_ + '/' + files_ext
                        f = open(imagePath, 'r')

                        points = f.readlines()

                        name = files_ext.replace(".txt", ".jpg")

                        self.imageFolderText[name] = points
                    else:
                        pass
                except IsADirectoryError: #if there is a directory inside folder
                    self.clickMethod4()
                    pass
                except PermissionError:#if there is permission error with the file
                    self.clickMethod5()
                    pass

            self.imageFolderIndex = 0

            if len(self.imageFolder) == 0: #if there is no file in imageFolder
                pass
            else:
                self.currentImage = self.imageFolder[self.imageFolderIndex]
                self.viewer.setPhoto(self.currentImage.pixmap)

                # if there is text file with points to the image
                if self.currentImage.name in self.imageFolderText:

                    numbers = []

                    for line in self.imageFolderText[self.currentImage.name]:
                        numbers.append(line.split())

                    for j in range(0, 2):
                        for i in range(0, 68):
                            numbers[i][j] = float(numbers[i][j])

                    self.drawPoints(numbers)


    def uploadTeButClicked(self):

        if not self.viewer.hasPhoto():
            self.clickMethod3()
        else:
            fNamePath = QFileDialog.getOpenFileName(self, "Open text", "/home/", "Text Files (*.txt)")

            # get coordinates from text files
            textPath = fNamePath[0]
            filepath_full = os.path.splitext(textPath)[0] + '.txt'

            with open(filepath_full) as data:
                lines = data.readlines()

            numbers = []

            lineNum = 0

            for line in lines:
                numbers.append(line.split())
                lineNum += 1

            if lineNum is 68:

                for j in range(0, 2):
                    for i in range(0, 68):
                        numbers[i][j] = float(numbers[i][j])

                self.drawPoints(numbers)
            else:
                self.clickMethod2()

    def label_update(self):
        update = self.currentImage.path
        #self.textLb.setText(update)
        #self.textLb.setText("")

    def clickMethod(self):
        QMessageBox.about(self, "Warning", "Landmark is empty. Try detection again.")

    def clickMethod2(self):
        QMessageBox.about(self, "Error", " Check text file(*.txt). Some landmarks are missing.")

    def clickMethod3(self):
        QMessageBox.about(self, "Error", "No photo uploaded")

    def clickMethod4(self):
        QMessageBox.about(self, "Error", "There is folder file inside")

    def clickMethod5(self):
        QMessageBox.about(self, "Error", "Permission Error")

    def detectClButClicked(self):

        if not self.viewer.hasPhoto():
            self.clickMethod3()

        else:
            for landmarkPath in self.currentImage.landmarkPath: #remove landmarkpath in image
                self.viewer.scene().removeItem(landmarkPath)

            self.drawn = False

    def detectButClicked(self):
        if not self.viewer.hasPhoto():
            self.clickMethod3()
        elif self.radio1.isChecked():
            self.pytorch_detect()
        elif self.radio2.isChecked():
            self.dlib_detect()

    #adrain detector
    def pytorch_detect(self):
        #fa = face_alignment.FaceAlignment(face_alignment.LandmarksType._2D, device='cpu')

        if not self.viewer.highReso:
            input = io.imread(self.currentImage.path)
            #self.currentImage.point = self.torch_detector.get_landmarks(input)[-1]

            start_time = time.time()
            #self.currentImage.point = fa.get_landmarks(input)[-1]
            self.currentImage.point = self.torch_detector.get_landmarks(input)[-1]

            print("pytorch without init : ---%s seconds ---" %(time.time() - start_time))

        else:
            self.viewer.pixmap.toImage().save('../tempo.jpg')
            input = io.imread('../tempo.jpg')
            os.remove('../tempo.jpg')
            #self.currentImage.point = self.torch_detector.get_landmarks(input)[-1]

            start_time = time.time()

            #self.currentImage.point = fa.get_landmarks(input)[-1]
            self.currentImage.point = self.torch_detector.get_landmarks(input)[-1]

            print("pytorch without init : ---%s seconds ---" %(time.time() - start_time))

            xratio = self.viewer.realPixmap.width() / self.viewer.pixmap.width()
            yratio = self.viewer.realPixmap.height() / self.viewer.pixmap.height()

            newPoint = []
            for point in self.currentImage.point:
                newPoint.append(np.array([point[0] * xratio, point[1] * yratio]))
            self.currentImage.point = newPoint

        self.drawPoints(self.currentImage.point)

    #dlib dector
    def dlib_detect(self):
        input = cv2.imread(self.currentImage.path)
        gray = cv2.cvtColor(input, cv2.COLOR_BGR2GRAY)

        #detector = dlib.get_frontal_face_detector()
        #predictor = dlib.shape_predictor(
        #    "./shape_predictor_68_face_landmarks.dat"
        #)

        #dets = self.dlib_detector(gray, 1)

        start_time = time.time()

        dets = self.dlib_detector(gray, 1)

        #dets = detector(gray, 1)
        points_all = []
        for face in dets:
            shape = self.dlib_predictor(input, face)
            #shape = predictor(input, face)

            for point in shape.parts():
                points = [point.x, point.y]
                points_all.append(points)

        print("dlib without init : ---%s seconds ---" % (time.time() - start_time))

        self.currentImage.point = points_all
        self.drawPoints(self.currentImage.point)
    #menu bar
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
        pass

    #show which radio button was clicked
    def checkboxClicked(self):
        #show a message box
        QMessageBox.about(self, "Message", "You clicked " + self.sender().text())
    def videoSourceChanged(self):
        #show a message box
        QMessageBox.about(self, "Message", "You selected " + self.sender().currentText())
    def frameSliderChanged(self):
        #show a message box
        QMessageBox.about(self, "Message", "You selected " + str(self.sender().value()))

    def pre_not_labeled_btn_clicked(self):
        pass
    def next_not_labeled_btn_clicked(self):
        pass
    def pre_frame_btn_clicked(self):
        pass
    def next_frame_btn_clicked(self):
        pass
    def play_btn_clicked(self):
        self.timer.start()
    def pause_btn_clicked(self):
        self.timer.stop()
    def timer_timeout(self):
        pass



if __name__ == '__main__':
    app = QApplication(sys.argv)
    app.setStyleSheet(qdarkgraystyle.load_stylesheet())
    window = MainWindow()
    window.show()
    app.exec()