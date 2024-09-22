import re

# Mapeamento de tipos para expressões regulares
TYPE_PATTERNS = {
    'int': r'(\d+)',                      # Captura inteiros
    'str': r'([\w-]+)',                   # Captura strings (letras, números, hífens)
    'bool': r'(true|false)',              # Captura booleanos (true ou false)
    'float': r'(\d+\.\d+)',               # Captura floats (números decimais)
}

def match_route(route, pattern):
    # Substitui os placeholders {tipo: nome} pelos regex correspondentes
    for type_name, regex in TYPE_PATTERNS.items():
        pattern = re.sub(r'\{{'+type_name+': \w+\}}', regex, pattern)
    
    # Adiciona os delimitadores de início e fim para garantir correspondência exata
    pattern = f"^{pattern}$"
    
    # Tenta fazer a correspondência
    match = re.match(pattern, route)
    
    if match:
        # Extrai os parâmetros capturados
        params = match.groups()
        return params
    else:
        return None

# Testando a função
route = "/user/1/true/25.5"
pattern = "/user/{int: id}/{bool: active}/{float: price}"

result = match_route(route, pattern)

if result:
    print(f"Rota correspondente! Parâmetros extraídos: {result}")
else:
    print("Rota não corresponde ao padrão.")
