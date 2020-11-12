import pandas as pd
import numpy as np
import pymysql as MySQLdb
import requests
import time
from utils import *
import argparse

parser = argparse.ArgumentParser()

parser.add_argument(
	'--slack_webhook', type=str, default='/home/minx/Documents/slack_webhook.txt',
	help = 'Text file with slack webhook link.')



def main(FLAGS):
	conn_cred = {
				"dbservername":"localhost",
				"dbname":"main_schema",
				"dbuser":"minx",
				"dbpassword":"!xobILE!!!111!"
			}

	with open(FLAGS.slack_webhook,'r') as txt:
		slack_hook = txt.read()

	first_rsi = True
	message_sent = False
	while 1==1:

		query = "WITH amzn AS ( \
				select * from {dbname}.bar_15min where symbol = 'AMZN' order by datetime_rounded desc limit 9 \
				), \
				aapl as ( \
				select * from {dbname}.bar_15min where symbol = 'AAPL' order by datetime_rounded desc limit 9 \
				), \
				tsla as ( \
				select * from {dbname}.bar_15min where symbol = 'TSLA' order by datetime_rounded desc limit 9 \
				), \
				googl as ( \
				select * from {dbname}.bar_15min where symbol = 'GOOGL' order by datetime_rounded desc limit 9 \
				) \
				SELECT * FROM amzn \
				UNION  \
				SELECT * FROM aapl \
				UNION \
				SELECT * FROM tsla \
				UNION \
				SELECT * FROM googl".format(dbname=conn_cred['dbname'])
		rows = run_query(conn_cred, query)
		df = pd.DataFrame(rows, columns = ['symbol','datetime','open','close','high','low','volume'])

		for symbol in ['AAPL','AMZN','GOOGL','TSLA']:
			try:
				df_part = df[df['symbol'] == symbol].copy()
				if df_part.shape[0] != 0:
					vals = (df_part['close'] - df_part['open']).values
					print(vals)
					if first_rsi:
						rsi_, prevU, prevD = rsi(vals) 
						first_rsi = False
						print('first rsi calculated: ' + str(rsi_))
					else:
						if last_datetime == df['datetime'].iloc[0].values:
							rsi_, _, _ = rsi(vals, prevU, prevD) 
							# print(rsi_)
						else:
							print('rsi @ ' + str(last_datetime) + ' = ' + str(rsi_))
							rsi_, prevU, prevD = rsi(vals, prevU, prevD)
						
					last_datetime = df['datetime'].iloc[0].values

					# send slack message based on rsi
					if (rsi_ <= 20) | (rsi_ >= 80):
						text = symbol + ' hit RSI ' + str(rsi_)
						requests.post(slack_hook, json = myobj)
						message_sent = True

			except Exception as e:
				myobj = {"text":'something happened with ' + str(symbol) + ": " + str(e)}
				requests.post(slack_hook, json = myobj)


		# suppress slack messages for five minute if a message was sent
		if message_sent:
			time.sleep(300)
			message_sent = False
		else:
			time.sleep(5)

def rsi(vals, prevU = 0, prevD = 0, n = 9):
	alpha = 2 / (n+1) # exponential method
	U = np.sum(vals * (vals > 0).astype(int)) / n
	D = -1 * np.sum(vals * (vals < 0).astype(int)) / n
	avgU = alpha * U + (1 - alpha) * prevU
	avgD = alpha * D + (1 - alpha) * prevD

	prevU = avgU
	prevD = avgD
	rs = avgU / avgD
	rsi = 100.0 - 100.0 / (1 + rs)
	return rsi, prevU, prevD


if __name__ == '__main__':
	FLAGS, unparsed = parser.parse_known_args()
	main(FLAGS)