import re
from numbers import Real
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st
from .presentation import MARKETPLACE_COLORS, marketplace_theme

BLUE='#007BC0'; NAVY='#173B57'; RED='#E20015'; TEAL='#20A4A0'
DISPLAY_API_VERSION=1


def polish(fig, height=350):
    fig.update_layout(height=height,margin=dict(l=8,r=12,t=30,b=12),paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',font=dict(family='Arial',size=12,color='#536779'),legend=dict(orientation='h',y=1.15,x=0),hovermode='x unified')
    fig.update_xaxes(showgrid=False,tickfont=dict(size=11))
    fig.update_yaxes(gridcolor='#E9EDF2',zeroline=False,tickfont=dict(size=11))
    return fig


def display_figure(fig, places=2, labels=False):
    """Apply one precision/label policy to every chart without altering values."""
    fig=go.Figure(fig)
    numeric_format=f',.{places}f'
    fig.update_yaxes(tickformat=numeric_format,hoverformat=numeric_format)
    for trace in fig.data:
        if trace.type=='pie':
            trace.textinfo='none'
            trace.texttemplate=(f'%{{label}}<br>%{{value:{numeric_format}}} · %{{percent:.{places}%}}' if labels else '')
            trace.textposition='outside' if labels else 'none'
            trace.hovertemplate=f'%{{label}}: %{{value:{numeric_format}}} (%{{percent:.{places}%}})<extra></extra>'
            fig.update_layout(showlegend=True)
        elif trace.type=='heatmap':
            trace.texttemplate=f'%{{z:{numeric_format}}}' if labels else ''
            trace.hovertemplate=f'%{{x}}<br>%{{y}}: %{{z:{numeric_format}}}<extra></extra>'
            fig.update_layout(coloraxis_colorbar_tickformat=numeric_format)
        elif trace.type in ('bar','scatter','scattergl'):
            axis=fig.layout['yaxis2' if trace.yaxis=='y2' else 'yaxis']
            suffix=axis.ticksuffix or ('%' if '%' in (trace.name or '') else '')
            template=trace.hovertemplate or '%{x}<br>%{fullData.name}: %{y}<extra></extra>'
            trace.hovertemplate=re.sub(r'%\{(y|z|value)(?::[^}]*)?\}',lambda m:'%{'+m[1]+':'+numeric_format+'}',template)
            if trace.type=='scattergl':
                from .presentation import number
                trace.text=[number(v,places)+suffix if labels and v is not None else '' for v in trace.y]
            else:trace.texttemplate=f'%{{y:{numeric_format}}}{suffix}' if labels else ''
            if trace.type=='bar':
                trace.textposition='outside' if labels else 'none'
                trace.cliponaxis=False
            else:
                modes=[part for part in (trace.mode or 'lines').split('+') if part!='text']
                trace.mode='+'.join(modes+(['text'] if labels else []))
                trace.textposition='top center'
                if trace.x is not None and len(trace.x) and all(isinstance(v,Real) for v in trace.x):
                    trace.hovertemplate=re.sub(r'%\{x(?::[^}]*)?\}',f'%{{x:{numeric_format}}}',trace.hovertemplate)
                    fig.update_xaxes(tickformat=numeric_format,hoverformat=numeric_format)
    if labels:fig.update_layout(margin=dict(t=55),uniformtext=dict(minsize=9,mode='hide'))
    return fig


def _remember_labels(key):
    st.session_state.setdefault('chart_label_preferences',{})[key]=st.session_state['chart_labels_'+key]


def plot(fig,key,height=350):
    prefs=st.session_state.setdefault('chart_label_preferences',{})
    enabled=st.toggle('Data labels',value=prefs.get(key,st.session_state.get('default_chart_labels',False)),key='chart_labels_'+key,on_change=_remember_labels,args=(key,),help='Show or hide values on this chart. Set the default for all charts in sidebar Display settings.')
    fig=display_figure(polish(fig,height),st.session_state.get('decimal_places',2),enabled)
    st.plotly_chart(fig,width='stretch',key=key,config={'displayModeBar':False})


def combo(df, bars, lines, currency='', second_axis=False, marketplace=None):
    f=go.Figure()
    colors=marketplace_theme(marketplace or st.session_state.get('marketplace'))
    for i,col in enumerate(bars):
        color=colors[1] if any(word in col.lower() for word in ['previous','prior','py ']) else colors[0]
        f.add_trace(go.Bar(x=df.index,y=df[col],name=col,marker_color=color,hovertemplate=currency+' %{y}<extra>%{fullData.name}</extra>'))
    for i,col in enumerate(lines):
        f.add_trace(go.Scatter(x=df.index,y=df[col],name=col,mode='lines+markers',line=dict(color=colors[2+i%2],width=2.5,dash='solid' if second_axis else 'dash'),marker=dict(size=5),yaxis='y2' if second_axis else 'y'))
    f.update_layout(barmode='group',bargap=.27)
    if second_axis:f.update_layout(yaxis2=dict(overlaying='y',side='right',showgrid=False,ticksuffix='%'))
    return f


def donut(df,names,values,key):
    palette=marketplace_theme(st.session_state.get('marketplace'))
    f=px.pie(df,names=names,values=values,hole=.72,color=names,color_discrete_map=MARKETPLACE_COLORS if names=='marketplace' else None,color_discrete_sequence=palette+[TEAL,'#9CAFC0','#6B8EA8','#BAD9DD','#8593B5'])
    f.update_layout(showlegend=True)
    plot(f,key,330)

