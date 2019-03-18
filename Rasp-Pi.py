from picamera.array import PiRGBArray
from picamera import PiCamera
import pyzbar.pyzbar as pyzbar
import numpy as np
import os,sys,time
import cv2
import wiringpi
from firebase import firebase
import firebase_admin
from firebase_admin import credentials
#initialize the firebase instance
cred = credentials.Certificate("test-7d663-firebase-adminsdk-p5gjr-631c2015b7.json")
default_app = firebase_admin.initialize_app(cred)
firebase = firebase.FirebaseApplication('https://test-7d663.firebaseio.com', None)

slideIdx = -1
totalTime = 0
timing = []
FLED1 = 2
FLED2 = 3
BUTTON = 0
BUZZER = 1
LED_R = 4
LED_G = 5
LED_B = 6
# helper function to initialize pins
def initializePins():
  wiringpi.wiringPiSetup()
  wiringpi.pinMode(BUTTON, 0)
  wiringpi.pinMode(BUZZER, 1)
  wiringpi.pinMode(FLED1, 1)
  wiringpi.pinMode(FLED2, 1)
  wiringpi.pinMode(LED_R, 1)
  wiringpi.pinMode(LED_G, 1)
  wiringpi.pinMode(LED_B, 1)
  wiringpi.digitalWrite(LED_R, 1)
  wiringpi.digitalWrite(LED_G, 0)
  wiringpi.digitalWrite(LED_B, 0)
  wiringpi.digitalWrite(BUZZER, 0)
  wiringpi.digitalWrite(FLED1, 0)
  wiringpi.digitalWrite(FLED2, 0)
# helper function to turn the lights and buzzer off after the end
def endPins():
  wiringpi.digitalWrite(LED_R, 0)
  wiringpi.digitalWrite(LED_G, 0)
  wiringpi.digitalWrite(LED_B, 0)
  wiringpi.digitalWrite(BUZZER, 0)
  wiringpi.digitalWrite(FLED1, 0)
  wiringpi.digitalWrite(FLED2, 0)
# helper function to get timing infos from the firebase database
def getTimings():
  global timing
  global totalTime

  timing = []
  totalTime = 0
  result = firebase.get('/timing/timing', None)
  timings = [float(i) for i in result.split()]
  totalTime = timings[0]
  timing = timings[1:]
  print(timings)
    
# helper function to send next command to firebase
def nextSlide():
  global slideIdx
  if slideIdx < len(timing)-1:
    slideIdx = slideIdx+1
  cmd = "next "+str(time.time())
  firebase.put('command','command',cmd)
  print("nextSlide: "+str(slideIdx))
  return

# helper function to send prev command to firebase
def prevSlide():
  global slideIdx
  if slideIdx > 0:
    slideIdx = slideIdx-1
  cmd = "prev "+str(time.time())
  firebase.put('command','command',cmd)
  print("prevSlide: "+str(slideIdx))
  return

# helper function to send zoom command to firebase
def zoom(zoom_point):
  x = int(zoom_point[0]/width * 2667)
  y = int(zoom_point[1]/height * 1500)
  cmd = "zoom "+str(x)+" "+str(y)+" "+str(time.time())
  firebase.put('command','command',cmd)
  print("zoom")
  return

# helper function to send draw command to firebase
def drawRect(max_x, max_y, min_x, min_y):
  max_x = int(max_x/width * 2667)
  min_x = int(min_x/width * 2667)
  max_y = int(max_y/height * 1500)
  min_y = int(min_y/height * 1500)
  cmd = "draw "+str(max_x)+" "+str(max_y)+" "+str(min_x)+" "+str(min_y)+" "+str(time.time())
  firebase.put('command','command',cmd)
  print("drawRect")
  return

