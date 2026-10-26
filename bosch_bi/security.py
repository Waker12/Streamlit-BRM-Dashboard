"""Optional owner-password gate; required by the supplied hosting configuration."""
import hashlib
import hmac
import os
import streamlit as st


def setting(name, default=''):
    value=os.environ.get(name)
    if value is not None:return value
    try:return str(st.secrets.get(name,default))
    except st.errors.StreamlitSecretNotFoundError:return default


def require_access():
    if setting('BOSCH_BI_REQUIRE_AUTH','1').lower() not in {'1','true','yes'}:return
    expected=setting('BOSCH_BI_PASSWORD')
    if not expected:
        st.error('Access is locked. Configure the owner password in the hosting secrets.');st.stop()
    fingerprint=hashlib.sha256(expected.encode()).hexdigest()
    if hmac.compare_digest(st.session_state.get('owner_auth',''),fingerprint):
        if st.sidebar.button('Sign out',key='owner_signout'):
            st.session_state.pop('owner_auth',None);st.rerun()
        return
    st.title('Bosch Commerce Intelligence')
    st.caption('Private reporting workspace · owner access')
    with st.form('owner_login',clear_on_submit=True):
        password=st.text_input('Password',type='password')
        submitted=st.form_submit_button('Sign in')
    if submitted:
        if hmac.compare_digest(password.encode(),expected.encode()):
            st.session_state['owner_auth']=fingerprint;st.rerun()
        else:st.error('Incorrect password.')
    st.stop()
