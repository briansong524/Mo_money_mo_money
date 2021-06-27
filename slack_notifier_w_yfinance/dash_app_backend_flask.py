import os
import sys
import traceback
import time
if sys.version_info[0] == 2:
    import thread
else:
    import _thread as thread

import json
import argparse
from datetime import datetime

import pandas as pd
import numpy as np
from flask import Flask, render_template, request
from flask import flash, redirect, session, abort
import yfinance as yf

import logging
from logging.handlers import RotatingFileHandler

from utils import midpoint_imputation, simple_lr, calculate_rsi, mult_rsi

app = Flask(__name__)


parser = argparse.ArgumentParser()

parser.add_argument(
    '--port', type=int, default= 8001,
    help = 'What port to host API server on.')

################### logger config ###################
global handler, logger, console_handler
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler('app_client.log', maxBytes=10485760, backupCount=5)
handler.setLevel(logging.DEBUG)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
console_handler.setFormatter(formatter)
logger.addHandler(handler)
logger.addHandler(console_handler)
#####################################################

@app.route('/heart-beat', methods=['GET'])
def run_heart_beat_check():  
    status_object = {'status':'alive'}
    response = app.response_class(
        response=json.dumps(status_object),
        status=200,
        mimetype='application/json'
    )
    return response

@app.route('/', methods = ['GET','POST'])
def data_load():
    global data_global
    # load dataset via POST request
    try:
        print(request.args)
        # print(request.form)
        symbol = request.args.get('symbol')
        bar_size = request.args.get('bar_size')
        try:
            print(data_global['Datetime'][-1])
            diff = datetime.now().timestamp() - data_global['Datetime'][-1]/1000
            print('# seconds since last download: ' + str(diff))
            diff = 1e7 #for testing
        except Exception as e:
            print('Exception in checking time: ' + str(e))
            diff = 1e7
        if diff < int(bar_size)*60.:
            return '200' 
        else:

            ticker = str(symbol)
            interval = str(bar_size) + 'm'
            period = period_by_barsize(int(bar_size))
            data = yf.download(tickers = ticker, period = period, interval = interval, 
                                group_by = 'ticker', prepost = True).reset_index()
            data = data_expand(data)

            # rsi
            n = 14
            rows = data['Close'].values
            rows = midpoint_imputation(rows)
            rsi_list = mult_rsi(rows, n)

            # modify shape to match indices with original data
            rsi_list_modified = [-1] * (data.shape[0] - len(rsi_list)) + rsi_list
            data['rsi'] = np.array(rsi_list_modified)
            print(data.head(10))
            data_as_json = data.to_json(orient='split')
            data_as_json = eval(data_as_json)
            vals_as_cols = zip(*data_as_json['data'])
            data_global = {}
            for i in data_as_json['columns']:
                data_global[i] = next(vals_as_cols)
            return '200'
    except Exception as err:
        type_, value_, traceback_ = sys.exc_info()
        tb = traceback.format_exception(type_, value_, traceback_)
        err_string = ' '.join(tb) + '\nException in getting data: ' + repr(err)
        print(err_string)
        return '400'

@app.route('/data', methods = ['GET'])
def get_data():
    cols = str(request.args.get('cols'))

    out_ = {}
    for i in cols.split(','):
        out_[i] = data_global[i]

    return {'data':out_}

def period_by_barsize(bar_size):
    if bar_size <= 5:
        return '1d'
    elif bar_size in [15,30]:
        return '5d'
    else:
        return '1mo'

def data_expand(df):
    df['Upper'] = df[['Open','Close']].max(axis = 1)
    df['Lower'] = df[['Open','Close']].min(axis = 1)
    df['Midpoint'] = df[['Open','Close']].mean(axis = 1)
    
    # fix anomalous high/low prices
    const = 5 # range of open/close
    diff = df['Open'].sub(df['Close']).abs()
    ceil = df['Upper'].add(const*diff)
    flr = df['Lower'].sub(const*diff)
    df['High'] = pd.concat([df['High'],ceil], axis = 1).min(axis = 1)
    df['Low'] = pd.concat([df['Low'],flr], axis = 1).max(axis = 1)

    
    vals = df['Datetime']
    v1 = vals.iloc[1:]
    v2 = vals.iloc[:-1]
    vals = list(map(lambda i: (v1.iloc[i]-v2.iloc[i]).total_seconds() / 60. / 60., range(len(v1))))
    vals = [0] + vals
    df['New Day'] = list(map(lambda x: x > 0.25, vals)); df['New Day'] = df['New Day'].astype(int)
    df['pos'] = df['Datetime'].map(lambda x: (x - df['Datetime'].iloc[0]).total_seconds() / 60 / 60) # for linear regression
    return df




if __name__ == '__main__':
    global data
    FLAGS, unparsed = parser.parse_known_args()
    app.run(debug=True, port=FLAGS.port, host='0.0.0.0')