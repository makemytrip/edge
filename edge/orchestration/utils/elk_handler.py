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

"""This File will be used to connect with ElasticSearch Cluster."""

import datetime, logging, re, socket

from elasticsearch import Elasticsearch
from space.utils.db_handler import DBHandler

logger = logging.getLogger(__name__)


class ELKHandler():
    """This class will be used to read/write data to ELK."""

    def __init__(self, correlation=None):
        """ES Intialization."""

        self.dbobj = DBHandler()
        self.host = self.dbobj.getValue("es_host")
        timeout = int(self.dbobj.getValue("es_timeout"))
        retries = int(self.dbobj.getValue("es_retries"))
        if not self.host or not timeout or not retries:
            raise AttributeError('Not able to create ES object')

        self.es = Elasticsearch(hosts=self.host, timeout=timeout, max_retries=retries)

        self.index = self.dbobj.getValue("es_index")
        self.detail_index = self.dbobj.getValue("es_detail_index")

        self.read_index = self.dbobj.getValue("es_read_index")
        self.read_detail_index = self.dbobj.getValue("es_read_detail_index")
        self.es_read_count = int(self.dbobj.getValue("es_read_count"))
        self.es_delete_template = self.dbobj.getValue("es_delete_template")
        self.correlation = correlation

        if not self.correlation:
            raise ValueError('Correlation key is mandatory for ES operations')

    def send(self, data, detailed=False):
        """write operation to ELK."""
        try:
            localtime = datetime.datetime.now()
            index_name = self.index if not detailed else self.detail_index
            elk_data = []
            index_data = {"index": {"_index" : index_name }}
            if type(data) is dict:
                data['timestamp'] = localtime
                data['worker_host'] = socket.gethostname()
                data['correlation'] = self.correlation
                elk_data.append(index_data)
                elk_data.append(data)
            elif type(data) is list:
                for record in data:
                    record['timestamp'] = localtime
                    record['worker_host'] = socket.gethostname()
                    record['correlation'] = self.correlation
                    elk_data.append(index_data)
                    elk_data.append(record)
            else:
                raise Exception("Unsupported type receieved for data writing - %s, data - %s" % (type(data), data))
            logger.info("Data Writing in ELK - %s" % elk_data)
            if len(elk_data) > 0:
                self.es.bulk(index=index_name, doc_type='edge', body=elk_data)
                self.es.indices.refresh(index=index_name)
            else:
                logger.error("No data available for ELK writing ELK_DATA - %s, DATA - %s" %(elk_data, data))
        except Exception, e:
            logger.exception(e)
            message = "Unable to Connect to ES cluster - %s, Error - %s" % (self.host, str(e))
            raise Exception(message)

    def read_action_entries(self, detailed=False):
        """read operation from ES."""

        index_name = self.read_index if not detailed else self.read_detail_index
        query = {"size" : self.es_read_count, "query": {"match": {"correlation": self.correlation}}}

        result = self.es.search(index=index_name, body=query, sort='timestamp')

        output = []
        for i in result['hits']['hits']:
            output.append(i['_source'])
        return output

    def write_logs(self, action=None, detailed=False, category='display', **kwargs):
        """ Write some Data format to ELK """
        try:
            if action is None:
                action = self.dbobj.getActionInfoActionName(self.correlation)
            data = kwargs
            if category == 'display':
                level = kwargs.get('level', 'error')
                data['level'] = level
            data['category'] = category
            data['action'] = action
            self.send(data, detailed)
        except Exception, e:
            logger.exception(e)

    def delete(self, detailed=True, **kwargs):
        try:
            index_name = self.read_index if not detailed else self.read_detail_index
            query_string=""
            if self.es_delete_template is None:
                raise Exception("template not configured")
            for key, value in kwargs.items():
                if type(value) is str or type(value) is unicode:
                    query_string += str({"terms" : {key : [value]}}) + str(',')
                elif type(value) is list:
                    query_string += str({"terms": {key: value}}) + str(',')
                else:
                    raise Exception("Unsupported Value - %s with Format - %s for key - %s" %(value, type(value), key))
            if query_string is None or len(query_string.strip()) == 0:
                raise Exception("search parameter not given")
            query_string = query_string.strip().strip(",")
            delete_query = self.es_delete_template % {'delete_query':query_string, 'correlation': self.correlation}
            logger.debug("Query for deleting data from ELK - %s" % delete_query)
            if re.search('correlation":\d', delete_query):
                delete_query = eval(delete_query)
                response = self.es.delete_by_query(index=index_name, body=delete_query)
                logger.debug("ELK deletion response - %s" % response)
                logger.info("Deleted %s records from ES in time - %s" %(response.get('deleted'), response.get('took')))
            else:
                raise Exception("correlation is not found in delete query - %s" % delete_query)
        except Exception, e:
            msg = "Unable to delete data from ES, Error -  %s" % e
            logger.error(msg)
            logger.exception(e)
