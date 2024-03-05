import re

# regex = re.compile(r'\{([^}]*)\}\:\{([^}]*)\}', re.I)
regex = re.compile(r'\!\{(.*?)\}\:\{(.*?)\}\!', re.I)

texto = "poaojdopajoadsdpads!{message}:{texto para ser enviado, False}açskdaskdaksdklç~kads!{message2}:{texto para ser enviado, False}"

print(regex.findall(texto))
