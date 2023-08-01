import io
import os
import cv2
import boto3
import numpy as np
import pandas as pd
from PIL import Image
import boto3 as boto3
import mysql.connector
from datetime import date
from base64 import b64encode
from datetime import datetime
# from IPython.display import display
from werkzeug.utils import secure_filename
from flask import Flask, flash, request, render_template, jsonify, redirect, Response
import multiprocessing


#Reading the cascadefile...
xml_data = cv2.CascadeClassifier('plate_number.xml')


#AWS OCR client config... 
textractclient = boto3.client("textract", aws_access_key_id="AKIA52BCQYJGTHX5HQFA", aws_secret_access_key="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", region_name="us-east-1")


# SQL database config...
connection = mysql.connector.connect(host='localhost', database='vehicle', user='root', password='')
cursor = connection.cursor()


# Defining Flask App
app = Flask(__name__)


# To get invoke the home page... 
@app.route('/')
def home():
    sql_fetch_blob_query = """SELECT COUNT(*) from logs where permission='Authorized'"""
    cursor.execute(sql_fetch_blob_query)
    total_auth_logs = cursor.fetchall()
    for row in total_auth_logs:
        auth_count=row[0]    
    sql_fetch_blob_query = """SELECT COUNT(*) from logs where permission='Unauthorized'"""
    cursor.execute(sql_fetch_blob_query)
    total_unauth_logs = cursor.fetchall()
    for row in total_unauth_logs:
        unauth_count=row[0]
    return render_template('index.html', auth_count=auth_count, unauth_count=unauth_count)


@app.route('/addvehicle')
def addvehicle():
    return render_template('addvehicle.html')


# Upload to the AWS S3 Bucket...
@app.route('/sent', methods=['GET', 'POST'])
def sent():
    # Get user name...
    vnumber = request.form['vnumber']
    vtype = request.form['vtype']
    vowner = request.form['owner']
    if request.method == "POST":
        sql_insert_query = """INSERT INTO auth_vehicle(number, type, owner) VALUES (%s,%s,%s)"""
        insert_tuple = (vnumber, vtype, vowner)
        result = cursor.execute(sql_insert_query, insert_tuple)
        connection.commit() 
        return render_template('addvehicle.html')
    return render_template('addvehicle.html')


# Authorized persons management...
@app.route('/auth')
def auth():
        sql_fetch_blob_query = """SELECT * from logs where permission='Authorized'"""
        cursor.execute(sql_fetch_blob_query)
        record = cursor.fetchall()
        # Send to html file...        
        return render_template('auth.html',result=record)


# Unauthorized persons management...
@app.route('/unauth')
def unauth():
        sql_fetch_blob_query = """SELECT * from logs where permission='Unauthorized'"""
        cursor.execute(sql_fetch_blob_query)
        record = cursor.fetchall()
        # Send to html file...        
        return render_template('unauth.html',result=record)


@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


#TO get a live video stream... 
def generate_frames():
    #capture the live video footage...
    capture = cv2.VideoCapture('car5.mp4')
    # capture = cv2.VideoCapture(0)
    try:
        p1.start()
        # p1.terminate()
    except Exception:
        print()
    while True:
        bollean, input_image = capture.read()   
        # load to the buffer and send it to HTML...
        ret, buffer = cv2.imencode('.jpg', input_image)
        input_image = buffer.tobytes()
        yield (b'--frame\r\n'
            b'Content-Type: image/jpeg\r\n\r\n' + input_image + b'\r\n')


def numberdebug(vehicle_number):
    vehicle_number = vehicle_number.replace(" ", "")
    vehicle_number = vehicle_number.replace("  ", "")
    # print(vehicle_number)
    try:
        flag=0
        sql_fetch_blob_query = """SELECT * from auth_vehicle"""
        cursor.execute(sql_fetch_blob_query)
        total_logs = cursor.fetchall()
        for row in total_logs:
            if vehicle_number == row[1]:
                sql_insert_query = """INSERT INTO logs(number, type, owner, permission) VALUES (%s,%s,%s,%s)"""
                insert_tuple = (row[1], row[2], row[3],"Authorized")
                result = cursor.execute(sql_insert_query, insert_tuple)
                connection.commit()
                flag=1
                break
        if flag == 0:
            sql_insert_query = """INSERT INTO logs(number, type, owner, permission) VALUES (%s,%s,%s,%s)"""
            insert_tuple = (vehicle_number, "Unknown", "Unknown","unauthorized")
            result = cursor.execute(sql_insert_query, insert_tuple)
            connection.commit()        
    except mysql.connector.Error as e:
        print(e)


def getFrame(sec):
    # capture = cv2.VideoCapture(0)
    capture = cv2.VideoCapture('./car5.mp4')
    capture.set(cv2.CAP_PROP_POS_MSEC,sec*1000)
    hasFrames,input_image = capture.read()
    #Convert into colorless image...
    gray_image = cv2.cvtColor(input_image,cv2.COLOR_BGR2GRAY)
    #Detecting the numberplate points...
    detected_points = xml_data.detectMultiScale(gray_image,1.2)
    # print(detected_points)
    if detected_points is None:
        print("number plate not deducted...")
    else:
        #Applying points in image...
        for points in detected_points:
            (x,y,w,h) = points
            roi_gray = gray_image[y:y+h, x:x+w]
            roi_color = input_image[y:y+h, x:x+h]
            marked_image = cv2.rectangle(input_image,(x,y),(x+w,y+h),(0,255,0),3)
            #Crop the number plate image...
            crop_image = marked_image[y:y+h, x:x+w]
            #Convert image into binary...
            im_resize = cv2.resize(crop_image, (500, 500))
            is_success, im_buf_arr = cv2.imencode(".jpg", im_resize)
            binaryFile = im_buf_arr.tobytes()
            #get AWS textract response...
            response = textractclient.detect_document_text(Document={'Bytes': binaryFile})
            vehicle_number = ""
            for block in response['Blocks']:
                if block["BlockType"] == "LINE":
                    vehicle_number = vehicle_number+block["Text"]
            #Show the output...
            print("Deducted license plate number is: ",vehicle_number)
            numberdebug(vehicle_number)
            # cv2.imshow('output', crop_image)
            cv2.imwrite('output.jpg', crop_image)
            # cv2.waitKey(0)
    return hasFrames

def workprocess():
    sec = 0
    # frameRate = 1.54545455 #//it will capture image in each 0.5 second
    frameRate = 1
    count=1
    success = getFrame(sec)
    while success:
        count = count + 1
        sec = sec + frameRate
        sec = round(sec, 2)
        success = getFrame(sec)
    p1.terminate()


p1 = multiprocessing.Process(target=workprocess)


# Our main function which runs the Flask App
if __name__ == '__main__':
    app.run(debug=True)