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
import signal
import sys


VERSION = "0.2h"
# pin 16 on header (bcm)
SENSOR_PIN = 23
# pin 12 on header
RELAIS_PIN = 18
PICAM_ROTATE = 270

## next todos
# - start thread at sensor trigger/rising edge
#   stop after configurable delay
#
# - trigger multiple images after motion detect
# - optional switch to livestream
# - fhem notify/trigger event (or mqtt?)
# - do same stuff with node.js ;)
# - face detect

logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)-8s %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        filename='pir.log')
console = logging.StreamHandler()
console.setLevel(logging.DEBUG)
logging.getLogger('').addHandler(console)


datestring = '%Y%m%d-%H%M%S'
imgdir = '/home/' + os.environ['USER'] + '/control/images/'


#MAX_IMAGES = 60
MIN_ONTIME = 15
sense_start_time = 0

########## camera setup ##########
# camera = PiCamera()
# #camera.resolution = (768, 1024)
# camera.resolution = (1024, 768)
# camera.rotation = PICAM_ROTATE
# camera.brightness = 60



########## gpio setup ##########
GPIO.setmode(GPIO.BCM)
GPIO.setup(SENSOR_PIN, GPIO.IN)
GPIO.setup(RELAIS_PIN, GPIO.OUT)
GPIO.output(RELAIS_PIN, GPIO.LOW)


# astronomy.dat file currently generated by a cronjob (put in suitable url)
# @daily curl -s "https://query.yahooapis.com/v1/public/yql?q=select\%20astronomy\%20from\%20weather.forecast\%20where\%20woeid...blabla..." > astronomy.dat
def signal_term_handler(signal, frame):
    print 'got SIGTERM'
    GPIO.cleanup()
    sys.exit(0)


def its_dark():
    now = datetime.datetime.now().time().strftime("%H:%M")
    try:
        with open('/home/' + os.environ['USER'] + '/control/astronomy.dat') as data_file:    
            data = json.load(data_file)
    except IOError:
        print "error opening astronomy.dat file"
        return True

    try:
        sunrise = data['query']['results']['channel']['astronomy']['sunrise']
        sunset  = data['query']['results']['channel']['astronomy']['sunset']

        format = '%I:%M %p'
        sunrise_date = time.strptime(sunrise, format)
        sunset_date  = time.strptime(sunset, format)
        sr = datetime.datetime.strptime(sunrise, '%I:%M %p').time().strftime("%H:%M")
        ss = datetime.datetime.strptime(sunset,  '%I:%M %p').time().strftime("%H:%M")
    
        logging.debug("now: " + now)
        logging.debug("sr:  " + sr)
        logging.debug("ss:  " + ss)
    except Exception, e:
        logging.error("cannot query astronomy file (wrong json??)")
        return True

    if now < ss and now > sr:
        logging.debug("It's NOT dark (not turn on light)")
        return False

    return True

# the idea was to trigger this from some timer (thread.Timer())
# 
def light_off():
    global sense_start_time
    timestamp = datetime.datetime.now().strftime(datestring)
    duration = time.time() - sense_start_time
    logging.info('Light OFF, ' + timestamp  + ' dauer: ' + str(duration) + 's')
    GPIO.output(RELAIS_PIN, GPIO.LOW)
    # if GPIO.input(SENSOR_PIN):
    #     logging.info('sensor output still high, not turning off!')
    # else:
    #     GPIO.output(RELAIS_PIN, GPIO.LOW)




def callback_pir(channel):
    global sense_start_time
    timestamp = datetime.datetime.now().strftime(datestring)

    if GPIO.input(SENSOR_PIN):
        camera = PiCamera()
        camera.resolution = (1024, 768)
        camera.rotation = PICAM_ROTATE
        camera.brightness = 60

        sense_start_time = time.time()
        image_name = imgdir + "image_" + timestamp + ".jpg"
        logging.info('Es gab eine Bewegung! ' + timestamp  +' Bild:' + image_name)
        #th_light_off = threading.Timer(35.0, light_off)
        #th_light_off.start()
        # turn on lamp if it's dark ...
        if its_dark():
            GPIO.output(RELAIS_PIN, GPIO.HIGH)
        time.sleep(2)
        #camera.start_preview()
        logging.debug("capture image...")
        camera.capture(image_name)
        if scp_images:
            time.sleep(2)
            os.system('scp "%s" "%s"' % (image_name, os.environ['PIR_SCPHOST']))
        camera.close()

    else:
        duration = time.time() - sense_start_time
        logging.info('Stillstand, ' + timestamp  + ' dauer: ' + str(duration) + 's')
        #if duration < MIN_ONTIME:
        GPIO.output(RELAIS_PIN, GPIO.LOW)
        #camera.stop_preview()


signal.signal(signal.SIGTERM, signal_term_handler)


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

