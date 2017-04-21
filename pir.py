#!/usr/bin/env python

import os
import re
from io import BytesIO
import RPi.GPIO as GPIO
import time, datetime
#import picamera
from picamera import PiCamera
import logging
import json
#import ftplib
#import netrc
import threading


VERSION = "0.2e"


## next todos
# - start thread at sensor trigger/rising edge
#   stop after configurable delay
#
# - trigger multiple images after motion detect
# - optional switch to livestream
# - fhem notify/trigger event (or mqtt?)
# - do same stuff with node.js ;)


logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)-8s %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        filename='pir.log')
console = logging.StreamHandler()
console.setLevel(logging.DEBUG)
logging.getLogger('').addHandler(console)


datestring = '%Y%m%d-%H%M%S'
imgdir = '/home/pi/control/images/'

camera = PiCamera()
camera.resolution = (768, 1024)
camera.rotation = 270


#MAX_IMAGES = 60
MIN_ONTIME = 15
start = 0

# pin 16 on header 
SENSOR_PIN = 23
 
GPIO.setmode(GPIO.BCM)
GPIO.setup(SENSOR_PIN, GPIO.IN)
GPIO.setup(18, GPIO.OUT)
GPIO.output(18, GPIO.LOW)


def its_dark():
    now = datetime.datetime.now().time().strftime("%H:%M")
    try:
        with open('astronomy.dat') as data_file:    
            data = json.load(data_file)
    except IOError:
        print "error opening file"
        return True

    sunrise = data['query']['results']['channel']['astronomy']['sunrise']
    sunset  = data['query']['results']['channel']['astronomy']['sunset']
    #logging.debug("sunrise: " + sunrise)
    #logging.debug("sunset:  " + sunset)

    format = '%I:%M %p'
    sunrise_date = time.strptime(sunrise, format)
    sunset_date  = time.strptime(sunset, format)
    sr = datetime.datetime.strptime(sunrise, '%I:%M %p').time().strftime("%H:%M")
    ss = datetime.datetime.strptime(sunset,  '%I:%M %p').time().strftime("%H:%M")
    
    logging.debug("now: " + now)
    logging.debug("sr:  " + sr)
    logging.debug("ss:  " + ss)

    if now < ss and now > sr:
        logging.debug("It's NOT dark (not turn on light)")
        return False

    return True


def light_off():
    global start
    timestamp = datetime.datetime.now().strftime(datestring)
    duration = time.time() - start
    logging.info('Light OFF, ' + timestamp  + ' dauer: ' + str(duration) + 's')
    GPIO.output(18, GPIO.LOW)
    # if GPIO.input(SENSOR_PIN):
    #     logging.info('sensor output still high, not turning off!')
    # else:
    #     GPIO.output(18, GPIO.LOW)




def callback_pir(channel):
    global start
    timestamp = datetime.datetime.now().strftime(datestring)

    if GPIO.input(SENSOR_PIN):
        start = time.time()
        image_name = imgdir + "image_" + timestamp + ".jpg"
        logging.info('Es gab eine Bewegung! ' + timestamp  +' Bild:' + image_name)
        #th_light_off = threading.Timer(35.0, light_off)
        #th_light_off.start()
        # turn on lamp if it's dark ...
        if its_dark():
            GPIO.output(18, GPIO.HIGH)
        time.sleep(2)
        #camera.start_preview()
        camera.capture(image_name)
        if scp_images:
            time.sleep(2)
            os.system('scp "%s" "%s"' % (image_name, os.environ['PIR_SCPHOST']))

    else:
        duration = time.time() - start
        logging.info('Stillstand, ' + timestamp  + ' dauer: ' + str(duration) + 's')
        #if duration < MIN_ONTIME:
        GPIO.output(18, GPIO.LOW)
        #camera.stop_preview()



try:
    logging.info("Hallo Tuer version: " + VERSION)

    if 'PIR_SCPHOST' in os.environ:
        logging.info("scp host: " + os.environ['PIR_SCPHOST'])
        scp_images = True
    else:
        print('no scphost defined')
        scp_images = False


    GPIO.add_event_detect(SENSOR_PIN , GPIO.BOTH, callback=callback_pir)
    while 1:
        time.sleep(100)
        #print "ping"



except KeyboardInterrupt:
    print "Beende..."
    GPIO.cleanup()

