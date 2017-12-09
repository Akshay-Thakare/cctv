from flask import Flask, render_template, Response
from camera import VideoCamera
from fileprocessor import FileProcessor
import atexit
import time
import logging

app = Flask(__name__)
vs = VideoCamera().start()
fp = FileProcessor().start()

@app.route('/')
def index():
    return render_template('index.html')

def gen(camera):
    while True:
        frame = vs.read()
        time.sleep(.2)
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')

@app.route('/video_feed')
def video_feed():
    return Response(gen(VideoCamera()),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
	logging.basicConfig(format='%(asctime)s %(message)s', filename='cctv.log', level=logging.INFO)
	app.run(host='0.0.0.0', port=8081)


# atexit.register(vs.stop())
