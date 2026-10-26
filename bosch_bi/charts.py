import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

BLUE='#007BC0'; NAVY='#173B57'; RED='#E20015'; TEAL='#20A4A0'

def polish(fig, height=350):
    fig.update_layout(height=height,margin=dict(l=8,r=12,t=20,b=8),paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',font=dict(family='Arial',size=12,color='#536779'),legend=dict(orientation='h',y=1.12,x=0),hovermode='x unified')
    fig.update_xaxes(showgrid=False,tickfont=dict(size=11))
    fig.update_yaxes(gridcolor='#E9EDF2',zeroline=False,tickfont=dict(size=11))
    return fig

def plot(fig,key,height=350):
    st.plotly_chart(polish(fig,height),width='stretch',key=key,config={'displayModeBar':False})

def combo(df, bars, lines, currency='', second_axis=False):
    f=go.Figure()
    colors=[BLUE,'#CBD5DF',TEAL,'#87C7E8']
    for i,col in enumerate(bars):
        f.add_trace(go.Bar(x=df.index,y=df[col],name=col,marker_color=colors[i%4],hovertemplate=currency+' %{y:,.0f}<extra>%{fullData.name}</extra>'))
    for i,col in enumerate(lines):
        f.add_trace(go.Scatter(x=df.index,y=df[col],name=col,mode='lines+markers',line=dict(color=[RED,TEAL][i%2],width=2.5,dash='solid' if second_axis else 'dash'),marker=dict(size=5),yaxis='y2' if second_axis else 'y'))
    f.update_layout(barmode='group',bargap=.27)
    if second_axis:f.update_layout(yaxis2=dict(overlaying='y',side='right',showgrid=False,ticksuffix='%'))
    return f

def donut(df,names,values,key):
    f=px.pie(df,names=names,values=values,hole=.76,color_discrete_sequence=[BLUE,NAVY,TEAL,'#89C8EA','#9CAFC0','#DAE5EF','#6B8EA8','#BAD9DD','#8593B5'])
    f.update_traces(textposition='outside',textinfo='label+percent',hovertemplate='%{label}: %{value:,.0f}<extra></extra>')
    f.update_layout(showlegend=False)
    plot(f,key,300)
