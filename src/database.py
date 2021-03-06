import sqlite3
import datetime
import os
from os.path import expanduser
from PyQt5.QtCore import QDate, QTime, QDateTime, Qt

## Database connection to store parameters and sbd messages
class DataBaseConnection():

	db_file = expanduser("~") + "/.local/share/QGIS/QGIS3/profiles/default/python/plugins/seabot/" + "Seabot_iridium.db"

	sqlite_tables_name = ["ROBOTS", "SBD_LOG_STATE", "CONFIG", "SBD_RECEIVED", "SBD_SENT"]
	sqlite_create_table = ['''CREATE TABLE "'''+sqlite_tables_name[0]+'''" (
										`IMEI`	NUMERIC NOT NULL,
										`NAME`	TEXT,
										`view_start_ts`	DATETIME DEFAULT `1514811661`,
										`view_end_ts` DATETIME DEFAULT `2524614120`,
										'view_last_received' BOOLEAN DEFAULT `1`,
										PRIMARY KEY(IMEI)
									)''',
							'''CREATE TABLE "'''+sqlite_tables_name[1]+'''" (
								`log_state_id`	INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
								`message_id`	INTEGER NOT NULL,
								`ts` DATETIME NOT NULL,
								`east` REAL NOT NULL,
								`north` REAL NOT NULL,
								`gnss_speed` REAL NOT NULL,
								`gnss_heading` REAL NOT NULL,
								`safety_published_frequency` BOOLEAN NOT NULL,
								`safety_depth_limit` BOOLEAN NOT NULL,
								`safety_batteries_limit` BOOLEAN NOT NULL,
								`safety_depressurization` BOOLEAN NOT NULL,
								`enable_mission` BOOLEAN NOT NULL,
								`enable_depth` BOOLEAN NOT NULL,
								`enable_engine` BOOLEAN NOT NULL,
								`enable_flash` BOOLEAN NOT NULL,
								`battery0` REAL NOT NULL,
								`battery1` REAL NOT NULL,
								`battery2` REAL NOT NULL,
								`battery3` REAL NOT NULL,
								`pressure` REAL NOT NULL,
								`temperature` REAL NOT NULL,
								`humidity` REAL NOT NULL,
								`waypoint` INTEGER NOT NULL,
								`last_cmd_received` INTEGER NOT NULL,
								FOREIGN KEY(`message_id`) REFERENCES SBD_RECEIVED (`message_id`)
							)''',
							'''CREATE TABLE "'''+sqlite_tables_name[2]+'''" (
									`config_id`	INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
									`email`	TEXT,
									`password`	TEXT,
									`server_imap_ip`	TEXT,
									`server_imap_port`	TEXT DEFAULT '993',
									`server_smtp_ip`	TEXT,
									`server_smtp_port`	TEXT,
									`iridium_server_mail`	TEXT,
									`last_sync`	TEXT NOT NULL
							)''',
							'''CREATE TABLE "'''+sqlite_tables_name[3]+'''" (
									`message_id`	INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
									`IMEI`	NUMERIC NOT NULL,
									`momsn`	NUMERIC NOT NULL,
									`mtmsn`	NUMERIC NOT NULL,
									`time_connection` DATETIME NOT NULL,
									FOREIGN KEY(`IMEI`) REFERENCES ROBOTS (`IMEI`)
							)''',
							'''CREATE TABLE "'''+sqlite_tables_name[4]+'''" (
									`message_id`	INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
									`type` NUMERIC,
									`IMEI`	NUMERIC NOT NULL,
									`mtmsn`	NUMERIC,
									`queue`	NUMERIC,
									`filename`	TEXT NOT NULL,
									`data` BLOB,
									`time_sent` DATETIME,
									`time_queue` DATETIME,
									`time_received` DATETIME,
									`status` NUMERIC NOT NULL,
									FOREIGN KEY(`IMEI`) REFERENCES ROBOTS (`IMEI`)
							)'''
							]

	sqlite_create_table_get_table = '''SELECT name FROM sqlite_master WHERE type='table' and name NOT LIKE 'sqlite_%';'''

	SBD_SENT_STATUS = {"SENT_TO_ICU":0, "RECEIVED_BY_ICU":1, "RECEIVED_BY_ROBOT":2}

	def __init__(self, credential_file=None, init_table=True):
		self.sqliteConnection = None
		self.sqliteCursor = None

		if(credential_file!=None):
			self.credential_file = credential_file

		# Connection to DB to store iridium messages
		try:
			self.sqliteConnection = sqlite3.connect(self.db_file,
													detect_types=sqlite3.PARSE_DECLTYPES |
																 sqlite3.PARSE_COLNAMES)
			self.sqliteCursor = self.sqliteConnection.cursor()

			# Querry the list of table names
			self.sqliteCursor.execute(self.sqlite_create_table_get_table)
			records = self.sqliteCursor.fetchall()

			if(init_table):
				# Extract the names and create a list of names
				list_table_name = []
				for name in records:
					list_table_name.append(name[0])

				# Test if the table exists, otherwise add a new table
				for i in range(len(self.sqlite_tables_name)):
					if(self.sqlite_tables_name[i] not in list_table_name):
						self.sqliteCursor.execute(self.sqlite_create_table[i])
						self.sqliteConnection.commit()

		except sqlite3.Error as error:
			print("Error while connecting to sqlite", error)
			exit()

	def get_email_list(self):
		try:
			self.sqliteCursor.execute('''SELECT email, config_id FROM CONFIG''')
			records = self.sqliteCursor.fetchall()
			list_email = []
			for data in records:
				table = {}
				table["email"] = data[0]
				table["config_id"] = data[1]
				list_email.append(table)
			return list_email
		except sqlite3.Error as error:
			print("Error while connecting to sqlite", error)
			return []

	def get_robot_list(self):
		try:
			# Remove robots where there is no message received
			self.sqliteCursor.execute('''SELECT ROBOTS.imei, ROBOTS.name FROM ROBOTS''')
			records = self.sqliteCursor.fetchall()
			list_robots = []
			for data in records:
				table = {}
				table["imei"] = data[0]
				table["name"] = data[1]
				list_robots.append(table)
			return list_robots
		except sqlite3.Error as error:
			print("Error while connecting to sqlite", error)
			return []

	def get_robot_name(self, imei):
		try:
			self.sqliteCursor.execute('''SELECT name FROM ROBOTS WHERE imei=?''', [imei])
			records = self.sqliteCursor.fetchone()
			return records[0]
		except sqlite3.Error as error:
			print("Error while connecting to sqlite", error)
			return []

	def update_robot_name(self, name, imei):
		try:
			self.sqliteCursor.execute("UPDATE ROBOTS SET name = ? WHERE imei=?", [name,imei])
			self.sqliteConnection.commit()
		except sqlite3.Error as error:
			print("Error while connecting to sqlite", error)


	def new_server(self, email, password, server_imap_ip, server_imap_port, server_smtp_ip, server_smtp_port, iridium_server_mail, t_zero = datetime.datetime.fromtimestamp(0)):
		try:
			sqlite_insert_config = '''INSERT INTO CONFIG
						  (email, password, server_imap_ip, server_imap_port, server_smtp_ip, server_smtp_port, iridium_server_mail, last_sync)
						  VALUES (?, ?, ?, ?, ?, ?, ?, ?);'''

			data_tuple = (email, password, server_imap_ip, server_imap_port, server_smtp_ip, server_smtp_port, iridium_server_mail, t_zero)
			self.sqliteCursor.execute(sqlite_insert_config, data_tuple)
			id = self.sqliteCursor.lastrowid
			self.sqliteConnection.commit()
			return id
		except:
			print("Error while connecting to sqlite", error)
			return None

	def save_server(self, email, password, server_imap_ip, server_imap_port, server_smtp_ip, server_smtp_port, iridium_server_mail, t_zero, config_id):
		try:
			sqlite_insert_config = '''UPDATE CONFIG SET
						  email= ?, password=?, server_imap_ip=?, server_imap_port=?, server_smtp_ip=?, server_smtp_port=?, iridium_server_mail=?, last_sync=?
						  WHERE config_id = ?'''

			data_tuple = (email, password, server_imap_ip, server_imap_port, server_smtp_ip, server_smtp_port, iridium_server_mail, t_zero, config_id)
			self.sqliteCursor.execute(sqlite_insert_config, data_tuple)
			self.sqliteConnection.commit()
			return True
		except:
			print("Error while connecting to sqlite", error)
			return False

	def delete_server(self, id_row):
		try:
			self.sqliteCursor.execute("DELETE FROM CONFIG WHERE config_id=(?)", [id_row])
			self.sqliteConnection.commit()
			return True
		except sqlite3.Error as error:
			print("Error while connecting to sqlite", error)
			return False

	def get_server_data(self, server_id):
		try:
			self.sqliteCursor.execute("SELECT * FROM CONFIG where config_id=?", [server_id])
			records = self.sqliteCursor.fetchone()
			data = {}
			if(len(records)>0):
				data["server_id"] = records[0]
				data["email"] = records[1]
				data["password"] = records[2]
				data["server_imap_ip"] = records[3]
				data["server_imap_port"] = records[4]
				data["server_smtp_ip"] = records[5]
				data["server_smtp_port"] = records[6]
				data["iridium_server_mail"] = records[7]
				data["last_sync"] = QDateTime.fromString(records[8], Qt.ISODate)
			return data
		except sqlite3.Error as error:
			print("Error while connecting to sqlite", error)
			return []

	def update_last_sync(self, server_id, t):
		try:
			self.sqliteCursor.execute("UPDATE CONFIG SET last_sync = ? WHERE config_id=?", [t,server_id])
			self.sqliteConnection.commit()
		except sqlite3.Error as error:
			print("Error while connecting to sqlite", error)

	def get_last_sync(self, server_id):
		try:
			self.sqliteCursor.execute("SELECT last_sync from CONFIG WHERE config_id=?", [server_id])
			row = self.sqliteCursor.fetchone()
			if(len(row)!=0):
				return QDateTime.fromString(row[0], Qt.ISODate)
			else:
				return None
		except sqlite3.Error as error:
			print("Error while connecting to sqlite", error)

	def add_new_robot(self, imei):
		try:
			self.sqliteCursor.execute("SELECT COUNT(1) from ROBOTS WHERE IMEI=(?)", [imei])
			row = self.sqliteCursor.fetchone()
			if(row[0]==0):
				self.sqliteCursor.execute("INSERT INTO ROBOTS (IMEI) VALUES (?)", [imei])
				self.sqliteConnection.commit()
				return True
			else:
				return False
		except sqlite3.Error as error:
			print("Error while connecting to sqlite", error)

	def add_sbd_sent_to_icu(self, imei, filename, type, data, time_sent):
		try:
			self.sqliteCursor.execute("SELECT COUNT(1) from SBD_SENT WHERE IMEI=(?) and filename=?", [imei,filename])
			row = self.sqliteCursor.fetchone()
			if(row[0]==0):
				self.sqliteCursor.execute("INSERT INTO SBD_SENT (IMEI, FILENAME, TYPE, DATA, STATUS, TIME_SENT) VALUES (?, ?, ?, ?, ?, ?)", [imei, filename, type, data, self.SBD_SENT_STATUS["SENT_TO_ICU"], time_sent])
				self.sqliteConnection.commit()
				return False
			else:
				return True
		except sqlite3.Error as error:
			print("Error while connecting to sqlite", error)

	def update_sbd_received_by_icu(self, imei, filename, mtmsn, queue, time_queue):
		try:
			self.sqliteCursor.execute("SELECT COUNT(1) from SBD_SENT WHERE IMEI=(?) and filename=?", [imei,filename])
			row = self.sqliteCursor.fetchone()
			if(row[0]==0):
				self.sqliteCursor.execute("INSERT INTO SBD_SENT (mtmsn, queue, time_queue, status, imei, filename) VALUES (?, ?, ?, ?, ?, ?)", [mtmsn, queue, time_queue, self.SBD_SENT_STATUS["RECEIVED_BY_ICU"], imei, filename])
				self.sqliteConnection.commit()
				return False
			else:
				self.sqliteCursor.execute("UPDATE SBD_SENT SET mtmsn = ?, queue = ?, time_queue = ?, status=?  WHERE imei= ? and filename = ?", [mtmsn, queue, time_queue, self.SBD_SENT_STATUS["RECEIVED_BY_ICU"], imei, filename])
				self.sqliteConnection.commit()
				return True
		except sqlite3.Error as error:
			print("Error while connecting to sqlite", error)

	def get_sbd_sent(self, imei):
		try:
			self.sqliteCursor.execute('''SELECT type, status, mtmsn, queue, filename, time_queue, time_sent, time_received FROM SBD_SENT WHERE IMEI=(?)''', [imei])
			records = self.sqliteCursor.fetchall()
			sbd_sent = []
			for data in records:
				table = {}
				table["type"] = data[0]
				table["status"] = data[1]
				table["mtmsn"] = data[2]
				table["queue"] = data[3]
				table["filename"] = data[4]
				table["time_queue"] = data[5]
				table["time_sent"] = data[6]
				table["time_received"] = data[7]
				sbd_sent.append(table)
			return sbd_sent
		except sqlite3.Error as error:
			print("Error while connecting to sqlite", error)
			return []

	def update_sbd_last_mtmsn(self, imei, mtmsn, time_connection):
		try:
			self.sqliteCursor.execute('''SELECT status, time_queue FROM SBD_SENT WHERE IMEI=(?) and MTMSN=(?) ORDER BY time_queue DESC, time_sent DESC''', [imei, mtmsn])
			records = self.sqliteCursor.fetchone()
			if(records!=None):
				print("Find pending mtmsn : "+str(mtmsn))
				status = records[0]
				time_queue = records[1]
				if(status<=1):
					# Update records
					self.sqliteCursor.execute("UPDATE SBD_SENT SET status = ?, time_received = ? WHERE imei=? and mtmsn=(?)", [2, time_connection, imei, mtmsn])
					self.sqliteConnection.commit()

		except sqlite3.Error as error:
			print("Error while connecting to sqlite", error)

	def add_sbd_received(self, imei, momsn, mtmsn, time_connection):
		try:
			self.sqliteCursor.execute("SELECT COUNT(1) from SBD_RECEIVED WHERE IMEI= ? and momsn=? and mtmsn=? and time_connection=?", [imei, momsn, mtmsn,time_connection])
			row = self.sqliteCursor.fetchone()
			if(row[0]==0):
				self.sqliteCursor.execute("INSERT INTO SBD_RECEIVED (IMEI, momsn, mtmsn, time_connection) VALUES (?, ?, ?, ?)", [imei, momsn, mtmsn, time_connection])
				self.sqliteConnection.commit()
				return self.sqliteCursor.lastrowid
			else:
				return None
		except sqlite3.Error as error:
			print("Error while connecting to sqlite (add_sbd_received)", error)

	def fill_data_log_state(self, row):
		data = {}
		data["log_state_id"] = row[0]
		data["message_id"] = row[1]
		data["ts"] = row[2]
		data["east"] = row[3]
		data["north"] = row[4]
		data["gnss_speed"] = row[5]
		data["gnss_heading"] = row[6]
		data["safety_published_frequency"] = row[7]
		data["safety_depth_limit"] = row[8]
		data["safety_batteries_limit"] = row[9]
		data["safety_depressurization"] = row[10]
		data["enable_mission"] = row[11]
		data["enable_depth"] = row[12]
		data["enable_engine"] = row[13]
		data["enable_flash"] = row[14]
		data["battery0"] = row[15]
		data["battery1"] = row[16]
		data["battery2"] = row[17]
		data["battery3"] = row[18]
		data["pressure"] = row[19]
		data["temperature"] = row[20]
		data["humidity"] = row[21]
		data["waypoint"] = row[22]
		data["last_cmd_received"] = row[23]
		return data

	def get_next_log_state(self, message_id):
		try:
			sql_sentence = '''SELECT *
								FROM SBD_LOG_STATE
								INNER JOIN SBD_RECEIVED ON
									SBD_LOG_STATE.message_id = SBD_RECEIVED.message_id
									INNER JOIN ROBOTS ON (
										ROBOTS.imei = SBD_RECEIVED.imei
										AND
										SBD_RECEIVED.IMEI IN (SELECT SBD_RECEIVED.IMEI FROM SBD_RECEIVED WHERE SBD_RECEIVED.message_id=?)
										AND
										SBD_RECEIVED.MOMSN > (SELECT SBD_RECEIVED.MOMSN FROM SBD_RECEIVED WHERE SBD_RECEIVED.message_id=?)
										AND
										SBD_LOG_STATE.ts >= ROBOTS.view_start_ts
										AND
										CASE ROBOTS.view_last_received
										WHEN 0 THEN
											SBD_LOG_STATE.ts <= ROBOTS.view_end_ts
										ELSE
											SBD_LOG_STATE.ts
										END
									)
								ORDER BY ts
								LIMIT 1'''
			self.sqliteCursor.execute(sql_sentence, [message_id, message_id])
			row = self.sqliteCursor.fetchone()
			if(row!=None):
				return self.fill_data_log_state(row)
			else:
				return None
		except sqlite3.Error as error:
			print("Error while connecting to sqlite", error)

	def get_previous_log_state(self, message_id):
		try:
			sql_sentence = '''SELECT *
								FROM SBD_LOG_STATE
								INNER JOIN SBD_RECEIVED ON
									SBD_LOG_STATE.message_id = SBD_RECEIVED.message_id
									INNER JOIN ROBOTS ON (
										ROBOTS.imei = SBD_RECEIVED.imei
										AND
										SBD_RECEIVED.IMEI IN (SELECT SBD_RECEIVED.IMEI FROM SBD_RECEIVED WHERE SBD_RECEIVED.message_id=?)
										AND
										SBD_RECEIVED.MOMSN < (SELECT SBD_RECEIVED.MOMSN FROM SBD_RECEIVED WHERE SBD_RECEIVED.message_id=?)
										AND
										SBD_LOG_STATE.ts >= ROBOTS.view_start_ts
										AND
										CASE ROBOTS.view_last_received
										WHEN 0 THEN
											SBD_LOG_STATE.ts <= ROBOTS.view_end_ts
										ELSE
											SBD_LOG_STATE.ts
										END
									)
								ORDER BY ts DESC
								LIMIT 1'''
			self.sqliteCursor.execute(sql_sentence, [message_id, message_id])
			row = self.sqliteCursor.fetchone()
			if(row!=None):
				return self.fill_data_log_state(row)
			else:
				return None
		except sqlite3.Error as error:
			print("Error while connecting to sqlite", error)

	def get_momsn_from_message_id(self, message_id):
		try:
			sql_sentence = '''SELECT SBD_RECEIVED.MOMSN FROM SBD_RECEIVED
								WHERE SBD_RECEIVED.message_id = ? '''
			self.sqliteCursor.execute(sql_sentence, [message_id])
			row = self.sqliteCursor.fetchone()
			if(row!=None):
				return row[0]
			else:
				return None
		except sqlite3.Error as error:
			print("Error while connecting to sqlite", error)

	def get_log_state(self, message_id):
		try:
			sql_sentence = '''SELECT *
								FROM SBD_LOG_STATE
								WHERE SBD_LOG_STATE.message_id = ?
								LIMIT 1'''
			self.sqliteCursor.execute(sql_sentence, [message_id])
			row = self.sqliteCursor.fetchone()
			if(row!=None):
				return self.fill_data_log_state(row)
			else:
				return None
		except sqlite3.Error as error:
			print("Error while connecting to sqlite", error)

	def get_last_log_state(self, imei):
		try:
			sql_sentence = '''SELECT *, SBD_RECEIVED.MOMSN
							FROM SBD_LOG_STATE
							INNER JOIN SBD_RECEIVED ON
								SBD_LOG_STATE.message_id = SBD_RECEIVED.message_id
								AND
								SBD_RECEIVED.IMEI = ?
								INNER JOIN ROBOTS ON (
									ROBOTS.imei = SBD_RECEIVED.imei
									AND
									SBD_LOG_STATE.ts >= ROBOTS.view_start_ts
									AND
									CASE ROBOTS.view_last_received
									WHEN 0 THEN
										SBD_LOG_STATE.ts <= ROBOTS.view_end_ts
									ELSE
										SBD_LOG_STATE.ts
									END
							)
							ORDER BY SBD_RECEIVED.MOMSN DESC
							LIMIT 1'''
			self.sqliteCursor.execute(sql_sentence, [imei])
			row = self.sqliteCursor.fetchone()
			if(row!=None):
				return self.fill_data_log_state(row[0:-2]), row[-1]
			else:
				return [None, None]
		except sqlite3.Error as error:
			print("Error while connecting to sqlite", error)

	def get_last_log_state_momsn(self, imei, momsn):
		try:
			sql_sentence = '''SELECT *
							FROM SBD_LOG_STATE
							INNER JOIN SBD_RECEIVED ON
								SBD_RECEIVED.MOMSN = ?
								AND
								SBD_RECEIVED.IMEI = ?
								INNER JOIN ROBOTS ON (
									ROBOTS.imei = SBD_RECEIVED.imei
									AND
									SBD_LOG_STATE.ts >= ROBOTS.view_start_ts
									AND
									CASE ROBOTS.view_last_received
									WHEN 0 THEN
										SBD_LOG_STATE.ts <= ROBOTS.view_end_ts
									ELSE
										SBD_LOG_STATE.ts
									END
								)
							LIMIT 1'''
			self.sqliteCursor.execute(sql_sentence, [momsn, imei])
			row = self.sqliteCursor.fetchone()
			if(row!=None):
				return self.fill_data_log_state(row)
			else:
				return None
		except sqlite3.Error as error:
			print("Error while connecting to sqlite", error)

	def get_pose(self, imei):
		try:
			sql_sentence = '''SELECT SBD_LOG_STATE.east, SBD_LOG_STATE.north
							FROM SBD_LOG_STATE
							INNER JOIN SBD_RECEIVED ON
								SBD_RECEIVED.IMEI = ?
								AND
								SBD_RECEIVED.message_id=SBD_LOG_STATE.message_id
								INNER JOIN ROBOTS ON (
									ROBOTS.imei = SBD_RECEIVED.imei
									AND
									SBD_LOG_STATE.ts >= ROBOTS.view_start_ts
									AND
									CASE ROBOTS.view_last_received
									WHEN 0 THEN
										SBD_LOG_STATE.ts <= ROBOTS.view_end_ts
									ELSE
										SBD_LOG_STATE.ts
									END
							)
							ORDER BY SBD_RECEIVED.MOMSN DESC'''

			self.sqliteCursor.execute(sql_sentence, [imei])
			row = self.sqliteCursor.fetchall()
			return row
		except sqlite3.Error as error:
			print("Error while connecting to sqlite", error)

	def get_last_pose(self, imei):
		try:
			sql_sentence = '''SELECT SBD_LOG_STATE.east, SBD_LOG_STATE.north
							FROM SBD_LOG_STATE
							INNER JOIN SBD_RECEIVED ON
								SBD_RECEIVED.IMEI = ?
								AND
								SBD_RECEIVED.message_id=SBD_LOG_STATE.message_id
								INNER JOIN ROBOTS ON (
									ROBOTS.imei = SBD_RECEIVED.imei
									AND
									SBD_LOG_STATE.ts >= ROBOTS.view_start_ts
									AND
									CASE ROBOTS.view_last_received
									WHEN 0 THEN
										SBD_LOG_STATE.ts <= ROBOTS.view_end_ts
									ELSE
										SBD_LOG_STATE.ts
									END
								)
							ORDER BY SBD_RECEIVED.MOMSN DESC
							LIMIT 1'''
			self.sqliteCursor.execute(sql_sentence, [imei])
			row = self.sqliteCursor.fetchone()
			return row
		except sqlite3.Error as error:
			print("Error while connecting to sqlite", error)

	def get_name(self, imei):
		try:
			sql_sentence = '''SELECT ROBOTS.name
							FROM SBD_LOG_STATE
							WHERE ROBOTS.imei = ?'''
			self.sqliteCursor.execute(sql_sentence, [imei])
			row = self.sqliteCursor.fetchone()
			return row
		except sqlite3.Error as error:
			print("Error while connecting to sqlite", error)

	def errase_com(self, imei):
		try:
			self.sqliteCursor.execute('''DELETE FROM SBD_SENT WHERE IMEI = ?''', [imei])
			self.sqliteConnection.commit()
			return True
		except sqlite3.Error as error:
			print("Error while connecting to sqlite", error)
			return False

	def errase_log(self, imei):
		try:
			self.sqliteCursor.execute('''DELETE FROM SBD_LOG_STATE WHERE SBD_LOG_STATE.message_id IN (
										  SELECT SBD_LOG_STATE.message_id FROM SBD_LOG_STATE
										  	INNER JOIN SBD_RECEIVED ON (
										    	SBD_RECEIVED.IMEI = ?
											AND
												SBD_RECEIVED.message_id=SBD_LOG_STATE.message_id
											))''', [imei])
			self.sqliteConnection.commit()
			self.sqliteCursor.execute("DELETE FROM SBD_RECEIVED WHERE IMEI=(?)", [imei])
			self.sqliteConnection.commit()
			return True
		except sqlite3.Error as error:
			print("Error while connecting to sqlite", error)
			return False

	def errase_robot(self, imei):
		try:
			self.sqliteCursor.execute("DELETE FROM ROBOTS WHERE IMEI=(?)", [imei])
			self.sqliteConnection.commit()
			return True
		except sqlite3.Error as error:
			print("Error while connecting to sqlite", error)
			return False

	def get_bounds_momsn(self, imei):
		try:
			sql_sentence = '''SELECT MIN(SBD_RECEIVED.momsn), MAX(SBD_RECEIVED.momsn)
							FROM SBD_RECEIVED
							WHERE SBD_RECEIVED.imei = ?'''
			self.sqliteCursor.execute(sql_sentence, [imei])
			data = self.sqliteCursor.fetchone()
			return data[0], data[1]
		except sqlite3.Error as error:
			print("Error while connecting to sqlite", error)

	def set_view_end(self, datetime, imei):
		try:
			self.sqliteCursor.execute("UPDATE ROBOTS SET view_end_ts = ? WHERE imei=?", [datetime,imei])
			self.sqliteConnection.commit()
		except sqlite3.Error as error:
			print("Error while connecting to sqlite", error)

	def set_view_start(self, datetime, imei):
		try:
			self.sqliteCursor.execute("UPDATE ROBOTS SET view_start_ts = ? WHERE imei=?", [datetime,imei])
			self.sqliteConnection.commit()
		except sqlite3.Error as error:
			print("Error while connecting to sqlite", error)

	def set_view_last(self, val, imei):
		try:
			self.sqliteCursor.execute("UPDATE ROBOTS SET view_last_received = ? WHERE imei=?", [val,imei])
			self.sqliteConnection.commit()
		except sqlite3.Error as error:
			print("Error while connecting to sqlite", error)

	def get_view_end(self, imei):
		try:
			sql_sentence = '''SELECT view_end_ts
							FROM ROBOTS
							WHERE ROBOTS.imei = ?'''
			self.sqliteCursor.execute(sql_sentence, [imei])
			row = self.sqliteCursor.fetchone()
			return row[0]
		except sqlite3.Error as error:
			print("Error while connecting to sqlite", error)

	def get_view_start(self, imei):
		try:
			sql_sentence = '''SELECT view_start_ts
							FROM ROBOTS
							WHERE ROBOTS.imei = ?'''
			self.sqliteCursor.execute(sql_sentence, [imei])
			row = self.sqliteCursor.fetchone()
			return row[0]
		except sqlite3.Error as error:
			print("Error while connecting to sqlite", error)

	def get_view_last_received(self, imei):
			try:
				sql_sentence = '''SELECT view_last_received
								FROM ROBOTS
								WHERE ROBOTS.imei = ?'''
				self.sqliteCursor.execute(sql_sentence, [imei])
				row = self.sqliteCursor.fetchone()
				return row[0]
			except sqlite3.Error as error:
				print("Error while connecting to sqlite", error)


	def add_sbd_log_state(self, message_id, data):
		try:
			sql_insert_log_state = ''' INSERT INTO SBD_LOG_STATE
			(message_id,
			 ts,
			 east,
			 north,
			 gnss_speed,
			 gnss_heading,
			 safety_published_frequency,
			 safety_depth_limit,
			 safety_batteries_limit,
			 safety_depressurization,
			 enable_mission,
			 enable_depth,
			 enable_engine,
			 enable_flash,
			 battery0,
			 battery1,
			 battery2,
			 battery3,
			 pressure,
			 temperature,
			 humidity,
			 waypoint,
			 last_cmd_received)
			 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'''

			seq = [message_id,
					data["ts"],
					data["east"],
					data["north"],
					data["gnss_speed"],
					data["gnss_heading"],
					data["safety_published_frequency"],
					data["safety_depth_limit"],
					data["safety_batteries_limit"],
					data["safety_depressurization"],
					data["enable_mission"],
					data["enable_depth"],
					data["enable_engine"],
					data["enable_flash"],
					data["battery0"],
					data["battery1"],
					data["battery2"],
					data["battery3"],
					data["pressure"],
					data["temperature"],
					data["humidity"],
					data["waypoint"],
					data["last_cmd_received"]]

			self.sqliteCursor.execute(sql_insert_log_state, seq)

			self.sqliteConnection.commit()
		except sqlite3.Error as error:
			print("Error while connecting to sqlite", error)

if __name__ == '__main__':
	db = DataBaseConnection()
	print(db.get_next_log_state(100))
	print(db.get_bounds_momsn("300234065392110"))
	print(db.get_pose("300234065392110"))
	print(db.get_last_log_state(""))
