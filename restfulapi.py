r"""                _
  __      _____| |__   _____  __
  \ \ /\ / / _ \ '_ \ / _ \ \/ /
   \ V  V /  __/ |_) |  __/>  <         @WebexDevs
    \_/\_/ \___|_.__/ \___/_/\_\

"""

# -*- coding:utf-8 -*-
from dotenv import load_dotenv
import requests
import json
import os
import time
import urllib.request
from datetime import datetime, timedelta
from urllib.parse import urlsplit


from flask import Flask, render_template, request, session

load_dotenv()


def _token_url():
    # Derive the OAuth token endpoint from the host used by OAUTH_URL so that
    # the authorize and token requests target the same Webex environment
    # (e.g. integration.webexapis.com vs. webexapis.com).
    oauth_url = os.getenv("OAUTH_URL") or ""
    parts = urlsplit(oauth_url)
    if parts.scheme and parts.netloc:
        return f"{parts.scheme}://{parts.netloc}/v1/access_token"
    return "https://webexapis.com/v1/access_token"


def _api_base_url():
    # Use the same host as OAUTH_URL for API calls. Tokens issued by the
    # integration env are not valid against production and vice-versa.
    oauth_url = os.getenv("OAUTH_URL") or ""
    parts = urlsplit(oauth_url)
    if parts.scheme and parts.netloc:
        return f"{parts.scheme}://{parts.netloc}/v1/"
    return "https://webexapis.com/v1/"

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

app = Flask(__name__)
app.secret_key = os.urandom(24)

clientID = os.getenv("APP_CLIENTID")
secretID = os.getenv("APP_SECRETID")
isDownload = os.getenv("IS_DOWNLOAD_BY_CODE")
localDownloadPath = os.getenv("LOCAL_DOWNLOAD_PATH")

redirectURI = os.getenv("REDIRECT_URI")  # This could be different if you publicly expose this endpoint.

baseApiUrl = _api_base_url()

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
    url = _token_url()
    headers = {'accept': 'application/json', 'content-type': 'application/x-www-form-urlencoded'}
    payload = ("grant_type=authorization_code&client_id={0}&client_secret={1}&"
               "code={2}&redirect_uri={3}").format(clientID, secretID, code, redirectURI)
    req = requests.post(url=url, data=payload, headers=headers)
    results = json.loads(req.text)
    print(results)
    if "access_token" not in results:
        raise RuntimeError(f"Token exchange failed: {results}")
    access_token = results["access_token"]
    refresh_token = results["refresh_token"]

    session['oauth_token'] = access_token
    session['refresh_token'] = refresh_token

    print("Token stored in session : ", session['oauth_token'])
    print("Refresh Token stored in session : ", session['refresh_token'])


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

    url = _token_url()
    headers = {'accept': 'application/json', 'content-type': 'application/x-www-form-urlencoded'}
    payload = ("grant_type=refresh_token&client_id={0}&client_secret={1}&"
               "refresh_token={2}").format(clientID, secretID, session['refresh_token'])
    req = requests.post(url=url, data=payload, headers=headers)
    results = json.loads(req.text)

    if "access_token" not in results:
        raise RuntimeError(f"Token refresh failed: {results}")
    access_token = results["access_token"]
    refresh_token = results["refresh_token"]

    session['oauth_token'] = access_token
    session['refresh_token'] = refresh_token

    print("Token stored in session : ", session['oauth_token'])
    print("Refresh Token stored in session : ", session['refresh_token'])


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
    r = []
    recordings = []

    response = api_call_recording(url, r)

    if isinstance(response, list):
        r = response
    else:
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

def api_call_recording(url, array=None):
    accessToken = session['oauth_token']

    headers = {'accept': 'application/json', 'Content-Type': 'application/json',
               'Authorization': 'Bearer ' + accessToken}
    response = requests.get(url=url, headers=headers)
    if response.status_code == 200:
        if not array:
            array = response.json().get('items', [])
        else:
            array += response.json().get('items', [])
        next_link = None
        if 'Link' in response.headers:
            links = response.headers['Link'].split(',')
            for link in links:
                if 'rel="next"' in link:
                    next_link = link[link.index('<')+1:link.index('>')]  # 提取链接URL
                    break

        if next_link:
            api_call_recording(next_link, array)
        return array
    else:
        return response


"""
Function Name : api_delete
Description : Issue an authenticated HTTP DELETE call. Refreshes the access
              token once on a 401 response and retries (mirrors api_call()).
"""


