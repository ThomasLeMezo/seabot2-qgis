import imaplib
import time
import os
import math
from os.path import expanduser

import email
from email.policy import default
from email.utils import parsedate_tz, parsedate

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
import base64

import time
import calendar

import shutil
import smtplib
import struct
import datetime
import subprocess
import yaml
import sqlite3
import sys
import re

import threading, queue
import logging
import socket

from PyQt5.QtCore import QDate, QTime, QDateTime, Qt, QLocale, QObject, pyqtSignal
from PyQt5.QtWidgets import QMessageBox, QFileDialog
from .database import *
from .mission import *

class ImapServer(QObject):
	socket.setdefaulttimeout(1)
	imap_signal = pyqtSignal()
	imap_signal_log = pyqtSignal(str)
	imap_signal_button_color = pyqtSignal(bool)
	imap_status_next_connection = pyqtSignal(int)
	imap_update_dt = 5 # in sec

	def __init__(self, send_mail_sleep, send_mail_parameters, send_mail_mission, imap_signal_stop_server, test_send_mission=None):
		super().__init__()
		self.serverIMAP = None
		self.mailbox = 'Inbox' # change function of imap server
		self.is_connected = False
		self.is_first_connection = True
		self.running = False
		self.imap_signal_log.emit("?")
		self.server_id = -1
		self.thread = None
		self.db = DataBaseConnection(init_table=True)
		self.locale = QLocale(QLocale.English, QLocale.UnitedStates)
		self.start_sync = None

		send_mail_sleep.connect(self.send_mail_sleep)
		send_mail_parameters.connect(self.send_mail_parameters)


		send_mail_mission.connect(self.send_mail_mission)

		imap_signal_stop_server.connect(self.stop_server)
		if(test_send_mission != None):
			test_send_mission.connect(self.test_mission_file)

	def __del__(self):
		# with self.lock:
		self.running = False
		if(threading.active_count()!=0 and self.thread!=None):
			self.thread.join()
		self.close_server()

	def send_mail_sleep(self, imei, duration):
		parser = IridiumMessageParser(DataBaseConnection(init_table=False))
		data, type = parser.serialize_cmd_sleep(duration)
		print(data)
		if parser.flag_msg_ok:
			self.send_mail(imei, data, type)
		return

	def send_mail_parameters(self, imei, enable_mission, enable_flash, enable_depth, enable_engine, period_message):
		parser = IridiumMessageParser(DataBaseConnection(init_table=False))
		data, type = parser.serialize_cmd_parameters(enable_mission, enable_flash, enable_depth, enable_engine, period_message)
		print(data)
		if parser.flag_msg_ok:
			self.send_mail(imei, data, type)
		return

	def test_mission_file(self, imei, mission, keep_old_mission):
		parser = IridiumMessageParser(DataBaseConnection(init_table=False))
		data, msg_type = parser.serialize_cmd_mission(mission, keep_old_mission)
		if data==None:
			return
		print(data)
		if(len(data)>270 or mission.get_nb_wp()>256):
			msgBox = QMessageBox()
			msgBox.setIcon(QMessageBox.Warning)
			msgBox.setText("Mission is too heavy "+str(len(data))+ "/270bytes " + str(mission.get_nb_wp())+"/256 wp")
			msgBox.setWindowTitle("Seabot")
			msgBox.setStandardButtons(QMessageBox.Ok)
			msgBox.exec()
			return
		debug_path = expanduser("~")+'/sbd_message.sbd'
		filename = QFileDialog.getSaveFileName(None,"Save file", debug_path,"SBD File (*.sbd)")
		if(filename[0]!=''):
			local_file_sbd = open(filename[0],'wb')
			local_file_sbd.write(data)
			local_file_sbd.close()

		db = DataBaseConnection(init_table=False)
		filename = imei + "_" + str(int(datetime.datetime.utcnow().timestamp())) + '.sbd'
		db.add_sbd_sent_to_icu(imei, filename, msg_type, data, datetime.datetime.utcnow().timestamp())

	def send_mail_mission(self, imei, mission, keep_old_mission):
		parser = IridiumMessageParser(DataBaseConnection(init_table=False))
		data, type = parser.serialize_cmd_mission(mission, keep_old_mission)
		if data==None:
			return
		print(data)

		# Check the length of the message
		if(len(data)>270 or mission.get_nb_wp()>256):
			msgBox = QMessageBox()
			msgBox.setIcon(QMessageBox.Warning)
			msgBox.setText("Mission is too heavy "+str(len(data))+ "/270bytes " + str(mission.get_nb_wp())+"/256 wp")
			msgBox.setWindowTitle("Seabot")
			msgBox.setStandardButtons(QMessageBox.Ok)
			msgBox.exec()
			return

		if parser.flag_msg_ok:
			self.send_mail(imei, data, type)
		return

	def send_mail(self, imei, data, msg_type):
		if(self.is_connected):
			db = DataBaseConnection(init_table=False)
			login_data = db.get_server_data(self.server_id)

			sbd_msg = MIMEBase("application", "octet-stream") # x-zip-compressed

			filename = imei + "_" + str(int(datetime.datetime.utcnow().timestamp())) + ".sbd"

			sbd_msg.set_payload(base64.b64encode(data))
			sbd_msg.add_header('Content-Disposition', 'attachment', filename=filename)
			sbd_msg.add_header('Content-Transfer-Encoding', 'base64')

			# encoders.encode_base64(sbd_msg)

			msg = MIMEMultipart('alternative')
			msg['Subject'] = imei
			msg['From'] = "<Seabot> <"+login_data["email"]+">"
			msg['To'] = login_data["iridium_server_mail"]
			msg.attach(sbd_msg)

			msgBox = QMessageBox()
			msgBox.setIcon(QMessageBox.Question)
			msgBox.setText("Are you sure you want to send the CMD "+str(msg_type))
			msgBox.setWindowTitle("Seabot")
			msgBox.setStandardButtons(QMessageBox.Cancel | QMessageBox.Ok)
			msgBox.setDefaultButton(QMessageBox.Cancel)
			ret = msgBox.exec()
			if(ret!=QMessageBox.Ok):
				return

			# Send message
			try:
				s = smtplib.SMTP(login_data["server_smtp_ip"], login_data["server_smtp_port"])
				s.ehlo()
				context = ssl.SSLContext(ssl.PROTOCOL_TLS)
				s.starttls(context=context)
				s.ehlo()
				s.login(login_data["email"],login_data["password"])
				s.sendmail(login_data["email"], login_data["iridium_server_mail"], msg.as_string())
				s.close()
			except socket.error as e:
				print(e, flush=True)
				return

			print("Message sent to ", imei)
			db.add_sbd_sent_to_icu(imei, filename, msg_type, data, datetime.datetime.utcnow().timestamp())

			msgBox = QMessageBox()
			msgBox.setText("The message was send to iridium server")
			msgBox.setWindowTitle("Seabot")
			msgBox.exec()
		else:
			print("Server Down")

	def start_server(self):
		# with self.lock:
		self.running = True
		self.thread = threading.Thread(target=self.update_imap, daemon=True)
		self.thread.start()

	def stop_server(self):
		print("STOP SERVER RECEIVED")
		# with self.lock:
		if(self.running == True):
			self.running = False
		self.close_server()
		if(self.thread != None):
			self.thread.join()

	def close_server(self):
		if self.is_connected == True:
			self.is_connected = False
			self.is_first_connection = True
			try:
				self.serverIMAP.close()
				self.serverIMAP.logout()
				self.imap_signal_log.emit("Disconnected")
				print("Server disconnected")
			except imaplib.IMAP4.error as err:
				print(err, flush=True)

	def update_imap(self):
		self.db = DataBaseConnection(init_table=False)
		time_counter = 0
		freq = 2 # Hz
		while self.running:
			if(not self.is_connected):
				self.imap_signal_button_color.emit(False)
				self.connect_imap()
			if(time_counter==0):
				if(self.is_connected and self.is_first_connection):
					self.update_first_connection()
				if(self.is_connected and not self.is_first_connection):
					self.update_recent()
				time_counter=freq*self.imap_update_dt
			time.sleep(1./freq)
			time_counter -= 1
			self.imap_status_next_connection.emit(math.ceil(time_counter/freq))
		self.imap_status_next_connection.emit(0)

	def set_server_id(self, server_id):
		self.server_id = server_id

	def connect_imap(self):
		print("Try connect")
		try:
			rsp = None
			# Retreive data from DB
			login_data = self.db.get_server_data(self.server_id)
			if(len(login_data)==0):
				raise Exception('wrong server_id ', self.server_id)
			print("Try Login")
			self.serverIMAP = imaplib.IMAP4_SSL(login_data["server_imap_ip"], login_data["server_imap_port"])
			rsp = self.serverIMAP.login(login_data["email"], login_data["password"])
			print(self.serverIMAP.list())
			if(rsp[1][0].decode()=="LOGIN completed." or re.search("Logged in", rsp[1][0].decode()).group(0)=="Logged in"):
				self.is_connected = True
				self.is_first_connection = True
				self.imap_signal_button_color.emit(True)
				rsp, nb_message_inbox = self.serverIMAP.select(mailbox=self.mailbox, readonly=False)
				print("select rsp = ", rsp, " nb_message = ", nb_message_inbox[0].decode())
				self.imap_signal_log.emit("Connected")
			else:
				raise Exception('Failed to select')

			return True

		except imaplib.IMAP4.error as err:
			print("Error imap ", err)
			self.imap_signal_log.emit("Error IMAP\n" + str(err))
			self.close_server()
			return False
		except sqlite3.Error as error:
			print("Error sqlite ", error)
			self.imap_signal_log.emit("Error SQLITE")
			self.close_server()
			return False
		except:
			print("Error ", sys.exc_info())
			self.imap_signal_log.emit("Error - No connection\n" + str(sys.exc_info()[1]))
			self.close_server()
			return False

	def process_msg(self, msgnums):
		if(msgnums[0] != None):
			k=1
			list_msg_num = msgnums[0].split()
			for num in list_msg_num:
				if(not self.download_msg(num.decode())):
					return False
				self.imap_signal_log.emit("Update " + str(k) + "/" + str(len(list_msg_num)) + " (" + str(num.decode()) + ")")
				k+=1
				if(k%10==0):
					self.imap_signal.emit()
			self.imap_signal.emit()
			return True

	def update_recent(self):
		self.imap_signal_log.emit("Update " + str(datetime.datetime.now().replace(microsecond=0)))
		try:
			t = datetime.datetime.now()
			rsp, msgnums = self.serverIMAP.recent()
			if(not self.process_msg(msgnums)):
				return False

			self.db.update_last_sync(self.server_id, t.replace(microsecond=0).isoformat()) # without microsecond
			return True
		except imaplib.IMAP4.error as err:
			self.close_server()
			print(err, flush=True)
			self.imap_signal_log.emit("Error imaplib")
			return False
		except:
			print("Error ", sys.exc_info())
			self.close_server()
			self.imap_signal_log.emit("Error (timeout)")
			return False

	def update_first_connection(self):
		print("Try update_first_connection")
		t = datetime.datetime.now()

		try:
			# Search for email since last sync date
			self.start_sync = self.db.get_last_sync(self.server_id)
			date_string = self.locale.toString(self.start_sync, "dd-MMM-yyyy")
			print(date_string)
			typ, msgnums = self.serverIMAP.search(None, 'SINCE {date}'.format(date=date_string), 'FROM "sbdservice@sbd.iridium.com"')
			if(not self.process_msg(msgnums)):
				return False

			self.is_first_connection = False
			self.db.update_last_sync(self.server_id, t)
			self.log =  "Connected"
			return True
		except imaplib.IMAP4.error as err:
			self.close_server()
			self.imap_signal_log.emit("Error IMAP")
			print(err)
			return False
		except sqlite3.Error as error:
			self.close_server()
			self.imap_signal_log.emit("Error SQLITE")
			print(error)
			return False
		except:
			print("Error ", sys.exc_info())
			self.close_server()
			self.imap_signal_log.emit("Error - No connection")
			return False

	def download_msg(self, msgnum):
		if(msgnum == "0"):
			return True
		print("Download msg ", msgnum)
		try:
			typ, data_msg = self.serverIMAP.fetch(msgnum, '(BODY.PEEK[])')

		except imaplib.IMAP4.error as err:
			self.close_server()
			self.imap_signal_log.emit("Error IMAP")
			print(err)
			return False

		# Parse received part (starting with "Received: ")
		mail = email.message_from_bytes(data_msg[0][1], policy=default)

		if(mail["From"]=="sbdservice@sbd.iridium.com"):
			# imei = mail["Subject"].split(": ")[1]

			# Determine type of mail
			sbd_received = mail["Subject"].startswith('SBD Msg From Unit: ')
			sbd_sent = mail["Subject"].startswith('SBD Mobile Terminated Message Queued for Unit: ')

			print(mail["Subject"])
			imei = re.search("Unit: (.*)",mail["Subject"]).group(1)
			time_connection = calendar.timegm(parsedate(mail["Date"]))

			if(sbd_received):
				return self.process_received_sbd(imei, mail, time_connection)

			if(sbd_sent):
				return self.process_sent_sbd(imei, mail, time_connection)

		return True

	def process_received_sbd(self, imei, mail, time_connection):
		self.db.add_new_robot(imei) # Add new robot if not existing

		mail_message = mail.get_body('plain').get_content()
		momsn = int(re.search("MOMSN: (.*)", mail_message).group(1))
		mtmsn = int(re.search("MTMSN: (.*)", mail_message).group(1))
		print("momsn =", momsn, "mtmsn =", mtmsn)

		# Check if mtmsn validate previous sent message
		self.db.update_sbd_last_mtmsn(imei, mtmsn, time_connection)

		if mail.get_content_maintype() != 'multipart':
			print("No attachment")
			return True

		## Extract enclosed file
		for part in mail.iter_attachments():
			if part.get_content_maintype() == 'application':
				#print(part.get_content_maintype(), part.get_content_subtype())
				# Extract momsn from attached file
				print(part.get_filename())

				# Add new entry to the database with the association of the imei and momsn
				message_id = self.db.add_sbd_received(imei, momsn, mtmsn, time_connection)

				# Test if message is already saved
				if(message_id != None):
					msg_data = part.get_payload(decode=True)
					ip = IridiumMessageParser(self.db)
					ip.save_log_state(msg_data, message_id, time_connection)

		return True

	def process_sent_sbd(self, imei, mail, time_connection):
		mail_message = mail.get_body('plain').get_content()
		mtmsn = int(re.search("The MTMSN is (.*),", mail_message).group(1))
		queue = int(re.search("the message is number (.*) in the queue", mail_message).group(1))
		filename = re.search("Attachment Filename: (.*).sbd", mail_message).group(1)+'.sbd'
		print(len(filename))
		print(filename)
		self.db.update_sbd_received_by_icu(imei, filename, mtmsn, queue, time_connection)
		return True

