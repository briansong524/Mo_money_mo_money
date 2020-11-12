import pandas as pd
import pymysql as MySQLdb
import requests
import time
from utils import *


def main():
	conn_cred = {
				"dbservername":"localhost",
				"dbname":"main_schema",
				"dbuser":"minx",
				"dbpassword":"!xobILE!!!111!"
			}

	slack_hook = "https://hooks.slack.com/services/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"
	first_rsi = True
	message_sent = False
	while 1==1:

		query = 'SELECT * FROM {dbname}.bar_15min ORDER BY id DESC LIMIT 50'.format(dbname=conn_cred['dbname'])
		rows = run_query(conn_cred, query)
		df = pd.DataFrame(rows, columns = ['symbol','datetime','open','high','low','close','volume'])

		for symbol in ['AAPL','AMZN','GOOGL','TSLA']:
			try:
				df_part = df[df['symbol'] == symbol].head(9).copy()
				vals = (df_part['close'] - df_part['open']).values
				if first_rsi:
					rsi, prevU, prevD = rsi(vals) 
				else:
					if last_datetime == df['datetime'].iloc[0].values:
						rsi, _, _ = rsi(vals, prevU, prevD) 
					else:
						rsi, prevU, prevD = rsi(vals, prevU, prevD)
					
				last_datetime = df['datetime'].iloc[0].values

				# send slack message based on rsi
				if (rsi <= 20) | (rsi >= 80):
					text = symbol + ' hit RSI ' + str(rsi)
					requests.post(slack_hook, json = myobj)
					message_sent = True

			except:
				myobj = {"text":'something happened with ' + str(symbol)}
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
	main()