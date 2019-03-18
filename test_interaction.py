from __future__ import print_function
import numpy as np
import cv2
from pdf2image import convert_from_path
from firebase import firebase
import firebase_admin
from firebase_admin import credentials

def convert_pdf_to_jpg():
	calibration_page = convert_from_path('calibration_page.pdf')
	calibration_page[0].save('jpg/calibration_page.jpg', 'JPEG')
	pages = convert_from_path('test_slide.pdf')
	i = 1
	for page in pages:
		string = str(i)
		page.save('jpg/out'+string+'.jpg', 'JPEG')
		i+=1
	return (i-1)

def calibration_page(qr,blank_page,qr_coordinates):
	cv2.rectangle(blank_page, (0,0), (2667,1500), (0,0,0), -1)
	for i in range(4):
		y_offset = qr_coordinates[i,0]
		x_offset = qr_coordinates[i,1]
		resized_qr = cv2.resize(qr[i], (600, 600),interpolation = cv2.INTER_AREA)
		blank_page[y_offset:y_offset+resized_qr.shape[0], x_offset:x_offset+resized_qr.shape[1]] = resized_qr 
	cv2.imshow("window", blank_page)

def generate_page(page_num,blank_page,buttons,button_coordinates):
	string = str(page_num)
	slide = cv2.imread("jpg/out"+string+".jpg")
	y_offset = 0
	x_offset = 333
	blank_page[y_offset:y_offset+slide.shape[0], x_offset:x_offset+slide.shape[1]] = slide
	#experiment code for measuring zoom and draw uncertainties
	#cv2.rectangle(blank_page, (1100, 400), (1600, 900), (0,255,0), -1)
	#cv2.circle(blank_page, (1333,750), 30, (255,0,0), -1)
	for i in range(3):
		y_offset = button_coordinates[i,0]
		x_offset = button_coordinates[i,1]
		resized_button = cv2.resize(buttons[i], (333, 500),interpolation = cv2.INTER_AREA)
		blank_page[y_offset:y_offset+resized_button.shape[0], x_offset:x_offset+resized_button.shape[1]] = resized_button
	cv2.imshow("window", blank_page)
	return blank_page

def magnify(page_name,clone,location):
	cropped_image = clone[location[1]-200:location[1], location[0]:location[0]+200]
	magnified_image = cv2.resize(cropped_image, (500, 500),interpolation = cv2.INTER_AREA)
	y_offset = 0
	x_offset = 2100
	clone[y_offset:y_offset+magnified_image.shape[0], x_offset:x_offset+magnified_image.shape[1]] = magnified_image
	cv2.imshow(window_name, clone)
	cv2.waitKey(10)

def click(event, x, y, flags, param):
	# grab references to the global variables
	global location
	if event == cv2.EVENT_LBUTTONDBLCLK:
		location = [x, y]

# Main 
if __name__ == '__main__':
	#connect to firebase database
	#the json file stores credentials, keep it private!
	cred = credentials.Certificate("test-7d663-firebase-adminsdk-p5gjr-631c2015b7.json")
	default_app = firebase_admin.initialize_app(cred)
	firebase = firebase.FirebaseApplication('https://test-7d663.firebaseio.com', None)
	#read slide timings from text file and upload to firebase
	#for timings follow the format in timings.txt, where first number is the total time, and the following for each slide
	f=open("timing.txt", "r")
	if f.mode == 'r':
		contents =f.read()
		firebase.put('timing','timing',contents)
	#convert slides to jpg
	num_slides = convert_pdf_to_jpg()
	#initialize boundary of tools bar, master frame
	qr = []
	qr1 = cv2.imread("qr_code/1.png")
	qr2 = cv2.imread("qr_code/2.png")
	qr3 = cv2.imread("qr_code/3.png")
	qr4 = cv2.imread("qr_code/4.png")
	qr.append(qr1)
	qr.append(qr2)
	qr.append(qr3)
	qr.append(qr4)

	#put buttons on slide
	buttons = []
	button_mode = cv2.imread("buttons/mode.png")
	button_up = cv2.imread("buttons/up.png")
	button_down = cv2.imread("buttons/down.png")
	buttons.append(button_mode)
	buttons.append(button_up)
	buttons.append(button_down)

	cali_img = cv2.imread("jpg/calibration_page.jpg")
	blank_page = cali_img.copy()
	qr_coordinates = np.array([[0, 0], [0, 2066],[900, 2066],[900, 0]], np.int32)
	button_coordinates = np.array([[0, 0], [500, 0],[1000, 0]], np.int32)
	#generate calibration page
	cv2.namedWindow("window", cv2.WND_PROP_FULLSCREEN)
	cv2.setWindowProperty("window",cv2.WND_PROP_FULLSCREEN,cv2.WINDOW_FULLSCREEN)
	calibration_page(qr,blank_page,qr_coordinates)
	page_num = 0
	window_name = "window"
	location = [100,200]   #location for zoom, lower left corner
	corners = np.array([[0, 0], [0, 0]])
	current_time = 0

	#initialize command with 0
	firebase.put('command','command','0')

	while(True):
		list = firebase.get('/command/command', None)
		k = list.split()[0]
		
		if (cv2.waitKey(10) == 27):         # wait for ESC key to exit
			cv2.destroyAllWindows()
			break

		if(float(list.split()[-1]) != current_time):
			current_time = float(list.split()[-1])
			if (k == 'next'):    # next page
				page_num += 1
				if (page_num > num_slides):
					page_num = num_slides
				blank_copy = cali_img.copy()
				blank_page = generate_page(page_num,blank_copy,buttons,button_coordinates)
			elif (k == 'prev'):     # previous page
				page_num -= 1
				if (page_num < 1):
					page_num = 1
				blank_copy = cali_img.copy()
				blank_page = generate_page(page_num,blank_copy,buttons,button_coordinates)
			elif (k == 'zoom'):    # magnify
				#cv2.setMouseCallback(window_name,click)
				while(True):
						coord = firebase.get('/command/command', None)
						if (coord.split()[0] in ['next','prev','draw']):
							break
						x = int(coord.split()[1])
						y = int(coord.split()[2])
						if(x!=location[0]):
							print([x,y])
						location = [x,y]
						#print(location)
						clone = blank_page.copy()
						magnify(window_name,clone,location)

			elif (k == 'draw'):    # highlight
				while(True):
					coord = firebase.get('/command/command', None)
					if (coord.split()[0] in ['next','prev','zoom']):
						cv2.imwrite('draw_test/draw_test_1.jpg', blank_page)
						break
					x1 = int(coord.split()[1])
					y1 = int(coord.split()[2])
					x2 = int(coord.split()[3])
					y2 = int(coord.split()[4])
					if(x1!=corners[0,1]):
						print(np.array([[y1, x1], [y2, x2]]))
					corners = np.array([[y1, x1], [y2, x2]])
					#print(corners)
					cv2.rectangle(blank_page, (corners[0,1], corners[0,0]), (corners[1,1], corners[1,0]), (255,0,0), 5)
					cv2.imshow(window_name, blank_page)
					cv2.waitKey(10)
				
