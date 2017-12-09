from threading import Thread
from collections import deque
import redisqueue as db
import time
import numpy
import cv2

class VideoCamera(object):
    def __init__(self):
        
        # queue for dynamic background segmentation
        self.q =  deque( maxlen=20 )

        # redis queue for file processing
        self.redis = db.ConnectToRedis()

        # to prevent check for motion while recording
        self.isRecording = False

        # keeping first frame seperate to detect end of motion
        self.recordingStartFrame = None

        # due to the time it takes the camera to settle down. 
        # A false motion is detected, thus we throw away the first motion detection call
        self.firstSkipped = False

        # Get video stream
        self.stream = cv2.VideoCapture(0)
        # self.stream.set(3,1280)
        # self.stream.set(4,768)

        # Grab a frame
        (self.grabbed, self.frame) = self.stream.read()

        # TODO :: Need to add checks for frame grab errors

        # initialize the variable used to indicate if the thread should
        # be stopped
        self.stopped = False
    
    def __del__(self):
        self.video.release()

    def start(self):
        # start the thread to read frames from the video stream
        t = Thread(target=self.update, args=())
        t.daemon = True
        t.start()

        # start the thread to detect motion using queued frames
        t2 = Thread(target=self.check_motion, args=())
        t2.daemon = True
        t2.start()

        return self

    def motion_score_calc(self, frame_1, frame_2):
        # Background subtraction algorithm
        frame_1 = cv2.cvtColor(frame_1, cv2.COLOR_BGR2GRAY)
        frame_1 = cv2.GaussianBlur(frame_1, (21, 21), 0)

        frame_2 = cv2.cvtColor(frame_2, cv2.COLOR_BGR2GRAY)
        frame_2 = cv2.GaussianBlur(frame_2, (21, 21), 0)

        # compute the absolute difference between the current frame and
        # first frame
        frameDelta = cv2.absdiff(frame_1, frame_2)
        thresh = cv2.threshold(frameDelta, 25, 255, cv2.THRESH_BINARY)[1]

        # dilate the thresholded image to fill in holes, then find contours
        # on thresholded image
        thresh = cv2.dilate(thresh, None, iterations=2)
        (_, cnts, _) = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if len(cnts)>0:
            return True
        else:
            return False

    def check_motion(self):
        # need to put in infinite loop since this runs on a thread
        while True:
            # do not check for motion if its being recorded
            if self.isRecording is False:
                # get current queue size
                list_len = (len(list(self.q))-1)
                # do something only if size > 0
                if list_len>0:
                    # need to cactch exceptions in case queue gets empty.
                    # This should ideally never occue
                    try:
                        # set the first frame to the mid of queue to give time for camera to init if requried
                        self.recordingStartFrame = self.q[int(list_len/2)]
                        # only if we have sufficient frames in queue start detection
                        if( list_len>10 ):
                            # check for motion
                            if self.motion_score_calc(self.recordingStartFrame, self.q[list_len]):
                                # if this is the first instance of motion detected it might be a 
                                # false positive. So we let a few frames be skipped
                                if self.firstSkipped is False:
                                    self.firstSkipped = True
                                else:
                                    # set recording status to true
                                    self.isRecording = True

                                    # start recording motion
                                    self.save_motion()
                                    # saving motion is a blocking operation. Hence put on a seperate thread.
                                    # t = Thread(target=self.save_motion, args=())
                                    # t.daemon = True
                                    # t.start()
                            else:
                                # to decrease CPU thrashing / utilization
                                time.sleep(1)
                    except IndexError as err:
                        print('index error while checking for motion')
            else:
                # OBSOLETE: This was needed when save_motion was running on a separate thread.
                # get a good sleep while motion is being recorded                
                time.sleep(5)

    def get_file_name(self):
        # use Unix Epoch Time as file name
        return str(time.time())+'.avi'

    def check_motion_stop(self):
        # to check if motion has stopped
        try:
            # calc background subtraction between start frame and last frame of queue
            # res_1 = self.motion_score_calc(self.recordingStartFrame, self.q[len(list(self.q))-1])

            # calc background subtraction between mid frame and last frame of queue
            res_2 = self.motion_score_calc(self.q[int((len(list(self.q))-1)/2)], self.q[len(list(self.q))-1])
            
            # TODO :: Verify
            # if no motion seen in mid and last frame then stop
            if res_2 is False:
                return True
            else:
                return False

        except IndexError as err:
            return True

    def save_motion(self):

        # get file name
        filename = self.get_file_name()

        # ready file for write
        fourcc = cv2.VideoWriter_fourcc(*'XVID')
        fileOut = cv2.VideoWriter(filename, fourcc, 30, (640,480))
        # fileOut = cv2.VideoWriter(filename, fourcc, 30, (1024,768))

        # check if motion has stopped
        while self.check_motion_stop() is False:
            try:
                # By default save atleast 10 seconds of video
                # https://stackoverflow.com/questions/24374620/python-loop-to-run-for-certain-amount-of-seconds
                t_end = time.time() + 20
                while time.time() < t_end:
                    if (len(list(self.q))-1)>0:
                        fileOut.write(self.q.popleft())
            except IndexError as err:
                # No more frames to process. Stop recording. Maybe some error has occured
                self.isRecording = False
                fileOut.release()
                print("Abruptly stopped recording")

        # when motion has stopped
        db.add_to_unprocessed_queue(self.redis, filename)
        self.isRecording = False
        return

    def update(self):
        # wait for camera to initalize
        time.sleep(2)

        # keep looping infinitely until the thread is stopped
        while True:
            # if the thread indicator variable is set, stop the thread
            if self.stopped:
                return

            # otherwise, read the next frame from the stream
            (self.grabbed, self.frame) = self.stream.read()
            self.q.append(self.frame)
    
    def read(self):
        # return the frame most recently read
        ret, jpeg = cv2.imencode('.jpg', self.frame)
        return jpeg.tobytes()

    def stop(self):
        # indicate that the thread should be stopped
        self.stopped = True