# helper function to generate a timing frame
def getTimingFrame(elapsed_time, slide_time):
  total_min = int(abs(totalTime - elapsed_time))//60
  total_sec = int(abs(totalTime - elapsed_time))%60
  slide_min = int(abs(slide_time))//60
  slide_sec = int(abs(slide_time))%60
  total_str = str(total_min) + " min " + str(total_sec) + " sec"
  slide_str = str(slide_min) + " min " + str(slide_sec) + " sec"
  total_title = "Total "
  slide_title = "Slide "
  if totalTime - elapsed_time < 0:
    total_title+="Over:"
    wiringpi.digitalWrite(FLED1, 1)
  else: 
    total_title+="Remaining:"
    wiringpi.digitalWrite(FLED1, 0)

  if slide_time < 0:
    slide_title+="Over:"
    wiringpi.digitalWrite(FLED2, 1)
  else:
    slide_title+="Remaining:"
    wiringpi.digitalWrite(FLED2, 0)
  image = np.ones((int(height/9*12),width,3), np.uint8)*255
  font = cv2.FONT_HERSHEY_SIMPLEX
  cv2.putText(image, total_title, (10,100), font, 2, (0,0,0),6,cv2.LINE_AA)
  cv2.putText(image, total_str, (10,200), font, 2, (0,0,0),6,cv2.LINE_AA)
  cv2.putText(image, slide_title, (10,300), font, 2, (0,0,0),6,cv2.LINE_AA)
  cv2.putText(image, slide_str, (10,400), font, 2, (0,0,0),6,cv2.LINE_AA)
  return image

getTimings()
initializePins()

# initialize the camera
fps=30
block_size = 40
height = 9*block_size 
width = 16*block_size 
camera = PiCamera()
camera.resolution = (1280, 720)
# In our case, the camera is flipped
camera.hflip = True
camera.vflip = True
camera.framerate = fps
rawCapture = PiRGBArray(camera, size=(1280, 720))
# allow the camera to warmup
time.sleep(0.5)

