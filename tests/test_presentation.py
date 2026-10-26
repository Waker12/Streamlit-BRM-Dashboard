import re
import pandas as pd
import plotly.graph_objects as go
import pytest
from bosch_bi.presentation import number,numeric_display,numeric_columns,marketplace_theme,SHOPEE,LAZADA
from bosch_bi.charts import display_figure,combo
from streamlit.testing.v1 import AppTest
from pathlib import Path


def test_display_precision_leaves_data_and_ids_unchanged():
    source=pd.DataFrame({'Amount':pd.Series([57.919427,None],dtype=object),'SKU':['00123','00456'],'Orders':[68.,101.]})
    display=numeric_display(source)
    assert display.Amount.iloc[0]==source.Amount.iloc[0]
    assert display.SKU.tolist()==['00123','00456']
    assert set(numeric_columns(display))=={'Amount','Orders'}
    assert number(57.919427,2)=='57.92'
    assert number(57.919427,0)=='58'
    assert number(None,2)=='—'
    assert number(12.3,2,True)=='+12.30'


@pytest.mark.parametrize('places',[0,2])
@pytest.mark.parametrize('labels',[False,True])
def test_labels_precision_and_missing_values_across_chart_types(places,labels):
    figures=[
        go.Figure(go.Bar(x=['Jan','Feb'],y=[1234.56789,None])),
        go.Figure(go.Scatter(x=['Jan','Feb'],y=[1234.56789,None],mode='lines+markers')),
        go.Figure(go.Scattergl(x=[10,20],y=[12.345,None],mode='markers')),
        go.Figure(go.Pie(labels=['Shopee','Lazada'],values=[1234.56789,900])),
        go.Figure(go.Heatmap(x=['Jan'],y=['Shopee'],z=[[12.34567]])),
    ]
    for original in figures:
        shown=display_figure(original,places,labels)
        assert original.to_json()!=shown.to_json()
        trace=shown.data[0]
        assert f',.{places}f' in trace.hovertemplate
        if trace.type=='pie':
            assert (trace.textposition=='outside')==labels
            assert trace.values[0]==original.data[0].values[0]
        elif trace.type=='heatmap':
            assert bool(trace.texttemplate)==labels
            assert trace.z==original.data[0].z
        else:
            assert ('text' in (trace.mode or ''))==labels if trace.type!='bar' else (trace.textposition=='outside')==labels
            assert trace.y==original.data[0].y
        # Formatting returns a copy and never rounds source values.
        assert not original.data[0].hovertemplate


def test_marketplace_palette_and_secondary_axis():
    assert marketplace_theme('Shopee')[0]==SHOPEE
    assert marketplace_theme('Lazada')[0]==LAZADA
    source=pd.DataFrame({'Current':[100.123],'Previous year':[90.456],'CR %':[1.1234]})
    for platform,color in [('Shopee',SHOPEE),('Lazada',LAZADA)]:
        fig=combo(source,['Current','Previous year'],['CR %'],second_axis=True,marketplace=platform)
        shown=display_figure(fig,2,True)
        assert shown.data[0].marker.color==color
        assert shown.data[1].marker.color==marketplace_theme(platform)[1]
        assert shown.data[2].yaxis=='y2'
        assert shown.data[2].texttemplate.endswith('%')
        assert shown.layout.yaxis2.tickformat==',.2f'


def test_display_controls_apply_across_pages_and_preserve_chart_choices(tmp_path,monkeypatch):
    monkeypatch.setenv('BOSCH_BI_DB',str(tmp_path/'display.sqlite'))
    app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=60).run()
    assert not app.exception
    assert re.search(r'\.\d{2}$',app.metric[0].value)
    app.selectbox(key='decimal_places').set_value(0).run()
    assert not app.exception and not re.search(r'\.\d+$',app.metric[0].value)
    app.radio[0].set_value('Financial performance').run()
    app.toggle(key='default_chart_labels').set_value(True).run()
    assert app.toggle(key='chart_labels_financial_main').value is True
    app.toggle(key='chart_labels_financial_main').set_value(False).run()
    assert app.toggle(key='chart_labels_finance_cumulative').value is True
    app.radio[0].set_value('Executive overview').run()
    app.radio[0].set_value('Financial performance').run()
    assert app.toggle(key='chart_labels_financial_main').value is False
    app.toggle(key='default_chart_labels').set_value(False).run()
    assert app.toggle(key='chart_labels_finance_cumulative').value is False
    for places in [0,2]:
        app.selectbox(key='decimal_places').set_value(places).run()
        app.toggle(key='default_chart_labels').set_value(True).run()
        for page in ['Executive overview','Financial performance','Marketplace performance','Product & SKU','Conversion analysis','Advertising performance','BRM workbook','Data workspace']:
            app.radio[0].set_value(page).run()
            assert not app.exception,(places,page,[e.message for e in app.exception])
        app.toggle(key='default_chart_labels').set_value(False).run()
