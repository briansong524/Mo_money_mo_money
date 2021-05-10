''' Dash Frontend For Control 

Have a frontend to configure config.json without the need to login to the 
aws/gcp instance

'''

import dash
import dash_core_components as dcc
import dash_html_components as html

app = dash.Dash()
colors = {
    'background': '#000000',
    'text': '#7FDBFF'
}
app.layout = html.Div(style={'backgroundColor': colors['background']}, children=[
    html.H1(
        children='RSI Notifier Configuration',
        style={
            'textAlign': 'center',
            'color': colors['text']
        }
    ),
    html.Div(children=[
        html.Label("Add Symbols: ",
            style={
                'color':colors['text']        
            }),
        dcc.Input(value='', type='text')
    ]),
    html.Div(children=[
        html.Label("Remove Symbols: ",
            style={
                'color':colors['text']        
            }),
        dcc.Input(value='', type='text')
    ])
])

if __name__ == '__main__':
    app.run_server(debug=True)
