# -*- coding: utf-8 -*-°
"""
/***************************************************************************
 SeabotDockWidget
                                 A QGIS plugin
 Seabot
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        begin                : 2018-10-31
        git sha              : $Format:%H$
        copyright            : (C) 2018 by Thomas Le Mézo
        email                : thomas.le_mezo@ensta-bretagne.org
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

import os, time, math

from PyQt5 import QtGui, QtWidgets, uic
from PyQt5.QtCore import pyqtSignal, QTimer, QFile, QFileInfo
from PyQt5.QtCore import QDate, QTime, QDateTime, Qt
from PyQt5.QtWidgets import QApplication, QWidget, QInputDialog, QLineEdit, QFileDialog, QTreeWidgetItem, QTableWidgetItem
from PyQt5.QtGui import QIcon

from seabot.src.layerSeabot import *
from seabot.src.layerBoat import *
from seabot.src.layerMission import *
from seabot.src.layerInfo import *

from seabot.src.mission import *
from seabot.src.iridiumIMAP import *

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'seabot_dockwidget_base.ui'))

class SeabotDockWidget(QtWidgets.QDockWidget, FORM_CLASS):

    closingPlugin = pyqtSignal()
    send_mail_sleep = pyqtSignal(str, int)
    send_mail_parameters = pyqtSignal(str, bool, bool, bool, bool, int)
    send_mail_mission = pyqtSignal(str, object, bool)

    imap_signal_stop_server = pyqtSignal()

    def __init__(self, iface, parent=None):
        """Constructor."""
        super(SeabotDockWidget, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.iface = iface

        # print(self.__dir__)
        self.setupUi(self)

        self.timer_seabot = QTimer()
        self.timer_boat = QTimer()
        self.timer_mission = QTimer()

        self.momsn_min = 0
        self.momsn_max = 0
        self.momsn_current = 0

        self.data_log = {}
        self.is_data = False

        # Layers
        self.layerSeabots = {}
        self.layerBoat = LayerBoat(self.iface)
        self.layerMissions = []
        self.layerInfo = LayerInfo()

        # DB
        self.db = DataBaseConnection()
        self.imapServer = ImapServer(self.send_mail_sleep, self.send_mail_parameters, self.send_mail_mission, self.imap_signal_stop_server)
        self.mission_selected = -1
        self.mission_selected_last = -2

        ################################################################

        # Imap Slots
        self.imapServer.imap_signal.connect(self.update_imap)
        self.imapServer.imap_signal_log.connect(self.update_log_msg)
        self.imapServer.imap_signal_button_color.connect(self.update_connect_button_color)
        self.imapServer.imap_status_next_connection.connect(self.update_progress_bar)

        ### Timer handle
        self.timer_seabot.timeout.connect(self.process_seabot)
        self.timer_seabot.setInterval(5000)
        self.timer_seabot.start()

        self.timer_boat.timeout.connect(self.process_boat)
        self.timer_boat.setInterval(1000)

        self.timer_mission.timeout.connect(self.process_mission)
        self.timer_mission.setInterval(1000)
        self.timer_mission.start()

        ### UI pushButton handle
        # Init tree Widget
        self.treeWidget_iridium.setColumnCount(2)
        self.tree_log_data = self.treeWidget_iridium.setHeaderLabels(["Parameter","Data"])

        # Config tab
        self.pushButton_boat.clicked.connect(self.enable_timer_boat)

        self.spinBox_gnss_trace.valueChanged.connect(self.update_vanish_trace)

        self.pushButton_server_save.clicked.connect(self.server_save)
        self.pushButton_server_new.clicked.connect(self.server_new)
        self.pushButton_server_delete.clicked.connect(self.server_delete)
        self.comboBox_config_email.currentIndexChanged.connect(self.select_server)
        self.pushButton_server_connect.clicked.connect(self.server_connect)

        self.checkBox_gnss_lock.stateChanged.connect(self.update_lock_view)
        self.checkBox_gnss_distance.stateChanged.connect(self.update_gnss_seabot_pose)
        self.checkBox_gnss_delete.stateChanged.connect(self.update_gnss_delete)

        self.dateTimeEdit_last_sync.dateTimeChanged.connect(self.update_last_sync)

        # Mission tab
        self.pushButton_open_mission.clicked.connect(self.open_mission)
        self.pushButton_delete_mission.clicked.connect(self.delete_mission)
        self.listWidget_mission.currentRowChanged.connect(self.update_mission_info)

        self.init_mission_table_widget()

        # State tab
        self.pushButton_state_rename.clicked.connect(self.rename_robot)
        self.pushButton_state_previous.clicked.connect(self.previous_log_state)
        self.pushButton_state_next.clicked.connect(self.next_log_state)
        self.pushButton_state_last.clicked.connect(self.last_log_state)
        self.comboBox_state_imei.currentIndexChanged.connect(self.update_state_imei)
        self.pushButton_errase_log.clicked.connect(self.errase_log_robot)

        self.checkBox_state_view_last_received.stateChanged.connect(self.update_sate_view_last_received)
        self.dateTimeEdit_state_view_end.dateTimeChanged.connect(self.update_sate_view_end)
        self.dateTimeEdit_state_view_start.dateTimeChanged.connect(self.update_sate_view_start)

        # COM tab
        self.pushButton_com_send_sleep.clicked.connect(self.send_com_sleep)
        self.pushButton_com_send_mission.clicked.connect(self.send_com_mission)
        self.pushButton_com_send_parameters.clicked.connect(self.send_com_parameters)

        self.dial_com_sleep_duration.valueChanged.connect(self.update_com_sleep_duration)
        self.dial_com_mission_message_period.valueChanged.connect(self.update_com_mission_message_period)
        self.pushButton_com_mission_open.clicked.connect(self.com_open_mission)

        # Iridium
        self.mission_iridium_com = None

        # Fill list of email account
        self.update_server_list()

        self.update_robots_list()
        self.update_state_imei()

    def server_save(self, event):
        email = self.lineEdit_email.text()
        password = self.lineEdit_password.text()
        server_imap_ip = self.lineEdit_imap_server_ip.text()
        server_imap_port = self.lineEdit_imap_server_port.text()
        server_smtp_ip = self.lineEdit_smtp_server_ip.text()
        server_smtp_port = self.lineEdit_smtp_server_port.text()
        iridium_mail = self.lineEdit_iridium_server_mail.text()
        t_zero = self.dateTimeEdit_last_sync.dateTime().toString(Qt.ISODate)
        self.db.save_server(email, password, server_imap_ip, server_imap_port, server_smtp_ip, server_smtp_port, iridium_mail, t_zero, self.comboBox_config_email.currentData())
        self.update_server_list()
        return True

    def server_new(self, event):
        email = self.lineEdit_email.text()
        password = self.lineEdit_password.text()
        server_imap_ip = self.lineEdit_imap_server_ip.text()
        server_imap_port = self.lineEdit_imap_server_port.text()
        server_smtp_ip = self.lineEdit_smtp_server_ip.text()
        server_smtp_port = self.lineEdit_smtp_server_port.text()
        iridium_mail = self.lineEdit_iridium_server_mail.text()
        t_zero = self.dateTimeEdit_last_sync.dateTime().toString(Qt.ISODate)
        self.db.new_server(email, password, server_imap_ip, server_imap_port, server_smtp_ip, server_smtp_port, iridium_mail, t_zero)
        self.update_server_list()
        return True

    def server_delete(self, event):
        id_config = self.comboBox_config_email.currentData()
        self.db.delete_server(id_config)
        self.update_server_list()
        return True

    def update_server_list(self):
        self.comboBox_config_email.clear()
        email_list = self.db.get_email_list()
        for email in email_list:
            self.comboBox_config_email.addItem(str(email["config_id"]) + " - " + email["email"], email["config_id"])

    def update_robots_list(self, index_comboBox=-1):
        self.comboBox_state_imei.clear()
        robot_list = self.db.get_robot_list()
        if(len(robot_list)==0):
            return

        for robot in robot_list:
            if robot["name"] != None:
                self.comboBox_state_imei.addItem(robot["name"] + " (" + str(robot["imei"]) + ")", robot["imei"])
            else:
                self.comboBox_state_imei.addItem(str(robot["imei"]), robot["imei"])

        if index_comboBox==-1:
            self.comboBox_state_imei.setCurrentIndex(len(robot_list)-1)
        else:
            self.comboBox_state_imei.setCurrentIndex(index_comboBox)

        # Create associate track
        for robot in robot_list:
            if robot["imei"] not in self.layerSeabots:
                self.layerSeabots[robot["imei"]]=LayerSeabot(robot["imei"], robot["name"])

        for key in self.layerSeabots:
            self.layerSeabots[key].update()

    def rename_robot(self):
        if(self.comboBox_state_imei.currentIndex() != -1):
            currentIndex = self.comboBox_state_imei.currentIndex()
            text, ok = QInputDialog().getText(self, "Database update",
                                         "Robot name:", QLineEdit.Normal,
                                         self.db.get_robot_name(self.comboBox_state_imei.currentData()))
            if ok and text:
                self.db.update_robot_name(text, self.comboBox_state_imei.currentData())
                self.update_robots_list(currentIndex)
                self.layerSeabots[self.comboBox_state_imei.currentData()].name = text

    def select_server(self, index=0):
        if index != -1:
            server_id = self.comboBox_config_email.currentData()
            server_data = self.db.get_server_data(server_id)
            self.lineEdit_email.setText(str(server_data["email"]))
            self.lineEdit_password.setText(str(server_data["password"]))
            self.lineEdit_imap_server_ip.setText(str(server_data["server_imap_ip"]))
            self.lineEdit_imap_server_port.setText(str(server_data["server_imap_port"]))
            self.lineEdit_smtp_server_ip.setText(str(server_data["server_smtp_ip"]))
            self.lineEdit_smtp_server_port.setText(str(server_data["server_smtp_port"]))
            self.lineEdit_iridium_server_mail.setText(str(server_data["iridium_server_mail"]))
            self.dateTimeEdit_last_sync.setDateTime(server_data["last_sync"])

    def open_mission(self, event):
        #options = QFileDialog.Options()
        #options |= QFileDialog.DontUseNativeDialog
        #options |= QFileDialog.ExistingFiles # Allow several files to be opened
        filenameList, _ = QFileDialog.getOpenFileNames(self,"Select mission file(s)", "","Mission Files (*.xml)")
        for filename in filenameList:
            print("filename=", filename)
            mission = SeabotMission(filename)
            layermission = LayerMission(mission)
            self.layerMissions.append(layermission)
            layermission.update_mission_layer()
            self.listWidget_mission.addItem(layermission.get_mission().get_mission_name())

    def delete_mission(self, event):
        mission_id = self.listWidget_mission.currentRow()
        print("mission selected = ", mission_id)
        if mission_id != -1:
            self.listWidget_mission.takeItem(mission_id)
            print(mission_id)
            print(self.layerMissions)
            del self.layerMissions[mission_id]
            print(self.layerMissions)
            self.mission_selected = self.listWidget_mission.currentRow()


    def closeEvent(self, event):
        self.timer_seabot.stop()
        self.timer_boat.stop()
        self.timer_mission.stop()
        self.imap_signal_stop_server.emit()

        self.closingPlugin.emit()
        event.accept()

    def set_enable_form_connect(self, enable):
        if(enable):
            self.comboBox_config_email.setEnabled(True)
            self.lineEdit_email.setEnabled(True)
            self.lineEdit_password.setEnabled(True)
            self.lineEdit_imap_server_ip.setEnabled(True)
            self.lineEdit_imap_server_port.setEnabled(True)
            self.lineEdit_smtp_server_ip.setEnabled(True)
            self.lineEdit_smtp_server_port.setEnabled(True)
            self.lineEdit_iridium_server_mail.setEnabled(True)
            self.pushButton_server_save.setEnabled(True)
            self.pushButton_server_new.setEnabled(True)
            self.pushButton_server_delete.setEnabled(True)
            self.dateTimeEdit_last_sync.setEnabled(True)
            self.pushButton_com_send_sleep.setEnabled(False)
            self.pushButton_com_send_parameters.setEnabled(False)
            self.pushButton_com_send_mission.setEnabled(False)
        else:
            self.comboBox_config_email.setEnabled(False)
            self.lineEdit_email.setEnabled(False)
            self.lineEdit_password.setEnabled(False)
            self.lineEdit_imap_server_ip.setEnabled(False)
            self.lineEdit_imap_server_port.setEnabled(False)
            self.lineEdit_smtp_server_ip.setEnabled(False)
            self.lineEdit_smtp_server_port.setEnabled(False)
            self.lineEdit_iridium_server_mail.setEnabled(False)
            self.pushButton_server_save.setEnabled(False)
            self.pushButton_server_new.setEnabled(False)
            self.pushButton_server_delete.setEnabled(False)
            self.dateTimeEdit_last_sync.setEnabled(False)
            self.pushButton_com_send_sleep.setEnabled(True)
            self.pushButton_com_send_parameters.setEnabled(True)
            self.pushButton_com_send_mission.setEnabled(True)

    def add_item_treeWidget(self, val1, val2=None, nb_digit=-1):
        item = None
        if(val2==None):
            text = self.data_log[val1]
        else:
            text = val2

        if nb_digit>0:
            text = round(float(text), nb_digit)
        elif nb_digit==0:
            text = int(round(float(text)))

        item = QTreeWidgetItem([str(val1), str(text)])
        self.treeWidget_iridium.addTopLevelItem(item)

    def fill_treeWidget_log_state(self):
        self.treeWidget_iridium.clear()
        if(self.data_log!=None):
            qtime = QDateTime.fromSecsSinceEpoch(self.data_log["ts"], Qt.UTC)
            self.add_item_treeWidget("message_id")
            self.add_item_treeWidget("ts", qtime.toString("dd/MM/yy hh:mm:ss"))
            self.add_item_treeWidget("east", nb_digit=0)
            self.add_item_treeWidget("north", nb_digit=0)
            self.add_item_treeWidget("gnss_speed", nb_digit=2)
            self.add_item_treeWidget("gnss_heading", nb_digit=0)
            self.add_item_treeWidget("safety_published_frequency", nb_digit=0)
            self.add_item_treeWidget("safety_depth_limit", nb_digit=0)
            self.add_item_treeWidget("safety_batteries_limit", nb_digit=0)
            self.add_item_treeWidget("safety_depressurization", nb_digit=0)
            self.add_item_treeWidget("enable_mission", nb_digit=0)
            self.add_item_treeWidget("enable_depth", nb_digit=0)
            self.add_item_treeWidget("enable_engine", nb_digit=0)
            self.add_item_treeWidget("enable_flash", nb_digit=0)
            self.add_item_treeWidget("battery0", nb_digit=2)
            self.add_item_treeWidget("battery1", nb_digit=2)
            self.add_item_treeWidget("battery2", nb_digit=2)
            self.add_item_treeWidget("battery3", nb_digit=2)
            self.add_item_treeWidget("pressure", nb_digit=0)
            self.add_item_treeWidget("temperature", nb_digit=1)
            self.add_item_treeWidget("humidity", nb_digit=2)
            self.add_item_treeWidget("waypoint", nb_digit=0)
            self.add_item_treeWidget("last_cmd_received")

    def update_state_info(self):
        if(self.data_log!=None):
            # Get current momsn
            self.momsn_current = self.db.get_momsn_from_message_id(self.data_log["message_id"])

            # Update Text
            self.label_state_info.setText(str(self.momsn_current) + "/ [" + str(self.momsn_min) + ", " + str(self.momsn_max) + "]")

            # Update view of log
            self.layerInfo.update(self.data_log["message_id"])
        else:
            self.label_state_info.setText("None/[None,None]")

    def update_momsn_bounds(self):
        self.momsn_min, self.momsn_max = self.db.get_bounds_momsn(self.comboBox_state_imei.currentData())

    def update_vanish_trace(self, value):
        if(value==-1):
            self.layerBoat.set_nb_points_max(value, False)
        else:
            self.layerBoat.set_nb_points_max(value, True)

    def init_mission_table_widget(self):
        self.tableWidget_mission.setColumnCount(5)
        self.tableWidget_mission.setHorizontalHeaderLabels(["Depth","D start", "D end", "T start", "T end"])

    ###########################################################################
    ### Handler Button

    def enable_timer_boat(self):
        if(self.pushButton_boat.isChecked()):
            self.layerBoat.start()
            self.timer_boat.start()
        else:
            self.timer_boat.stop()
            self.layerBoat.stop()

    def server_connect(self):
        if(self.pushButton_server_connect.isChecked()):
            self.set_enable_form_connect(False)
            self.imapServer.set_server_id(self.comboBox_config_email.currentData())
            self.imapServer.start_server()
        else:
            self.imap_signal_stop_server.emit()
            self.set_enable_form_connect(True)
            self.pushButton_server_connect.setStyleSheet("background-color: rgb(251, 251, 251)")
            self.select_server()

    def update_last_sync(self, qt_time):
        if(self.comboBox_config_email.currentIndex() != -1):
            self.db.update_last_sync(self.comboBox_config_email.currentData(), qt_time.toString(Qt.ISODate))

    def next_log_state(self):
        if(self.data_log != None):
            data = self.db.get_next_log_state(self.data_log["message_id"])
            if(data != None):
                self.data_log = data
                self.update_state_info()
                self.fill_treeWidget_log_state()

    def previous_log_state(self):
        if(self.data_log != None):
            data = self.db.get_previous_log_state(self.data_log["message_id"])
            if(data != None):
                self.data_log = data
                self.update_state_info()
                self.fill_treeWidget_log_state()

    def errase_log_robot(self):
        if(self.comboBox_state_imei.currentIndex() != -1):
            currentIndex = self.comboBox_state_imei.currentIndex()
            self.db.errase_log(self.comboBox_state_imei.currentData())

    def last_log_state(self):
        self.data_log, self.momsn_current = self.db.get_last_log_state(self.comboBox_state_imei.currentData())
        self.update_state_info()
        self.fill_treeWidget_log_state()

    def update_state_view(self):
        if(self.comboBox_state_imei.currentIndex() != -1):
            ts_end = self.db.get_view_end(self.comboBox_state_imei.currentData())
            ts_start = self.db.get_view_start(self.comboBox_state_imei.currentData())
            last_received = self.db.get_view_last_received(self.comboBox_state_imei.currentData())

            self.dateTimeEdit_state_view_start.setDateTime(QDateTime.fromSecsSinceEpoch(ts_start, Qt.UTC))
            self.dateTimeEdit_state_view_end.setDateTime(QDateTime.fromSecsSinceEpoch(ts_end, Qt.UTC))
            if(last_received):
                self.dateTimeEdit_state_view_end.setEnabled(False)

            self.checkBox_state_view_last_received.setCheckState(last_received)


    def update_sate_view_last_received(self, val):
        if(self.comboBox_state_imei.currentIndex() != -1):
            self.db.set_view_last(val, self.comboBox_state_imei.currentData())
            self.update_state_info()
            if(self.comboBox_state_imei.currentData() in self.layerSeabots):
                self.layerSeabots[self.comboBox_state_imei.currentData()].update()

        if(val):
            self.dateTimeEdit_state_view_end.setEnabled(False)
        else:
            self.dateTimeEdit_state_view_end.setEnabled(True)

    def update_sate_view_end(self, datetime):
        if(self.comboBox_state_imei.currentIndex() != -1):
            self.db.set_view_end(datetime.toSecsSinceEpoch(), self.comboBox_state_imei.currentData())
            self.update_state_info()
            if(self.comboBox_state_imei.currentData() in self.layerSeabots):
                self.layerSeabots[self.comboBox_state_imei.currentData()].update()
        return True

    def update_sate_view_start(self, qt_time):
        if(self.comboBox_state_imei.currentIndex() != -1):
            self.db.set_view_start(qt_time.toSecsSinceEpoch(), self.comboBox_state_imei.currentData())
            self.update_state_info()
            if(self.comboBox_state_imei.currentData() in self.layerSeabots):
                self.layerSeabots[self.comboBox_state_imei.currentData()].update()
        return True

    def update_state_imei(self):
        if(self.comboBox_state_imei.currentIndex() != -1):
            self.data_log, self.momsn_current = self.db.get_last_log_state(self.comboBox_state_imei.currentData())

            self.fill_treeWidget_log_state()
            self.update_momsn_bounds()
            self.update_state_info()
            self.update_tracking_seabot()
            self.update_state_view()

    def update_mission_info(self, row):
        self.mission_selected = row
        self.update_mission_ui()

    def update_imap(self):
        self.update_robots_list()
        self.update_state_imei()

    def update_tracking_seabot(self):
        data = self.db.get_last_pose(self.comboBox_state_imei.currentData())
        if(data!=None):
            self.layerBoat.seabot_east = data[0]
            self.layerBoat.seabot_north = data[1]

    def update_lock_view(self, val):
        self.layerBoat.enable_lock_view(val==2) # 2 = Checked

    def update_gnss_seabot_pose(self, val):
        self.layerBoat.set_enable_seabot((val==2)) # 2 = Checked

    def update_gnss_delete(self, val):
        self.layerBoat.delete_layer_exist = (val==2)

    ###########################################################################
    ## TIMERS processing

    def process_seabot(self):
        for key in self.layerSeabots:
            self.layerSeabots[key].update_pose()

    def process_boat(self):
        self.layerBoat.update()

    def process_mission(self):
        if(len(self.layerMissions)>0):
            for layerMission in self.layerMissions:
                # Update mission set point on map
                layerMission.update_mission_pose()
            self.update_mission_ui()

    def update_mission_ui(self):
        if self.mission_selected != -1:
            seabotMission = self.layerMissions[self.mission_selected].get_mission()
            self.label_mission_file.setText(seabotMission.get_filename())
            # Update IHM with mission data set point
            wp = seabotMission.get_current_wp()
            if(wp!=None):
                if(wp.get_depth()==0.0 or seabotMission.is_end_mission()):
                    self.label_mission_status.setText("SURFACE")
                    self.label_mission_status.setStyleSheet("background-color: green")
                else:
                    self.label_mission_status.setText("UNDERWATER")
                    self.label_mission_status.setStyleSheet("background-color: red")

                self.label_mission_start_time.setText(str(wp.get_time_start()))
                self.label_mission_end_time.setText(str(wp.get_time_end()))
                self.label_mission_depth.setText(str(wp.get_depth()))
                self.label_mission_waypoint_id.setText(str(wp.get_id())+"/"+str(seabotMission.get_nb_wp()))
                self.label_mission_time_remain.setText(str(wp.get_time_end()-datetime.datetime.utcnow().replace(microsecond=0)))

                wp_next = seabotMission.get_next_wp()
                if(wp_next != None):
                    self.label_mission_next_depth.setText(str(wp_next.get_depth()))
                else:
                    self.label_mission_next_depth.setText("END OF MISSION")
            else:
                self.label_mission_status.setText("NO WAYPOINTS")
                self.label_mission_waypoint_id.setText(str(seabotMission.get_current_wp_id()+1) + "/"+str(seabotMission.get_nb_wp()))


            # Update Table widget
            if(self.mission_selected_last != self.mission_selected):
                wp_list = seabotMission.get_wp_list()
                self.tableWidget_mission.clearContents()
                self.tableWidget_mission.setRowCount(len(wp_list))
                row = 0
                for wp in wp_list:
                    self.tableWidget_add_waypoint(wp, row)
                    row+=1
        else:
            self.label_mission_status.setStyleSheet("background-color: gray")
            self.label_mission_start_time.setText("-")
            self.label_mission_end_time.setText("-")
            self.label_mission_depth.setText("-")
            self.label_mission_waypoint_id.setText("-")
            self.label_mission_time_remain.setText("-")
            self.label_mission_next_depth.setText("-")
            self.label_mission_status.setText("-")
            self.label_mission_waypoint_id.setText("-")
        self.mission_selected_last = self.mission_selected

    def tableWidget_add_waypoint(self, wp, row):
        time_now = datetime.datetime.utcnow().replace(microsecond=0)
        self.tableWidget_mission.setItem(row, 0, QTableWidgetItem(str(wp.get_depth())))
        self.tableWidget_mission.setItem(row, 1, QTableWidgetItem(str(wp.get_time_end()-time_now)))
        self.tableWidget_mission.setItem(row, 2, QTableWidgetItem(str(wp.get_time_start()-time_now)))
        self.tableWidget_mission.setItem(row, 3, QTableWidgetItem(str(wp.get_time_start())))
        self.tableWidget_mission.setItem(row, 4, QTableWidgetItem(str(wp.get_time_end())))

    def send_com_sleep(self):
        if(self.comboBox_state_imei.currentIndex() != -1):
            self.send_mail_sleep.emit(str(self.comboBox_state_imei.currentData()), self.dial_com_sleep_duration.value())

    def send_com_mission(self):
        if(self.comboBox_state_imei.currentIndex() != -1 and self.mission_iridium_com!=None):
            self.send_mail_mission.emit(str(self.comboBox_state_imei.currentData()), self.mission_iridium_com, self.radioButton_com_mission_add.isChecked())

    def send_com_parameters(self):
        if(self.comboBox_state_imei.currentIndex() != -1):
            self.send_mail_parameters.emit(str(self.comboBox_state_imei.currentData()),\
                self.checkBox_com_param_mission.isChecked(),\
                self.checkBox_com_param_flash.isChecked(),\
                self.checkBox_com_param_depth.isChecked(),\
                self.checkBox_com_param_engine.isChecked(),\
                self.dial_com_mission_message_period.value())

    def update_log_msg(self, val):
        self.label_server_log.setText(val)

    def update_connect_button_color(self, is_connected):
        if(is_connected):
            self.pushButton_server_connect.setStyleSheet("background-color: green")
        else:
            self.pushButton_server_connect.setStyleSheet("background-color: red")

    def update_progress_bar(self, val):
        self.progressBar_imap_next_connection.setValue(val)

    def update_com_sleep_duration(self, val):
        val_hours = math.floor(val/60.)
        val_min = val-val_hours*60
        self.label_com_sleep_duration.setText("Duration\n" + str(val_hours) + "h " + str(val_min) + "min" + "")

    def update_com_mission_message_period(self, val):
        val= val/10.*60. # in sec
        val_min = math.floor(val/60.)
        val_sec = val-val_min*60
        self.label_com_mission_message_period.setText("Message Period\n" + str(val_min) + "min " + str({}).format(int(val_sec)) + "s")

    def com_open_mission(self, event):
        filename, _ = QFileDialog.getOpenFileName(self,"Select mission file to send", "","Mission File (*.xml)")
        print("filename=", filename)
        self.mission_iridium_com = SeabotMission(filename)
        self.label_com_mission_name.setText(self.mission_iridium_com.get_mission_name())
        self.label_com_mission_nb_wp.setText(str(self.mission_iridium_com.get_nb_wp()))
        self.label_com_mission_tstart.setText(str(self.mission_iridium_com.start_time_utc))
        self.label_com_mission_tend.setText(str(self.mission_iridium_com.end_time))
