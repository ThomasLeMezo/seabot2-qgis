import imaplib
import time
import os
import math

import email
from email.policy import default
from email.utils import parsedate_tz, parsedate

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

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
from PyQt5.QtWidgets import QMessageBox
from .database import *

class ImapServer(QObject):
	socket.setdefaulttimeout(1)
	imap_signal = pyqtSignal()
	imap_signal_log = pyqtSignal(str)
	imap_signal_button_color = pyqtSignal(bool)
	imap_status_next_connection = pyqtSignal(int)
	imap_update_dt = 5 # in sec

	def __init__(self, send_mail_test, imap_signal_stop_server):
		super().__init__()
		self.serverIMAP = None
		self.mailbox = 'INBOX'
		self.is_connected = False
		self.is_first_connection = True
		self.running = False
		self.imap_signal_log.emit("?")
		self.server_id = -1
		self.thread = None
		self.db = DataBaseConnection(init_table=True)
		self.locale = QLocale(QLocale.English, QLocale.UnitedStates)
		self.start_sync = None
		self.last_mail_datetime = None

		send_mail_test.connect(self.test_send_mail)
		imap_signal_stop_server.connect(self.stop_server)

	def __del__(self):
		# with self.lock:
		self.running = False
		if(threading.active_count()!=0 and self.thread!=None):
			self.thread.join()
		self.close_server()

	def test_send_mail(self, iridium_imei):
		if(self.is_connected):
			db = DataBaseConnection(init_table=False)
			login_data = db.get_server_data(self.server_id)

			sbd_msg = MIMEBase("application", "x-zip-compressed")

			iridium_mtmsn = "000001"
			filename = iridium_imei + "_" + iridium_mtmsn + ".sbd"
			sbd_msg.add_header('Content-Disposition', 'attachment', filename=filename)
			sbd_msg.set_payload("Test")
			encoders.encode_base64(sbd_msg)

			msg = MIMEMultipart('alternative')
			msg['Subject'] = iridium_imei
			msg['From'] = "<Seabot> <"+login_data["email"]+">"
			msg['To'] = login_data["iridium_server_mail"]
			msg.attach(sbd_msg)
			print(iridium_imei)

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
			except smtplib.SMTP.error as err:
				print(err, flush=True)
				return

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

	def set_server_id(self, server_id):
		self.server_id = server_id

	def connect_imap(self):
		print("Try connect")
		try:
			# Retreive data from DB
			login_data = self.db.get_server_data(self.server_id)
			if(len(login_data)==0):
				raise Exception('wrong server_id ', self.server_id)

			self.serverIMAP = imaplib.IMAP4_SSL(login_data["server_imap_ip"], login_data["server_imap_port"])
			rsp = self.serverIMAP.login(login_data["email"], login_data["password"])

			if(rsp[1][0].decode()=="LOGIN completed."):
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
			self.imap_signal_log.emit("Error IMAP")
			self.close_server()
			return False
		except sqlite3.Error as error:
			print("Error sqlite ", error)
			self.imap_signal_log.emit("Error SQLITE")
			self.close_server()
			return False
		except:
			print("Error ", sys.exc_info())
			self.imap_signal_log.emit("Error - No connection")
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
			print(mail["Subject"])
			imei = re.search("SBD (.*): (.*)",mail["Subject"]).group(2)
			time_connection = calendar.timegm(parsedate(mail["Date"]))

			# Check timed received
			mail_datetime = QDateTime.fromString(mail["Date"], Qt.RFC2822Date)
			# if(self.last_mail_datetime>=mail_datetime):
			# 	print("Before last mail datetime")
			# 	return True

			if mail.get_content_maintype() != 'multipart':
				print("No attachment")
				return True

			self.db.add_new_robot(imei) # Add new robot if not existing
			## Extract enclosed file
			for part in mail.iter_attachments():
				if part.get_content_maintype() == 'application':
					#print(part.get_content_maintype(), part.get_content_subtype())
					# Extract momsn from attached file
					print(part.get_filename())
					momsn = int(re.search("_(.*)\.", part.get_filename()).group(1))

					# Add new entry to the database with the association of the imei and momsn
					message_id = self.db.add_sbd_received(imei, momsn, time_connection)

					# Test if message is already saved
					if(message_id != None):
						msg_data = part.get_payload(decode=True)
						IridiumMessageParser(msg_data, self.db, message_id, time_connection)
		return True

class IridiumMessageParser():
	message_type = 0
	message = None
	db = None

	def __init__(self, message_string, db, message_id, send_time):
		self.message = int.from_bytes(message_string, byteorder='little', signed=False)
		self.db = db
		# self.message_type = message_string[-1] & 0x0F
		# Test type of message

		## Assume
		self.save_log_state(message_id, send_time)

	def save_log_state(self, message_id, send_time):
		message_data = self.deserialize_log_state(self.message, send_time)
		self.db.add_sbd_log_state(message_id, message_data)

	def deserialize_data(self, data, nb_bit, start_bit, value_min=None, value_max=None):
		mask = ((1<<nb_bit)-1) << start_bit
		v = (data & mask)>>start_bit
		if(value_min!=None and value_max!=None):
			scale = (value_max-value_min)/(1<<nb_bit-1)
			v=v*scale+value_min
		return v, start_bit+nb_bit

	def deserialize_log_state(self, data, send_time):
		bit_position = 0
		fields = {}

		# To be updated
		message_type, bit_position = self.deserialize_data(data, 4, bit_position)
		time_day_LQ, bit_position = self.deserialize_data(data, 14, bit_position)
		time_day = 3*time_day_LQ
		# Compute difference between send_time and time_day

		fields["ts"] = send_time

		fields["east"], bit_position = self.deserialize_data(data, 21, bit_position, 0, 1300000)
		fields["north"], bit_position = self.deserialize_data(data, 21, bit_position, 6000000, 7200000)
		fields["gnss_speed"], bit_position = self.deserialize_data(data, 8, bit_position, 0, 5.0)
		fields["gnss_heading"], bit_position = self.deserialize_data(data, 8, bit_position, 0, 359.0)

		safety, bit_position = self.deserialize_data(data, 8, bit_position)
		safety = round(safety)
		fields["safety_published_frequency"] = (safety >>0) & 0b1
		fields["safety_depth_limit"] = (safety >>1) & 0b1
		fields["safety_batteries_limit"] = (safety >>2) & 0b1
		fields["safety_depressurization"] = (safety >>3) & 0b1
		fields["enable_mission"] = (safety >>4) & 0b1
		fields["enable_depth"] = (safety >>5) & 0b1
		fields["enable_engine"] = (safety >>6) & 0b1
		fields["enable_flash"] = (safety >>7) & 0b1

		fields["battery0"], bit_position = self.deserialize_data(data, 5, bit_position, 9, 12.4)
		fields["battery1"], bit_position = self.deserialize_data(data, 5, bit_position, 9, 12.4)
		fields["battery2"], bit_position = self.deserialize_data(data, 5, bit_position, 9, 12.4)
		fields["battery3"], bit_position = self.deserialize_data(data, 5, bit_position, 9, 12.4)

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
