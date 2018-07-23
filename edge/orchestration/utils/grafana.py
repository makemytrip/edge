# Copyright 2018 MakeMyTrip (Paritosh Anand)
#
# This file is part of edge.
#
# edge is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# edge is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with dataShark.  If not, see <http://www.gnu.org/licenses/>.

""" This file will send annotations to grafana dashborards """

import json
import logging
import requests
from django.conf import settings
import datetime, time

from space.models import Configs

logger = logging.getLogger(__name__)

class Grafana:
	""" This class will be used to send annotations to Grafana """

	def __init__(self, dashboard_name=None):

		if dashboard_name is None:
			raise Exception("Cannot create class object without dashboard name")
		try:
			self.grafana_host = Configs().getValue("grafana_host")
			self.grafana_port = Configs().getValue("grafana_port")
			self.auth_key = Configs().getValue("auth_key")
			self.fetch_info_url = Configs().getValue("fetch_info_url")
			self.send_annotations_url = Configs().getValue("send_annotations_url")
			self.headers = {"Content-Type":"application/json","Authorization":"Bearer {auth_key}".format(auth_key=self.auth_key)}
		except Exception as e:
			logger.error(e)
		self.dashboard_info = None
		self.dashboard_name = dashboard_name
	
	def fetch_info(self):
		# This method will return dashboard info
		try:
			fetch_info_url = "http://{host}:{port}/{fetch_info_url}/{db_name}".format(host=self.grafana_host,port=self.grafana_port,fetch_info_url=self.fetch_info_url,db_name=self.dashboard_name)
			response = requests.get(url=fetch_info_url, headers=self.headers)
			self.dashboard_info = response.json()
		except Exception as e:
			logger.error("Error fetching dashboard id for name - {name}".format(name=self.dashboard_name))
		finally:
			return self.dashboard_info

	def convert_to_epoch(self, d_time):
		# This method converts datetime to epoch millis
		epoch_time = None
		try:
			epoch_time = time.mktime(d_time.timetuple()) * 1000
		except Exception as e:
			logger.error("Unable to convert to epoch time - {time}".format(time=d_time))
		finally:
			return epoch_time

	def send_annotations(self, task_id, endtime, version, space, action, project):
		# This method will send annotations to grafana dashboard
		try:
			dashboard_info = self.fetch_info()
			end_epoch_time = self.convert_to_epoch(endtime)
			if dashboard_info is not None and end_epoch_time is not None:
				
				send_annotations_url = "http://{host}:{port}/{send_annotations_url}".format(host=self.grafana_host,port=self.grafana_port,send_annotations_url=self.send_annotations_url)
				# Text to send as annotation
				text = "<h5>{project}</h5><h6> {action} version <br><a href=\"http://edge.mmt.com/space/action/{space}/{tid}/\">{version}</a></br></h6>".format(project=project,action=action,space=space,tid=task_id,version=version)
				# Payload for request
				payload = {"dashboardId":dashboard_info.get('dashboard').get('id'),"time":int(end_epoch_time),"tags":["Deploy"],"text":text}

				response = requests.post(url=send_annotations_url, data=json.dumps(payload), headers=self.headers)
				result = response.json()
				logger.info("Annotation sent for taskid {tid} to dashboard {db}".format(tid=task_id,db=self.dashboard_name))
				return result
			else:
				logger.info("This was error getting dashboard info for task id - {tid} & dashboard - {db}".format(tid=task_id,db=self.dashboard_name))
				return {}
		except Exception as e:
			logger.error(e)
			return {"error":str(e)}