# Save the transformation matrix
transformMatrix = []
cv2.namedWindow('frame', cv2.WND_PROP_FULLSCREEN)
cv2.setWindowProperty('frame', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
# Use the qrcodes' locations to calculate the transformation matrix 
def computeTransformMatrix(decodedObjects):
  pts = [(0,0),(0,0),(0,0),(0,0)]
  #not all QR-codes are found
  if len(decodedObjects) < 4:
    return []
  for decodedObject in decodedObjects: 
    points = decodedObject.polygon
 
    # If the points do not form a quad, find convex hull
    if len(points) > 4 : 
      hull = cv2.convexHull(np.array([point for point in points], dtype=np.float32))
      hull = list(map(tuple, np.squeeze(hull)))
    else : 
      hull = points
    # Sort the hull
    hull.sort(key=lambda tup: tup[0])
    # Find the points of QRcodes to extract the screen
    if(int(decodedObject.data) == 1):
      if hull[0][1] > hull[1][1]:
        pts[0] = hull[1]
      else:
        pts[0] = hull[0]
    elif(int(decodedObject.data) == 2):
      if hull[2][1] > hull[3][1]:
        pts[1] = hull[3]
      else:
        pts[1] = hull[2]
    elif(int(decodedObject.data) == 3):
      if hull[2][1] > hull[3][1]:
        pts[2] = hull[2]
      else:
        pts[2] = hull[3]
    else:
      if hull[0][1] > hull[1][1]:
        pts[3] = hull[0]
      else:
        pts[3] = hull[1]
  # Calculate the transform matrxi that is used to extract the screen frame.
  pts1 = np.float32([pts[0],pts[1],pts[3],pts[2]])
  pts2 = np.float32([[0,0],[width,0],[0,height],[width,height]])
  transformMatrix=cv2.getPerspectiveTransform(pts1,pts2)
  return transformMatrix

# Function to determine if any button is clicked
def computeCommand (points):
  nextslide = False
  prevslide = False
  changemode = False
  n_c = 0
  p_c = 0
  c_c = 0
  for pt in points:
    if pt[0] < block_size*2:
      if pt[1] < 3*block_size:
        c_c += 1
      elif pt[1] < 3*block_size*2:
        p_c += 1
      else:
        n_c += 1
  # Check which one is most clicked.
  if n_c > p_c and n_c > c_c and n_c > len(points)/2:
    nextslide = True
  if p_c > n_c and p_c > c_c and p_c > len(points)/2:
    prevslide = True
  if c_c > p_c and c_c > n_c and c_c > len(points)/2:
    changemode = True
  return nextslide, prevslide, changemode

# HSV bounds to find the skin colors
lower = np.array([0, 48, 80], dtype = "uint8")
upper = np.array([20, 255, 255], dtype = "uint8")
points = []
tmp_points = []
camera_set_up = False
start_presenting = False
zoom_mode = True
prev_button = True
prev_time = time.time()
start_time = time.time()
# capture frames from the camera
for image in camera.capture_continuous(rawCapture, format="bgr", use_video_port=True):
  frame0 = image.array
  button = wiringpi.digitalRead(BUTTON)
  # Check if button is pushed
  if button == 0 and prev_button and not start_presenting:
    camera_set_up = True
  elif button == 0 and prev_button:
    endPins()
    break
  
  if button == 0:
    prev_button = False
  else:
    prev_button = True
  
  key = cv2.waitKey(1) & 0xFF
  if key == ord('q'):
    endPins()
    break
  # Check the QR-code and update the transform matrix
  if not start_presenting :
    frame1 = cv2.cvtColor(frame0,cv2.COLOR_BGR2GRAY)
    qrcodes = pyzbar.decode(frame1)
    transformMatrix = computeTransformMatrix(qrcodes)
    if len(transformMatrix) == 0: 
      # Not all the qr-codes are found
      wiringpi.digitalWrite(BUZZER, 1)
      frame0 = cv2.resize(frame0, (width, height))
      camera_set_up = False
    elif camera_set_up == True: 
      # The button is pushed, perform the last transform matrix calculation
      # Go to presenting state if we find the transform matrix in this image
      wiringpi.digitalWrite(BUZZER, 0)
      start_presenting = True
      nextSlide()
      prev_time = time.time()
      start_time = prev_time
      rawCapture.truncate(0)
      continue
    else:
      # Show the screen part. Let user check its sanity
      wiringpi.digitalWrite(BUZZER, 0)
      frame0 = cv2.warpPerspective(frame0,transformMatrix,(width,height))
    cv2.imshow('frame',frame0)
    rawCapture.truncate(0)
    continue
  # Record and update the timings for the current slide and the total time.
  current_time = time.time()
  elapsed_time = current_time-start_time
  timing[slideIdx] -= (current_time-prev_time)
  prev_time = current_time
  # Find the color segement in the picture
  frame0 = cv2.warpPerspective(frame0,transformMatrix,(width,height))
  hsv = cv2.cvtColor(frame0, cv2.COLOR_BGR2HSV)
  skinMask = cv2.inRange(hsv, lower, upper)
  kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
  skinMask = cv2.erode(skinMask, kernel, iterations = 1)
  skinMask = cv2.dilate(skinMask, kernel, iterations = 1)
  skinMask = cv2.GaussianBlur(skinMask, (3, 3), 0)
  skin = cv2.bitwise_and(frame0, frame0, mask = skinMask)
  # Find all the contours
  contours,_ = cv2.findContours(skinMask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
  
  extRight = [0,0]
  # Find the right most point in all the contours
  for c in contours:
    if tuple(c[c[:, :, 0].argmax()][0])[0] > extRight[0]:
      extRight = tuple(c[c[:, :, 0].argmax()][0])

  # Check if we find the rightmost point
  if extRight[0] != 0 and extRight[1] != 0:
    cv2.circle(frame0,extRight,2,(255,0,0),2)
    tmp_points.append(extRight)
  # Check if any button is pressed
  elif len(tmp_points)!=0:
    points=tmp_points
    tmp_points=[]
    nextslide, prevslide, changemode = computeCommand(points)
    if nextslide:
      nextSlide()
      points=[]
    if prevslide:
      prevSlide()
      points=[]
    if changemode:
      zoom_mode = not zoom_mode
      if zoom_mode:
        wiringpi.digitalWrite(LED_R, 1)
        wiringpi.digitalWrite(LED_G, 0)
      else:
        wiringpi.digitalWrite(LED_R, 0)
        wiringpi.digitalWrite(LED_G, 1)
      print ("changemode")
      points=[]
  # Send the draw command or the zoom command
  if len(points) > 6:
    if not zoom_mode:
      xx, yy = zip(*(points[2:-2]))
      min_x = min(xx); min_y = min(yy); max_x = max(xx); max_y = max(yy)
      drawRect(max_x, max_y, min_x, min_y)
    else:
      zoom_point=(0,0)
      for pt in points:
        if pt[0] > zoom_point[0]:
          zoom_point = pt
      zoom(zoom_point)
    points=[]
  # Generate a timing frame for the LCD to display
  timingFrame=getTimingFrame(elapsed_time,timing[slideIdx])
  cv2.imshow("frame", timingFrame)
  # clear the stream in preparation for the next frame
  rawCapture.truncate(0)
  if key == ord("q"):
    endPins()
    break