def api_delete(url, json_body=None, form_body=None):
    accessToken = session['oauth_token']
    headers = {'accept': 'application/json',
               'Authorization': 'Bearer ' + accessToken}
    if form_body is not None:
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
        response = requests.delete(url=url, headers=headers, data=form_body)
    else:
        headers['Content-Type'] = 'application/json'
        response = requests.delete(url=url, headers=headers, json=json_body)
    if response.status_code == 401:
        get_tokens_refresh()
        accessToken = session['oauth_token']
        headers['Authorization'] = 'Bearer ' + accessToken
        if form_body is not None:
            response = requests.delete(url=url, headers=headers, data=form_body)
        else:
            response = requests.delete(url=url, headers=headers, json=json_body)
    return response


def api_post(url, json_body=None):
    accessToken = session['oauth_token']
    headers = {'accept': 'application/json',
               'Content-Type': 'application/json',
               'Authorization': 'Bearer ' + accessToken}
    response = requests.post(url=url, headers=headers, json=json_body)
    if response.status_code == 401:
        get_tokens_refresh()
        headers['Authorization'] = 'Bearer ' + session['oauth_token']
        response = requests.post(url=url, headers=headers, json=json_body)
    return response


"""
Function Name : bulk_soft_delete_converged_recordings
Description : POST /v1/convergedRecordings/softDelete — moves up to 100
              recordings into the recycle bin in a single call.
              Returns (ok, status, body).
"""


def bulk_soft_delete_converged_recordings(recording_ids):
    url = baseApiUrl + "convergedRecordings/softDelete"
    payload = {"recordingIds": recording_ids, "trashAll": False}
    print(f"[bulk_soft_delete] POST {url} count={len(recording_ids)}")
    response = api_post(url, json_body=payload)
    ok = 200 <= response.status_code < 300
    try:
        body = response.json()
    except Exception:
        body = response.text
    if not ok:
        print(f"[bulk_soft_delete] FAILED status={response.status_code} body={body}")
    return ok, response.status_code, body


"""
Function Name : bulk_purge_converged_recordings_api
Description : POST /v1/convergedRecordings/purge — permanently purges up to
              100 recordings from the recycle bin in a single call.
              Returns (ok, status, body).
"""


def bulk_purge_converged_recordings_api(recording_ids):
    url = baseApiUrl + "convergedRecordings/purge"
    payload = {"recordingIds": recording_ids, "purgeAll": False}
    print(f"[bulk_purge] POST {url} count={len(recording_ids)}")
    response = api_post(url, json_body=payload)
    ok = 200 <= response.status_code < 300
    try:
        body = response.json()
    except Exception:
        body = response.text
    if not ok:
        print(f"[bulk_purge] FAILED status={response.status_code} body={body}")
    return ok, response.status_code, body


"""
Function Name : list_converged_recordings
Description : List a single page of your org's converged recordings via
              GET /v1/admin/convergedRecordings within the
              [from_iso, to_iso] window. Returns (items, error_msg).
              The Webex platform constrains the window to <= 1 year.
              Requires Admin or Compliance Officer role.
"""


def list_converged_recordings(from_iso, to_iso, max_num=100):
    url = (baseApiUrl + "admin/convergedRecordings"
           + "?max=" + str(max_num)
           + "&status=available"
           + "&from=" + from_iso
           + "&to=" + to_iso)
    print(f"[list_converged_recordings] GET {url}")
    response = api_call(url)
    if response.status_code == 401:
        get_tokens_refresh()
        response = api_call(url)
    if response.status_code != 200:
        try:
            body = response.json()
        except Exception:
            body = response.text
        return [], f"List failed (HTTP {response.status_code}): {body}"
    return response.json().get('items', []) or [], None


"""
Function Name : delete_converged_recording
Description : Delete a single converged recording by id, via
              DELETE /v1/convergedRecordings/{id}. Returns (ok, status, body).
"""


def delete_converged_recording(recording_id):
    # Compliance Officer delete requires reason/comment in the JSON request body.
    payload = {"reason": "audit", "comment": "bulk delete by code"}
    url = baseApiUrl + "convergedRecordings/" + recording_id
    print(f"[delete_converged_recording] DELETE {url} payload={payload}")
    response = api_delete(url, json_body=payload)
    # 404 means the recording is already gone — treat as success (idempotent).
    # The Webex list endpoint is eventually consistent, so re-list passes often
    # return ids we just deleted.
    ok = (200 <= response.status_code < 300) or response.status_code == 404
    try:
        body = response.json()
    except Exception:
        body = response.text
    if not ok:
        print(f"[delete_converged_recording] FAILED status={response.status_code} body={body}")
    return ok, response.status_code, body


