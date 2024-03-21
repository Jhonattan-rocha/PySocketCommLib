import http.client

def make_http_request(method, url, headers=None, body=None):
    # Parse URL to get host and path
    url_parts = http.client.urlsplit(url)
    host = url_parts.netloc
    path = url_parts.path

    # Determine the appropriate port
    if url_parts.scheme == 'https':
        conn = http.client.HTTPSConnection(host)
    else:
        conn = http.client.HTTPConnection(host)

    # Make request
    conn.request(method, path, body, headers or {})
    response = conn.getresponse()

    # Read and return response
    response_body = response.read()
    return response.status, response.reason, response_body

# Exemplo de uso
method = 'GET'
url = 'https://ciclovivo.com.br/wp-content/uploads/2018/10/iStock-536613027-1024x683.jpg'
status, reason, body = make_http_request(method, url)

print(f'Status: {status} {reason}')
print(f'Response body:\n{body}')

with open('./tests/img.jpg', 'wb') as file:
    file.write(body)
