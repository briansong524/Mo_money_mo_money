import yfinance as yf
from pytz import timezone
import numpy as np

import pymysql as MySQLdb

import requests
import time
from datetime import datetime

import logging
from logging.handlers import RotatingFileHandler

from sklearn.linear_model import LinearRegression

## regular functions

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


## technical functions

def simple_lr(x,y):
    lr = LinearRegression(n_jobs = -1)
    lr.fit(x,y)
    
    return lr, lr.coef_[0], lr.intercept_

def calculate_epsilon(df, last_val_only = False):
	df['Midpoint'] = df[['Open','Close']].mean(axis = 1)
	df['pos'] = df['Datetime'].map(lambda x: (x - df['Datetime'].iloc[0]).total_seconds() / 60 / 60) # for linear regression
	df = df[df['Midpoint'].notna()].copy()

	## obtain epsilon 
	x = df['pos']
	lr1, m, b = simple_lr(np.array(x).reshape(-1, 1), df['Midpoint'])
	pred = lr1.predict(np.array(x).reshape(-1,1)) 
	df['prop_dist_1'] = (pred - df['Midpoint']).abs() / pred
	cutoff = np.percentile(df['prop_dist_1'], 65)
	cutoff2 = np.percentile(df['prop_dist_1'], 50)
	df = df[df['prop_dist_1'] < cutoff].copy()
	x = np.array(df['pos']).reshape(-1,1)
	lr2, m, b = simple_lr(x, df['Midpoint'])
	pred = lr2.predict(np.array(x).reshape(-1,1))
	df['prop_dist_2'] = (pred - df['Midpoint']).abs() / df['Midpoint']
	df2 = df[df['prop_dist_2'] < cutoff2].copy()
	x = np.array(df2['pos']).reshape(-1,1)
	lr3, m, b = simple_lr(x, df2['Midpoint'])
	pred = lr3.predict(df['pos'].values.reshape(-1,1))
	df['epsilon'] = df['Midpoint'] - pred
	epsilon = df['epsilon'].iloc[-1]
	if last_val_only:
		return epsilon
	else:
		return df

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

def mult_rsi(vals, n_int = 9, last_val_only = False):
	# given a sequential list of values, obtain the last [len(vals)-n_int] rsi 
	# vals expected to be a numpy array

	assert (len(vals) - 1) > n_int, "there needs to be more values than number of intervals (n_int)"

	rsi_list = []
	vals = vals[1:] - vals[:-1]
	
	# initialize starting values
	init_vals = vals[:n_int]
	prevU = np.sum(init_vals * (init_vals > 0).astype(int)) / 9
	prevD = -1 * np.sum(init_vals * (init_vals < 0).astype(int)) / 9

	# iterate through the rest of the values
	for i in range(n_int, len(vals)):
		rsi_, prevU, prevD = calculate_rsi(vals[i], prevU, prevD, n_int)
		rsi_list.append(rsi_)
	if last_val_only:
		return rsi_
	else:
		return rsi_list

def calculate_ema(new_val, last_ema, interval, smoothing):
    x = new_val*(smoothing / (1 + interval)) + last_ema*(1-(smoothing / (1 + interval)))
    return x

def calculate_macd(val, last_long_ema, last_short_ema,
                   long_int = 26, short_int = 12, smoothing = 2):
    
    long_ema = calculate_ema(val, last_long_ema, long_int, smoothing)
    short_ema = calculate_ema(val, last_short_ema, short_int, smoothing)
    macd = short_ema - long_ema
    return macd, long_ema, short_ema

def mult_macd(vals, long_int = 26, short_int = 12, 
			  signal_int = 9, smoothing = 2, last_val_only  = False):
	# given a sequential list of values, obtain the last
	# [len(vals) - long_int] macd and 
	# [len(vals) - long_int - signal_int] signals

	assert long_int > short_int, "long interval size needs to be greater than short interval size"
	assert len(vals) > (long_int + signal_int), "there needs to be more values for given interval sizes"

	# iteratively calculate macd
	macd_list = []
	long_ema = np.mean(vals[:long_int]) # simple average of first 26 values
	short_ema = np.mean(vals[(long_int - short_int):long_int]) # simple average of last 12 values from 26th index

	for i in range(long_int, len(vals)):
		macd, long_ema, short_ema = calculate_macd(vals[i], long_ema, short_ema, long_int, short_int, smoothing)
		macd_list.append(macd)

	# iterate through macd and calculate signal values
	vals = np.array(macd_list)
	ema = np.mean(vals[:signal_int]) # initialize ema
	signal_list = [ema]

	for i in range(signal_int, len(vals)):
		ema = calculate_ema(vals[i], ema, signal_int, smoothing)
		signal_list.append(ema)
	if last_val_only:
		return macd_list[-1], signal_list[-1]
	else:
		return macd_list, signal_list
	
def categorize_trend(x, high_val, low_val, as_color = False):
    if x >= high_val:
        if as_color:
            return 'g'
        else:
            return 'high'
    elif x <= low_val:
        if as_color:
            return 'r'
        else:
            return 'low'
    else:
        if as_color:
            return 'y'
        else:
            return 'normal'

def rsi_as_category(rsi, overbought, oversold):

	if rsi <= oversold:
		status = 'Oversold'
	elif rsi >= overbought:
		status = 'Overbought'
	else:
		status = 'Normal'
	return status

## notifier functions

def epoch_check_slack_gate(last_epoch):
	silence_time = 300 # 5 minutes
	if time.time() - last_epoch > silence_time:
		return True
	else:
		return False

def rsi_peak_check_slack_gate(max_min_rsi, rsi, status):
	# dont send redundant message if the rsi is less oversold/overbought when it previously was

	send_message = False
	try:
		if status == 'Oversold':
			if max_min_rsi[1] > rsi:
				send_message = True
		elif status == 'Overbought':
			if max_min_rsi[0] < rsi:
				send_message = True
	except:
		send_message = True
	finally:
		return send_message

## data functions

def midpoint_imputation(vals):
	# impute missing data with the midpoint of the two neighboring values
	# input expects a numpy array of shape (n,)
	# drop leading and tailing nans
	# if there are multiple na's in a row, impute the same midpoint for all
	edges = np.where(~np.isnan(vals))[0][[0,-1]]
	vals = vals[edges[0]:(edges[1]+1)]
	na_inds = np.where(np.isnan(vals))[0]
	for i in na_inds:
		if ~np.isnan(vals[i]):
			pass
		else:
			left = 1; right = 1
			while np.isnan(vals[i-left]):
				left += 1
			while np.isnan(vals[i+right]):
				right += 1
			vals[(i-left+1):(i+right)] = np.mean([vals[i-left],vals[i+right]])
	return vals