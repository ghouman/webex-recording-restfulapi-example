"""                _
  __      _____| |__   _____  __
  \ \ /\ / / _ \ '_ \ / _ \ \/ /
   \ V  V /  __/ |_) |  __/>  <         @WebexDevs
    \_/\_/ \___|_.__/ \___/_/\_\

"""

# -*- coding:utf-8 -*-
from webbrowser import get
from dotenv import load_dotenv
import requests
import json
import os
import urllib.request


from flask import Flask, render_template, request, session

load_dotenv()

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

app = Flask(__name__)
app.secret_key = os.urandom(24)

clientID = os.getenv("APP_CLIENTID")
secretID = os.getenv("APP_SECRETID")
isDownload = os.getenv("IS_DOWNLOAD_BY_CODE")
localDownloadPath = os.getenv("LOCAL_DOWNLOAD_PATH")

redirectURI = os.getenv("REDIRECT_URI")  # This could be different if you publicly expose this endpoint.

baseApiUrl = "https://webexapis.com/v1/"

errormsg = ""
"""
Function Name : get_tokens
Description : This is a utility function that takes in the 
              Authorization Code as a parameter. The code 
              is used to make a call to the access_token end 
              point on the webex api to obtain a access token
              and a refresh token that is then stored as in the 
              Session for use in other parts of the app. 
              NOTE: in production, auth tokens would not be stored
              in a Session. This app will request a new token each time
              it runs which will not be able to check against expired tokens. 
"""


def get_tokens(code):
    print("function : get_tokens()")
    print("code:", code)
    # STEP 3 : use code in response from webex api to collect the code parameter
    # to obtain an access token or refresh token
    url = "https://webexapis.com/v1/access_token"
    headers = {'accept': 'application/json', 'content-type': 'application/x-www-form-urlencoded'}
    payload = ("grant_type=authorization_code&client_id={0}&client_secret={1}&"
               "code={2}&redirect_uri={3}").format(clientID, secretID, code, redirectURI)
    req = requests.post(url=url, data=payload, headers=headers)
    results = json.loads(req.text)
    print(results)
    access_token = results["access_token"]
    refresh_token = results["refresh_token"]

    session['oauth_token'] = access_token
    session['refresh_token'] = refresh_token

    print("Token stored in session : ", session['oauth_token'])
    print("Refresh Token stored in session : ", session['refresh_token'])
    return


"""
Function Name : get_tokens_refresh()
Description : This is a utility function that leverages the refresh token
              in exchange for a fresh access_token and refresh_token
              when a 401 is received when using an invalid access_token
              while making an api_call().
              NOTE: in production, auth tokens would not be stored
              in a Session. This app will request a new token each time
              it runs which will not be able to check against expired tokens. 
"""


def get_tokens_refresh():
    print("function : get_token_refresh()")

    url = "https://webexapis.com/v1/access_token"
    headers = {'accept': 'application/json', 'content-type': 'application/x-www-form-urlencoded'}
    payload = ("grant_type=refresh_token&client_id={0}&client_secret={1}&"
               "refresh_token={2}").format(clientID, secretID, session['refresh_token'])
    req = requests.post(url=url, data=payload, headers=headers)
    results = json.loads(req.text)

    access_token = results["access_token"]
    refresh_token = results["refresh_token"]

    session['oauth_token'] = access_token
    session['refresh_token'] = refresh_token

    print("Token stored in session : ", session['oauth_token'])
    print("Refresh Token stored in session : ", session['refresh_token'])
    return


"""
Function Name : main_page
Description : when using the browser to access server at
              http://127/0.0.1:10060 this function will 
              render the html file index.html. That file 
              contains the button that kicks off step 1
              of the Oauth process with the click of the 
              grant button
"""


@app.route("/")
def main_page():
    oauth_url = os.getenv("OAUTH_URL")
    """Main Grant page"""
    return render_template('index.html', oauthUrl=oauth_url)


"""
Function Name : oauth
Description : After the grant button is click from index.html
              and the user logs into thier Webex account, the 
              are redirected here as this is the html file that
              this function renders upon successful authentication
              is granted.html. else, the user is sent back to index.html
              to try again. This function retrieves the authorization
              code and calls get_tokens() for further API calls against
              the Webex API endpoints. 
"""


