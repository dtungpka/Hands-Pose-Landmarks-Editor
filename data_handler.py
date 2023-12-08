import os
import numpy as np
import json
import cv2
import datetime as dt
import time
#from PyQt5.QtGui import *

class DataHandler:
    '''
    A class to handle the data
    '''
    def __init__(self, data_path):
        '''
        data_path: path to the data folder
        '''
        self.data_path = data_path
        self.current_video = None
        self.current_video_data = None
        self.current_frame = 0
        self.total_frame = 0
        #check if a metadata.json file exists
        if os.path.isfile(os.path.join(data_path, 'metadata.json')):
            with open(os.path.join(data_path, 'metadata.json'), 'r',encoding='utf-8') as f:
                self.metadata = json.load(f)
        else:
            self.metadata = None
            raise Exception('No metadata.json file found in the data path')
        self.methods = []
        for video in self.metadata:
            for method in self.metadata[video]['methods']:
                if method not in self.methods:
                    self.methods.append(method)
    def get_video_list(self):
        '''
        return a list of keys in the metadata
        '''
        return list(self.metadata.keys())
    def get_method_list(self):
        '''return a list of methods in the metadata'''
        return self.methods
    def set_video(self, video_name):
        '''
        set the current video
        '''
        #if _current_video is not None, release it
        if hasattr(self, '_current_video'):
            self._current_video.release()
        assert video_name in self.metadata, 'Video name not in the metadata'
        assert os.path.isfile(os.path.join(self.data_path, self.metadata[video_name]['local_path'])), 'Video file not found'

        self.current_video = video_name
        self.current_video_data = self.metadata[video_name]

        assert len(self.get_current_method_list()) == len([a for a in self.metadata[video_name]['methods'] if os.path.isfile(os.path.join(self.data_path, self.metadata[video_name]['methods'][a]))]), 'Some method files not found'

        self.skeleton_data = {}

        #TODO: load in UI, create a set_skeleton_data method for later use (or could change to pickle file)
        for method in self.get_current_method_list():
            with open(os.path.join(self.data_path, self.metadata[video_name]['methods'][method]), 'r',encoding='utf-8') as f:
                self.skeleton_data[method] = json.load(f)

        self.current_frame = 0
        #set the total frame by reading the video using cv2
        video_path = os.path.join(self.data_path, self.metadata[video_name]['local_path'])
        self._current_video = cv2.VideoCapture(video_path)
        self.total_frame = int(self._current_video.get(cv2.CAP_PROP_FRAME_COUNT))
        self._width = int(self._current_video.get(cv2.CAP_PROP_FRAME_WIDTH))
        self._height = int(self._current_video.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self._fps = self._current_video.get(cv2.CAP_PROP_FPS)
        
        return self.current_video, self.current_video_data
    def get_current_method_list(self):
        '''
        return a list of methods for the current video
        '''
        assert self.current_video_data is not None, 'No current video is set'
        return list(self.current_video_data['methods'].keys())
    def get_duration(self):
        '''
        return the duration of the current video, format: HH:MM:SS, rounded to the nearest .01
        '''
        assert self.current_video_data is not None, 'No current video is set'
        duration = self.total_frame/self._fps
        s = str(dt.timedelta(seconds=duration))
        if '.' in s:
            _s = s.split('.')
            return _s[0]+'.'+_s[1][:2]
        else:
            return s
    def set_current_frame(self, frame_number):
        '''
        set the current frame number
        '''
        assert self.current_video_data is not None, 'No current video is set'
        assert frame_number < self.total_frame and frame_number >= 0, f'Frame number out of range: {frame_number}'
        self.current_frame = frame_number
    def get_frame(self):
        '''
        return the frame number of the current video
        '''
        assert self.current_video_data is not None, 'No current video is set'
        assert self.current_frame < self.total_frame, 'Frame number out of range'
        self._current_video.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame)
        success, image = self._current_video.read()
        if not success:
            raise Exception('Error reading frame')
        return image
    def get_current_duration(self):
        '''
        return the duration of the current video, format: HH:MM:SS, rounded to the nearest .01
        '''
        assert self.current_video_data is not None, 'No current video is set'
        duration = self.current_frame/self._fps
        s = str(dt.timedelta(seconds=duration))
        if '.' in s:
            _s = s.split('.')
            return _s[0]+'.'+_s[1][:2]
        else:
            return s
    def get_current_frame_skeleton(self, method):
        '''
        return the skeleton data for the current frame and the current method
        '''
        assert self.current_video_data is not None, 'No current video is set'
        assert method in self.get_current_method_list(), 'Method not found'
        pose = self.skeleton_data[method]['pose'][str(self.current_frame)]
        hand = self.skeleton_data[method]['hands'][str(self.current_frame)]
        return pose, hand
    def get_alt_name(self):
        '''
        return the alt name of all videos if exists
        '''
        #as a dict, key is the video name, value is the alt name
        alt_name = {}
        for video in self.metadata:
            if 'alt_name' in self.metadata[video]:
                alt_name[video] = self.metadata[video]['alt_name']
            else:
                alt_name[video] = video
        return alt_name


if __name__ == '__main__':
    d =DataHandler('D:\\2023-2024\\Research\\Skeleton-ed\\')
    d.set_video('src15')
    #test
    print(d.get_video_list())
    print(d.get_method_list())
    print(d.get_current_method_list())
    print(d.get_duration())
    print(d.current_video)

    #test get_frame, increase the frame number by 100 each time, monitor the time taken to get the frame
    start = time.time()
    for i in range(10):
        d.get_frame()
        d.current_frame += 100
        print(d.get_current_duration())
    end = time.time()
    print(f'Time taken: {end-start}')

    #play the video using cv2
    d.set_current_frame(0)
    for i in range(d.total_frame):
        image = d.get_frame()
        cv2.imshow('image', image)
        cv2.waitKey(2)
        d.current_frame += 1
        print(f'\r{d.get_current_duration()}', end='')

