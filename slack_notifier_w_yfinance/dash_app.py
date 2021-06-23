''' Dash Frontend For Control 

Have a frontend to configure config.json without the need to login to the 
aws/gcp instance

'''

import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output, State
import plotly.express as px
import plotly.graph_objects as go

import yfinance as yf
import pytz
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import requests

from sklearn.linear_model import LinearRegression

from utils import midpoint_imputation, simple_lr, calculate_rsi, mult_rsi


external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']
app = dash.Dash(__name__, external_stylesheets=external_stylesheets)
colors = {
    'background': '#000000',
    'text': '#7FDBFF'
}
timezone_names = ['New York (GMT-5/GMT-4 DST)','Chicago (GMT-6/GMT-5 DST)',
                  'Denver (GMT-7/GMT-6 DST)','Los Angeles (GMT-8/GMT-7 DST)',
                  'Anchorage (GMT-9/GMT-8 DST)','Honolulu (GMT-10)']
# pytz_names = ['America/New_York','America/Chicago',
#               'America/Denver','America/Los_Angeles',
#               'America/Anchorage','America/Honolulu']
# timezones = zip(timezone_names, pytz_names)

is_dst = time.localtime().tm_isdst == 1 
if is_dst:
    adjust = list(map(str,reversed(range(-9,-4)))) + ['-10']
else:
    adjust = list(map(str,reversed(range(-8,-3)))) + ['-10']
timezones = zip(timezone_names, adjust)

## Page Layout
app.layout = html.Div(style={'backgroundColor': colors['background']}, children=[
    html.H1(
        children='RSI Notifier Visualizer',
        style={
            'textAlign': 'center',
            'color': colors['text']
        }
    ),
    html.Div(children=[
        html.Div(children=[
            html.Label("Symbol: ",
                style={
                       'color':colors['text']        
                       }
            ),
            dcc.Input(id='symbol', value='SPY', type='text')
        ]),
        html.Div(children=[
            html.Label("Graph Style ('Line' or 'Bar'): ",
                style={
                       'color':colors['text']        
                       }
            ),
            dcc.Input(id='graph-style', value='Bar', type='text')
        ]),
        html.Div(children=[
            html.Label("New Bar Size (minutes) [1,2,5,15,30]: ",
                style={
                      'color':colors['text']        
                      }
            ),
            dcc.Input(id='bar-size', value='5', type='text')
        ]),
        html.Div(children=[
            html.Label("Timezone: ",
                style={
                      'color':colors['text']        
                      }
            ),
            dcc.Dropdown(id='timezone', 
                         options = [{'label':i,'value':j} for i,j in timezones],
                         value='-4' if is_dst else '-5'
                        )
        ]),
        html.Div(
            html.Button(id='submit-button-state', n_clicks=0, children='Submit',
                style={
                       'margin-top':'5px',
                       'margin-bottom':'3px'
                       }
            )
        )],
        style={'margin-left':'2px'}
    ),

    # html.Div(id='output-state', style={
    #             'color':colors['text']        
    #         })
    dcc.Graph(id='output-state')
])

@app.callback(
    Output('output-state','figure'),
    Input('submit-button-state','n_clicks'), #n_clicks needed to update
    State('symbol','value'),
    State('graph-style','value'),
    State('bar-size','value'),
    State('timezone','value')
    )
def market_graph(button, symbol, graph_style, bar_size, timezone):
    timezone = int(timezone)
    adjust_hours = timedelta(hours = timezone)
    # send data info
    data_url = 'http://localhost' + ':8001/'
    params = {'symbol':symbol,
              'bar_size':bar_size
             }
    response = requests.get(url = data_url, params = params).json()

    assert str(response) == '200', 'Data did not load properly'

    params = {'cols':'Datetime,Open,High,Low,Close,pos,Midpoint'}
    data = requests.get(url = data_url + 'data', params = params).json()['data']
    data = pd.DataFrame(data)
    print(data.head())
    print(adjust_hours)
    data['Datetime'] = data['Datetime'].map(lambda x: \
                            datetime.fromtimestamp(x/1000., pytz.utc) + adjust_hours) #\
                            # .replace(tzinfo = pytz.timezone('America/New_York'))) #\
                            # .astimezone(pytz.timezone(timezone)))
    print(data.head())
    lr3 = three_pass_lr(data)


    # if graph_style == 'Line':
    #     fig = px.scatter(x = data['Datetime'], y = data['rsi'])
    if graph_style == 'Bar':
        fig = go.Figure(data=[go.Candlestick(x=data['Datetime'],
                open=data['Open'],
                high=data['High'],
                low=data['Low'],
                close=data['Close'])])
        y_trace = lr3.predict(data['pos'].values.reshape(-1,1))
        fig.add_trace(go.Scatter(x=data['Datetime'], y=y_trace,
                            mode='lines',
                            name='regression line',
                            marker_color='rgba(0,153,255,0.5)'))
    return fig


def three_pass_lr(df):
    # run lr three times to build a lr model with volatile points reduced

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
    lr3, m3, b3 = simple_lr(x, df2['Midpoint'])
    return lr3

if __name__ == '__main__':
    app.run_server(debug=True)