@app.route("/oauth")  # Endpoint acting as Redirect URI.
def oauth():
    print("function : oauth()")
    """Retrieves oauth code to generate tokens for users"""
    state = request.args.get("state")
    print('state : ' + state)
    if state == 'set_state_here':
        code = request.args.get("code")  # STEP 2 : Capture value of the
        # authorization code.
        print("OAuth code:", code)
        print("OAuth state:", state)
        get_tokens(code)
        return render_template("granted.html")
    else:
        return render_template("index.html")


"""
Funcion Name : spaces
Description : Now that we have our authentication code the spaces button
              on the granted page can leverage this function to get list 
              of spaces that the user behind the token is listed in. The
              Authentication Token is accessed via Session Key 'oauth_token'
              and used to construct the api call in authenticated mode. 
"""


@app.route("/spaces", methods=['GET'])
def spaces():
    print("function : spaces()")
    print("accessing token ...")
    url = "https://webexapis.com/v1/rooms"
    response = api_call(url)

    print("status code : ", response.status_code)
    # Do a check on the response. If the access_token is invalid then use refresh
    # tokent to ontain a new set of access token and refresh token.
    if (response.status_code == 401):
        get_tokens_refresh()
        response = api_call(url)

    r = response.json()['items']
    print("response status code : ", response.status_code)
    spaces = []
    for i in range(len(r)):
        spaces.append(r[i]['title'])

    return render_template("spaces.html", spaces=spaces)


@app.route("/recordings", methods=['GET'])
def recordings():
    print("function : recordings()")

    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    api_url = request.args.get("apiUrl")

    print("start_date." + start_date)
    print("end_date." + end_date)

    max_num = os.getenv("RECORDING_NUM")
    # api document: https://developer.webex.com/docs/api/v1/recordings, v1/admin/recordings api need admin or compliance officer role
    url = baseApiUrl + api_url + "?max=" + max_num + "&from=" + start_date + "&to=" + end_date
    response = api_call(url)
    recordings = []
    print("status code : ", response.status_code)
    # Do a check on the response. If the access_token is invalid then use refresh
    # tokent to ontain a new set of access token and refresh token.
    if response.status_code == 401:
        get_tokens_refresh()
        response = api_call(url)

    if response.status_code == 403:
        print("403 forbidden to request")
        errormsg = "403 forbidden to request:your account not have privilege to request this api"
        return render_template("granted.html", errormsg=errormsg)
    if 'errors' in response.json():
        errormsg = response.json()['errors'][0]["description"]
        print(errormsg)
        return render_template("granted.html", errormsg=errormsg)
    print("response status code : ", response.status_code)

    r = response.json()['items']
    for i in range(len(r)):
        getRecordingDetailsUrl = "https://webexapis.com/v1/recordings/" + r[i]['id']
        responseDetail = api_call(getRecordingDetailsUrl)
        if responseDetail.status_code == 200:
            recordingDetail = responseDetail.json()
            recordings.append(recordingDetail)
            if (isDownload == 'true') & ('temporaryDirectDownloadLinks' in recordingDetail.keys()):
                url = recordingDetail['temporaryDirectDownloadLinks']['recordingDownloadLink']
                filename: str = localDownloadPath + recordingDetail['topic'] + '.' + recordingDetail['format']
                urllib.request.urlretrieve(url, filename, lambda blocknum, blocksize, totalsize: callbackfunc(blocknum, blocksize, totalsize, filename))

    return render_template("recordings.html", recordings=recordings)


def callbackfunc(blocknum, blocksize, totalsize, filename):
    downloaded = round(blocknum * blocksize / 1024, 0)
    totalsize = round(totalsize / 1024, 0)
    percent = downloaded / totalsize * 100
    print(f"Downloaded {filename}: {downloaded} kb / {totalsize} kb ({percent:.2f}%)")
    if downloaded >= totalsize:
        print(f"Download of {filename} completed.")


def api_call(url):
    accessToken = session['oauth_token']

    headers = {'accept': 'application/json', 'Content-Type': 'application/json',
               'Authorization': 'Bearer ' + accessToken}
    response = requests.get(url=url, headers=headers)
    return response


if __name__ == '__main__':
    app.run("0.0.0.0", port=10060, debug=True)
