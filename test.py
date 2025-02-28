import requests
import json

headers = {
    "App-Token": "ghznXhfMVzlk1v1Hb7jP5upDblFtfjvlqW7lNkK6",
    "Authorization": "user_token 7h2Q6POOspfyhUxTds35HiE1u1Fhiq5iepDTuH0r",
    "Session-Token": "6fktb7cdvg2v0rujuijfh1n5et"
}

dados = {
    "input": {
        "name": "Problema com Sistema",
        "content": "nada demais",
        "_users_id_requester": "11",
        "type": "2",
        "status": "1",
        "users_id_recipient": "2",
        "sla_waiting_duration": 10
    }
}

dados2 = {
    "input": {
        "users_id": 7,
        "is_default": 0,
        "is_dynamic": 0,
        "email": "israel.viado@imktec.com.br",
        "links": [
            {
                "rel": "User",
                "href": "http://cloud.imktec.com.br:11214/glpi/apirest.php/User/7"
            }
        ]
    }
}

URL = 'https://cloud.imktec.com.br:11213/glpi/apirest.php/UserEmail/'

request = requests.get(URL, headers=headers,)

# print(request.text)
with open('.\chamados.json', "w") as file:
    json.dump(request.json(), file, indent=4)    