@app.route("/purge_converged_recordings", methods=['GET'])
def purge_converged_recordings():
    """
    Bulk-delete your org's converged recordings that were created on or
    before `cutoff_date`.

    Strategy (user needs Compliance Officer role to use this endpoint):
      1. List your org's converged recordings via
         GET /v1/admin/convergedRecordings using a 30-day window
         [from, cutoff]. The admin endpoint requires the interval between
         `from` and `to` to be within 30 days.
      2. Delete every returned recording one by one
         (DELETE /v1/convergedRecordings/{id}).
      3. Re-list. Repeat until the list comes back empty.
      4. Walk the window back one more month and repeat, so older
         recordings are also purged (controlled by `months_back`, default 60
         = 5 years).

    Query params:
      cutoff_date  : ISO date (YYYY-MM-DD). Required. Default 2025-01-01.
      months_back  : how many 30-day windows to walk back from cutoff
                     (default 12; covers ~1 year of history).
      max_loops    : safety cap on the inner list+delete loop per window
                     (default 50, in case the API keeps returning items).
    """
    cutoff_date = request.args.get("cutoff_date", "2025-01-01")
    months_back = int(request.args.get("months_back", "12"))
    max_loops = int(request.args.get("max_loops", "50"))

    try:
        cutoff_dt = datetime.strptime(cutoff_date, "%Y-%m-%d")
    except ValueError:
        return render_template(
            "granted.html",
            errormsg=f"Invalid cutoff_date '{cutoff_date}'. Expected YYYY-MM-DD."
        )

    report = {
        "cutoff_date": cutoff_date,
        "months_back": months_back,
        "windows": [],
        "total_deleted": 0,
        "total_failed": 0,
    }

    # Walk backward in 30-day windows. The Webex admin endpoint requires
    # the interval between `from` and `to` to be within 30 days.
    window_end = cutoff_dt
    for window_idx in range(months_back):
        window_start = window_end - timedelta(days=30)
        from_iso = window_start.strftime("%Y-%m-%dT00:00:00Z")
        to_iso = window_end.strftime("%Y-%m-%dT23:59:59Z")

        window_report = {
            "from": from_iso, "to": to_iso,
            "iterations": 0, "deleted": 0, "failed": 0, "failures": [],
        }

        # Inner loop: list -> delete each -> re-list, until list is empty.
        for loop_idx in range(max_loops):
            window_report["iterations"] += 1
            items, err = list_converged_recordings(from_iso, to_iso, max_num=100)
            if err:
                window_report["failures"].append({"phase": "list", "error": err})
                break
            if not items:
                # List is empty -> this window is fully purged.
                break

            print(f"[purge] window {window_idx+1}/{months_back} "
                  f"loop {loop_idx+1}: {len(items)} recordings to delete")

            deleted_this_pass = 0
            for it in items:
                rec_id = it.get("id")
                if not rec_id:
                    continue
                ok, status, body = delete_converged_recording(rec_id)
                if ok:
                    window_report["deleted"] += 1
                    deleted_this_pass += 1
                else:
                    window_report["failed"] += 1
                    window_report["failures"].append({
                        "phase": "delete",
                        "id": rec_id,
                        "topic": it.get("topic", ""),
                        "status": status,
                        "body": body,
                    })
                # Small pause to be gentle on the API.
                time.sleep(0.1)

            # Guard against an infinite loop when the server keeps returning
            # items we cannot actually delete (e.g. 403/405). If a full pass
            # made no progress, stop iterating this window.
            if deleted_this_pass == 0:
                print(f"[purge] window {window_idx+1}/{months_back}: "
                      f"no recordings deleted this pass, aborting window to "
                      f"avoid infinite loop")
                break

        report["windows"].append(window_report)
        report["total_deleted"] += window_report["deleted"]
        report["total_failed"] += window_report["failed"]

        # Shift window earlier by 30 days (1 second to avoid overlap).
        window_end = window_start - timedelta(seconds=1)

    print(f"[purge] DONE — total_deleted={report['total_deleted']} "
          f"total_failed={report['total_failed']}")
    return render_template("purge_result.html", report=report,
                           report_json=json.dumps(report, indent=2, default=str))


