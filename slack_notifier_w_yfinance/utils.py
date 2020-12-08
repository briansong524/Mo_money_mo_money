import yfinance as yf
from pytz import timezone
import numpy as np

import pymysql as MySQLdb

import time
from datetime import datetime

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