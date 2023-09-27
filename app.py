import os
import json
import time
import requests
import base64
import hmac
import hashlib

PROFILES_ENDPOINT = "https://a.klaviyo.com/api/profiles/"
LIST_ENDPOINT = "https://a.klaviyo.com/api/lists/{}/relationships/profiles/"
BLVD_ADMIN_API_URL = "https://dashboard.boulevard.io/api/2020-01/admin"


# Secrets
KLAVIYO_TOKEN = os.environ.get("KLAVIYO_TOKEN", "")
BLVD_BUSINESS_ID = os.environ.get("BLVD_BUSINESS_ID", "")
BLVD_SECRET_KEY = os.environ.get("BLVD_SECRET_KEY", "")
BLVD_API_KEY = os.environ.get("BLVD_API_KEY", "")

# Cities:
# Miami
# NYC
# DC

# Locations:
# Upper East Side
# Flatiron
# Bryant Park
# Manhattan West
# Dupont Circle
# Navy Yard
# Penn Quarter
# Brickell

LIST_MAP = {
    "Coral Gables": "XxxKcc",
    "Brickell": "Yv5Pcp",
    "Penn Quarter": "R2SfVq",
    "Navy Yard": "UeAKmV",
    "Dupont Circle": "VTM8k9",
    "Bryant Park": "XY7M3j",
    "Brooklyn Heights": "SbFQLU",
    "Manhattan West": "W74Dbs",
    "Flatiron": "SnXmCd",
    "Upper East Side": "Y49Mkm",
}


def lambda_handler(event, context):
    print("Processing request:", event)
    event_body = json.loads(event["body"])

    return handle_customer_event(event_body)


def handle_customer_event(event_body):
    validation = validate(event_body)
    if validation:
        return {
            "isBase64Encoded": False,
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": '{"success": "false", "error":"' + validation + '" }',
        }

    locations = get_locations()
    location = None

    for loc in locations:
        apps = get_last_appointment(loc["node"]["id"], event_body["data"]["node"]["id"])

        if len(apps) > 0:
            location = loc
            break

    if location["node"]["name"] not in LIST_MAP:
        print("Invalid location: ")
        print(location["node"])
        print(LIST_MAP)
        raise Exception("Invalid location name returned")

    try:
        profile = create_profile(event_body["data"]["node"])
    except Exception as e:
        print("Error while creating profile: {}".format(repr(e)))

        return {
            "isBase64Encoded": False,
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": '{"success": "false"}',
        }

    try:
        add_profile_to_list(profile, LIST_MAP[location["node"]["name"]])
    except Exception as e:
        print("Error while creating profile: {}".format(repr(e)))

        return {
            "isBase64Encoded": False,
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": '{"success": "false"}',
        }

    return {
        "isBase64Encoded": False,
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": '{"success": "true"}',
    }


def create_profile(event_body):
    url = PROFILES_ENDPOINT

    payload = """{{
        "data": {{
            "type": "profile",
            "attributes": {{
                "email":"{}",
                "first_name":"{}",
                "last_name":"{}",
                "phone_number":"{}"
            }}
        }}
    }}""".format(
        event_body["email"],
        event_body["firstName"],
        event_body["lastName"],
        event_body["mobilePhone"],
    )

    headers = {
        "Accept": "application/json",
        "Revision": "2023-09-15",
        "Authorization": "Klaviyo-API-Key {}".format(KLAVIYO_TOKEN),
        "Content-Type": "application/json",
    }

    response = requests.request("POST", url, data=payload, headers=headers)

    if response.status_code != 201:
        print("Error while creating profile: ", response.text)

    r_json = response.json()

    return r_json["data"]


def add_profile_to_list(profile, list_id):
    url = LIST_ENDPOINT.format(list_id)

    payload = """{{
        "data": [{{
            "type": "profile",
            "id":"{}"
        }}]
    }}""".format(
        profile["id"],
    )

    headers = {
        "Accept": "application/json",
        "Revision": "2023-09-15",
        "Authorization": "Klaviyo-API-Key {}".format(KLAVIYO_TOKEN),
        "Content-Type": "application/json",
    }

    response = requests.request("POST", url, data=payload, headers=headers)

    if response.status_code != 204:
        print("Error while adding profile to list: ", response.text)

    return response.status_code == "204"


def get_locations():
    token = generate_blvd_auth_token(BLVD_BUSINESS_ID, BLVD_SECRET_KEY, BLVD_API_KEY)

    payload = """{{"query":"{{ locations(first:20) {{ edges {{ node {{ id name }} }} }} }}"}}""".format()

    headers = {
        "Accept": "application/json",
        "Authorization": "Basic {}".format(token),
        "Content-Type": "application/json",
    }

    response = requests.request(
        "POST", BLVD_ADMIN_API_URL, data=payload, headers=headers
    )

    r_json = response.json()

    return r_json["data"]["locations"]["edges"]


def get_last_appointment(location_id, user_id):
    token = generate_blvd_auth_token(BLVD_BUSINESS_ID, BLVD_SECRET_KEY, BLVD_API_KEY)

    payload = """{{"query":"{{ appointments(first:5, clientId: \\"{}\\", locationId: \\"{}\\") {{ edges {{ node {{ id clientId location {{ id name }} }} }} }} }}"}}""".format(
        user_id,
        location_id,
    )

    headers = {
        "Accept": "application/json",
        "Authorization": "Basic {}".format(token),
        "Content-Type": "application/json",
    }

    response = requests.request(
        "POST", BLVD_ADMIN_API_URL, data=payload, headers=headers
    )

    r_json = response.json()

    return r_json["data"]["appointments"]["edges"]


########################
### Helper functions
########################


def generate_blvd_auth_token(business_id, api_secret, api_key):
    prefix = "blvd-admin-v1"
    timestamp = str(int(time.time()))

    payload = f"{prefix}{business_id}{timestamp}"

    raw_key = base64.b64decode(api_secret)
    signature = hmac.new(raw_key, payload.encode("utf-8"), hashlib.sha256).digest()
    signature_base64 = base64.b64encode(signature).decode("utf-8")

    token = f"{signature_base64}{payload}"

    http_basic_payload = f"{api_key}:{token}"
    http_basic_credentials = base64.b64encode(
        http_basic_payload.encode("utf-8")
    ).decode("utf-8")

    return http_basic_credentials


def validate(event_body):
    if "data" not in event_body:
        return "data is required"
    if "node" not in event_body["data"]:
        return "node is required in ['data']"
    if "email" not in event_body["data"]["node"]:
        return "email is required in ['data']['node']"
    if "firstName" not in event_body["data"]["node"]:
        return "firstName is required in ['data']['node']"
    if "lastName" not in event_body["data"]["node"]:
        return "lastName is required in ['data']['node']"
    if "mobilePhone" not in event_body["data"]["node"]:
        return "mobilePhone is required in ['data']['node']"

    return False


# print(
#     lambda_handler(
#         {
#             "headers": {"token": "asd"},
#             "body": """{
#                 "data": {
#                     "node": {
#                         "id": "urn:blvd:Client:2f25c171-495b-4d56-9be8-940f893fe52a",
#                         "email": "nenadspp@gmail.com",
#                         "firstName": "Ne",
#                         "lastName": "Lo",
#                         "mobilePhone": "+381637134357"
#                     }
#                 }
#             }""",
#         },
#         None,
#     )
# )
