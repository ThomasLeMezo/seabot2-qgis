# -*- coding: utf-8 -*-°

import os, time, datetime, sys
import xml.etree.ElementTree as ET
from PyQt5.QtCore import QFileInfo

class SeabotWaypoint():

	def __init__(self, wp_id ,time_end, time_start, duration, depth, east, north, limit_velocity, approach_velocity, enable_thrusters):
		self.time_end = time_end
		self.time_start = time_start
		self.duration = duration
		self.depth = depth
		self.east = east
		self.north = north
		self.limit_velocity = limit_velocity
		self.approach_velocity = approach_velocity
		self.enable_thrusters = enable_thrusters
		self.id = wp_id

	def __str__(self):
		s = ""
		s += "time_start" + "=" + str(self.time_start) + "\n"
		s += "time_end" + "=" + str(self.time_end) + "\n"
		s += "duration" + "=" + str(self.duration) + "\n"
		s += "depth" + "=" + str(self.depth) + "\n"
		s += "east" + "=" + str(self.east) + "\n"
		s += "north" + "=" + str(self.north) + "\n"
		s += "limit_velocity" + "=" + str(self.limit_velocity) + "\n"
		s += "approach_velocity" + "=" + str(self.approach_velocity) + "\n"
		s += "enable_thrusters" + "=" + str(self.enable_thrusters) + "\n"
		return s

	def get_time_end(self):
		return self.time_end

	def get_time_start(self):
		return self.time_start

	def get_duration(self):
		return self.duration

	def get_depth(self):
		return self.depth

	def get_east(self):
		return self.east

	def get_north(self):
		return self.north

	def get_limit_velocity(self):
		return self.limit_velocity

	def get_approach_velocity(self):
		return self.approach_velocity

	def get_enable_thrusters(self):
		return self.enable_thrusters

	def get_id(self):
		return self.id

class SeabotMission():

	def __init__(self, filename=None):
		self.waypoint_list = []
		self.current_wp_id = 0
		self.start_time_utc = None
		self.end_time = None
		self.filepath = ""
		self.filename = ""

		if filename!=None:
			self.load_mission_xml(filename)

	def __str__(self):
		s = ""
		for wp in self.waypoint_list:
			s+=wp.__str__()+"\n\n"
		return s

	def is_empty(self):
		if(len(self.waypoint_list)==0):
			return True
		else:
			return False

	def get_wp_list(self):
		return self.waypoint_list

	def get_nb_wp(self):
		return len(self.waypoint_list)

	def get_current_wp_id(self):
		return self.current_wp_id

	def add_waypoint(self, wp):
		self.waypoint_list.append(wp)

	def get_current_wp(self):
		t = datetime.datetime.utcnow()

		while(len(self.waypoint_list)-1>self.current_wp_id and self.waypoint_list[self.current_wp_id].time_end<t):
			self.current_wp_id+=1

		if self.current_wp_id<len(self.waypoint_list):
			return self.waypoint_list[self.current_wp_id]
		else:
			return None

	def get_next_wp(self):
		if self.current_wp_id+1<len(self.waypoint_list):
			return self.waypoint_list[self.current_wp_id+1]
		else:
			return None

	def load_mission_xml(self, filepath):
		self.filepath = filepath
		file_info = QFileInfo(filepath)
		self.filename = file_info.fileName()
		self.waypoint_list.clear()
		self.current_wp_id = 0
		tree = ET.parse(filepath)
		root = tree.getroot()

		child_offset = root.find("offset/start_time_utc")
		self.start_time_utc = datetime.datetime(year=int(child_offset.find("year").text),
									month=int(child_offset.find("month").text),
									day=int(child_offset.find("day").text),
									hour=int(child_offset.find("hour").text),
									minute=int(child_offset.find("min").text))
		self.end_time = self.start_time_utc

		paths = root.find("paths")

		for child in paths:
			self.parse_node(child)
		self.get_current_wp() # Update current_wp_id

	def parse_node(self, child, depth_offset=0.0):
		if child.tag=="waypoint":
			self.parse_wy(child, depth_offset)
		if child.tag=="loop":
			self.parse_loop(child, depth_offset)

	def parse_wy(self, wp, depth_offset=0.0):
		duration = datetime.timedelta(seconds=float(wp.findtext("duration")))
		time_start = self.end_time
		self.end_time += duration
		self.waypoint_list.append(SeabotWaypoint(time_start = time_start,
											time_end = self.end_time,
											duration=duration,
											depth=float(wp.findtext("depth"))+depth_offset,
											east=int(wp.findtext("east")),
											north=int(wp.findtext("north")),
											limit_velocity=float(wp.findtext("limit_velocity", default="0.02")),
											approach_velocity=float(wp.findtext("approach_velocity", default="1.0")),
											enable_thrusters=True,
											wp_id=len(self.waypoint_list)+1))

	def parse_loop(self, l, depth_offset=0.0):
		n = int(l.attrib["number"])
		dz = float(l.attrib["depth_increment"])
		for i in range(n):
			for child in l:
				self.parse_node(child, depth_offset+i*dz)

	def get_set_point_east(self):
		if self.current_wp_id+1<len(self.waypoint_list):
			east1 = self.waypoint_list[self.current_wp_id].get_east()
			east2 = self.waypoint_list[self.current_wp_id+1].get_east()
			t1 = self.waypoint_list[self.current_wp_id].get_time_start().timestamp()
			t2 = self.waypoint_list[self.current_wp_id].get_time_end().timestamp()
			if(t1!=t2):
				t = datetime.datetime.now().timestamp()
				if(t>t2):
					t=t2
				if(t<t1):
					t=t1
				ratio = (t-t1)/(t2-t1)
				return east1+(east2-east1)*ratio
			else:
				return east2
		else:
			return self.waypoint_list[self.current_wp_id].get_east()

	def get_set_point_north(self):
		if self.current_wp_id+1<len(self.waypoint_list):
			north1 = self.waypoint_list[self.current_wp_id].get_north()
			north2 = self.waypoint_list[self.current_wp_id+1].get_north()
			t1 = self.waypoint_list[self.current_wp_id].get_time_start().timestamp()
			t2 = self.waypoint_list[self.current_wp_id].get_time_end().timestamp()
			if(t1!=t2):
				t = datetime.datetime.now().timestamp()
				if(t>t2):
					t=t2
				if(t<t1):
					t=t1
				ratio = (t-t1)/(t2-t1)
				return north1+(north2-north1)*ratio
			else:
				return north2
		else:
			return self.waypoint_list[self.current_wp_id].get_north()

	def is_end_mission(self):
		if(self.current_wp_id == len(self.waypoint_list)-1 and datetime.datetime.now().timestamp()>self.waypoint_list[self.current_wp_id].get_time_end().timestamp()):
			return True
		else:
			return False

	def is_surface(self):
		if self.current_wp_id+1<len(self.waypoint_list):
			if(self.waypoint_list[self.current_wp_id].get_depth()==0 or self.is_end_mission()):
				return True
			else:
				return False
		else:
			return True

	def get_filename(self):
		return self.filename

	def get_mission_name(self):
		return self.filename # ToDo


if __name__ == '__main__':
	s_m = SeabotMission()
	if(sys.argv[1] != ""):
		s_m.load_mission_xml(sys.argv[1])
	else:
		s_m.load_mission_xml("/home/lemezoth/workspaceFlotteur/src/seabot/mission/mission_guerledan.xml")
	print(s_m)