@app.route("/bulk_purge_converged_recordings", methods=['GET'])
def bulk_purge_converged_recordings_route():
    """
    Fast bulk-delete of converged recordings using the batch endpoints:
      POST /v1/convergedRecordings/softDelete  (up to 100 ids / call)
      POST /v1/convergedRecordings/purge       (up to 100 ids / call)

    For each 30-day window walking back from `cutoff_date`:
      1. List recordings via GET /v1/admin/convergedRecordings
         (status=available, max=100).
      2. softDelete the page in one call (moves them to the recycle bin).
      3. If purge_after=true (default), purge the same ids in one call
         (permanently removes them from the recycle bin).
      4. Re-list and repeat until the window is empty.

    Query params:
      cutoff_date  : YYYY-MM-DD. Required. Default 2025-01-01.
      months_back  : how many 30-day windows to walk back (default 12).
      max_loops    : safety cap on list+batch loops per window (default 50).
      purge_after  : "true"/"false" — also purge from recycle bin
                     (default "true"). If false, recordings are only moved
                     to the recycle bin and can still be restored.
    """
    cutoff_date = request.args.get("cutoff_date", "2025-01-01")
    months_back = int(request.args.get("months_back", "12"))
    max_loops = int(request.args.get("max_loops", "50"))
    purge_after = request.args.get("purge_after", "true").lower() == "true"

    try:
        cutoff_dt = datetime.strptime(cutoff_date, "%Y-%m-%d")
    except ValueError:
        return render_template(
            "granted.html",
            errormsg=f"Invalid cutoff_date '{cutoff_date}'. Expected YYYY-MM-DD."
        )

    report = {
        "cutoff_date": cutoff_date,
        "months_back": months_back,
        "purge_after": purge_after,
        "mode": "bulk (softDelete + purge)" if purge_after else "bulk (softDelete only)",
        "windows": [],
        "total_deleted": 0,
        "total_failed": 0,
    }

    window_end = cutoff_dt
    for window_idx in range(months_back):
        window_start = window_end - timedelta(days=30)
        from_iso = window_start.strftime("%Y-%m-%dT00:00:00Z")
        to_iso = window_end.strftime("%Y-%m-%dT23:59:59Z")

        window_report = {
            "from": from_iso, "to": to_iso,
            "iterations": 0, "deleted": 0, "failed": 0, "failures": [],
        }

        for loop_idx in range(max_loops):
            window_report["iterations"] += 1
            items, err = list_converged_recordings(from_iso, to_iso, max_num=100)
            if err:
                window_report["failures"].append({"phase": "list", "error": err})
                break
            if not items:
                break

            ids = [it.get("id") for it in items if it.get("id")]
            if not ids:
                break

            print(f"[bulk_purge] window {window_idx+1}/{months_back} "
                  f"loop {loop_idx+1}: {len(ids)} recordings to softDelete"
                  f"{' + purge' if purge_after else ''}")

            ok_sd, st_sd, body_sd = bulk_soft_delete_converged_recordings(ids)
            if not ok_sd:
                window_report["failed"] += len(ids)
                window_report["failures"].append({
                    "phase": "softDelete", "status": st_sd, "body": body_sd,
                    "count": len(ids),
                })
                # Avoid spinning on the same page if softDelete keeps failing.
                break

            if purge_after:
                ok_pg, st_pg, body_pg = bulk_purge_converged_recordings_api(ids)
                if not ok_pg:
                    window_report["failed"] += len(ids)
                    window_report["failures"].append({
                        "phase": "purge", "status": st_pg, "body": body_pg,
                        "count": len(ids),
                    })
                    break

            window_report["deleted"] += len(ids)
            # Be gentle on the API between batches.
            time.sleep(0.2)

        report["windows"].append(window_report)
        report["total_deleted"] += window_report["deleted"]
        report["total_failed"] += window_report["failed"]

        window_end = window_start - timedelta(seconds=1)

    print(f"[bulk_purge] DONE — total_deleted={report['total_deleted']} "
          f"total_failed={report['total_failed']}")
    return render_template("purge_result.html", report=report,
                           report_json=json.dumps(report, indent=2, default=str))


if __name__ == '__main__':
    app.run("0.0.0.0", port=10060, debug=True)
