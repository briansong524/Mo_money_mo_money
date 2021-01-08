import yfinance as yf
from pytz import timezone
import numpy as np

import pymysql as MySQLdb

import requests
import time
from datetime import datetime

import logging
from logging.handlers import RotatingFileHandler


def convert_dt_to_epoch(x):
    # converting the New York (UTC-5) to epoch
    # have to do some manipulation by using a 'wrong' conversion and compensating it
    x = x.replace(tzinfo = timezone('GMT')) # timezone changes, but time itself doesnt
    x = (x - datetime(1970, 1, 1, tzinfo = timezone('GMT'))).total_seconds() # as epoch
    x = x + 5*60*60 # compensating the time difference 
    return x

def run_query(creds, query, selectBool = False):
	conn, cursor = mysql_conn(creds)

	try:
		cursor.execute(query)
		if selectBool:
			rows = cursor.fetchall()
	except Exception as e:
		print('Error in running query: ' + str(e))
	finally:
		db_conn_close(conn, cursor)
		if selectBool:
			return rows


def mysql_conn(db_conn_info):
	'''
	Call to connect to the database
	'''
	try:
		dbconn_ = MySQLdb.connect(host=db_conn_info['dbservername'],
					db = db_conn_info['dbname'],
					user = db_conn_info['dbuser'],
					passwd = db_conn_info['dbpassword']
					)
		cursor_ = dbconn_.cursor()
		return dbconn_, cursor_

	except Exception as e:
		print('Error: ' + str(e))

def db_conn_close(dbconn, cursor):
	# closing connections to free up sockets
	dbconn.commit()
	cursor.close()
	dbconn.close()

def send_message_slack(slack_hook, myobj):
	try:
		requests.post(slack_hook, json = myobj)
	except Exception as e:
		print('request failed for some reason, probably internet connection lost. not sending message to slack')



def calculate_rsi(val, prevU = 0, prevD = 0, n = 9):
	if val > 0:
		avgU = (prevU*(n-1) + val) / n
		avgD = prevD*((n-1)/n)
	else:
		avgU = prevU*((n-1)/n)
		avgD = (prevD*(n-1) - val) / n
		
	rs = avgU / (avgD + 1e-5)
	rsi = 100.0 - 100.0 / (1 + rs)
	return rsi, avgU, avgD



def global_logger_init(work_dir,add_ = ''):

	# global logger
	# global handler
	# global console_handler
	############# logger config ###########
	#logging.config.dictConfig({
	#  'version': 1,
	# 'disable_existing_loggers': True,
	#})

	# Remove all handlers associated with the root logger object.
	# for handler in logging.root.handlers[:]:
	# 		logging.root.removeHandler(handler)
	try:
		handler_log_file = work_dir + '/logger.log'
		handler = RotatingFileHandler(handler_log_file, maxBytes=10485760, backupCount=3)
		handler.setLevel(logging.DEBUG)

		formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
		handler.setFormatter(formatter)

		logger.addHandler(handler)
	except Exception as err:
		print(err)
	return logger, handler


def global_logger_cleanup(logger, handler, add_ = ''):
	# global handler
	handler.close()
	logger.removeHandler(handler)
	log = logging.getLogger('utils_logger' + add_)
	handlers = list(log.handlers)
	for handler in handlers:
		 log.removeHandler(handler)
		 handler.flush()
		 handler.close()