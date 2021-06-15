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

import pandas as pd
import numpy as np
from flask import Flask, render_template, request
from flask import flash, redirect, session, abort


import logging
from logging.handlers import RotatingFileHandler
app = Flask(__name__)


parser = argparse.ArgumentParser()

parser.add_argument(
    '--port', type=int, default= 8000,
    help = 'What port to host API server on.')

parser.add_argument(
    '--file_dir', type=str, default= '',
    help = 'Where the config file and others are located.')

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
def update_page():
    # Update config file via POST request

    if True: #session.get('logged_in'):
        # print(request.args)
        # print(request.form)
        add_symbols = request.form.get('add_symbols')
        remove_symbols = request.form.get('remove_symbols')
        bar_size = request.form.get('bar_size')
        overbought = request.form.get('overbought')
        oversold = request.form.get('oversold')

        update_text = ''
        update_text = update_config(add_symbols, remove_symbols, 
                                        bar_size, overbought, oversold)

        # format for html
        format_symbols = config_['symbols'].split(',')
        # format_symbols = '<br>'.join(format_symbols)
        config_html = config_.copy()
        config_html['symbols'] = format_symbols 
        update_text = update_text.split('\n')
        config_html['update_text'] = update_text
        return render_template('update_page.html', variable=config_html)
    # else:
    #     return render_template('login.html')

@app.route('/login', methods=['POST'])
def do_admin_login():
    
    if request.form['password'] == app.secret_key:
        session['logged_in'] = True
    else:
        flash('wrong password!')
    return update_page()

def update_config(add_symbols, remove_symbols, bar_size, overbought, oversold):
    print_output = ''

    if add_symbols not in [None,'']:
        #maybe add space remover
        symbols = add_symbols.split(',')
        temp = config_['symbols'].split(',')
        temp.extend(symbols)
        temp = list(set(temp)) # remove duplicates
        temp.sort()
        config_['symbols'] = ','.join(temp)
        print_output += 'added ' + add_symbols + ' to list\n'
    if remove_symbols not in [None,'']:
        symbols = remove_symbols.split(',')
        temp = config_['symbols'].split(',')
        for symbol in symbols:
            if symbol in temp:
                temp.remove(symbol)
        config_['symbols'] = ','.join(temp)
        print_output += 'removed ' + remove_symbols + ' from list\n'
    if bar_size not in [None,'']:
        try:
            old_bar_size = config_['interval']
            bar_size = int(bar_size)
            config_['interval'] = str(bar_size) + 'm'
            print_output += 'changed bar size from ' + str(old_bar_size) \
                            + ' to ' + str(bar_size) + 'm\n'
        except Exception as e:
            print('bar_size inputi ncorrect: ' + str(e))
            print_output += 'New bar size input seems incorrect ("' \
                            + str(bar_size) + '"). Did not update.\n'
    if overbought not in [None,'']:
        try:
            old_overbought = config_['overbought_threshold']
            overbought = int(overbought)
            config_['overbought_threshold'] = str(overbought)
            print_output += ' changed overbought threshold from ' \
                                + str(old_bar_size) + ' to ' \
                                + str(bar_size) + '\n'
        except Exception as e:
            print(e)
            print_output += 'New overbought threshold input seems incorrect ("' \
                            + str(overbought) + '"). Did not update.\n'
    if oversold not in [None,'']:
        try:
            old_oversold = config_['oversold_threshold']
            oversold = int(oversold)
            config_['oversold_threshold'] = str(oversold)
            print_output += ' changed oversold threshold from ' \
                                + str(old_bar_size) + ' to ' + str(bar_size)
        except Exception as e:
            print(e)
            print_output += 'New oversold threshold input seems incorrect ("' \
                            + str(oversold) + '"). Did not update.'    
    with open(FLAGS.file_dir + '/config.conf','w') as out_:
        print(FLAGS.file_dir)
        json.dump(config_, out_)
    return print_output

if __name__ == '__main__':
    global work_dir, config_, FLAGS
    FLAGS, unparsed = parser.parse_known_args()

    main_dir = os.path.dirname(os.path.realpath(__file__))


    with open(FLAGS.file_dir + '/super_secure.txt','r') as in_:
        app.secret_key = in_.read()
    

    with open(FLAGS.file_dir + '/config.conf','r') as in_:
        config_ = json.load(in_)

    app.run(debug=True, port=FLAGS.port, host='0.0.0.0')