class IridiumMessageParser():
	message_type = 0
	db = None
	CMD_MSG_TYPE = {"LOG_STATE":0, "CMD_SLEEP":1, "CMD_PARAMETERS":2, "CMD_MISSION_NEW":3, "CMD_MISSION_KEEP":4}
	flag_msg_ok = True
	wp_id = 0

	L93_EAST_MIN = 0.0
	L93_EAST_MAX  = 1300000.0
	L93_NORTH_MIN = 6000000.0
	L93_NORTH_MAX = 7200000.0
	REF_POSIX_TIME = 1604874973 #To be update every 5 years !

	def __init__(self, db=None):
		self.db = db

	def save_log_state(self, message_string, message_id, send_time):
		if(len(message_string)!=17):
			print("DECODE LOG STATE ERROR : message length != 17")
			return
		message = int.from_bytes(message_string, byteorder='little', signed=False)
		message_data = self.deserialize_log_state(message, send_time)
		self.db.add_sbd_log_state(message_id, message_data)

	def serialize_data(self, data, val, nb_bit, start_bit, value_min=None, value_max=None, flag_debug=False):
		if(flag_debug):
			print("------")
			print("val init =", val)
		if(value_min!=None and value_max!=None):
			scale = ((1<<nb_bit)-1)/(value_max-value_min)
			val=int(round((val-value_min)*scale))
		else:
			value_min = 0.0
			scale = 1.0
		mask = ((1<<nb_bit)-1) << start_bit
		data = data | (mask & (val<<start_bit))

		if(flag_debug):
			print("val_min =", value_min)
			print("scale = ", scale)
			print("val = ", val)
		return data, nb_bit+start_bit, val/scale+value_min

	def deserialize_data(self, data, nb_bit, start_bit, value_min=None, value_max=None):
		mask = ((1<<nb_bit)-1) << start_bit
		v = (data & mask)>>start_bit
		if(value_min!=None and value_max!=None):
			scale = ((1<<nb_bit)-1)/(value_max-value_min)
			v=v/scale+value_min
		return v, start_bit+nb_bit

	def serialize_cmd_parameters(self, enable_mission=True, enable_flash=True, enable_depth=True, enable_engine=True, period_message=60):
		bit_position = 0
		data = 0b0
		type = self.CMD_MSG_TYPE["CMD_PARAMETERS"]
		data, bit_position, _ = self.serialize_data(data, type,4, bit_position)
		data, bit_position, _ = self.serialize_data(data, enable_mission,1, bit_position)
		data, bit_position, _ = self.serialize_data(data, enable_flash,1, bit_position)
		data, bit_position, _ = self.serialize_data(data, enable_depth,1, bit_position)
		data, bit_position, _ = self.serialize_data(data, enable_engine,1, bit_position)
		data, bit_position, _ = self.serialize_data(data, period_message,8, bit_position)
		return data.to_bytes(int(bit_position/8), byteorder='little'), type

	def serialize_cmd_sleep(self, duration=0):
		bit_position = 0
		data = 0b0
		type = self.CMD_MSG_TYPE["CMD_SLEEP"]
		data, bit_position, _ = self.serialize_data(data, type,4, bit_position)
		data, bit_position, _ = self.serialize_data(data, duration,12, bit_position)
		return data.to_bytes(int(bit_position/8), byteorder='little'), type

	def serialize_cmd_mission_wp(self, data, wp, bit_position, mean_east, mean_north):
		self.wp_id+=1
		data, bit_position, _ = self.serialize_data(data, wp.enable_thrusters, 1, bit_position)

		# Duration : 0 to 256min
		duration = round(wp.duration.total_seconds()/60.0)
		data, bit_position, _ = self.serialize_data(data, duration, 9, bit_position)

		if(wp.enable_thrusters):
			d_east = round((wp.east-mean_east)/4.0)
			d_north = round((wp.north-mean_north)/4.0)
			if(abs(d_east)>2**14 or abs(d_north)>2**14 or duration>2**8):
				msgBox = QMessageBox()
				msgBox.setIcon(QMessageBox.Warning)
				msgBox.setText("wp " + str(self.wp_id) + " is out of bounds (65km, 256min): " + str(d_east*4) + " " + str(d_north*4) + " " + str(duration))
				msgBox.setWindowTitle("Seabot")
				msgBox.setStandardButtons(QMessageBox.Ok)
				msgBox.exec()
				self.flag_msg_ok = False
				return None, None
			data, bit_position, _ = self.serialize_data(data, d_east, 15, bit_position, flag_debug=False) # Should be signed ! be carefull
			data, bit_position, _ = self.serialize_data(data, d_north, 15, bit_position, flag_debug=False)
		else:
			depth = round(wp.depth*4.0) #25cm resolution
			data, bit_position, _ = self.serialize_data(data, depth, 11, bit_position)
			data, bit_position, _ = self.serialize_data(data, wp.seafloor_landing, 1, bit_position)

			bit_position +=2 # Two bits reserved for future use

		# 1+9+15+15 = 40 (5*8)
		# or 1+9+11+1+(2) = (3*8)
		return data, bit_position

	def serialize_cmd_mission(self, mission, keep_old_mission):
		bit_position = 0
		data = 0b0
		type = 0
		if(keep_old_mission):
			type = self.CMD_MSG_TYPE["CMD_MISSION_KEEP"]
			data, bit_position, _ = self.serialize_data(data, type,4, bit_position)
		else:
			type = self.CMD_MSG_TYPE["CMD_MISSION_NEW"]
			data, bit_position, _ = self.serialize_data(data, type,4, bit_position)

		# Number of wp in the message
		data, bit_position, _ = self.serialize_data(data, len(mission.get_wp_list()),8, bit_position)

		# Head info
		mean_east, mean_north = mission.compute_mean_position()

		time_posix = mission.start_time_utc.replace(tzinfo=datetime.timezone.utc).timestamp()
		print("mission start_time_utc", time_posix)

		start_time = round((time_posix-self.REF_POSIX_TIME)/60) # Starting near the minute

		if(start_time<=0 or start_time>2**22-1):
			msgBox = QMessageBox()
			msgBox.setIcon(QMessageBox.Warning)
			msgBox.setText("Time is out of bounds : " + str(start_time))
			msgBox.setWindowTitle("Seabot")
			msgBox.setStandardButtons(QMessageBox.Ok)
			msgBox.exec()
			self.flag_msg_ok = False

		data, bit_position, _ = self.serialize_data(data, start_time,22, bit_position)
		data, bit_position, mean_east_serialized = self.serialize_data(data, mean_east,15, bit_position, self.L93_EAST_MIN, self.L93_EAST_MAX)
		data, bit_position, mean_north_serialized = self.serialize_data(data, mean_north,15, bit_position, self.L93_NORTH_MIN, self.L93_NORTH_MAX)

		print("mean_serialized = ",mean_east_serialized, mean_north_serialized, start_time)
		### Header size is 64 (8*8): 4+8+22+15+15

		# -----------------------------------------
		# WP
		for wp in mission.get_wp_list():
			data, bit_position = self.serialize_cmd_mission_wp(data, wp, bit_position, mean_east_serialized, mean_north_serialized)
			if not self.flag_msg_ok:
				return None

		# ---------------------------------

		return data.to_bytes(int(bit_position/8), byteorder='little'), type

	def deserialize_log_state(self, data, send_time):
		bit_position = 0
		fields = {}

		# To be updated
		message_type, bit_position = self.deserialize_data(data, 4, bit_position)
		time_day_LQ, bit_position = self.deserialize_data(data, 14, bit_position)
		time_day = 3*time_day_LQ
		# Compute difference between send_time and time_day

		fields["ts"] = send_time

		fields["east"], bit_position = self.deserialize_data(data, 21, bit_position, self.L93_EAST_MIN, self.L93_EAST_MAX)
		fields["north"], bit_position = self.deserialize_data(data, 21, bit_position, self.L93_NORTH_MIN, self.L93_NORTH_MAX)
		fields["gnss_speed"], bit_position = self.deserialize_data(data, 8, bit_position, 0, 5.0)
		fields["gnss_heading"], bit_position = self.deserialize_data(data, 8, bit_position, 0, 359.0)

		safety, bit_position = self.deserialize_data(data, 8, bit_position)
		safety = int(safety)
		fields["safety_published_frequency"] = (safety >>0) & 0b1
		fields["safety_depth_limit"] = (safety >>1) & 0b1
		fields["safety_batteries_limit"] = (safety >>2) & 0b1
		fields["safety_depressurization"] = (safety >>3) & 0b1
		fields["enable_mission"] = (safety >>4) & 0b1
		fields["enable_depth"] = (safety >>5) & 0b1
		fields["enable_engine"] = (safety >>6) & 0b1
		fields["enable_flash"] = (safety >>7) & 0b1

		fields["battery0"], bit_position = self.deserialize_data(data, 5, bit_position, 9.0, 12.4)
		fields["battery1"], bit_position = self.deserialize_data(data, 5, bit_position, 9.0, 12.4)
		fields["battery2"], bit_position = self.deserialize_data(data, 5, bit_position, 9.0, 12.4)
		fields["battery3"], bit_position = self.deserialize_data(data, 5, bit_position, 9.0, 12.4)

		fields["pressure"], bit_position = self.deserialize_data(data, 6, bit_position, 680.0, 800.0)
		fields["temperature"], bit_position = self.deserialize_data(data, 6, bit_position, 8.0, 50.0)
		fields["humidity"], bit_position = self.deserialize_data(data, 6, bit_position, 50.0, 100.0)

		fields["waypoint"], bit_position = self.deserialize_data(data, 8, bit_position)
		fields["last_cmd_received"], bit_position = self.deserialize_data(data, 6, bit_position)

		print(fields)
		return fields

# if __name__ == '__main__':
# 	imapServer = ImapServer()
# 	imapServer.set_server_id(1)
# 	imapServer.start_server()
# 	try:
# 		while True:
# 			imapServer.run_imap()
# 			time.sleep(1)
# 	except KeyboardInterrupt:
# 		print('interrupted!', flush=True)
